"""
api.py — FastAPI backend for the IR Copilot.

Endpoints
---------
POST /query          : Main analysis endpoint (raw_text → full analysis).
GET  /health         : Liveness check (confirms Ollama is reachable).
GET  /diagnostics    : Last retrieval diagnostic record (for debugging UI).

Changes from Phase 8
--------------------
- Returns ``confidence`` and ``retrieval_diagnostics`` from generate_answer.
- Exposes a /diagnostics endpoint so the Streamlit UI can render score breakdowns.
- RetrievalConfig parameters are configurable via query-string overrides.
- Separate exception handling for ConnectionError vs OllamaError (unchanged logic).
"""

from __future__ import annotations

import logging
from typing import Optional

import requests as _requests
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from src.extract import extract_fields
from src.generate import generate_answer, format_incident
from src.hybrid_retrieve import RetrievalConfig
from src.llm import OllamaError


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="IR Copilot API",
    description="Local, grounded incident response analysis — no data leaves your machine.",
    version="2.0.0",
)

# Shared slot for last diagnostic record (single-user local tool)
_last_diagnostics: dict = {}


# ── request / response models ──────────────────────────────────────────────────

class IncidentInput(BaseModel):
    raw_text: str
    model_name: str = "llama3.1:8b"


class AnalysisResponse(BaseModel):
    answer: str
    sources: list[dict]
    flagged_citations: list[str]
    unverified_quotes: list[str]
    confidence: dict
    extracted_fields: dict
    retrieval_diagnostics: dict


# ── endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check(model_name: str = Query(default="llama3.1:8b")):
    """
    Check Ollama reachability and whether the requested model is available.
    Returns 200 if healthy, 503 otherwise.
    """
    try:
        resp = _requests.get("http://localhost:11434/api/tags", timeout=5)
        available_models = [m["name"] for m in resp.json().get("models", [])]
        model_ok = any(model_name in m for m in available_models)
        return {
            "ollama": "reachable",
            "requested_model": model_name,
            "model_available": model_ok,
            "available_models": available_models,
        }
    except _requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running. Start it with: ollama serve",
        )


@app.post("/query", response_model=AnalysisResponse)
def query_copilot(
    payload: IncidentInput,
    # Retrieval tuning via query-string — useful for testing without restarting
    top_k: int = Query(default=5, ge=1, le=20),
    min_similarity: float = Query(default=0.30, ge=0.0, le=1.0),
    alpha: float = Query(default=0.65, ge=0.0, le=1.0),
    recall_k: int = Query(default=20, ge=5, le=50),
    reranker: Optional[str] = Query(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        description="HuggingFace model name for cross-encoder reranking; set to '' to disable.",
    ),
):
    global _last_diagnostics

    cfg = RetrievalConfig(
        top_k=top_k,
        min_similarity=min_similarity,
        alpha=alpha,
        recall_k=recall_k,
        reranker_model_name=reranker or "",
    )

    try:
        fields = extract_fields(payload.raw_text, payload.model_name)
        incident_description = format_incident(fields)
        result = generate_answer(
            incident_description,
            model_name=payload.model_name,
            retrieval_cfg=cfg,
            k=top_k,
        )
    except _requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Local LLM unreachable at localhost:11434. "
                "Is Ollama running? Try: ollama serve"
            ),
        )
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Knowledge base not built yet: {exc}. Run the build and ingest steps first.",
        )

    result["extracted_fields"] = fields
    _last_diagnostics = result.get("retrieval_diagnostics", {})

    logger.info(
        "QUERY complete — confidence=%.3f grade=%s flagged=%d",
        result["confidence"]["overall"],
        result["confidence"]["grade"],
        len(result["flagged_citations"]),
    )

    return result


@app.get("/diagnostics")
def get_diagnostics():
    """Return the retrieval diagnostic record from the most recent /query call."""
    if not _last_diagnostics:
        return {"message": "No queries processed yet."}
    return _last_diagnostics