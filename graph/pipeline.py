from langgraph.graph import StateGraph, END
from schemas.state import FulfillmentState

from agents.normalization_agent import normalization_node
from agents.risk_agent import risk_node
from agents.routing_agent import routing_node
from agents.notification_agent import notification_node

def build_graph():

    builder = StateGraph(FulfillmentState)

    # Add nodes (agents)
    builder.add_node("normalize", normalization_node)
    builder.add_node("risk", risk_node)
    builder.add_node("route", routing_node)
    builder.add_node("notify", notification_node)
    
    # Define entry point
    builder.set_entry_point("normalize")

    # Define flow
    builder.add_edge("normalize", "risk")
    builder.add_edge("risk", "route")
    builder.add_edge("route", "notify")
    builder.add_edge("notify", END)

    # Compile graph
    return builder.compile()