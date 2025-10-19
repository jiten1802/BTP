import logging
from typing import Dict
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime, timezone

from app.models.state import AgenticState, Lead
from app.models.prompts import FOLLOWUP_SYSTEM_PROMPT, FOLLOWUP_HUMAN_PROMPT_TEMPLATE
from app.key_manager import api_key_manager
from app.google_api_client import send_reply_in_thread

class FollowUpEmail(BaseModel):
    follow_up_body: str = Field(description="The HTML body of the follow-up email.")

def Followup(state: AgenticState) -> AgenticState:
    """
    Drafts and sends a follow-up email to a lead who hasn't replied.
    """
    lead_to_follow_up = state.lead[0]
    
    print(f"Follower Agent: Preparing follow-up for lead {lead_to_follow_up.lead_id}")

    # 1. Find the original message from the history
    original_message = None
    for msg in lead_to_follow_up.communication_history:
        if msg.get('type') == 'outreach_email':
            original_message = msg
            break
            
    if not original_message:
        lead_to_follow_up.status = "follow_up_failed"
        logging.error("Follower: Could not find original outreach email in history.")
        return state

    # 2. Use LLM to draft the follow-up message
    api_key = api_key_manager.get_random_key()
    llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.5, groq_api_key=api_key)
    structured_llm = llm.with_structured_output(FollowUpEmail)
    
    human_message = FOLLOWUP_HUMAN_PROMPT_TEMPLATE.format(
        original_subject=original_message.get('subject'),
        original_body=original_message.get('message')
    )
    messages = [SystemMessage(content=FOLLOWUP_SYSTEM_PROMPT), HumanMessage(content=human_message)]
    
    try:
        response = structured_llm.invoke(messages)
        follow_up_body = response.follow_up_body
    except Exception as e:
        logging.error(f"Follower: LLM call failed: {e}")
        # Fallback message
        follow_up_body = "<p>Just wanted to gently follow up on my previous email. Let me know if you had a moment to consider it.</p>"

    # 3. Send the follow-up as a reply in the original thread
    # We need the thread ID from the original sent message
    thread_id = original_message.get('thread_id')
    
    if not thread_id:
        lead_to_follow_up.status = "follow_up_failed"
        logging.error("Follower: No thread_id found in original message to reply to.")
        return state
        
    email_sent = send_reply_in_thread(
        thread_id=thread_id,
        to_email=lead_to_follow_up.raw_data.get('email'),
        body=follow_up_body
    )
    
    if email_sent:
        lead_to_follow_up.status = "outreach_sent" # Return to waiting state
        lead_to_follow_up.last_outreach_timestamp = datetime.utcnow().isoformat()
        communication_entry = {
            "type": "follow_up_email",
            "message": follow_up_body,
            "sent_at": lead_to_follow_up.last_outreach_timestamp
        }
        lead_to_follow_up.communication_history.append(communication_entry)
        timestamp = datetime.now(timezone.utc).isoformat()
        lead_to_follow_up.last_outreach_timestamp = timestamp

        print(f"  - Follow-up email sent successfully to {lead_to_follow_up.raw_data.get('email')}")
    else:
        lead_to_follow_up.status = "follow_up_failed"
        logging.error(f"  - Failed to send follow-up email.")
        
    return state
