from models.state import AgenticState, Lead
from typing import List, Dict, Any
import pandas as pd
from pathlib import Path

df = pd.read_csv("data/leads.csv")

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