# app/agents/scheduler.py
from json import load
import logging
from datetime import datetime, timedelta
from app.models.state import AgenticState
from app.google_api_client import find_free_slots, create_calendar_event
from app.tools.scheduling_tools import send_meeting_options_email 
from app.utils import update_performance_metrics
from dotenv import load_dotenv
import os

def _get_sender_email() -> str:
    load_dotenv()
    return os.getenv("SENDERS_EMAIL", "")
def Scheduler(state: AgenticState) -> AgenticState:
    """
    A two-stage agent that first offers meeting times, and then books them upon confirmation.
    """
    lead = state.lead[0]
    
    # --- STAGE 1: Offer meeting times to an 'interested' lead ---
    if lead.status == "interested":
        print(f"Scheduler (Stage 1): Finding available times for lead {lead.lead_id}")
        
        # 1. Find real available slots in the next 7 days
        now = datetime.now().astimezone()
        start_range = now + timedelta(days=1)
        end_range = now + timedelta(days=7)
        available_slots = find_free_slots(start_range, end_range)

        if not available_slots:
            logging.error(f"No available slots found for lead {lead.lead_id}. Manual review needed.")
            lead.status = "scheduling_failed_no_slots"
            return state

        # Format times for the email prompt (e.g., "Monday, July 26th at 10:00 AM")
        formatted_times = [datetime.fromisoformat(slot['start']).strftime('%A, %B %d at %I:%M %p %Z') for slot in available_slots]

        # 2. Use the existing tool to draft and send the email with REAL times
        result, email_body = send_meeting_options_email(
            lead_email=lead.raw_data.get("email"),
            communication_history=lead.communication_history,
            available_times=formatted_times,
            supervisor_context=lead.scheduling_context
        )

        if "SUCCESS" in result:
            lead.status = "scheduling_in_progress"
            # Log the full slot data in history for later use
            communication_entry = {
                "type": "outbound_scheduling", "message": email_body,
                "sent_at": datetime.now().isoformat(), "proposed_slots": available_slots
            }
            lead.communication_history.append(communication_entry)
            print(f"  - Scheduling email with real times sent to {lead.raw_data.get('email')}.")
        else:
            lead.status = "scheduling_failed"

    # --- STAGE 2: Book the meeting for a 'meeting_time_confirmed' lead ---
    elif lead.status == "meeting_time_confirmed":
        print(f"Scheduler (Stage 2): Booking meeting for lead {lead.lead_id}")
        
        # 1. Find the proposed slots from the last outbound message
        proposed_slots = []
        for msg in reversed(lead.communication_history):
            if msg.get('type') == 'outbound_scheduling':
                proposed_slots = msg.get('proposed_slots', [])
                break
        
        # 2. Match the confirmed time with one of the proposed slots
        # (A more robust solution would use LLM to parse confirmed_time and match it)   
        confirmed_slot = proposed_slots[0] # Simple example: assume they chose the first one
        
        # 3. Create the calendar event
        event = create_calendar_event(
            summary=f"Meeting with {lead.raw_data.get('contact_person')} ({lead.raw_data.get('company_name')})",
            start_time=confirmed_slot['start'],
            end_time=confirmed_slot['end'],
                attendees=[_get_sender_email(), lead.raw_data.get('email')]
        )

        if event:
            lead.status = "meeting_booked"
            lead.meeting_details = event
            update_performance_metrics(state, "meetings_booked", 1)
            print(f"  - Meeting successfully booked for {lead.raw_data.get('email')}.")
        else:
            lead.status = "booking_failed"
            
    return state