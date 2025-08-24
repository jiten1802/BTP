from models.state import MarketingAgent
from langgraph.graph import START, END, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage

def lead_scorer(state: MarketingAgent) -> MarketingAgent:
    """
    A simple lead scoring function based on predefined criteria.
    """

