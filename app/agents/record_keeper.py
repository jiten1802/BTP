import logging
from app.models.state import AgenticState, Lead
from app.utils import get_leads_by_status
from app.database import create_connection, publish_lead

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def RecordKeeper(state: AgenticState) -> AgenticState:
    """
    Handles leads that are not interested or are the wrong person.
    It updates their final status and logs them to the database.
    """
    leads_to_archive = get_leads_by_status(state, "not_interested") + get_leads_by_status(state, "wrong_person")

    if not leads_to_archive:
        print("Record Keeper: No leads to process.")
        return state
    
    print(f"Record Keeper: Processing {len(leads_to_archive)} leads for archival.")

    db_conn = create_connection()
    if not db_conn:
        logging.error("Record Keeper: Could not connect to the database. Aborting.")
        return state

    for lead in leads_to_archive:
        # Set a final, terminal status
        lead.status = "archived"
        
        # Log the final state of the lead to the database
        try:
            publish_lead(db_conn, lead)
            logging.info(f"  - Lead {lead.lead_id} status set to 'archived' and logged to DB.")
        except Exception as e:
            logging.error(f"  - Failed to publish lead {lead.lead_id} to DB: {e}")

    if db_conn:
        db_conn.close()
        
    return state