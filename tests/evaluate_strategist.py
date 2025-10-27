import os
import sys
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
import logging
from typing import Dict, Any, List, Literal, Optional

# --- Add project root to Python path ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

# --- App-specific Imports ---
from app.models.state import Lead
from app.models.prompts import STRATEGIST_SYSTEM_PROMPT, STRATEGIST_HUMAN_PROMPT_TEMPLATE
# We also import the Pydantic model the Strategist uses for structured output
from app.agents.strategist import PersonalizedMessage
from app.key_manager import api_key_manager

# --- Imports for the LLM-as-a-Judge (Now using Google) ---
from langchain_google_genai import ChatGoogleGenerativeAI 
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

# --- Setup ---
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# --- Configure the Google client for the judge ---
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY_2")
GROQ_API_KEY = os.getenv("GROQ_API_KEY_4")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY_4 not found in .env file. Please add it from Google AI Studio.")

# --- 1. Define the Judge's Pydantic Model (The Scorecard) - NO CHANGES HERE ---
class Evaluation(BaseModel):
    preference: Literal["Email A is better", "Email B is better", "Both are of equal quality"] = Field(...)
    rationale: str = Field(...)
    score_a_personalization: int = Field(description="Score for Email A on personalization (1-10).", ge=1, le=10)
    score_a_persuasiveness: int = Field(description="Score for Email A on persuasiveness (1-10).", ge=1, le=10)
    score_b_personalization: int = Field(description="Score for Email B on personalization (1-10).", ge=1, le=10)
    score_b_persuasiveness: int = Field(description="Score for Email B on persuasiveness (1-10).", ge=1, le=10)

def generate_email_in_script(
    lead: Lead, 
    prompt_strategy: Literal["multi_message", "single_message"]
) -> Optional[PersonalizedMessage]:
    """
    This function re-creates the core logic of the Strategist agent's LLM call
    for the purpose of this isolated experiment.
    """
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.7, groq_api_key=api_key_manager.get_random_key())
    structured_llm = llm.with_structured_output(PersonalizedMessage)
    
    lead_data_str = f"""
        Company: {lead.raw_data.get("company_name", "N/A")}
        Industry: {lead.raw_data.get("industry", "N/A")}
        Employee Count: {lead.raw_data.get("employee_count", "N/A")}
        Location: {lead.raw_data.get("location", "N/A")}
        Contact Person: {lead.raw_data.get("contact_person", "N/A")}
        Job Title: {lead.raw_data.get("job_title", "N/A")}
        Email: {lead.raw_data.get("email", "N/A")}
        Lead Score: {lead.score}
        Qualification Status: {"QUALIFIED" if lead.qualified_lead else "NOT_QUALIFIED"}
    """
    
    if prompt_strategy == "multi_message":
        # Strategy B: Separate system and human messages
        human_message = STRATEGIST_HUMAN_PROMPT_TEMPLATE.format(
        lead_data=lead_data_str,
        expected_response="""
        A PersonalizedMessage object with:
        "subject_line": "A compelling subject line",
        "salutation": "Dear [Contact Person],",
        "email_body": "The main paragraphs of the email...",
        "signature": "Best regards,",
        "tone": "professional",
        "key_personalization_points": {{...}},
        "call_to_action": "A clear call-to-action",
        "follow_up_suggestion": "A follow-up strategy"
      """
    )                                                    
        messages = [
            SystemMessage(content=STRATEGIST_SYSTEM_PROMPT),
            HumanMessage(content=human_message)
        ]
    
    elif prompt_strategy == "single_message":
        # Strategy A: Combine everything into one large user prompt
        single_prompt_content =  """You are an expert B2B sales outreach strategist. Your task is to write a highly personalized and persuasive outreach email to a potential lead.
            Your output MUST be a valid JSON object that calls the `PersonalizedMessage` tool.

            Guidelines:
            1.  **Personalization:** Reference specific details about the lead's role, company, or industry.
            2.  **Clarity:** Communicate a clear value proposition concisely.
            3.  **Tone:** Be professional, confident, and solution-oriented.
            4.  **Brevity:** Keep the main `email_body` between 100-150 words.
            5.  **Structure:** Generate the `subject_line`, `salutation`, `email_body`, and `signature` as separate fields.
            Please write a personalized email for the following lead:
            - {lead_data}
            Expected Response:
            {expected_response}
            """
        
        single_prompt_content = single_prompt_content.format( 
            lead_data=lead_data_str,
            expected_response="""A PersonalizedMessage object with:
                "subject_line": "A compelling subject line",
                "salutation": "Dear [Contact Person],",
                "email_body": "The main paragraphs of the email...",
                "signature": "Best regards,",
                "tone": "professional",
                "key_personalization_points": {{...}},
                "call_to_action": "A clear call-to-action",
                "follow_up_suggestion": "A follow-up strategy"
                """
        )
        messages = [HumanMessage(content=single_prompt_content)]

    try:
        result = structured_llm.invoke(messages)
        return result
    except Exception as e:
        logging.error(f"Error generating email with {prompt_strategy}: {e}")
        return None
    

