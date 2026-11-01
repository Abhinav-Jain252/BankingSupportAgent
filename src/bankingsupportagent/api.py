import logging
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Literal

import groq
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from langchain.messages import HumanMessage
from pydantic import BaseModel, Field
from langgraph.types import Command

from bankingsupportagent.graph import build_graph
from bankingsupportagent.tools.account_tools import get_connection
from bankingsupportagent.rag.retriever import get_vector_store

from bankingsupportagent.auth import authenticate, create_access_token, private_key, public_key
from bankingsupportagent.config import ACCESS_TOKEN_MINUTES


logger = logging.getLogger("securebank.api")
STATIC_DIR = Path(__file__).parent/"static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once, when the server starts
    app.state.graph = build_graph()
    get_vector_store()
    private_key()
    public_key()
    yield
    # Runs once, when the server stops (nothing to clean up yet)


app = FastAPI(
    title="SecureBank Support API",
    description="Multi-support banking support assistant built with langgraph",
    version="2.0.0",
    lifespan=lifespan
)



def error_response(status_code:int, detail:str, headers:dict|None=None) -> JSONResponse:
    """Same shape as FastAPI's own errors"""
    return JSONResponse(status_code=status_code, content={"detail":detail},headers=headers)


@app.exception_handler(groq.APITimeoutError)
async def llm_timeout(request: Request, exc: groq.APITimeoutError):
    logger.warning("LLM timed out on %s", request.url.path)
    return error_response(504, "The assistant took too long to answer. Please try again.")


@app.exception_handler(groq.RateLimitError)
async def llm_rate_limited(request: Request, exc: groq.RateLimitError):
    logger.warning("LLM rate limit hit on %s", request.url.path)
    return error_response(503, "The assistant is busy right now. Please try again shortly.",
                          headers={"Retry-After": "30"})


@app.exception_handler(groq.APIConnectionError)
async def llm_unreachable(request: Request, exc: groq.APIConnectionError):
    logger.error("Could not reach the LLM on %s", request.url.path)
    return error_response(502, "The assistant is temporarily unavailable. Please try again.")


@app.exception_handler(groq.APIStatusError)
async def llm_bad_response(request: Request, exc: groq.APIStatusError):
    logger.error("LLM returned HTTP %s on %s", exc.status_code, request.url.path)
    return error_response(502, "The assistant is temporarily unavailable. Please try again.")


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.exception("Unexpected error on %s", request.url.path)
    return error_response(500, "Something went wrong on our side. Please try again.")


# Request Model

class LoginRequest(BaseModel):
    customer_id: str = Field(min_length=1,max_length=20)
    password: str = Field(min_length=1,max_length=64)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Seconds until the token expires")

class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100, description="One ID per conversation")
    message: str = Field(min_length=1,max_length=100, description="The customer's message")
    customer_id: str | None = Field(default=None, description="TEMP, this comes from login token instead")


# Response Model
class ChatResponse(BaseModel):
    status: Literal["ok","needs_confirmation"]
    reply: str
    route: str | None = None


class ApproveRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100, description="The conversation that is waiting")
    approved: bool = Field(description="true = go ahead, false = cancel")

# Helpers
def config_for(thread_id: str) -> dict:
    """Langgraph config: which saved conversation to load"""
    return {"configurable": {"thread_id": thread_id}}


def is_waiting_for_confirmation(graph, thread_id: str) -> bool:
    """True if this conversation is paused at an interrupt()."""
    return bool(graph.get_state(config_for(thread_id)).interrupts)


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


@app.post("/login",response_model=TokenResponse)
def login(body: LoginRequest):
    if not authenticate(body.customer_id,body.password):
        # Same message for "no such customer" and "wrong password": don't reveal which IDs exist
        raise HTTPException(status_code=401, detail="Incorrect customer ID or password.")
    return TokenResponse(
        access_token=create_access_token(body.customer_id),
        expires_in=ACCESS_TOKEN_MINUTES*60,
    )


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


@app.post("/approve",response_model=ChatResponse)
def approve(body: ApproveRequest):
    graph = app.state.graph

    if not is_waiting_for_confirmation(graph, body.thread_id):
        raise HTTPException(status_code=409, detail="There is nothing to approve in this conversation.")

    result = graph.invoke(Command(resume={"approved": body.approved}), config=config_for(body.thread_id))
    return to_response(result)


@app.get("/",include_in_schema=False)
def chat_page():
    """Serve the chat web page"""
    return FileResponse(STATIC_DIR/"index.html")