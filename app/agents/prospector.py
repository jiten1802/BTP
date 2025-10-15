from app.models.state import AgenticState, Lead
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Literal, List
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level=logging.INFO, # Set the minimum level of messages to display
    format="%(asctime)s - %(levelname)s - %(message)s"
)
from app.models.prompts import (
    PROSPECTOR_SYSTEM_PROMPT,
    PROSPECTOR_HUMAN_PROMPT_TEMPLATE,
    BATCH_PROSPECTOR_HUMAN_PROMPT_TEMPLATE,
)
from app.utils import get_leads_by_status, update_performance_metrics, rate_limited_call
from app.key_manager import api_key_manager
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import threading

load_dotenv()

class LeadScore(BaseModel):
    lead_score: int = Field(description="ICP Score from 0-100", ge=0, le=100)
    qualification_status: Literal["QUALIFIED", "NOT_QUALIFIED", "NEEDS_REVIEW"] = Field(description="Qualification status based on score and criteria")
    reasoning: str = Field(description="Detailed explanation of scoring decision")
    matched_criteria: Dict[str, bool] = Field(
        description="Which ICP criteria were matched",
        example={
            "industry_match": True,
            "employee_count_match": False,
            "location_match": True,
            "job_title_match": True,
            "is_excluded_title": False
        }
    )
    recommendations: str = Field(description="Next steps or suggestions for this lead")

    @field_validator("matched_criteria", mode="before")
    def parse_matched_criteria(cls, v):
        if isinstance(v, str):
            try:
                # Handles boolean values being capitalized by the LLM
                v_fixed = v.replace("True", "true").replace("False", "false")
                return json.loads(v_fixed)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid matched_criteria JSON: {e}")
        return v

class BatchLeadScore(BaseModel):
    """Response model for batch processing - contains up to 5 lead scores"""
    lead_scores: List[LeadScore] = Field(
        description="List of lead scores, qualification status, reasoning, matched criteria, and recommendations in the same order as input leads",
        min_items=5,
        max_items=5
    )

# --- LLM and API Call Handling ---
def create_llm_with_key(api_key: str, batch_mode: bool = False):
    """Creates an LLM instance with a specific API key."""
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.7, groq_api_key=api_key)
    return llm.with_structured_output(BatchLeadScore if batch_mode else LeadScore)

@rate_limited_call(max_per_minute=25)  
def call_llm(messages: List, api_key: str, batch_mode: bool = False):
    """
    Calls the LLM with a specific API key.
    CORRECTION: This function now accepts an api_key, making the data flow explicit
    and allowing a per-key rate limiter to function correctly.
    """
    try:
        structured_llm = create_llm_with_key(api_key, batch_mode=batch_mode)
        result = structured_llm.invoke(messages)
        api_key_manager.record_api_call(api_key, success=True)
        return result
    except Exception as e:
        api_key_manager.record_api_call(api_key, success=False)
        print(f"API call failed with key ending in ...{api_key[-4:]}: {str(e)}")
        raise e

# --- Lead Formatting and Scoring Logic ---
def format_lead_data(lead: Dict[str, Any]) -> str:
    """Formats a single lead's data into a string for the prompt."""
    return (
        f"Company: {lead.get('company_name', 'N/A')}\n"
        f"Industry: {lead.get('industry', 'N/A')}\n"
        f"Employee Count: {lead.get('employee_count', 'N/A')}\n"
        f"Location: {lead.get('location', 'N/A')}\n"
        f"Contact Person: {lead.get('contact_person', 'N/A')}\n"
        f"Job Title: {lead.get('job_title', 'N/A')}\n"
        f"Email: {lead.get('email', 'N/A')}"
    )

