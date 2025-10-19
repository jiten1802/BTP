# app/tools/scheduling_tools.py
import logging
from typing import List, Dict
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from app.models.prompts import SCHEDULER_SYSTEM_PROMPT, SCHEDULER_HUMAN_PROMPT_TEMPLATE
from app.key_manager import api_key_manager
from app.google_api_client import send_email

# --- Pydantic Model for LLM's Structured Output ---
class SchedulingEmail(BaseModel):
    subject: str = Field(description="A clear and friendly subject line for the scheduling email.")
    email_body: str = Field(description="The full HTML body of the email offering meeting times.")

def _draft_scheduling_email_llm(history: List[dict], times: List[str], api_key: str) -> SchedulingEmail:
    """Internal LLM call to draft an email offering meeting times."""
    convo_str = "\n".join([f"<{msg.get('type', 'message')}>: {msg.get('message', '')}" for msg in history])
    times_str = "\n".join([f"- {time}" for time in times])

    human_message = SCHEDULER_HUMAN_PROMPT_TEMPLATE.format(
        conversation_history=convo_str, meeting_times=times_str
    )
    messages = [SystemMessage(content=SCHEDULER_SYSTEM_PROMPT), HumanMessage(content=human_message)]

    try:
        llm = ChatGroq(model="llama-3.1-8b-8192", temperature=0.5, groq_api_key=api_key)
        structured_llm = llm.with_structured_output(SchedulingEmail)
        result = structured_llm.invoke(messages)
        api_key_manager.record_api_call(api_key, success=True)
        return result
    except Exception as e:
        api_key_manager.record_api_call(api_key, success=False)
        logging.error(f"LLM call failed for scheduling email: {e}")
        return SchedulingEmail(subject="Meeting Availability", email_body="<p>Hi,</p><p>Thanks for your interest. Here are some times we could connect:</p><ul><li>Monday at 10 AM</li><li>Tuesday at 2 PM</li></ul><p>Let me know what works!</p>")

def send_meeting_options_email(
    lead_email: str,
    communication_history: List[Dict],
    available_times: List[str]
) -> str:
    """
    This is the TOOL. It drafts and sends an email to an interested lead with meeting options.
    It returns a string indicating the result of the operation.
    """
    logging.info(f"Using scheduling tool for lead: {lead_email}")
    api_key = api_key_manager.get_random_key()
    
    # 1. Draft the email using the LLM
    scheduling_email = _draft_scheduling_email_llm(communication_history, available_times, api_key)
    
    # 2. Send the email
    email_sent = send_email(
        to_email=lead_email,
        subject=scheduling_email.subject,
        html_content=scheduling_email.email_body
    )

    if email_sent:
        # 3. Return a success message and the content for logging
        return_message = f"Successfully sent scheduling email to {lead_email}."
        # We also need to return the email body to save it in the history
        return f"SUCCESS: {return_message}", scheduling_email.email_body
    else:
        return_message = f"Failed to send scheduling email to {lead_email}."
        return f"FAILURE: {return_message}", ""