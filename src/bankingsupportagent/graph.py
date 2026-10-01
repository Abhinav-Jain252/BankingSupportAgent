from langchain.messages import AIMessage
from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.memory import InMemorySaver

from bankingsupportagent.agents.faq import faq_agent
from bankingsupportagent.state import SupportState
from bankingsupportagent.agents.router import router_node

# Placeholder agents (we replace them in the later steps)
def account_agent(state:SupportState):
    return {"messages":[AIMessage("[Account Agent] I will look up your balance and transactions.")]}

def card_agent(state:SupportState):
    return {"messages":[AIMessage("[Card Agent] I will help with blocking card and disputes.")]}

def escalation(state:SupportState):
    return {"messages":[AIMessage("[Escalation] Connecting you to a human specialist.")]}


# Decides which node runs after the router
def pick_agent(state:SupportState) -> str:
    return state["route"]


def build_graph():
    builder = StateGraph(SupportState)

    #Nodes
    builder.add_node("router",router_node)
    builder.add_node("faq_agent",faq_agent)
    builder.add_node("account_agent",account_agent)
    builder.add_node("card_agent",card_agent)
    builder.add_node("escalation",escalation)

    #Edges
    builder.add_edge(START,"router")
    builder.add_conditional_edges(
        "router",
        pick_agent,
        {
            "faq": "faq_agent",
            "account": "account_agent",
            "card": "card_agent",
            "escalate": "escalation",
        },
    )

    for node in ["faq_agent","account_agent","card_agent","escalation"]:
        builder.add_edge(node,END)

    return builder.compile(checkpointer=InMemorySaver())