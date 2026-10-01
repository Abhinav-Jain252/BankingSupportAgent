from pathlib import Path

from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

from bankingsupportagent.config import DOCS_DIR,CHROMA_DIR,COLLECTION_NAME,get_embeddings

CHUNK_SIZE=200
CHUNK_OVERLAP=40

def word_count(text:str)->int:
    return len(text.split())


def load_pdfs():
    """Load every PDF in DOCS_DIR. Each page becomes one Document."""
    pages = []
    for path in sorted(DOCS_DIR.glob("*.pdf")):
        reader = PdfReader(path)
        for page_number, page in enumerate(reader.pages, start=1):
            pages.append(Document(
                page_content=page.extract_text(),
                metadata={"source": path.name, "page": page_number},
            ))
    return pages


def split_pages(pages):
    """Cut edges into overlapping chunks of about CHUNK_SIZE words."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size = CHUNK_SIZE,
        chunk_overlap = CHUNK_OVERLAP,
        length_function = word_count,
    )
    return splitter.split_documents(pages)


def build_vector_store():
    """Load, split, embed and save all chunks in Chroma (rebuilds from scratch)"""
    pages = load_pdfs()
    chunks = split_pages(pages)

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR)
    )
    vector_store.reset_collection()
    vector_store.add_documents(chunks)

    print(f"Loaded {len(pages)} pages -> {len(chunks)} chunks -> saved to {CHROMA_DIR}")


if __name__ == "__main__":
    build_vector_store()