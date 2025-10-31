from app.agents.prospector import Prospector
from app.agents.strategist import Strategist
from app.agents.communicator import Communicator
from app.agents.interpreter import Interpreter
from app.agents.scheduler import Scheduler
from app.agents.record_keeper import RecordKeeper
from fastapi import FastAPI
from app.database import initialize_database
from app.models.state import AgenticState
from app.initialize import initialize_state
from langgraph.graph import StateGraph, END, START
from typing import Literal

initialize_database()
global_state = initialize_state()

graph = StateGraph(AgenticState)

graph.add_node("Prospector", Prospector)
graph.add_node("Strategist", Strategist)
graph.add_node("Communicator", Communicator)
graph.add_node("Interpreter", Interpreter)
graph.add_node("Scheduler", Scheduler)
graph.add_node("RecordKeeper", RecordKeeper)

graph.add_edge(START, "Prospector")
graph.add_edge("Prospector", "Strategist")
graph.add_edge("Strategist", "Communicator")
graph.add_edge("Communicator", END)

app_graph = graph.compile()

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Marketing.ai Agentic System"}

@app.get("/state")
async def get_state():
    """Fetch the current Agentic state (for debugging/monitoring)."""
    return global_state 

@app.post("/run_workflow")
async def run_workflow():
    """Run the full workflow."""
    global global_state

    for s in app_graph.stream(global_state):
        final_state = s

    global_state = final_state

    # Safely access performance metrics whether it's an object with attr or a dict
    metrics = getattr(global_state, 'performance_metrics', None)
    if isinstance(metrics, dict):
        processed = metrics.get("processed_leads", 0)
        qualified = metrics.get("qualified_leads", 0)
        messages = metrics.get("messages_generated", 0)
    else:
        processed = getattr(metrics, 'get', lambda k, d=0: d)("processed_leads", 0) if metrics else 0
        qualified = getattr(metrics, 'get', lambda k, d=0: d)("qualified_leads", 0) if metrics else 0
        messages = getattr(metrics, 'get', lambda k, d=0: d)("messages_generated", 0) if metrics else 0

    return {
        "message": "Full workflow completed",
        "processed_leads": processed,
        "qualified_leads": qualified,
        "messages_generated": messages
    }

@app.post("/prospector/run")
async def run_prospector():
    """
    Run ONLY the Prospector agent on the current state.
    """
    global global_state

    updated_state = app_graph.nodes['Prospector'].invoke(global_state)
    global_state = updated_state
    
    metrics = getattr(global_state, 'performance_metrics', None)
    if isinstance(metrics, dict):
        processed = metrics.get("processed_leads", 0)
        qualified = metrics.get("qualified_leads", 0)
    else:
        processed = getattr(metrics, 'get', lambda k, d=0: d)("processed_leads", 0) if metrics else 0
        qualified = getattr(metrics, 'get', lambda k, d=0: d)("qualified_leads", 0) if metrics else 0

    return {
        "message": "Prospector run completed",
        "processed_leads": processed,
        "qualified_leads": qualified,
    }

@app.post("/strategist/run")
async def run_strategist():
    """
    Run ONLY the Strategist agent on the current state.
    """
    global global_state

    updated_state = app_graph.nodes['Strategist'].invoke(global_state)
    global_state = updated_state
    
    metrics = getattr(global_state, 'performance_metrics', None)
    if isinstance(metrics, dict):
        messages = metrics.get("messages_generated", 0)
        strategist_processed = metrics.get("strategist_processed", 0)
    else:
        messages = getattr(metrics, 'get', lambda k, d=0: d)("messages_generated", 0) if metrics else 0
        strategist_processed = getattr(metrics, 'get', lambda k, d=0: d)("strategist_processed", 0) if metrics else 0

    return {
        "message": "Strategist run completed",
        "messages_generated": messages,
        "strategist_processed": strategist_processed,
    }
@app.post("/communicator/run")
async def run_communicator():
    """
    Run ONLY the Communicator agent on the current state.
    """
    global global_state

    updated_state = app_graph.nodes['Communicator'].invoke(global_state)
    global_state = updated_state
    
    metrics = getattr(global_state, 'performance_metrics', None)
    if isinstance(metrics, dict):
        emails_sent = metrics.get("emails_sent", 0)
    else:
        emails_sent = getattr(metrics, 'get', lambda k, d=0: d)("emails_sent", 0) if metrics else 0

    return {
        "message": "Communicator run completed",
        "emails_sent": emails_sent,
    }

@app.post("/interpreter/run")
async def run_interpreter():
    """
    Run ONLY the Interpreter agent on the current state.
    """
    global global_state
    global_state = app_graph.nodes['Interpreter'].invoke(global_state)
    metrics = getattr(global_state, 'performance_metrics', None)
    return {
        "message": "Interpreter run completed",
        "metrics": metrics if isinstance(metrics, dict) else (metrics.__dict__ if metrics else {}),
    }
