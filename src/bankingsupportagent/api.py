from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field
from langgraph.types import Command

from bankingsupportagent.graph import build_graph

STATIC_DIR = Path(__file__).parent/"static"

app = FastAPI(
    title = "SecureBank Support Agent",
    description="Multi-agent banking support assistant built with Langgraph",
    version="1.0.0",
)
graph = build_graph()


# Request and response shapes

class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100, description="One ID per conversation")
    message: str = Field(min_length=1,max_length=2000,description="The customer's message")
    customer_id: str | None = Field(
        default=None,
        description="Logged in customer. DEMO ONLY: a real app takes this from the login token, never from the request body"
    )


class ConfirmRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100)
    approved: bool


class ChatResponse(BaseModel):
    status: Literal["ok","needs_confirmation"]
    reply: str
    route: str | None = None



# Helpers
def config_for(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def to_response(result:dict) -> ChatResponse:
    """Turn the graphs final state into what the app need to show"""
    if "__interrupt__" in result:
        question = result["__interrupt__"][0].value["message"]
        return ChatResponse(status="needs_confirmation",reply=question, route=result.get("route"))
    return ChatResponse(status="ok",reply=result["messages"][-1].content, route = result.get("route"))


def run_graph(graph_input, thread_id:str) -> ChatResponse:
    try:
        result = graph.invoke(graph_input,config=config_for(thread_id))
    except Exception:
        # Never show internal errors to the users
        raise HTTPException(status_code=503, detail="The assistant is temporarily unavailable. Please try again.")
    return to_response(result)


def is_waiting_for_confirmation(thread_id:str) -> bool:
    return bool(graph.get_state(config_for(thread_id)).next)



# Endpoints
@app.get("/health")
def health():
    return {"status":"ok"}


@app.post("/chat",response_model=ChatResponse)
def chat(request: ChatRequest):
    if is_waiting_for_confirmation(request.thread_id):
        raise HTTPException(status_code=409, detail="Please answer the pending confirmation first.")
    graph_input = {"messages": request.message}
    if request.customer_id:
        graph_input["customer_id"] = request.customer_id
    return run_graph(graph_input, request.thread_id)


@app.post("/confirm", response_model=ChatResponse)
def confirm(request: ConfirmRequest):
    if not is_waiting_for_confirmation(request.thread_id):
        raise HTTPException(status_code=409, detail="There is nothing to confirm in this conversation.")
    return run_graph(Command(resume={"approved": request.approved}), request.thread_id)


@app.get("/")
def chat_page():
    return FileResponse(STATIC_DIR / "index.html")