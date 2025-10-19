# run_background_workers.py
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from app.models.state import AgenticState
from app.database import create_connection, create_table, load_leads_by_status, update_lead_in_db
from datetime import datetime, timedelta, timezone
from app.agents.interpreter import Interpreter
from app.agents.scheduler import Scheduler
from app.agents.record_keeper import RecordKeeper
from app.agents.supervisor import Supervisor
from app.agents.followup import Followup


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def check_for_follow_ups(db_conn):
    """Finds leads that haven't replied in over 2 days and marks them for follow-up."""
    two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()

    # This is a conceptual query. You might need a more complex one depending on your DB.
    # We load all leads and filter in Python for simplicity.
    leads_to_check = load_leads_by_status(db_conn, "outreach_sent")
    
    for lead in leads_to_check:
        if lead.last_outreach_timestamp and lead.last_outreach_timestamp < two_days_ago:
            lead.status = "follow_up_due"
            update_lead_in_db(db_conn, lead)
            print(f"Background Worker: Lead {lead.lead_id} is due for a follow-up.")

def process_pending_leads():
    """
    The core job that runs on a schedule. It processes leads in a specific order
    based on their status, creating a state machine.
    """
    logging.info("--- Starting background worker run ---")
    
    db_conn = create_connection()
    if not db_conn:
        logging.error("Background Worker: Could not connect to the database. Skipping run.")
        return
    # Ensure the table exists for background operations
    try:
        create_table(db_conn)
    except Exception as e:
        logging.error(f"Background Worker: Failed to ensure table exists: {str(e)}")
        db_conn.close()
        return
    
    check_for_follow_ups(db_conn)

    # --- NEW: Run Follower Agent ---
    leads_to_follow_up = load_leads_by_status(db_conn, "follow_up_due")
    if leads_to_follow_up:
        for lead in leads_to_follow_up:
            single_lead_state = AgenticState(lead=[lead])
            updated_state = Followup(single_lead_state)
            update_lead_in_db(db_conn, updated_state.lead[0])

    # --- Run Scheduler First ---
    leads_for_scheduler = load_leads_by_status(db_conn, "interested") + load_leads_by_status(db_conn, "meeting_time_confirmed")
    if leads_for_scheduler:
        # The supervisor logic only applies to newly interested leads
        interested_leads_state = AgenticState(lead=[l for l in leads_for_scheduler if l.status == 'interested'])
        supervisor_state = Supervisor(interested_leads_state)
        
        # Combine the supervised leads with the confirmed leads
        prioritized_leads = supervisor_state.lead + [l for l in leads_for_scheduler if l.status == 'meeting_time_confirmed']

        for lead in prioritized_leads:
            single_lead_state = AgenticState(lead=[lead])
            updated_state = Scheduler(single_lead_state)
            update_lead_in_db(db_conn, updated_state.lead[0])

    # --- Run Interpreter Second ---
    leads_awaiting_reply = load_leads_by_status(db_conn, "outreach_sent") + load_leads_by_status(db_conn, "scheduling_in_progress")
    if leads_awaiting_reply:
        interpreter_state = AgenticState(lead=leads_awaiting_reply)
        updated_state = Interpreter(interpreter_state)
        for lead in updated_state.lead:
            if lead.status not in ["outreach_sent", "scheduling_in_progress"]:
                update_lead_in_db(db_conn, lead)

    # --- Run RecordKeeper Third ---
    leads_to_archive = load_leads_by_status(db_conn, "not_interested") + load_leads_by_status(db_conn, "wrong_person")
    if leads_to_archive:
        record_keeper_state = AgenticState(lead=leads_to_archive)
        updated_state = RecordKeeper(record_keeper_state)
        for lead in updated_state.lead:
            update_lead_in_db(db_conn, lead)

    db_conn.close()
    logging.info("--- Background worker run finished ---")


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(process_pending_leads, 'interval', minutes=30) # Runs every 30 minutes
    
    print("Starting background worker. It will check for tasks every 30 minutes. Press Ctrl+C to exit.")
    
    try:
        process_pending_leads() # Run once on startup
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass