"""
retrieve.py — Backward-compatible semantic-only retrieval shim.

The full production pipeline lives in hybrid_retrieve.py.
This module re-exports a simplified ``retrieve()`` function that matches
the original Phase 6 API signature so existing code (eval harness, tests)
that calls ``from src.retrieve import retrieve`` continues to work.

For new code, import directly from src.hybrid_retrieve.
"""

from __future__ import annotations
from typing import Optional
from src.hybrid_retrieve import RetrievalConfig, retrieve as _hybrid_retrieve


def retrieve(query: str, k: int = 5) -> list[dict]:
    """
    Semantic-only retrieval (no BM25 fusion, no reranking).
    Preserved for the eval harness recall-@k baseline.
    """
    cfg = RetrievalConfig(
        top_k=k,
        recall_k=max(k, 10),
        alpha=1.0,            # pure semantic — BM25 weight = 0
        reranker_model_name="",  # no reranker for baseline
    )
    chunks, _ = _hybrid_retrieve(query, cfg=cfg)
    return chunks