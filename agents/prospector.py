from models.state import AgenticState, Lead
from pydantic import BaseModel, Field, field_validator
import json
from typing import Dict, Any, Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
from models.prompts import PROSPECTOR_SYSTEM_PROMPT, PROSPECTOR_HUMAN_PROMPT_TEMPLATE
from utils import get_leads_by_status, update_performance_metrics, rate_limited_call
import os

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")


class LeadScore(BaseModel):
    lead_score: int = Field(description="ICP Score form 0-100", ge=0, le=100)
    qualification_status: Literal["QUALIFIED", "NOT_QUALIFIED", "NEEDS_REVIEW"] = Field(description="Qualification status based on socre and criteria")
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
                v_fixed = v.replace("True", "true").replace("False", "false")
                return json.loads(v_fixed)   # convert string → dict
            except Exception as e:
                raise ValueError(f"Invalid matched_criteria JSON: {e}")
        return v

llm = ChatGoogleGenerativeAI(model = "gemini-2.0-flash", temperature = 0.7, api_key = api_key)
structured_llm = llm.with_structured_output(LeadScore)

@rate_limited_call(max_per_minute=13)
def call_llm(messages):
    return structured_llm.invoke(messages)

def score_lead(lead: Dict[str, Any]) -> LeadScore:
    """
    Score Lead with LLM  using ICP criteria
    """

    lead_data = f"""
    Company: {lead.get("company_name", "N/A")}
    Industry: {lead.get("industry", "N/A")}
    Employee Count: {lead.get("employee_count", "N/A")}
    Location: {lead.get("location", "N/A")}
    Contact Person: {lead.get("contact_person", "N/A")}
    Job Title: {lead.get("job_title", "N/A")}
    Email: {lead.get("email", "N/A")}
    """

    human_message = PROSPECTOR_HUMAN_PROMPT_TEMPLATE.format(
        leads_data = lead_data,
        response_format = "Return a single JSON object. Use true/false for boolean values (lowercase), and double quotes for strings.",
        expected_response = """
        A LeadScore object with lead_score, qualification_status, reasoning, matched_criteria, and recommendations.
        {
            lead_score: ICP Score form 0-100,
            qualification_status: Qualification status based on socre and criteria,
            reasoning: Detailed explanation of scoring decision,
            matched_criteria: Which ICP criteria were matched,
            example for matched criteria={
            "industry_match": True,
            "employee_count_match": False,
            "location_match": True,
            "job_title_match": True,
            "is_excluded_title": False
            },
            recommendations: Next steps or suggestions for this lead
        }
        """
    )

    messages = [
        SystemMessage(content = PROSPECTOR_SYSTEM_PROMPT),
        HumanMessage(content = human_message)
    ]

    try:
        result = call_llm(messages)
        return result    
    except Exception as e:
        print(f"Error scoring the lead: {str(e)}")
        error_response = LeadScore(
            lead_score = 0,
            qualification_status = "NOT_QUALIFIED",
            reasoning=f"Error during scoring: {str(e)}",
            matched_criteria={
                "industry_match": False,
                "employee_count_match": False,
                "location_match": False,
                "job_title_match": False,
                "is_excluded_title": False
            },
            recommendations="Manual review required due to processing error"
        )
        return error_response

def process_single_lead(lead: Lead) -> Lead:
    """
    Process a single lead through the prospector workflow.
    """
    score = score_lead(lead.raw_data)

    lead.contacts = {"email": lead.raw_data["email"]}
    lead.score = int(score.lead_score)
    lead.qualified_lead = score.qualification_status == "QUALIFIED"
    lead.status = "scored"

    if lead.communication_history is None:
        lead.communication_history = []
    
    return lead

def Prospector(state: AgenticState) -> AgenticState:
    """ 
    Score each lead that we have
    """
    new_leads = get_leads_by_status(state, "new")

    if not new_leads:
        print("No new leads present")
        return state

    print(f"Processing {len(new_leads)} new leads...")

    processed_count = 0
    qualified_count = 0

    for lead in new_leads:
        try:
            processed_lead = process_single_lead(lead)
            processed_count+=1
            if processed_lead.qualified_lead:
                qualified_count+=1
            
            if processed_count % 100 == 0:
                print(f"Processed {processed_count}/{len(new_leads)} leads...")
            
        except Exception as e:
            print(f"Error processing the lead {lead.lead_id}: {str(e)}")
            lead.status = "failed"
    
    update_performance_metrics(state, "processed_leads", processed_count)
    update_performance_metrics(state, "qualified_leads", qualified_count)

    print(f"✅ Prospector: Completed processing {processed_count} leads")
    print(f"🎯 Prospector: Found {qualified_count} qualified leads")
    print(f"📤 Prospector: Publishing all {processed_count} scored leads to Strategist")
    
    return state