"""
Utility functions for batch processing and state management.
Contains helper functions for creating and managing MarketingAgent and BatchState instances.
"""

import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from models.state import MarketingAgent, BatchState, LeadData, LeadStatus

def create_initial_marketing_agent_state(lead_data: LeadData) -> MarketingAgent:
    """
    Create an initial MarketingAgent state from lead data.
    Used during batch processing to initialize individual lead states.
    """
    return MarketingAgent(
        # Lead Identification
        lead_id=lead_data.lead_id,
        company_name=lead_data.company_name,
        contact_person=lead_data.contact_person,
        contact_email=lead_data.contact_email,
        initial_source=lead_data.initial_source,
        
        # Lead Data
        industry=lead_data.industry,
        employee_count=lead_data.employee_count,
        location=lead_data.location,
        job_title=lead_data.job_title,
        
        # Scoring & Qualification
        icp_score=lead_data.icp_score or 0,
        is_qualified=None,
        qualification_status=lead_data.qualification_status or LeadStatus.PENDING,
        qualification_notes=lead_data.reasoning,
        
        # Batch Processing Fields
        batch_processed=False,
        batch_id=lead_data.batch_id,
        batch_processing_time=lead_data.processing_time,
        
        # Outreach & Engagement
        outreach_channel=None,
        outreach_strategy="Initial Outreach",
        messages=[],
        
        # Response & Intent
        last_response=None,
        lead_intent=None,
        
        # Scheduling & Meetings
        meeting_booked=False,
        meeting_details=None,
        
        # System & Workflow
        next_agent="prospector",
        error_message=lead_data.error_message,
        retries=0
    )

def create_batch_state(leads: List[MarketingAgent], batch_size: int = 50, max_workers: int = 10) -> BatchState:
    """
    Create a batch state for processing multiple leads efficiently.
    """
    total_batches = (len(leads) + batch_size - 1) // batch_size
    
    return BatchState(
        batch_id=f"batch_{int(time.time())}",
        batch_size=batch_size,
        max_workers=max_workers,
        total_leads=len(leads),
        processed_leads=0,
        leads=leads,
        qualified_leads=[],
        not_qualified_leads=[],
        needs_review_leads=[],
        error_leads=[],
        start_time=time.time(),
        end_time=None,
        total_processing_time=None,
        average_time_per_lead=None,
        current_batch=0,
        total_batches=total_batches,
        is_complete=False,
        qualification_summary={},
        performance_summary={}
    )

def load_leads_from_csv(csv_path: str) -> List[LeadData]:
    """
    Load leads from CSV and convert to LeadData objects.
    """
    df = pd.read_csv(csv_path)
    leads = []
    
    for _, row in df.iterrows():
        lead = LeadData(
            lead_id=str(row.name),  
            company_name=row['company_name'],
            contact_person=row['contact_person'],
            contact_email=row['email'],
            industry=row['industry'],
            employee_count=int(row['employee_count']),
            location=row['location'],
            job_title=row['job_title']
        )
        leads.append(lead)
        
    return leads

def convert_lead_data_to_marketing_agent(lead_data_list: List[LeadData]) -> List[MarketingAgent]:
    """
    Convert a list of LeadData objects to MarketingAgent states.
    """
    return [create_initial_marketing_agent_state(lead_data) for lead_data in lead_data_list]

def update_batch_state_results(batch_state: BatchState, processed_leads: List[MarketingAgent]) -> BatchState:
    """
    Update batch state with processed results and categorize leads by status.
    """
    # Categorize leads by status
    for lead in processed_leads:
        if lead["qualification_status"] == LeadStatus.QUALIFIED:
            batch_state["qualified_leads"].append(lead)
        elif lead["qualification_status"] == LeadStatus.NOT_QUALIFIED:
            batch_state["not_qualified_leads"].append(lead)
        elif lead["qualification_status"] == LeadStatus.NEEDS_REVIEW:
            batch_state["needs_review_leads"].append(lead)
        elif lead["qualification_status"] == LeadStatus.ERROR:
            batch_state["error_leads"].append(lead)
    
    # Update counters
    batch_state["processed_leads"] += len(processed_leads)
    batch_state["current_batch"] += 1
    
    # Update summary
    batch_state["qualification_summary"] = {
        "qualified": len(batch_state["qualified_leads"]),
        "not_qualified": len(batch_state["not_qualified_leads"]),
        "needs_review": len(batch_state["needs_review_leads"]),
        "errors": len(batch_state["error_leads"])
    }
    
    return batch_state