def evaluate_emails_with_llm_judge(
    lead: Dict[str, Any],
    email_a_body: str,
    email_b_body: str
) -> Optional[Evaluation]:
    """
    Uses a powerful Google Gemini model to compare two emails and return a structured evaluation.
    """
    judge_prompt = f"""
    You are an expert Sales Manager tasked with evaluating two draft emails for a B2B outreach campaign. Your goal is to be an impartial, objective judge.

    ### The Prospect You Are Contacting ###
    - Name: {lead.get('contact_person')}
    - Title: {lead.get('job_title')}
    - Company: {lead.get('company_name')}
    - Industry: {lead.get('industry')}

    ### The Emails to Evaluate ###
    --- Email A ---
    {email_a_body}
    --- END OF EMAIL A ---

    --- Email B ---
    {email_b_body}
    --- END OF EMAIL B ---

    ### Your Task ###
    Evaluate both emails based on the following criteria and call the `Evaluation` function with your results.
    1.  **Personalization:** How well is the email tailored to the specific lead? Does it reference their role, company, or industry in a meaningful way? (Score 1-10)
    2.  **Persuasiveness:** How compelling is the message? Does it clearly articulate a value proposition and have a strong call-to-action? (Score 1-10)
    3.  **Overall Preference:** Based on your analysis, which email is more likely to get a positive response?
    """
    
    try:
        model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7, api_key=GOOGLE_API_KEY)
        llm = model.with_structured_output(Evaluation)
        response = llm.invoke(judge_prompt)
        
        # with_structured_output already returns a Pydantic model directly
        return response

    except Exception as e:
        logging.error(f"LLM-as-a-Judge (Google) failed: {e}")
        return None

def load_dataset(filepath: str) -> List[Lead]:
    """Loads a subset of qualified leads for the experiment."""
    df = pd.read_csv(filepath)
    qualified_leads_df = df[df['qualification_status'] == 'QUALIFIED'].head(30)
    
    leads = []
    for idx, row in qualified_leads_df.iterrows():
        leads.append(Lead(lead_id=str(idx), raw_data=row.to_dict(), status="qualified", score=row.get('score')))
    return leads

if __name__ == "__main__":
    DATASET_PATH = os.path.join(PROJECT_ROOT, "data", "qualified_leads_data.csv")
    qualified_leads = load_dataset(DATASET_PATH)
    print(f"Loaded {len(qualified_leads)} qualified leads for evaluation.")

    evaluation_data = []
    
    for lead in tqdm(qualified_leads, desc="Generating and Judging Emails"):
        
        # --- Run Config A (Baseline: Single Message) ---
        email_a_components = generate_email_in_script(lead, prompt_strategy="single_message")
        
        # --- Run Config B (Standard: Multi-Message) ---
        email_b_components = generate_email_in_script(lead, prompt_strategy="multi_message")
        
        # --- Run the Judge ---
        if email_a_components and email_b_components:
            # Email A = Single Message, Email B = Multi-Message
            evaluation = evaluate_emails_with_llm_judge(
                lead=lead.raw_data,
                email_a_body=email_a_components.email_body,
                email_b_body=email_b_components.email_body
            )
            
            if evaluation:
                evaluation_data.append(evaluation.model_dump())
            else:
                logging.warning(f"Failed to get evaluation for lead: {lead.lead_id}")
        else:
            logging.warning(f"Failed to generate emails for lead: {lead.lead_id}")

    # --- 4. Compile and print the final report (No changes here) ---
    if not evaluation_data:
        print("\nNo evaluations were generated. Please check your logs for errors.")
        sys.exit(0)
    
    results_df = pd.DataFrame(evaluation_data)

    print("\n" + "="*70)
    print("      LLM-as-a-Judge Report: Prompt Structure Evaluation")
    print("="*70)
    
    preference_counts = results_df['preference'].value_counts()
    print("\n### Head-to-Head Preference ###")
    print("Note: 'Email A' used a single combined prompt. 'Email B' used separate System/Human prompts.")
    print(preference_counts)
    print("\nPercentage Breakdown:")
    print((preference_counts / len(results_df) * 100).round(1).astype(str) + '%')

    avg_scores = results_df[[
        'score_a_personalization', 'score_b_personalization',
        'score_a_persuasiveness', 'score_b_persuasiveness'
    ]].mean()
    print("\n### Average Numerical Scores (out of 10) ###")
    print(f"Personalization (Baseline):     {avg_scores['score_a_personalization']:.2f}")
    print(f"Personalization (Enriched):     {avg_scores['score_b_personalization']:.2f}")
    print("-" * 30)
    print(f"Persuasiveness (Baseline):    {avg_scores['score_a_persuasiveness']:.2f}")
    print(f"Persuasiveness (Enriched):    {avg_scores['score_b_persuasiveness']:.2f}")
    print("\n" + "="*50)