import logging
from typing import List
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime

from app.models.state import AgenticState, Lead
from app.models.prompts import SCHEDULER_SYSTEM_PROMPT, SCHEDULER_HUMAN_PROMPT_TEMPLATE
from app.utils import get_leads_by_status, update_performance_metrics
from app.key_manager import api_key_manager
from app.email_client import send_email

# --- Pydantic Model for LLM's Structured Output ---
class SchedulingEmail(BaseModel):
    subject: str = Field(description="A clear and friendly subject line for the scheduling email.")
    email_body: str = Field(description="The full HTML body of the email offering meeting times.")

def create_llm_with_key(api_key: str):
    llm = ChatGroq(model="llama-3.1-8b-8192", temperature=0.5, groq_api_key=api_key)
    return llm.with_structured_output(SchedulingEmail)

def draft_scheduling_email(history: List[dict], times: List[str], api_key: str) -> SchedulingEmail:
    """Calls an LLM to draft an email offering meeting times."""
    
    # Format the conversation history for the prompt
    convo_str = "\n".join([f"<{msg['type']}>: {msg['message']}" for msg in history])
    times_str = "\n".join([f"- {time}" for time in times])

    human_message = SCHEDULER_HUMAN_PROMPT_TEMPLATE.format(
        conversation_history=convo_str,
        meeting_times=times_str
    )
    messages = [SystemMessage(content=SCHEDULER_SYSTEM_PROMPT), HumanMessage(content=human_message)]

    try:
        structured_llm = create_llm_with_key(api_key)
        result = structured_llm.invoke(messages)
        api_key_manager.record_api_call(api_key, success=True)
        return result
    except Exception as e:
        api_key_manager.record_api_call(api_key, success=False)
        logging.error(f"LLM call failed for scheduling email: {e}")
        return SchedulingEmail(subject="Meeting Availability", email_body="<p>Hello,</p><p>Following up on your interest, here are some times we could connect:</p><ul><li>Monday at 10 AM</li><li>Tuesday at 2 PM</li></ul><p>Let me know if one of these works for you.</p>")

def Scheduler(state: AgenticState) -> AgenticState:
    """
    Identifies interested leads and sends them an email with proposed meeting times.
    """
    interested_leads = get_leads_by_status(state, "interested")
    if not interested_leads:
        print("Scheduler: No interested leads to schedule.")
        return state
        
    print(f"Scheduler: Processing {len(interested_leads)} interested leads.")
    
    api_key = api_key_manager.get_key_for_thread()
    # In a real app, you would get these from a calendar API
    available_times = ["Monday, 10:00 AM PST", "Tuesday, 2:00 PM PST", "Wednesday, 11:00 AM PST"]

    for lead in interested_leads:
        # 1. Draft the scheduling email using the LLM
        scheduling_email = draft_scheduling_email(lead.communication_history, available_times, api_key)
        
        # 2. Send the email
        email_sent = send_email(
            to_email=lead.raw_data.get("email"),
            subject=scheduling_email.subject,
            html_content=scheduling_email.email_body
        )

        if email_sent:
            # 3. Update the lead's state and history
            lead.status = "scheduling_in_progress"
            communication_entry = {
                "type": "outbound_scheduling",
                "message": scheduling_email.email_body,
                "sent_at": datetime.isoformat()
            }
            lead.communication_history.append(communication_entry)
            print(f"  - Scheduling email sent to {lead.raw_data.get('email')}.")
        else:
            logging.error(f"  - Failed to send scheduling email to {lead.raw_data.get('email')}.")
            lead.status = "scheduling_failed"

    return state