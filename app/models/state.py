from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

class Lead(BaseModel):
    """
    Represents a single lead and its associated data using a TypedDict.
    """
    lead_id: str
    raw_data: Dict[str, Any]
    status: str = "new"  # "new", "in_progress", "completed", "failed", "meeting_booked", "wrong_person"
    qualified_lead: bool = False 
    score: Optional[float] = None
    contacts: Optional[List[Dict[str, Any]]] = None
    personalized_message: Optional[str] = None
    communication_history: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    intent: Optional[str] = None
    meeting_details: Optional[Dict[str, Any]] = None

class AgenticState(BaseModel):
    """
    The overall state of the agentic workflow using a TypedDict.
    """
    lead: List[Lead] = Field(default_factory=list)
    performance_metrics: Dict[str, Any] = Field(default_factory=dict)
    optimization_insights: Optional[str] = None