from typing import TypedDict, Any, Optional, List, Dict

class MarketingAgent(TypedDict):
    """
    Represents the state of a single lead as it moves through the qualification process.
    """
    # --- Lead Identification ---
    lead_id: str
    company_name: str
    contact_person: str
    contact_email: str
    #contact_linkedin_url: Optional[str]
    #contact_whatsapp_number: Optional[str]
    initial_source: str

    # --- Scoring & Qualification ---
    icd_score: int
    is_qualified: Optional[bool]
    qualification_notes: Optional[str]

    # --- Outreach & Engagement ---
    outreach_channel: Optional[str] # "email", "linkedin", "whatsapp"
    outreach_strategy: str # e.g., "Initial Outreach", "Follow-up 1"
    messages: List[Dict] # A log of all messages sent and received
    
    #---Response & Intent---
    last_response: Optional[str] # The raw text of the last reply from the lead
    lead_intent: Optional[str] # "Interested", "Not Interested", "Request for Demo", "Wrong Person", "Ambiguous"

    # --- Scheduling & Meetings ---
    meeting_booked: bool
    meeting_details: Optional[Dict] # e.g., {"time": "...", "link": "...", "attendees": [...]}

     # --- System & Workflow ---
    next_agent: str # The name of the next agent/node to execute
    error_message: Optional[str] # To log any errors during the process
    retries: int # A counter for retrying failed operations (like API calls)


