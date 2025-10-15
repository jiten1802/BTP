from app.agents.prospector import Prospector
from app.agents.strategist import Strategist
from app.agents.communicator import Communicator
from app.agents.interpreter import Interpreter
from app.agents.scheduler import Scheduler
from app.agents.record_keeper import RecordKeeper
from fastapi import FastAPI
from app.models.state import AgenticState
from app.initialize import initialize_state
from langgraph.graph import StateGraph, END, START
from typing import Literal

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

    return {
        "message": "Full workflow completed",
        "processed_leads": global_state.performance_metrics.get("processed_leads", 0),
        "qualified_leads": global_state.performance_metrics.get("qualified_leads", 0),
        "messages_generated": global_state.performance_metrics.get("messages_generated", 0)
    }

@app.post("/prospector/run")
async def run_prospector():
    """
    Run ONLY the Prospector agent on the current state.
    """
    global global_state

    updated_state = app_graph.nodes['prospector'].invoke(global_state)
    global_state = updated_state
    
    return {
        "message": "Prospector run completed",
        "processed_leads": global_state.performance_metrics.get("processed_leads", 0),
        "qualified_leads": global_state.performance_metrics.get("qualified_leads", 0),
    }

@app.post("/strategist/run")
async def run_strategist():
    """
    Run ONLY the Strategist agent on the current state.
    """
    global global_state

    updated_state = app_graph.nodes['strategist'].invoke(global_state)
    global_state = updated_state
    
    return {
        "message": "Strategist run completed",
        "messages_generated": global_state.performance_metrics.get("messages_generated", 0),
        "strategist_processed": global_state.performance_metrics.get("strategist_processed", 0),
    }
@app.post("communicator/run")
async def run_communicator():
    """
    Run ONLY the Communicator agent on the current state.
    """
    global global_state

    updated_state = app_graph.nodes['communicator'].invoke(global_state)
    global_state = updated_state
    
    return {
        "message": "Communicator run completed",
        "emails_sent": global_state.performance_metrics.get("emails_sent", 0),
    }

@app.post("/interpreter/run")
async def run_interpreter():
    """
    Run ONLY the Interpreter agent on the current state.
    """
    global global_state
    global_state = app_graph.nodes['interpreter'].invoke(global_state)
    return {
        "message": "Interpreter run completed",
        "metrics": global_state.performance_metrics
    }
    