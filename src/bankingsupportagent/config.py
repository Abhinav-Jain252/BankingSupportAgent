import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings


load_dotenv()

MODEL_NAME = os.getenv("GROQ_MODEL","groq:openai")

def get_llm(temperature: float = 0):
    """Return the chat model used by every agent in the project"""
    if not os.getenv("GROQ_API_KEY"):
        raise ValueError("GROQ_API_KEY not found. Add it to your .env file...")
    return init_chat_model(MODEL_NAME,temperature=temperature)


# RAG
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = PROJECT_ROOT/"data"/"docs"
CHROMA_DIR = PROJECT_ROOT/"data"/"chroma_db"
COLLECTION_NAME = "bank_docs"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DB_PATH = PROJECT_ROOT/"data"/"bank.db"

def get_embeddings():
    """Return the embedding model used for both indexing and searching"""
    return HuggingFaceEmbeddings(model_name = EMBEDDING_MODEL)