def score_batch_of_leads(leads: List[Dict[str, Any]], api_key: str) -> List[LeadScore]:
    """
    Scores a batch of 1-5 leads in a single API call.
    CORRECTION: Now accepts an api_key to pass to the LLM call.
    """
    if not len(leads) == 5:
        raise ValueError(f"Batch processing supports 5 leads, but got {len(leads)}")
    
    PROSPECTOR_BATCH_RESPONSE_FORMAT = """
        Your response must contain a JSON object for each lead. Each object must have the following structure:
        ```json
        {
            "lead_score": "integer between 0 and 100",
            "qualification_status": "QUALIFIED, NOT_QUALIFIED, or NEEDS_REVIEW",
            "reasoning": "A detailed explanation of how the score was calculated based on the ICP criteria.",
            "matched_criteria": {
                "industry_match": "boolean",
                "employee_count_match": "boolean",
                "location_match": "boolean",
                "job_title_match": "boolean",
                "is_excluded_title": "boolean"
            },
            "recommendations": "Suggested next steps for this lead."
        }
    """

    PROSPECTOR_BATCH_EXPECTED_RESPONSE = """
        ```json
        [
            {
                "lead_score": 95,
                "qualification_status": "QUALIFIED",
                "reasoning": "The lead strongly aligns with all key ICP criteria.",
                "matched_criteria": {"industry_match": true, "employee_count_match": true, "location_match": true, "job_title_match": true, "is_excluded_title": false},
                "recommendations": "Highly qualified lead. Recommend immediate outreach."
            },
            {
                "lead_score": 60,
                "qualification_status": "NEEDS_REVIEW",
                "reasoning": "The lead meets some ICP criteria but has uncertainties.",
                "matched_criteria": {"industry_match": true, "employee_count_match": false, "location_match": true, "job_title_match": false, "is_excluded_title": false},
                "recommendations": "Potentially qualified. Suggest further research before outreach."
            },
            {
                "lead_score": 25,
                "qualification_status": "NOT_QUALIFIED",
                "reasoning": "The lead does not meet key ICP criteria and has an excluded title.",
                "matched_criteria": {"industry_match": false, "employee_count_match": false, "location_match": false, "job_title_match": false, "is_excluded_title": true},
                "recommendations": "Not a qualified lead. No further action recommended."
            },
            {
                "lead_score": 80,
                "qualification_status": "QUALIFIED",
                "reasoning": "The lead aligns well with most ICP criteria.",
                "matched_criteria": {"industry_match": true, "employee_count_match": true, "location_match": true, "job_title_match": false, "is_excluded_title": false},
                "recommendations": "Qualified lead. Recommend outreach within the next week."
            },
            {
                "lead_score": 45,
                "qualification_status": "NEEDS_REVIEW",
                "reasoning": "The lead has mixed alignment with ICP criteria.",
                "matched_criteria": {"industry_match": false, "employee_count_match": true, "location_match": false, "job_title_match": true, "is_excluded_title": false},
                "recommendations": "Uncertain qualification. Suggest additional vetting before outreach."
            }
        ]

    """
    human_message = BATCH_PROSPECTOR_HUMAN_PROMPT_TEMPLATE.format(
        lead_1_data=format_lead_data(leads[0]),
        lead_2_data=format_lead_data(leads[1]),
        lead_3_data=format_lead_data(leads[2]),
        lead_4_data=format_lead_data(leads[3]),
        lead_5_data=format_lead_data(leads[4]),
        response_format=PROSPECTOR_BATCH_RESPONSE_FORMAT,
        expected_response=PROSPECTOR_BATCH_EXPECTED_RESPONSE
    )
    
    messages = [SystemMessage(content=PROSPECTOR_SYSTEM_PROMPT), HumanMessage(content=human_message)]

    try:
        result = call_llm(messages, api_key=api_key, batch_mode=True)
        return result.lead_scores
    except Exception as e:
        print(f"Error scoring batch of leads: {str(e)}")
        # Return a list of error responses, one for each lead in the failed batch
        return [LeadScore(
            lead_score=0,
            qualification_status="NOT_QUALIFIED",
            reasoning=f"Error during batch scoring: {str(e)}",
            matched_criteria={"industry_match": False, "employee_count_match": False, "location_match": False, "job_title_match": False, "is_excluded_title": False},
            recommendations="Manual review required due to processing error"
        )] * len(leads)

def score_lead(lead: Dict[str, Any], api_key: str) -> LeadScore:
    """
    Scores a single lead with the LLM.
    CORRECTION: Simplified prompt and now accepts an api_key.
    """
    lead_data = format_lead_data(lead)
    human_message = PROSPECTOR_HUMAN_PROMPT_TEMPLATE.format(leads_data=lead_data)
    messages = [SystemMessage(content=PROSPECTOR_SYSTEM_PROMPT), HumanMessage(content=human_message)]

    try:
        return call_llm(messages, api_key=api_key, batch_mode=False)
    except Exception as e:
        print(f"Error scoring single lead: {str(e)}")
        return LeadScore(
            lead_score=0,
            qualification_status="NOT_QUALIFIED",
            reasoning=f"Error during scoring: {str(e)}",
            matched_criteria={"industry_match": False, "employee_count_match": False, "location_match": False, "job_title_match": False, "is_excluded_title": False},
            recommendations="Manual review required due to processing error"
        )

