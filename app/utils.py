from app.models.state import AgenticState, Lead
from typing import List, Dict, Any
import time
from functools import wraps

def get_lead_by_id(state: AgenticState, lead_id: str) -> Lead:
    """
    Get a specific lead by its ID.
    
    Args:
        state: Current agentic state
        lead_id: ID of the lead to retrieve
        
    Returns:
        Lead: The lead with matching ID, or None if not found
    """
    for lead in state.lead:
        if lead.lead_id == lead_id:
            return lead
    return None

def update_lead_status(state: AgenticState, lead_id: str, new_status: str) -> bool:
    """
    Update the status of a specific lead.
    
    Args:
        state: Current agentic state
        lead_id: ID of the lead to update
        new_status: New status to set
        
    Returns:
        bool: True if update was successful, False if lead not found
    """
    lead = get_lead_by_id(state, lead_id)
    if lead:
        lead.status = new_status
        return True
    return False

def get_leads_by_status(state: AgenticState, status: str) -> List[Lead]:
    """
    Get all leads with a specific status.
    
    Args:
        state: Current agentic state
        status: Status to filter by
        
    Returns:
        List[Lead]: List of leads with the specified status
    """
    return [lead for lead in state.lead if lead.status == status]

def update_performance_metrics(state: AgenticState, metric_name: str, increment: int = 1) -> None:
    """
    Update performance metrics in the state.
    
    Args:
        state: Current agentic state
        metric_name: Name of the metric to update
        increment: Amount to increment by (default: 1)
    """
    if metric_name in state.performance_metrics:
        state.performance_metrics[metric_name] += increment
    else:
        state.performance_metrics[metric_name] = increment

def get_workflow_summary(state: AgenticState) -> Dict[str, Any]:
    """
    Get a summary of the current workflow state.
    
    Args:
        state: Current agentic state
        
    Returns:
        Dict[str, Any]: Summary of the workflow state
    """
    status_counts = {}
    for lead in state.lead:
        status = lead.status
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return {
        "total_leads": len(state.lead),
        "status_breakdown": status_counts,
        "performance_metrics": state.performance_metrics,
        "qualified_leads_count": sum(1 for lead in state.lead if lead.qualified_lead),
        "leads_with_scores": sum(1 for lead in state.lead if lead.score is not None),
        "leads_with_contacts": sum(1 for lead in state.lead if lead.contacts is not None)
    }



# Rate limiter decorator
def rate_limited_call(max_per_minute: int = 13):
    """
    Sleep-based rate limiter for API calls.
    
    Args:
        max_per_minute: Maximum allowed calls per minute (default 2 for Gemini free-tier).
    """
    interval = 60.0 / max_per_minute  # seconds to wait between calls

    def decorator(func):
        last_called = [0.0]

        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            elapsed = now - last_called[0]
            wait = interval - elapsed
            if wait > 0:
                time.sleep(wait)  # throttle
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result
        return wrapper
    return decorator