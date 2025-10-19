# app/agents/supervisor.py
import logging
from typing import List, Dict
from app.models.state import AgenticState, Lead

def Supervisor(state: AgenticState) -> AgenticState:
    """
    The Supervisor Agent, now with useful logic.
    1.  ENRICHES interested leads with context for the Scheduler.
    2.  PRIORITIZES leads so high-score leads are handled first.
    """
    print("\n--- SUPERVISOR AGENT ---")
    
    interested_leads = [lead for lead in state.lead if lead.status == "interested"]
    
    if not interested_leads:
        print("Supervisor: No interested leads to process.")
        # Return an empty list for the leads to process
        state.lead = []
        return state

    print(f"Supervisor: Found {len(interested_leads)} interested lead(s). Enriching and prioritizing...")
    
    enriched_leads = []
    for lead in interested_leads:
        # --- ENRICHMENT ---
        context = {}
        # 1. Determine priority
        priority = "Normal"
        if lead.score and lead.score >= 80:
            priority = "High"
        context['priority'] = priority

        # 2. Extract a summary of the last interaction
        last_inbound_message = "No specific reason given."
        for msg in reversed(lead.communication_history):
            if msg.get('type') == 'inbound_reply':
                last_inbound_message = msg.get('analysis', {}).get('summary', last_inbound_message)
                break
        context['interest_summary'] = last_inbound_message
        
        # 3. Add key lead details
        context['contact_person'] = lead.raw_data.get('contact_person', 'the contact')
        context['company_name'] = lead.raw_data.get('company_name', 'their company')
        
        # Attach the context to the lead
        lead.scheduling_context = context
        enriched_leads.append(lead)
        print(f"  - Lead {lead.lead_id}: Priority set to '{priority}'.")

    # --- PRIORITIZATION ---
    # Sort the leads so that 'High' priority ones are first.
    # The background worker will process them in this new order.
    def sort_key(lead: Lead):
        return 0 if lead.scheduling_context.get('priority') == 'High' else 1

    sorted_leads = sorted(enriched_leads, key=sort_key)
    
    # Update the state with the sorted and enriched leads
    state.lead = sorted_leads
    
    return state