def finalize_batch_state(batch_state: BatchState) -> BatchState:
    """
    Finalize batch state with performance metrics and completion status.
    """
    batch_state["end_time"] = time.time()
    batch_state["total_processing_time"] = batch_state["end_time"] - batch_state["start_time"]
    batch_state["average_time_per_lead"] = batch_state["total_processing_time"] / batch_state["total_leads"]
    batch_state["is_complete"] = True
    
    # Performance summary
    batch_state["performance_summary"] = {
        "total_time": batch_state["total_processing_time"],
        "average_time_per_lead": batch_state["average_time_per_lead"],
        "leads_per_second": batch_state["total_leads"] / batch_state["total_processing_time"],
        "parallelization_efficiency": (batch_state["total_processing_time"] / (batch_state["total_leads"] / batch_state["max_workers"])) * 100
    }
    
    return batch_state

def get_batch_results_summary(batch_state: BatchState) -> Dict[str, Any]:
    """
    Get a summary of batch processing results.
    """
    return {
        "total_leads": batch_state["total_leads"],
        "processing_time": f"{batch_state['total_processing_time']:.2f} seconds",
        "average_time_per_lead": f"{batch_state['average_time_per_lead']:.3f} seconds",
        "leads_per_second": f"{batch_state['performance_summary']['leads_per_second']:.2f}",
        "qualification_breakdown": batch_state["qualification_summary"],
        "performance_metrics": batch_state["performance_summary"]
    }

def process_batch_parallel(leads: List[MarketingAgent], processor_func, max_workers: int = 10) -> List[MarketingAgent]:
    """
    Process a batch of leads in parallel using ThreadPoolExecutor.
    """
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all leads for processing
        future_to_lead = {executor.submit(processor_func, lead): lead for lead in leads}
        
        # Collect results as they complete
        processed_leads = []
        for future in as_completed(future_to_lead):
            lead = future.result()
            processed_leads.append(lead)
            
    return processed_leads

def calculate_icp_score_rule_based(lead: MarketingAgent) -> int:
    """
    Calculate ICP score based on predefined criteria (rule-based scoring).
    """
    score = 10  # Base score
    
    # Industry match (25 points)
    target_industries = ["Software as a Service (SaaS)", "Financial Technology", "E-commerce"]
    if lead["industry"] in target_industries:
        score += 25
        
    # Employee count match (15 points)
    if lead["employee_count"] and 50 <= lead["employee_count"] <= 1000:
        score += 15
        
    # Location match (20 points)
    target_locations = ["North America", "Western Europe"]
    if lead["location"] in target_locations:
        score += 20
        
    # Job title match (20 points)
    target_titles = ["Head of Sales", "VP of Marketing", "Sales Director", "Chief Revenue Officer"]
    if lead["job_title"] in target_titles:
        score += 20
        
    # Excluded titles (-50 points)
    excluded_titles = ["Intern", "Assistant", "Analyst"]
    if lead["job_title"] in excluded_titles:
        score -= 50
        
    return max(0, min(100, score))

def determine_qualification_status(score: int, lead: MarketingAgent) -> LeadStatus:
    """
    Determine qualification status based on score and criteria.
    """
    excluded_titles = ["Intern", "Assistant", "Analyst"]
    
    if score >= 70 and lead["job_title"] not in excluded_titles:
        return LeadStatus.QUALIFIED
    elif score < 30 or lead["job_title"] in excluded_titles:
        return LeadStatus.NOT_QUALIFIED
    else:
        return LeadStatus.NEEDS_REVIEW

def process_lead_rule_based(lead: MarketingAgent) -> MarketingAgent:
    """
    Process a single lead using rule-based scoring.
    """
    start_time = time.time()
    
    try:
        # Calculate score
        score = calculate_icp_score_rule_based(lead)
        status = determine_qualification_status(score, lead)
        
        # Update lead
        lead["icp_score"] = score
        lead["is_qualified"] = (status == LeadStatus.QUALIFIED)
        lead["qualification_status"] = status
        lead["qualification_notes"] = f"Rule-based: Score {score}, Status {status.value}"
        lead["batch_processed"] = True
        lead["batch_processing_time"] = time.time() - start_time
        
    except Exception as e:
        lead["qualification_status"] = LeadStatus.ERROR
        lead["error_message"] = str(e)
        lead["batch_processed"] = True
        lead["batch_processing_time"] = time.time() - start_time
        
    return lead
