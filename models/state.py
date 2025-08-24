from typing import TypedDict, Any, Optional, List, Dict, Union
from dataclasses import dataclass
from enum import Enum

class LeadStatus(Enum):
    """Lead qualification status"""
    PENDING = "pending"
    PROCESSING = "processing"
    QUALIFIED = "qualified"
    NOT_QUALIFIED = "not_qualified"
    NEEDS_REVIEW = "needs_review"
    ERROR = "error"

class MarketingAgent(TypedDict):
    """
    Represents the state of a single lead as it moves through the qualification process.
    """
    # --- Lead Identification ---
    lead_id: str
    company_name: str
    contact_person: str
    contact_email: str
    # contact_linkedin_url: Optional[str]
    # contact_whatsapp_number: Optional[str]
    initial_source: str

    # --- Lead Data (from CSV/import) ---
    industry: Optional[str]
    employee_count: Optional[int]
    location: Optional[str]
    job_title: Optional[str]

    # --- Scoring & Qualification ---
    icp_score: int
    is_qualified: Optional[bool]
    qualification_status: Optional[LeadStatus]
    qualification_notes: Optional[str]

    # --- Batch Processing Fields ---
    batch_processed: bool
    batch_id: Optional[str]
    batch_processing_time: Optional[float]

    # --- Outreach & Engagement ---
    outreach_channel: Optional[str]  # "email", "linkedin", "whatsapp"
    outreach_strategy: str  # e.g., "Initial Outreach", "Follow-up 1"
    messages: List[Dict]  # A log of all messages sent and received
    
    # --- Response & Intent ---
    last_response: Optional[str]  # The raw text of the last reply from the lead
    lead_intent: Optional[str]  # "Interested", "Not Interested", "Request for Demo", "Wrong Person", "Ambiguous"

    # --- Scheduling & Meetings ---
    meeting_booked: bool
    meeting_details: Optional[Dict]  # e.g., {"time": "...", "link": "...", "attendees": [...]}

    # --- System & Workflow ---
    next_agent: str  # The name of the next agent/node to execute
    error_message: Optional[str]  # To log any errors during the process
    retries: int  # A counter for retrying failed operations (like API calls)

class BatchState(TypedDict):
    """
    State for batch processing multiple leads efficiently.
    Used for initial qualification of large lead lists.
    """
    # --- Batch Configuration ---
    batch_id: str
    batch_size: int
    max_workers: int
    total_leads: int
    processed_leads: int
    
    # --- Lead Data ---
    leads: List[MarketingAgent]
    qualified_leads: List[MarketingAgent]
    not_qualified_leads: List[MarketingAgent]
    needs_review_leads: List[MarketingAgent]
    error_leads: List[MarketingAgent]
    
    # --- Performance Metrics ---
    start_time: Optional[float]
    end_time: Optional[float]
    total_processing_time: Optional[float]
    average_time_per_lead: Optional[float]
    
    # --- Batch Processing Status ---
    current_batch: int
    total_batches: int
    is_complete: bool
    
    # --- Results Summary ---
    qualification_summary: Dict[str, int]
    performance_summary: Dict[str, Any]

@dataclass
class LeadData:
    """
    Data structure for individual lead information during batch processing.
    Used to efficiently load and process leads from CSV files.
    """
    lead_id: str
    company_name: str
    contact_person: str
    contact_email: str
    industry: str
    employee_count: int
    location: str
    job_title: str
    initial_source: str = "csv_import"
    
    # Scoring results
    icp_score: Optional[int] = None
    qualification_status: Optional[LeadStatus] = None
    reasoning: Optional[str] = None
    matched_criteria: Optional[Dict[str, bool]] = None
    recommendations: Optional[str] = None
    
    # Processing metadata
    processing_time: Optional[float] = None
    error_message: Optional[str] = None
    batch_id: Optional[str] = None


