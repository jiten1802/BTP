# test_prospector.py
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

def test_imports():
    """Test if all imports work correctly"""
    print("�� Testing imports...")
    
    try:
        from models.state import AgenticState, Lead
        print("✅ models.state imported successfully")
    except Exception as e:
        print(f"❌ Error importing models.state: {e}")
        return False
    
    try:
        from utils import get_leads_by_status, update_performance_metrics, get_workflow_summary
        print("✅ utils imported successfully")
    except Exception as e:
        print(f"❌ Error importing utils: {e}")
        return False
    
    try:
        from models.prompts import PROSPECTOR_SYSTEM_PROMPT, PROSPECTOR_HUMAN_PROMPT_TEMPLATE
        print("✅ models.prompts imported successfully")
    except Exception as e:
        print(f"❌ Error importing models.prompts: {e}")
        return False
    
    try:
        from agents.prospector import Prospector, score_lead, process_single_lead, LeadScore
        print("✅ agents.prospector imported successfully")
    except Exception as e:
        print(f"❌ Error importing agents.prospector: {e}")
        return False
    
    return True

def test_state_initialization():
    """Test if state can be initialized correctly"""
    print("\n🔍 Testing state initialization...")
    
    try:
        from models.state import AgenticState, Lead
        
        # Create a test lead
        test_lead = Lead(
            lead_id="#test_1",
            raw_data={
                "company_name": "TestCorp",
                "industry": "Software as a Service (SaaS)",
                "employee_count": 500,
                "location": "United States",
                "contact_person": "John Doe",
                "job_title": "VP of Sales",
                "email": "john@testcorp.com"
            },
            status="new",
            qualified_lead=False,
            score=None,
            contacts=None,
            personalized_message=None,
            communication_history=[],
            intent=None,
            meeting_details=None
        )
        
        # Create test state
        test_state = AgenticState(
            lead=[test_lead],
            performance_metrics={
                "total_leads": 1,
                "processed_leads": 0,
                "qualified_leads": 0,
                "meetings_booked": 0,
                "not_interested": 0,
                "wrong_person": 0
            },
            optimization_insights=None
        )
        
        print("✅ State initialization successful")
        return test_state
        
    except Exception as e:
        print(f"❌ Error initializing state: {e}")
        return None

def test_single_lead_scoring():
    """Test scoring a single lead"""
    print("\n🔍 Testing single lead scoring...")
    
    try:
        from agents.prospector import score_lead
        
        test_lead_data = {
            "company_name": "TechCorp",
            "industry": "Software as a Service (SaaS)",
            "employee_count": 500,
            "location": "United States",
            "contact_person": "Jane Smith",
            "job_title": "VP of Sales",
            "email": "jane@techcorp.com"
        }
        
        result = score_lead(test_lead_data)
        
        print(f"✅ Lead scored successfully:")
        print(f"   Score: {result.lead_score}")
        print(f"   Status: {result.qualification_status}")
        print(f"   Reasoning: {result.reasoning[:100]}...")
        
        return result
        
    except Exception as e:
        print(f"❌ Error scoring lead: {e}")
        return None

def test_single_lead_processing():
    """Test processing a single lead"""
    print("\n🔍 Testing single lead processing...")
    
    try:
        from models.state import Lead
        from agents.prospector import process_single_lead
        
        test_lead = Lead(
            lead_id="#test_2",
            raw_data={
                "company_name": "InnovateCorp",
                "industry": "Financial Technology",
                "employee_count": 750,
                "location": "Canada",
                "contact_person": "Mike Johnson",
                "job_title": "Head of Sales",
                "email": "mike@innovatecorp.com"
            },
            status="new",
            qualified_lead=False,
            score=None,
            contacts=None,
            personalized_message=None,
            communication_history=[],
            intent=None,
            meeting_details=None
        )
        
        processed_lead = process_single_lead(test_lead)
        
        print(f"✅ Lead processed successfully:")
        print(f"   Lead ID: {processed_lead.lead_id}")
        print(f"   Status: {processed_lead.status}")
        print(f"   Score: {processed_lead.score}")
        print(f"   Qualified: {processed_lead.qualified_lead}")
        print(f"   Contacts: {len(processed_lead.contacts) if processed_lead.contacts else 0}")
        
        return processed_lead
        
    except Exception as e:
        print(f"❌ Error processing lead: {e}")
        return None

