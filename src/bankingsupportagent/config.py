import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.chat_models import init_chat_model

load_dotenv()

MODEL_NAME = os.getenv("GROQ_MODEL","groq:openai")

def get_llm(temperature: float = 0):
    """Return the chat model used by every agent in the project"""
    if not os.getenv("GROQ_API_KEY"):
        raise ValueError("GROQ_API_KEY not found. Add it to your .env file...")
    return init_chat_model(MODEL_NAME,temperature=temperature)