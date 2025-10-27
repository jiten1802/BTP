import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List
from tqdm import tqdm

from app.models.state import AgenticState, Lead
from app.utils import get_leads_by_status, update_performance_metrics

# --- Import our new tools and aggregator ---
from app.tools.prospector_tools import (
    check_industry,
    check_employee_count,
    check_location,
    check_job_title,
    check_excluded_job_title,
    calculate_final_score,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def score_one_lead_with_tools(lead: Lead) -> Lead:
    """
    Processes a single lead by calling all the deterministic tools
    and then aggregating the results. NO LLM is used.
    """
    raw_data = lead.raw_data
    
    # 1. Call all the deterministic tool functions
    tool_results = {
        "industry_match": check_industry(raw_data.get('industry', '')),
        "employee_count_match": check_employee_count(raw_data.get('employee_count', 0)),
        "location_match": check_location(raw_data.get('location', '')),
        "job_title_match": check_job_title(raw_data.get('job_title', '')),
        "is_excluded_title": check_excluded_job_title(raw_data.get('job_title', ''))
    }
    
    final_score, final_status, reasoning = calculate_final_score(tool_results)
    lead.score = final_score
    lead.qualified_lead = (final_status == "QUALIFIED")
    lead.status = "scored"
    return lead

# --- Main Agent Function ---
def Prospector(state: AgenticState) -> AgenticState:
    """
    Scores all new leads using a multithreaded, deterministic, tool-based approach.
    """
    new_leads = get_leads_by_status(state, "new")
    if not new_leads:
        print("Prospector: No new leads to process.")
        return state

    num_workers = 10 
    print(f"🚀 Processing {len(new_leads)} new leads with {num_workers} worker threads (using tools)...")

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        list(tqdm(executor.map(score_one_lead_with_tools, new_leads), total=len(new_leads), desc="Scoring leads"))

    qualified_count = sum(1 for lead in new_leads if lead.qualified_lead)
    
    update_performance_metrics(state, "processed_leads", len(new_leads))
    update_performance_metrics(state, "qualified_leads", qualified_count)

    print("\n--- Prospector Run Complete ---")
    print(f"✅ Total Processed: {len(new_leads)}")
    print(f"🎯 Qualified Leads: {qualified_count}")
    
    return state