from functools import lru_cache
from langchain_chroma import Chroma
from bankingsupportagent.config import CHROMA_DIR, COLLECTION_NAME, get_embeddings

TOP_K = 4           # How many chunks to return per question

@lru_cache
def get_vector_store():
    """Open the chroma db once and reuse it later"""
    return Chroma(
        collection_name = COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )


def retrieve(query: str, k:int=TOP_K):
    """Return the K chunks most similar in meaning to the query"""
    return get_vector_store().similarity_search(query,k=k)

def format_docs(docs) -> str:
    """Join chunks into one text block, even labelled with its source and page"""
    return "\n\n".join(
        f"[Source: {d.metadata['source']}, page {d.metadata['page']}]\n{d.page_content}"
        for d in docs
    )