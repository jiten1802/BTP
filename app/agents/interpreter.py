import logging
from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

from app.models.state import AgenticState, Lead
from app.models.prompts import INTERPRETER_SYSTEM_PROMPT, INTERPRETER_HUMAN_PROMPT_TEMPLATE
from app.utils import get_leads_by_status, update_performance_metrics
from app.key_manager import api_key_manager
# --- Import the real email client functions ---
from app.google_api_client import search_for_replies, get_message_details, mark_as_read

load_dotenv()

# --- Pydantic Model for LLM's Structured Output ---
class LeadIntent(BaseModel):
    intent: Literal["INTERESTED", "NOT_INTERESTED", "WRONG_PERSON", "NEEDS_CLARIFICATION"] = Field(
        description="The classified intent of the lead's email reply."
    )
    summary: str = Field(description="A brief one-sentence summary of the lead's reply.")
    confirmed_time: Optional[str] = Field(None, description="If intent is MEETING_TIME_CONFIRMED, this is the specific time the user agreed to.")
    suggested_next_step: str = Field(description="A suggested next action based on the intent.")

# --- LLM and API Call Handling ---
def create_llm_with_key(api_key: str):
    """Creates a ChatGroq instance with a specific API key and structured output."""
    llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0, groq_api_key=api_key)
    return llm.with_structured_output(LeadIntent)

def get_lead_intent(initial_message: str, lead_reply: str, api_key: str) -> LeadIntent:
    """Calls the LLM to determine the intent of a lead's reply."""
    human_message = INTERPRETER_HUMAN_PROMPT_TEMPLATE.format(
        initial_message=initial_message,
        lead_reply=lead_reply
    )
    messages = [SystemMessage(content=INTERPRETER_SYSTEM_PROMPT), HumanMessage(content=human_message)]
    
    try:
        structured_llm = create_llm_with_key(api_key)
        result = structured_llm.invoke(messages)
        api_key_manager.record_api_call(api_key, success=True)
        return result
    except Exception as e:
        api_key_manager.record_api_call(api_key, success=False)
        logging.error(f"LLM call failed for intent analysis: {e}")
        # Fallback in case of an API error
        return LeadIntent(
            intent="NEEDS_CLARIFICATION",
            summary="Failed to analyze intent due to an API error.",
            suggested_next_step="Manual review required."
        )

def Interpreter(state: AgenticState) -> AgenticState:
    """
    Checks Gmail for replies from leads, analyzes their intent, and updates their state.
    """
    leads_to_check = state.lead
    if not leads_to_check:
        return state

    print(f"Interpreter: Checking Gmail for replies from {len(leads_to_check)} leads...")
    
    api_key = api_key_manager.get_key_for_thread() # Use a single key for this agent's run
    replies_found_and_processed = 0

    for lead in leads_to_check:
        lead_email = lead.raw_data.get("email")
        if not lead_email:
            continue

        # 1. Search for unread replies from this lead's email address
        new_messages = search_for_replies(sender_email=lead_email)
        
        if new_messages:
            # We'll process the first new message we find and then stop for this lead in this run.
            message_summary = new_messages[0]
            message_id = message_summary['id']

            # 2. Get the full content (body, subject, etc.) of the email
            details = get_message_details(message_id)
            if not details or not details['body']:
                logging.warning(f"Could not retrieve details for message ID {message_id}. Skipping.")
                continue

            replies_found_and_processed += 1
            reply_text = details['body']
            initial_message = lead.personalized_message
            
            # 3. Call the LLM to get the intent
            intent_result = get_lead_intent(initial_message, reply_text, api_key)
            
            # 4. Update the lead in the state
            lead.intent = intent_result.intent
            status_map = {
                "INTERESTED": "interested",
                "NOT_INTERESTED": "not_interested",
                "WRONG_PERSON": "wrong_person",
                "MEETING_TIME_CONFIRMED": "meeting_time_confirmed",
                "NEEDS_CLARIFICATION": "needs_clarification"
            }
            lead.status = status_map.get(lead.intent, "needs_clarification")

            if lead.status == "meeting_time_confirmed":
                lead.meeting_details = {"confirmed_time_iso": intent_result.confirmed_time}            

            # Log the reply and the AI's analysis to the lead's communication history
            communication_entry = {
                "type": "inbound_reply",
                "message": reply_text,
                "analysis": intent_result.model_dump()
            }
            lead.communication_history.append(communication_entry)
            
            # Update central performance metrics
            metric_map = {
                "INTERESTED": "interested_leads",
                "NOT_INTERESTED": "not_interested",
                "WRONG_PERSON": "wrong_person",
            }
            if lead.intent in metric_map:
                update_performance_metrics(state, metric_map[lead.intent], 1)

            print(f"  - Reply from {lead_email} analyzed. Intent determined as: {lead.intent}")
            
            # 5. Mark the email as read in Gmail so we don't process it again
            mark_as_read(message_id)

    if replies_found_and_processed == 0:
        print("Interpreter: No new replies found in this run.")
    else:
        print(f"Interpreter: Successfully processed {replies_found_and_processed} new replies.")
    
    return state