# --- Concurrent Processing Workflow ---
def process_lead_with_score(lead: Lead, score: LeadScore) -> Lead:
    """Applies a LeadScore object to a Lead object."""
    lead.contacts = {"email": lead.raw_data.get("email", "N/A")}
    lead.score = int(score.lead_score)
    lead.qualified_lead = score.qualification_status == "QUALIFIED"
    lead.status = "scored"
    logging.info(
        f"\n--- Lead: {lead.raw_data.get('company_name', 'N/A')} ---\n"
        f"  - Score: {score.lead_score}\n"
        f"  - Status: {score.qualification_status}\n"
        f"  - Reasoning: {score.reasoning}\n"
        f"  - Matched Criteria: {score.matched_criteria}"
    )
    if score.reasoning.startswith("Error"):
        lead.status = "failed"
    if lead.communication_history is None:
        lead.communication_history = []
    return lead

def process_batch(leads: List[Lead]) -> List[Lead]:
    """Task for processing a full batch of 5 leads."""
    thread_id = threading.get_ident()
    api_key = api_key_manager.get_key_for_thread()
    key_index = api_key_manager.keys.index(api_key) + 1 if api_key in api_key_manager.keys else 'N/A'
    
    try:
        leads_data = [lead.raw_data for lead in leads]
        scores = score_batch_of_leads(leads_data, api_key=api_key)
        
        # Ensure we got a score for each lead, even if scoring failed
        if len(scores) != len(leads):
            raise ValueError(f"Mismatch between number of leads ({len(leads)}) and scores ({len(scores)}) returned.")

        processed_leads = [process_lead_with_score(lead, score) for lead, score in zip(leads, scores)]
        qualified_in_batch = sum(1 for lead in processed_leads if lead.qualified_lead)
        print(f"✅ Thread {thread_id} (Key {key_index}) processed batch: {qualified_in_batch}/{len(leads)} qualified")
        return processed_leads
    except Exception as e:
        print(f"❌ Thread {thread_id} (Key {key_index}) error processing batch: {str(e)}")
        return [process_lead_with_score(lead, score_lead({}, api_key)) for lead in leads] # Mark all as failed

def process_single(lead: Lead) -> Lead:
    """Task for processing a single lead (used for partial batches)."""
    api_key = api_key_manager.get_key_for_thread()
    score = score_lead(lead.raw_data, api_key=api_key)
    return process_lead_with_score(lead, score)

# --- Main Agent Function ---
def Prospector(state: AgenticState) -> AgenticState:
    """
    Scores all new leads using concurrent batch processing.
    CORRECTION: Handles partial batches correctly by processing leftovers individually.
    """
    new_leads = get_leads_by_status(state, "new")
    if not new_leads:
        print("No new leads to process.")
        return state

    batch_size = 5
    num_workers = 3
    
    # Separate leads into full batches and a final partial batch
    full_batches = [new_leads[i:i + batch_size] for i in range(0, len(new_leads) - len(new_leads) % batch_size, batch_size)]
    partial_batch_start_index = len(full_batches) * batch_size
    partial_batch = new_leads[partial_batch_start_index:]
    
    total_api_calls = len(full_batches) + len(partial_batch)
    
    print(f"🚀 Processing {len(new_leads)} new leads with {num_workers} threads...")
    print(f"📦 Submitting {len(full_batches)} full batches of {batch_size} and {len(partial_batch)} single leads.")

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(process_batch, batch) for batch in full_batches]
        futures += [executor.submit(process_single, lead) for lead in partial_batch]

        processed_count = 0
        for future in as_completed(futures):
            try:
                result = future.result()
                # The lead objects within the state are modified in-place, so no need to re-assign.
                count = len(result) if isinstance(result, list) else 1
                processed_count += count
                
                if processed_count % 25 == 0 or processed_count == len(new_leads):
                    print(f"📈 Progress: {processed_count}/{len(new_leads)} leads processed.")
            except Exception as e:
                print(f"A task generated an unexpected error: {str(e)}")

    # --- Final Statistics ---
    qualified_count = sum(1 for lead in new_leads if lead.qualified_lead)
    failed_count = sum(1 for lead in new_leads if lead.status == 'failed')
    
    update_performance_metrics(state, "processed_leads", len(new_leads))
    update_performance_metrics(state, "qualified_leads", qualified_count)

    print("\n--- Prospector Run Complete ---")
    print(f"✅ Total Processed: {len(new_leads)}")
    print(f"🎯 Qualified Leads: {qualified_count}")
    if failed_count > 0:
        print(f"⚠️ Failed Leads: {failed_count}")
    
    print("\n📊 Optimization Statistics:")
    api_calls_saved = len(new_leads) - total_api_calls
    reduction_percent = (api_calls_saved / len(new_leads) * 100) if new_leads else 0
    print(f"   - API Calls Made: {total_api_calls} (vs. {len(new_leads)} without batching)")
    print(f"   - API Calls Saved: {api_calls_saved} ({reduction_percent:.1f}% reduction)")
    
    print("\n🔑 API Key Usage:")
    api_key_manager.print_stats()
    
    return state