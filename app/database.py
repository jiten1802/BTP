import sqlite3
import json
from .models.state import Lead
from pathlib import Path
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define the database path within your project's data directory
DB_PATH = Path(__file__).parent.parent / "data" / "qualified_leads.db"

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
                communication_history TEXT, -- Stored as a JSON string
                raw_data TEXT,               -- Stored as a JSON string
                published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
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
                score, qualified_lead, personalized_message, communication_history, raw_data
              ) VALUES(?,?,?,?,?,?,?,?,?,?,?) '''
    
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