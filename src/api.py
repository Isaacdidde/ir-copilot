# src/api.py
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from src.generate import generate_answer

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown logs) ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("IR Copilot API starting up...")
    yield
    logger.info("IR Copilot API shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="IR Copilot API",
    description="RAG-grounded SOC incident response assistant. No data leaves your machine.",
    version="1.0.0",
    lifespan=lifespan
)

# Allow Streamlit (localhost:8501) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────
class IncidentQuery(BaseModel):
    incident_description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Plain-text description of the alert or incident",
        examples=["Encoded PowerShell at 2am followed by outbound connection to unknown IP"]
    )
    model_name: str = Field(
        default="llama3.1:8b",
        description="Ollama model to use for generation"
    )
    k: int = Field(
        default=5,
        ge=1,
        le=15,
        description="Number of context chunks to retrieve (1–15)"
    )

    @field_validator("model_name")
    @classmethod
    def validate_model(cls, v: str) -> str:
        allowed = {"llama3.1:8b", "mistral:7b", "phi3:mini"}
        if v not in allowed:
            raise ValueError(f"model_name must be one of {allowed}")
        return v


class IncidentResponse(BaseModel):
    answer: str
    sources: list[dict]
    query: str
    chunks_used: int
    error: bool
    latency_seconds: float


# ── Middleware: request logging + latency ─────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = round(time.perf_counter() - start, 3)
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed}s)")
    return response


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "IR Copilot API is running. POST to /query."}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


@app.post("/query", response_model=IncidentResponse, tags=["Copilot"])
def query_copilot(q: IncidentQuery):
    """
    Submit an incident description and receive a grounded ATT&CK-mapped
    response with recommended next steps and cited sources.
    """
    logger.info(f"Query received | model={q.model_name} k={q.k} | '{q.incident_description[:80]}...'")

    start = time.perf_counter()
    try:
        result = generate_answer(
            query=q.incident_description,
            model_name=q.model_name,
            k=q.k
        )
    except Exception as e:
        logger.error(f"generate_answer failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

    latency = round(time.perf_counter() - start, 3)
    logger.info(f"Query completed in {latency}s | chunks={result.get('chunks_used', '?')}")

    return IncidentResponse(
        answer=result["answer"],
        sources=result["sources"],
        query=result["query"],
        chunks_used=result["chunks_used"],
        error=result["error"],
        latency_seconds=latency
    )


# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check API logs."}
    )