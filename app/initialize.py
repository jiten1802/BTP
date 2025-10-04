from app.models.state import AgenticState, Lead
from typing import List, Dict, Any
import pandas as pd
from pathlib import Path
import os

def initialize_state() -> AgenticState:
    """
    Initialize the agentic state by loading leads from CSV file.
    
    Returns:
        AgenticState: Initialized state with leads loaded from CSV
    """
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    csv_path = project_root / "data" / "leads.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found at {csv_path}")

    df = pd.read_csv(csv_path)

    leads = []
    for idx, row in df.iterrows():
        lead_data = row.to_dict()

        lead = Lead(
            lead_id=f"#{idx}",
            raw_data=lead_data,
            status="new",
            qualified_lead=False,
            score=None,
            contacts=None,
            personalized_message=None,
            communication_history=[],
            intent=None,
            meeting_details=None
        )
        leads.append(lead)

    state = AgenticState(
        lead=leads,
        performance_metrics={
            "total_leads": len(leads),
            "processed_leads": 0,
            "qualified_leads": 0,
            "meetings_booked": 0,
            "not_interested": 0,
            "wrong_person": 0
        },
        optimization_insights=None
    )
    
    return state
