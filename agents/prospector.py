from models.state import MarketingAgent, LeadData, LeadStatus
from models.prompts import PROSPECTOR_SYSTEM_PROMPT, PROSPECTOR_HUMAN_PROMPT_TEMPLATE
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
import os
import time
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

# Pydantic models for structured LLM output
class MatchedCriteria(BaseModel):
    """Criteria matching results for lead qualification"""
    industry_match: bool = Field(..., description="Whether the industry matches target industries")
    employee_count_match: bool = Field(..., description="Whether employee count is within ideal range")
    location_match: bool = Field(..., description="Whether location matches target regions")
    job_title_match: bool = Field(..., description="Whether job title matches target titles")
    is_excluded_title: bool = Field(..., description="Whether job title is in excluded list")

class LeadAnalysisResponse(BaseModel):
    """Structured response for individual lead analysis"""
    lead_score: int = Field(..., ge=0, le=100, description="The ICP score from 0 to 100")
    qualification_status: str = Field(..., description="QUALIFIED, NOT_QUALIFIED, or NEEDS_REVIEW")
    reasoning: str = Field(..., description="Detailed explanation of scoring and qualification")
    matched_criteria: MatchedCriteria = Field(..., description="Criteria matching results")
    recommendations: str = Field(..., description="Next steps or suggestions for this lead")

class BatchAnalysisResponse(BaseModel):
    """Structured response for batch lead analysis"""
    leads: List[LeadAnalysisResponse] = Field(..., description="Analysis results for each lead in the batch")

# LLM setup with structured output
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    temperature=0.4,
    api_key=os.getenv("GOOGLE_API_KEY")
)

# Structured LLM for single lead analysis
single_lead_llm = llm.with_structured_output(LeadAnalysisResponse)

# Structured LLM for batch analysis
batch_lead_llm = llm.with_structured_output(BatchAnalysisResponse)


def Prospector(state: MarketingAgent) -> MarketingAgent:
    """
    A prospector agent that can prospect for new leads.
    """
    leads_data = load_leads_from_csv("data/leads.csv")

    for lead in leads_data:
        
    return state