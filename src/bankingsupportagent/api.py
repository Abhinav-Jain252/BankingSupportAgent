from contextlib import asynccontextmanager, closing
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from langchain.messages import HumanMessage
from pydantic import BaseModel, Field

from bankingsupportagent.graph import build_graph
from bankingsupportagent.tools.account_tools import get_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once, when the server starts
    app.state.graph = build_graph()
    yield
    # Runs once, when the server stops (nothing to clean up yet)


app = FastAPI(
    title="SecureBank Support API",
    description="Multi-support banking support assistant built with langgraph",
    version="2.0.0",
    lifespan=lifespan
)


# Request Model
class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100, description="One ID per conversation")
    message: str = Field(min_length=1,max_length=100, description="The customer's message")
    customer_id: str | None = Field(default=None, description="TEMP, this comes from login token instead")


# Response Model
class ChatResponse(BaseModel):
    status: Literal["ok","needs_confirmation"]
    reply: str
    route: str | None = None


# Helpers
def config_for(thread_id: str) -> dict:
    """Langgraph config: which saved conversation to load"""
    return {"configurable": {"thread_id": thread_id}}


def is_waiting_for_confirmation(graph, thread_id:str) -> bool:
    """True if this conversation is paused at an interrupt"""
    return bool(graph.get_state(config_for(thread_id)).next)


def to_response(result:dict) -> ChatResponse:
    """Turn the graphs final state to what the app shows"""
    if "__interrupt__" in result:
        question = result["__interrupt__"][0].value["message"]
        return ChatResponse(status="needs_confirmation",reply=question, route=result.get("route"))
    return ChatResponse(status="ok",reply=result["messages"][-1].content, route=result.get("route"))



def database_ok() -> bool:
    """True if the bank database exists and has been seeded"""
    try:
        with closing(get_connection()) as conn:
            conn.execute("Select 1 FROM customers LIMIT 1")
        return True
    except Exception:
        return False


@app.get("/health")
def health():
    """Liveness: the server process is running and can answer"""
    return {"status":"ok"}


@app.get("/ready")
def ready():
    """Readiness: Everything a chat request needs is available."""
    checks = {
        "graph": hasattr(app.state,"graph"),
        "database": database_ok(),
    }
    if all(checks.values()):
        return {"status":"ready","checks":checks}
    return JSONResponse(status_code=503,content={"status":"not_ready","checks":checks})



@app.post("/chat",response_model=ChatResponse)
def chat(body: ChatRequest):
    graph = app.state.graph


    if is_waiting_for_confirmation(graph, body.thread_id):
        raise HTTPException(status_code=409, detail="Please answer the pending confirmation first.")

    # Build the graph input and run it
    graph_input = {"messages": [HumanMessage(body.message)]}
    if body.customer_id:
        graph_input["customer_id"] = body.customer_id

    result = graph.invoke(graph_input, config=config_for(body.thread_id))
    return to_response(result)