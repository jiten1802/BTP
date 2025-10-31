from asyncio import SendfileNotAvailableError
from app.models.state import AgenticState, Lead
from pydantic import BaseModel, Field
from typing import Dict, Literal
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
from app.models.prompts import STRATEGIST_SYSTEM_PROMPT, STRATEGIST_HUMAN_PROMPT_TEMPLATE
from app.utils import update_performance_metrics, rate_limited_call
from app.database import create_connection, create_table, publish_lead
import yaml
from pathlib import Path
import os

load_dotenv()
api_key = os.getenv("GROQ_API_KEY_1")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in environment variables")

class PersonalizedMessage(BaseModel):
    subject_line: str = Field(description="Compelling email subject line (max 50 characters)")
    salutation: str = Field(description="The opening salutation, e.g., 'Dear Neha Chauhan,'")
    email_body: str = Field(description="The main paragraphs of the personalized email body (150-200 words). Do NOT include the salutation or closing.")
    signature: str = Field(description="The closing of the email, e.g., 'Best regards,' or 'Sincerely,'")
    tone: Literal["professional", "conversational", "executive", "friendly"] = Field(description="Tone of the email based on recipient's role")
    key_personalization_points: Dict[str, str] = Field(
        description="Key personalization elements used in the email",
        example={
            "company_mention": "Reference to their company",
            "role_insight": "Insight about their role",
            "industry_connection": "Industry-specific value proposition"
        }
    )
    call_to_action: str = Field(description="Clear call-to-action for the recipient")
    follow_up_suggestion: str = Field(description="Suggested follow-up strategy if no response")

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=1, api_key=api_key)
structured_llm = llm.with_structured_output(PersonalizedMessage)

@rate_limited_call(max_per_minute=5)
def call_llm(messages):
    if structured_llm is None:
        raise ValueError("LLM not initialized. Please set GEMINI_API_KEY environment variable.")
    return structured_llm.invoke(messages)

def load_sender_config():
    config_path = Path(__file__).parent.parent.parent / "configs" / "sender_configs.yaml"
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)
    
sender_config = load_sender_config()
SENDER_NAME = sender_config.get("name", "Your Name")
SENDER_TITLE = sender_config.get("title", "Your Title")

def generate_personalized_message(lead: Lead) -> PersonalizedMessage:
    """
    Generate a personalized outreach message for a qualified lead using LLM.
    """
    lead_data = f"""
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

    human_message = STRATEGIST_HUMAN_PROMPT_TEMPLATE.format(
        lead_data=lead_data,
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

    try:
        result = call_llm(messages)
        return result
    except Exception as e:
        print(f"Error generating personalized message for lead {lead.lead_id}: {str(e)}")
        # Return a fallback message
        fallback_message = PersonalizedMessage(
            subject_line="Quick question about your sales process",
            email_body=f"Hi {lead.raw_data.get('contact_person', 'there')},\n\nI noticed {lead.raw_data.get('company_name', 'your company')} is in the {lead.raw_data.get('industry', 'industry')} space. I'd love to share how we've helped similar companies improve their sales efficiency.\n\nWould you be open to a brief 15-minute conversation this week?\n\nBest regards,\n[Your Name]",
            tone="professional",
            key_personalization_points={
                "company_mention": lead.raw_data.get("company_name", "N/A"),
                "role_insight": f"Targeting {lead.raw_data.get('job_title', 'decision maker')}",
                "industry_connection": f"Industry: {lead.raw_data.get('industry', 'N/A')}"
            },
            call_to_action="Schedule a 15-minute conversation",
            follow_up_suggestion="Follow up in 3-5 days with additional value proposition"
        )
        return fallback_message

def process_single_lead_message(lead: Lead, db_conn) -> Lead:
    """
    Process a single qualified lead to generate personalized message.
    """
    if not lead.qualified_lead:
        print(f"Lead {lead.lead_id} is not qualified, skipping message generation")
        return lead

    personalized_message = generate_personalized_message(lead)
    
    final_email_html = f"""
    <p>{personalized_message.salutation}</p>
    
    <p>{personalized_message.email_body.replace(chr(10), '<br>')}</p>
    
    <p>{personalized_message.call_to_action}</p>
    
    <p>{personalized_message.signature}<br>
    <b>{SENDER_NAME}</b><br>
    <i>{SENDER_TITLE}</i></p>
    """

    # Update the lead with the personalized message
    lead.personalized_message = final_email_html
    
    # Add to communication history
    if lead.communication_history is None:
        lead.communication_history = []
    
    communication_entry = {
        "type": "outreach_email",
        "subject": personalized_message.subject_line,
        "message": final_email_html,
        "tone": personalized_message.tone,
        "personalization_points": personalized_message.key_personalization_points,
        "call_to_action": personalized_message.call_to_action,
        "follow_up_suggestion": personalized_message.follow_up_suggestion,
        "timestamp": "generated"
    }
    
    lead.communication_history.append(communication_entry)
    lead.status = "message_generated"

    try:
        publish_lead(db_conn, lead)
    except Exception as e:
        print(f"Error publishing lead {lead.lead_id} to database: {str(e)}")
    
    return lead

def Strategist(state: AgenticState) -> AgenticState:
    """
    Generate personalized outreach messages for qualified leads.
    """
    # Get leads that are qualified but don't have personalized messages yet
    qualified_leads = [lead for lead in state.lead 
                      if lead.qualified_lead and 
                      lead.status == "scored" and 
                      lead.personalized_message is None]

    if not qualified_leads:
        print("No qualified leads ready for message generation")
        return state

    print(f"Generating personalized messages for {len(qualified_leads)} qualified leads...")

    db_conn = create_connection()
    if not db_conn:
        print("Could not connect to the database. Aborting strategist run.")
        return state
    # Ensure table exists before inserting
    try:
        create_table(db_conn)
    except Exception as e:
        print(f"Failed to ensure table exists: {str(e)}")
        db_conn.close()
        return state

    processed_count = 0
    message_generated_count = 0

    for lead in qualified_leads:
        try:
            processed_lead = process_single_lead_message(lead, db_conn)
            processed_count += 1
            
            if processed_lead.personalized_message:
                message_generated_count += 1
            
            if processed_count % 10 == 0:
                print(f"Generated messages for {processed_count}/{len(qualified_leads)} leads...")
            
        except Exception as e:
            print(f"Error generating message for lead {lead.lead_id}: {str(e)}")
            lead.status = "message_generation_failed"

    if db_conn:
        db_conn.close()

    update_performance_metrics(state, "messages_generated", message_generated_count)
    update_performance_metrics(state, "strategist_processed", processed_count)

    print(f"Strategist: Completed generating {message_generated_count} personalized messages")
    print(f"Strategist: Processed {processed_count} qualified leads")
    
    return state
