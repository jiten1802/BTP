from app.agents.prospector import Prospector
from app.agents.strategist import Strategist
from fastapi import FastAPI
from app.models.state import AgenticState
from app.initialize import initialize_state

app = FastAPI()

# Initialize the global state with leads from CSV
global_state = initialize_state()

@app.get("/")
async def root():
    return {"message": "Marketing.ai Agentic System"}

@app.get("/state")
async def get_state():
    """Fetch the current Agentic state (for debugging/monitoring)."""
    return global_state 

@app.post("/prospector/run")
async def run_prospector():
    """Run the Prospector agent on new leads."""
    global global_state
    global_state = Prospector(global_state)
    return {
        "message": "Prospector run completed",
        "processed_leads": global_state.performance_metrics.get("processed_leads", 0),
        "qualified_leads": global_state.performance_metrics.get("qualified_leads", 0),
    }

@app.post("/strategist/run")
async def run_strategist():
    """Run the Strategist agent to generate personalized messages for qualified leads."""
    global global_state
    global_state = Strategist(global_state)
    return {
        "message": "Strategist run completed",
        "messages_generated": global_state.performance_metrics.get("messages_generated", 0),
        "strategist_processed": global_state.performance_metrics.get("strategist_processed", 0),
    }


    