def test_prospector_agent():
    """Test the full Prospector agent"""
    print("\n�� Testing Prospector agent...")
    
    try:
        from agents.prospector import Prospector
        from utils import get_workflow_summary
        
        # Create test state with multiple leads
        test_state = test_state_initialization()
        if not test_state:
            return None
        
        # Add a few more test leads
        from models.state import Lead
        
        additional_leads = [
            Lead(
                lead_id="#test_3",
                raw_data={
                    "company_name": "StartupCorp",
                    "industry": "E-commerce",
                    "employee_count": 150,
                    "location": "United Kingdom",
                    "contact_person": "Sarah Wilson",
                    "job_title": "Sales Director",
                    "email": "sarah@startupcorp.com"
                },
                status="new",
                qualified_lead=False,
                score=None,
                contacts=None,
                personalized_message=None,
                communication_history=[],
                intent=None,
                meeting_details=None
            ),
            Lead(
                lead_id="#test_4",
                raw_data={
                    "company_name": "BigCorp",
                    "industry": "Manufacturing",
                    "employee_count": 50,
                    "location": "Germany",
                    "contact_person": "Tom Brown",
                    "job_title": "Intern",
                    "email": "tom@bigcorp.com"
                },
                status="new",
                qualified_lead=False,
                score=None,
                contacts=None,
                personalized_message=None,
                communication_history=[],
                intent=None,
                meeting_details=None
            )
        ]
        
        test_state.lead.extend(additional_leads)
        test_state.performance_metrics["total_leads"] = len(test_state.lead)
        
        print(f"📊 Initial state: {len(test_state.lead)} leads")
        
        # Run the Prospector
        result_state = Prospector(test_state)
        
        # Get summary
        summary = get_workflow_summary(result_state)
        
        print(f"✅ Prospector completed successfully:")
        print(f"   Total leads: {summary['total_leads']}")
        print(f"   Processed leads: {summary['performance_metrics'].get('processed_leads', 0)}")
        print(f"   Qualified leads: {summary['performance_metrics'].get('qualified_leads', 0)}")
        print(f"   Status breakdown: {summary['status_breakdown']}")
        
        # Show sample results
        scored_leads = [lead for lead in result_state.lead if lead.status == "scored"]
        print(f"\n�� Sample Results:")
        for lead in scored_leads[:3]:
            print(f"   - {lead.lead_id}: Score={lead.score}, Qualified={lead.qualified_lead}")
        
        return result_state
        
    except Exception as e:
        print(f"❌ Error running Prospector: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_with_real_data():
    """Test with real data from CSV (if available)"""
    print("\n🔍 Testing with real data...")
    
    try:
        import pandas as pd
        
        # Check if CSV exists
        csv_path = "data/leads.csv"
        if not os.path.exists(csv_path):
            print(f"⚠️ CSV file not found at {csv_path}")
            return None
        
        # Read first 5 rows for testing
        df = pd.read_csv(csv_path)
        print(f"📊 Found {len(df)} leads in CSV, testing with first 5...")
        
        from models.state import AgenticState, Lead
        
        test_leads = []
        for idx, row in df.head(5).iterrows():
            lead = Lead(
                lead_id=f"#real_{idx}",
                raw_data=row.to_dict(),
                status="new",
                qualified_lead=False,
                score=None,
                contacts=None,
                personalized_message=None,
                communication_history=[],
                intent=None,
                meeting_details=None
            )
            test_leads.append(lead)
        
        test_state = AgenticState(
            lead=test_leads,
            performance_metrics={
                "total_leads": len(test_leads),
                "processed_leads": 0,
                "qualified_leads": 0,
                "meetings_booked": 0,
                "not_interested": 0,
                "wrong_person": 0
            },
            optimization_insights=None
        )
        
        from agents.prospector import Prospector
        result_state = Prospector(test_state)
        
        from utils import get_workflow_summary
        summary = get_workflow_summary(result_state)
        
        print(f"✅ Real data test completed:")
        print(f"   Processed: {summary['performance_metrics'].get('processed_leads', 0)}")
        print(f"   Qualified: {summary['performance_metrics'].get('qualified_leads', 0)}")
        
        return result_state
        
    except Exception as e:
        print(f"❌ Error testing with real data: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Run all tests"""
    print("🚀 Starting Prospector Tests...\n")
    
    # Test 1: Imports
    if not test_imports():
        print("\n❌ Import tests failed. Please fix import issues first.")
        return
    
    # Test 2: State initialization
    test_state = test_state_initialization()
    if not test_state:
        print("\n❌ State initialization failed.")
        return
    
    # Test 3: Single lead scoring
    scoring_result = test_single_lead_scoring()
    if not scoring_result:
        print("\n❌ Single lead scoring failed.")
        return
    
    # Test 4: Single lead processing
    processed_lead = test_single_lead_processing()
    if not processed_lead:
        print("\n❌ Single lead processing failed.")
        return
    
    # Test 5: Full Prospector agent
    prospector_result = test_prospector_agent()
    if not prospector_result:
        print("\n❌ Prospector agent test failed.")
        return
    
    # Test 6: Real data (optional)
    real_data_result = test_with_real_data()
    
    print("\n🎉 All tests completed!")
    print("\n📋 Test Summary:")
    print("✅ Imports: PASSED")
    print("✅ State initialization: PASSED")
    print("✅ Single lead scoring: PASSED")
    print("✅ Single lead processing: PASSED")
    print("✅ Prospector agent: PASSED")
    if real_data_result:
        print("✅ Real data test: PASSED")
    else:
        print("⚠️ Real data test: SKIPPED/FAILED")

if __name__ == "__main__":
    main()