import sqlite3
import json
from .models.state import Lead
from pathlib import Path
import logging
from typing import List

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define the database path within your project's data directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "qualified_leads.db"

# --- Add a print statement for debugging ---
print(f"DATABASE PATH IS SET TO: {DB_PATH}")

def create_connection():
    """Create a database connection to the SQLite database."""
    conn = None
    try:
        # Ensure the parent directory exists
        DB_PATH.parent.mkdir(exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
    return conn

def create_table(conn):
    """Create the qualified_leads table if it doesn't exist."""
    try:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS qualified_leads (
                lead_id TEXT PRIMARY KEY,
                company_name TEXT,
                contact_person TEXT,
                job_title TEXT,
                email TEXT,
                status TEXT,
                score INTEGER,
                qualified_lead BOOLEAN,
                personalized_message TEXT,
                intent TEXT,
                meeting_details TEXT,
                last_outreach_timestamp TEXT,
                communication_history TEXT,
                raw_data TEXT,
                published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Backwards-compatible ALTER TABLEs for old DBs
        try:
            c.execute("ALTER TABLE qualified_leads ADD COLUMN intent TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE qualified_leads ADD COLUMN meeting_details TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE qualified_leads ADD COLUMN last_outreach_timestamp TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE qualified_leads ADD COLUMN communication_history TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE qualified_leads ADD COLUMN raw_data TEXT;")
        except sqlite3.OperationalError:
            pass
        conn.commit()

    except sqlite3.Error as e:
        logging.error(f"Table creation error: {e}")

def publish_lead(conn, lead: Lead):
    """
    Publish a single qualified lead to the database.
    Uses INSERT OR REPLACE to handle both new and updated leads.
    """
    if not lead.qualified_lead:
        return

    sql = ''' INSERT OR REPLACE INTO qualified_leads(
                lead_id, company_name, contact_person, job_title, email, status, 
                score, qualified_lead, personalized_message, intent, meeting_details, last_outreach_timestamp, communication_history, raw_data
              ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) '''
    
    cursor = conn.cursor()
    
    # Prepare data for insertion, converting dicts/lists to JSON strings
    lead_data = (
        lead.lead_id,
        lead.raw_data.get('company_name', 'N/A'),
        lead.raw_data.get('contact_person', 'N/A'),
        lead.raw_data.get('job_title', 'N/A'),
        lead.raw_data.get('email', 'N/A'),
        lead.status,
        int(lead.score) if lead.score is not None else None,
        lead.qualified_lead,
        lead.personalized_message,
        lead.intent,
        json.dumps(lead.meeting_details) if lead.meeting_details else None,
        lead.last_outreach_timestamp,
        json.dumps(lead.communication_history) if lead.communication_history else '[]',
        json.dumps(lead.raw_data)
    )

    cursor.execute(sql, lead_data)
    conn.commit()
    logging.info(f"Successfully published lead_id {lead.lead_id} to the database.")
    return cursor.lastrowid

def initialize_database():
    """A utility to be called on application startup."""
    conn = create_connection()
    if conn is not None:
        create_table(conn)
        conn.close()
    else:
        logging.error("Database initialization failed: Could not create connection.")

# Add these two new functions to app/database.py

def load_leads_by_status(conn, status: str) -> List[Lead]:
    """
    Loads all leads from the database that have a specific status.
    """
    leads = []
    try:
        conn.row_factory = sqlite3.Row # Allows accessing columns by name
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM qualified_leads WHERE status = ?", (status,))
        rows = cursor.fetchall()

        for row in rows:
            # Reconstruct the Lead Pydantic model from the database row
            lead = Lead(
                lead_id=row['lead_id'],
                raw_data=json.loads(row['raw_data']),
                status=row['status'],
                qualified_lead=bool(row['qualified_lead']),
                score=row['score'],
                personalized_message=row['personalized_message'],
                communication_history=json.loads(row['communication_history']),
                # Ensure other fields from your model are reconstructed here if they exist in the DB
                intent=row.get('intent'),
                meeting_details=json.loads(row['meeting_details']) if row.get('meeting_details') else None
            )
            leads.append(lead)
    except Exception as e:
        logging.error(f"Failed to load leads with status '{status}': {e}")
    
    return leads

def update_lead_in_db(conn, lead: Lead):
    """
    Updates an existing lead's information in the database.
    This is effectively the same as publish_lead, which uses INSERT OR REPLACE.
    """
    publish_lead(conn, lead)