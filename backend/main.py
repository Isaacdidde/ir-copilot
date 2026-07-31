"""FastAPI application entrypoint for IR-Copilot."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.embeddings import get_active_embedding_model_name
from backend.logger import get_logger
from backend.models import IncidentRequest, IncidentResponse, KBStatus, SourceType
from backend.pipeline import run_pipeline
from backend.vectorstore import get_vector_store

logger = get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="Evidence-grounded RAG incident response assistant for SOC analysts.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_last_indexed_at: str | None = None


@app.on_event("startup")
def on_startup() -> None:
    global _last_indexed_at
    logger.info("Starting %s...", settings.app_name)
    try:
        store = get_vector_store()
        indexed = store.reindex_all(force=False)
        _last_indexed_at = datetime.now(timezone.utc).isoformat()
        logger.info("Startup indexing complete. %d new/changed chunks indexed.", indexed)
    except Exception as exc:  # noqa: BLE001
        logger.error("Startup indexing failed: %s", exc)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


@app.get("/kb/status", response_model=KBStatus)
def kb_status() -> KBStatus:
    store = get_vector_store()
    try:
        return KBStatus(
            indexed_documents=store.count(),
            mitre_count=store.count_by_source(SourceType.MITRE),
            sigma_count=store.count_by_source(SourceType.SIGMA),
            nist_count=store.count_by_source(SourceType.NIST),
            playbook_count=store.count_by_source(SourceType.PLAYBOOK),
            llm_model=settings.groq_model if settings.llm_provider == "groq" else settings.llm_model,
            embedding_model=get_active_embedding_model_name(),
            vector_db_status="connected",
            last_indexed_at=_last_indexed_at,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to compute KB status: %s", exc)
        raise HTTPException(status_code=503, detail="Vector DB unavailable") from exc


@app.post("/kb/reindex")
def reindex(force: bool = False) -> dict:
    global _last_indexed_at
    store = get_vector_store()
    count = store.reindex_all(force=force)
    _last_indexed_at = datetime.now(timezone.utc).isoformat()
    return {"newly_indexed_chunks": count, "reindexed_at": _last_indexed_at}


@app.post("/analyze", response_model=IncidentResponse)
def analyze(request: IncidentRequest) -> IncidentResponse:
    try:
        return run_pipeline(request.incident_description)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline execution failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host=settings.api_host, port=settings.api_port, reload=False)
