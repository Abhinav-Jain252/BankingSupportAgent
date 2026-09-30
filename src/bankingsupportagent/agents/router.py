from typing import Literal
from pydantic import BaseModel, Field
from langchain.messages import SystemMessage, HumanMessage
from bankingsupportagent.config import get_llm


class RouteDecision(BaseModel):
    route: Literal["faq","account","card","escalate"] = Field(
        description="which team should handle the customer's message"
    )
    reason: str = Field(description="One short sentence explaining why this route was chosen")


ROUTER_PROMPT = """You are the routing assistant for SecureBank customer support.
Read the customer's message and choose exactly one route:

-faq: general questions about bank products, fees, interest rates, documents, branch timings or policies. No personal account
data is needed.
-account: questions about the customer's own account, such as balance, recent transactions or statements
-card: debit/credit card issues, such as a lost or stolen card, blocking a card, card limits, or a charge the customer does
not recognize
-escalate: anything that needs a human, such as suspected fraud, a hacked account, complaints, legal issues, or when the customer
asks for a human.

If a message fits more than one route, choose the more serious one (escalate>card>account>faq)."""


def route_query(query:str) -> RouteDecision:
    llm = get_llm()
    router = llm.with_structured_output(RouteDecision)
    return router.invoke([SystemMessage(ROUTER_PROMPT),HumanMessage(query)])