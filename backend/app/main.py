
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID
import logging

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import config
from .ai import embed_texts, synthesize
from .ingestion import extract_pages, chunk_pages
from .storage import get_storage


# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("knowledge_assistant")

store = None


# --------------------------------------------------
# Application Lifecycle
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global store

    logger.info("Starting Atlas Knowledge Assistant")

    store = get_storage()

    logger.info("Database initialized")

    yield

    logger.info("Shutting down Atlas Knowledge Assistant")


# --------------------------------------------------
# FastAPI Application
# --------------------------------------------------

app = FastAPI(
    title="Knowledge Assistant API",
    description="AI-powered document chatbot with Gemini and RAG",
    version="0.1.0",
    lifespan=lifespan,
)


# --------------------------------------------------
# CORS Configuration
# --------------------------------------------------

# Explicitly allow local React development origins.
# Also include additional origins from config.py.

default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

allowed_origins = list(
    dict.fromkeys(
        origin.strip().rstrip("/")
        for origin in [
            *default_origins,
            *config.CORS_ORIGINS,
        ]
        if origin.strip()
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
)

logger.info("Allowed CORS origins: %s", allowed_origins)


# --------------------------------------------------
# Request Models
# --------------------------------------------------

class ChatRequest(BaseModel):
    question: str = Field(
        min_length=3,
        max_length=600
    )


# --------------------------------------------------
# Health Check
# --------------------------------------------------

@app.get("/api/health")
def health():

    return {
        "status": "ok",
        "mode": (
            "AI RAG"
            if config.API_KEY
            else "Offline keyword preview"
        ),
        "database": (
            "PostgreSQL / pgvector"
            if config.DATABASE_URL
            else "SQLite"
        ),
    }


# --------------------------------------------------
# List Uploaded Documents
# --------------------------------------------------

@app.get("/api/documents")
def documents():

    return {
        "documents": store.list()
    }


# --------------------------------------------------
# Delete Document
# --------------------------------------------------

@app.delete("/api/documents/{document_id}")
def delete_document(document_id: UUID):

    deleted = store.delete(str(document_id))

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    return {
        "deleted": True
    }


# --------------------------------------------------
# Upload and Index Documents
# --------------------------------------------------

@app.post("/api/documents", status_code=201)
async def upload_document(
    file: UploadFile = File(...)
):

    filename = Path(
        file.filename or "document"
    ).name[:120]

    # Validate file extension
    if not filename.lower().endswith((".pdf", ".txt")):

        raise HTTPException(
            status_code=400,
            detail="Upload a PDF or TXT file."
        )

    # Read file with size limit
    raw = await file.read(
        config.MAX_FILE_BYTES + 1
    )

    if len(raw) > config.MAX_FILE_BYTES:

        raise HTTPException(
            status_code=413,
            detail="File exceeds the 8 MB limit."
        )

    if not raw:

        raise HTTPException(
            status_code=400,
            detail="File is empty."
        )

    try:

        logger.info("Processing document: %s", filename)

        # Extract text from PDF or TXT
        pages = extract_pages(
            raw,
            filename
        )

        # Split text into searchable chunks
        chunks = list(
            chunk_pages(pages)
        )

        if not chunks:

            raise ValueError(
                "This file does not contain readable text."
            )

        if len(chunks) > config.MAX_CHUNKS:

            raise ValueError(
                f"Too many text chunks "
                f"(maximum {config.MAX_CHUNKS})."
            )

        # Generate Gemini embeddings
        vectors = []

        if config.API_KEY:

            for start in range(
                0,
                len(chunks),
                32
            ):

                batch = chunks[
                    start:start + 32
                ]

                texts = [
                    chunk["content"]
                    for chunk in batch
                ]

                embeddings = embed_texts(
                    texts,
                    purpose="document"
                )

                vectors.extend(embeddings)

        # Store documents and vectors
        result = store.add(
            filename,
            chunks,
            vectors
        )

        logger.info(
            "Document indexed: %s | %d chunks",
            filename,
            len(chunks)
        )

        return result

    except ValueError as e:

        raise HTTPException(
            status_code=422,
            detail=str(e)
        ) from e

    except Exception as e:

        logger.exception(
            "Failed to index document"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to index the file. "
                "Check database/API configuration."
            )
        ) from e


# --------------------------------------------------
# Gemini-Powered RAG Chat
# --------------------------------------------------

@app.post("/api/chat")
def chat(body: ChatRequest):

    try:

        logger.info(
            "Processing chatbot question"
        )

        # Generate query embedding
        vector = None

        if config.API_KEY:

            embeddings = embed_texts(
                [body.question],
                purpose="query"
            )

            if not embeddings:
                raise RuntimeError(
                    "Gemini returned no query embedding."
                )

            vector = embeddings[0]

        # Retrieve relevant passages
        sources = store.search(
            body.question,
            vector,
            limit=4
        )

        # Generate answer using Gemini
        answer = synthesize(
            body.question,
            sources
        )

        # Attach source numbers
        formatted_sources = [
            {
                "id": i + 1,
                **source
            }
            for i, source in enumerate(sources)
        ]

        return {
            "answer": answer,
            "sources": formatted_sources,
            "mode": (
                "ai"
                if config.API_KEY
                else "offline"
            )
        }

    except Exception as e:

        logger.exception(
            "Chat query failed"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to process question. "
                "Check database/API configuration."
            )
        ) from e
