# run_background_workers.py
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from app.models.state import AgenticState
from app.database import create_connection, load_leads_by_status, update_lead_in_db

# Import all the agents that will act as background workers
from app.agents.interpreter import Interpreter
from app.agents.scheduler import Scheduler
from app.agents.record_keeper import RecordKeeper

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

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

    # --- Run Scheduler First ---
    interested_leads = load_leads_by_status(db_conn, "interested")
    if interested_leads:
        scheduler_state = AgenticState(lead=interested_leads)
        updated_state = Scheduler(scheduler_state)
        for lead in updated_state.lead:
            update_lead_in_db(db_conn, lead)

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
    scheduler.add_job(process_pending_leads, 'interval', minutes=30) # Runs every 2 minutes
    
    print("Starting background worker. It will check for tasks every 2 minutes. Press Ctrl+C to exit.")
    
    try:
        process_pending_leads() # Run once on startup
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass