"""
hybrid_retrieve.py — Production-quality retrieval pipeline.

Stages
------
1.  Semantic recall   : dense embedding search (top ``recall_k`` candidates).
2.  BM25 keyword re-score : normalized BM25 scores merged with alpha weighting.
3.  Similarity threshold  : discard chunks below ``min_similarity`` before reranking.
4.  Cross-encoder reranking : precision stage over the surviving candidates.
5.  Source-diversity enforcement : ensure the final ``k`` results include a
    balanced mix of MITRE ATT&CK, Sigma rules, and Internal runbook chunks
    when all three source types are available in the candidate pool.
6.  Diagnostic logging : emit a structured log record per retrieval for
    debugging and recall-@k evaluation harness.

Score conventions
-----------------
- Semantic similarity     : cosine similarity in [0, 1] (1 = identical)
- BM25 score (raw)        : unbounded; normalised to [0, 1] via max-norm
- Hybrid score            : alpha * semantic + (1 - alpha) * bm25_norm
- Reranker score          : cross-encoder logit, rescaled to [0, 1] via sigmoid
- Final score             : reranker score when available, else hybrid score
"""

from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path
from typing import Optional

import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ── module-level singletons (lazy-loaded) ─────────────────────────────────────
_dense_model: Optional[SentenceTransformer] = None
_reranker_model = None          # sentence_transformers CrossEncoder
_chroma_collection = None
_bm25_index: Optional[BM25Okapi] = None
_corpus_records: Optional[list[dict]] = None   # full corpus for BM25


# ── public configuration dataclass ────────────────────────────────────────────

class RetrievalConfig:
    """
    Single place to tune all retrieval hyperparameters.
    Defaults chosen to balance recall quality vs. latency on CPU.
    """

    def __init__(
        self,
        # candidates fetched from the dense index before filtering/reranking
        recall_k: int = 20,
        # final number of chunks returned to the generator
        top_k: int = 5,
        # score threshold below which a chunk is discarded before reranking
        min_similarity: float = 0.30,
        # weight for semantic vs BM25 during hybrid scoring (1.0 = pure semantic)
        alpha: float = 0.65,
        # cross-encoder model; set to None to skip reranking (faster, less precise)
        reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        # dense embedding model
        embedding_model_name: str = "all-MiniLM-L6-v2",
        # corpus JSON path (needed for BM25)
        corpus_path: str = "data/processed/corpus.json",
        # chroma DB path
        chroma_path: str = "./chroma_db",
        # chroma collection name
        collection_name: str = "ir_knowledge",
        # source diversity: desired share per source type in final top_k
        # {"attack": 0.4, "sigma": 0.3, "playbook": 0.3} means at least 40% ATT&CK etc.
        # Set to None to disable diversity enforcement.
        diversity_weights: Optional[dict[str, float]] = None,
    ):
        self.recall_k = recall_k
        self.top_k = top_k
        self.min_similarity = min_similarity
        self.alpha = alpha
        self.reranker_model_name = reranker_model_name
        self.embedding_model_name = embedding_model_name
        self.corpus_path = corpus_path
        self.chroma_path = chroma_path
        self.collection_name = collection_name
        self.diversity_weights = diversity_weights or {
            "attack": 0.40,
            "sigma": 0.30,
            "playbook": 0.30,
        }


# ── lazy loader helpers ────────────────────────────────────────────────────────

def _get_dense_model(cfg: RetrievalConfig) -> SentenceTransformer:
    global _dense_model
    if _dense_model is None:
        logger.info("Loading dense embedding model: %s", cfg.embedding_model_name)
        _dense_model = SentenceTransformer(cfg.embedding_model_name)
    return _dense_model


def _get_reranker(cfg: RetrievalConfig):
    global _reranker_model
    if _reranker_model is None and cfg.reranker_model_name:
        try:
            from sentence_transformers import CrossEncoder
            logger.info("Loading cross-encoder reranker: %s", cfg.reranker_model_name)
            _reranker_model = CrossEncoder(cfg.reranker_model_name)
        except Exception as exc:
            logger.warning(
                "Could not load reranker %s: %s — falling back to hybrid scores only.",
                cfg.reranker_model_name,
                exc,
            )
    return _reranker_model


def _get_collection(cfg: RetrievalConfig):
    global _chroma_collection
    if _chroma_collection is None:
        client = chromadb.PersistentClient(path=cfg.chroma_path)
        _chroma_collection = client.get_collection(cfg.collection_name)
    return _chroma_collection


def _get_bm25(cfg: RetrievalConfig) -> tuple[BM25Okapi, list[dict]]:
    global _bm25_index, _corpus_records
    if _bm25_index is None:
        corpus_path = Path(cfg.corpus_path)
        if not corpus_path.exists():
            raise FileNotFoundError(
                f"Corpus not found at {cfg.corpus_path}. Run: python -m src.build_corpus"
            )
        with open(corpus_path, "r", encoding="utf-8") as f:
            _corpus_records = json.load(f)
        logger.info("Building BM25 index over %d corpus chunks…", len(_corpus_records))
        tokenised = [r["text"].lower().split() for r in _corpus_records]
        _bm25_index = BM25Okapi(tokenised)
    return _bm25_index, _corpus_records


# ── normalisation helpers ──────────────────────────────────────────────────────

def _max_normalise(scores: list[float]) -> list[float]:
    """Max-normalisation: divide by the max score.  Safe for BM25 (always >= 0)."""
    max_score = max(scores) if scores else 1.0
    if max_score == 0:
        return [0.0] * len(scores)
    return [s / max_score for s in scores]


def _sigmoid(x: float) -> float:
    """Squash cross-encoder logit to (0, 1)."""
    return 1.0 / (1.0 + math.exp(-x))


# ── main retrieval entry point ─────────────────────────────────────────────────

def retrieve(
    query: str,
    cfg: Optional[RetrievalConfig] = None,
    # convenience shorthands (override cfg when provided)
    k: Optional[int] = None,
    min_similarity: Optional[float] = None,
) -> tuple[list[dict], dict]:
    """
    Run the full retrieval pipeline for ``query``.

    Returns
    -------
    chunks : list[dict]
        Final ranked chunks, each with keys:
        ``text``, ``metadata``, ``semantic_score``, ``bm25_score``,
        ``hybrid_score``, ``reranker_score``, ``final_score``.
    diagnostics : dict
        Structured log record for debugging / eval harness.
    """
    cfg = cfg or RetrievalConfig()
    if k is not None:
        cfg.top_k = k
    if min_similarity is not None:
        cfg.min_similarity = min_similarity

    t_start = time.perf_counter()

    # ── Stage 1: dense recall ──────────────────────────────────────────────
    model = _get_dense_model(cfg)
    collection = _get_collection(cfg)
    query_embedding = model.encode(query).tolist()

    chroma_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=cfg.recall_k,
    )

    # ChromaDB returns L2 distances; convert to cosine-like similarity.
    # For normalised embeddings (which sentence-transformers produces), the
    # relationship is: cosine_sim = 1 - (distance² / 2).
    # We clamp to [0,1] to handle floating-point edge cases.
    raw_distances = chroma_results["distances"][0]
    semantic_scores = [
        max(0.0, min(1.0, 1.0 - (d * d / 2.0))) for d in raw_distances
    ]

    candidates: list[dict] = []
    for doc, meta, sem_score in zip(
        chroma_results["documents"][0],
        chroma_results["metadatas"][0],
        semantic_scores,
    ):
        candidates.append(
            {
                "text": doc,
                "metadata": meta,
                "semantic_score": sem_score,
                "bm25_score": 0.0,       # filled in Stage 2
                "hybrid_score": 0.0,     # filled in Stage 2
                "reranker_score": None,  # filled in Stage 4 (optional)
                "final_score": sem_score,
            }
        )

    # ── Stage 2: BM25 re-score with max-normalisation ─────────────────────
    bm25_index, corpus_records = _get_bm25(cfg)
    query_tokens = query.lower().split()
    raw_bm25_scores = bm25_index.get_scores(query_tokens).tolist()

    # Build a lookup from chunk id → bm25 raw score
    bm25_by_uid = {
        r.get("uid", r.get("id", "")): score
        for r, score in zip(corpus_records, raw_bm25_scores)
    }

    # Collect raw BM25 for candidates only (for per-batch normalisation)
    candidate_raw_bm25 = [
        bm25_by_uid.get(c["metadata"].get("uid", ""), 0.0)
        for c in candidates
    ]
    normalised_bm25 = _max_normalise(candidate_raw_bm25)

    for cand, raw_b25, norm_b25 in zip(candidates, candidate_raw_bm25, normalised_bm25):
        cand["bm25_score"] = norm_b25
        cand["hybrid_score"] = cfg.alpha * cand["semantic_score"] + (1 - cfg.alpha) * norm_b25
        cand["final_score"] = cand["hybrid_score"]

    # ── Stage 3: similarity threshold ─────────────────────────────────────
    before_threshold = len(candidates)
    candidates = [c for c in candidates if c["semantic_score"] >= cfg.min_similarity]
    after_threshold = len(candidates)

    if not candidates:
        logger.warning(
            "All %d candidates fell below similarity threshold %.2f — "
            "returning empty result set.",
            before_threshold,
            cfg.min_similarity,
        )
        diagnostics = _build_diagnostics([], [], query, cfg, t_start, "threshold_empty")
        return [], diagnostics

    # Sort by hybrid score descending for reranker input
    candidates.sort(key=lambda c: c["hybrid_score"], reverse=True)

    # ── Stage 4: cross-encoder reranking ──────────────────────────────────
    reranker = _get_reranker(cfg)
    if reranker is not None:
        pairs = [(query, c["text"]) for c in candidates]
        raw_logits = reranker.predict(pairs).tolist()
        for cand, logit in zip(candidates, raw_logits):
            sig = _sigmoid(logit)
            cand["reranker_score"] = sig
            cand["final_score"] = sig  # reranker supersedes hybrid score

        candidates.sort(key=lambda c: c["final_score"], reverse=True)

    # ── Stage 5: source diversity enforcement ─────────────────────────────
    final_chunks = _enforce_diversity(candidates, cfg)

    diagnostics = _build_diagnostics(candidates, final_chunks, query, cfg, t_start)
    _log_diagnostics(diagnostics)

    return final_chunks, diagnostics


# ── diversity enforcement ──────────────────────────────────────────────────────

def _enforce_diversity(
    ranked: list[dict],
    cfg: RetrievalConfig,
) -> list[dict]:
    """
    Fill the final top_k slots while respecting source diversity targets.

    Strategy
    --------
    1. Compute the ideal slot allocation per source type from cfg.diversity_weights.
    2. Fill each slot greedily from the top of ``ranked``, preferring under-
       represented source types.
    3. If a source type has exhausted its available candidates, remaining slots
       are filled by overall score rank (no starvation).

    This means a query that only returns ATT&CK chunks (e.g. a very specific
    technique ID query) still gets a full result set — diversity targets are
    best-effort, not hard quotas.
    """
    k = cfg.top_k
    weights = cfg.diversity_weights or {}

    # Group candidates by source_type
    buckets: dict[str, list[dict]] = {"attack": [], "sigma": [], "playbook": [], "_other": []}
    for chunk in ranked:
        src = chunk["metadata"].get("source", "").lower()
        if "att&ck" in src or src == "mitre att&ck":
            buckets["attack"].append(chunk)
        elif "sigma" in src:
            buckets["sigma"].append(chunk)
        elif "runbook" in src or "playbook" in src:
            buckets["playbook"].append(chunk)
        else:
            buckets["_other"].append(chunk)

    # Ideal slot counts (floor, so we never exceed k)
    slots: dict[str, int] = {}
    available_types = [t for t in ["attack", "sigma", "playbook"] if buckets[t]]
    if len(available_types) < 2:
        # Not enough diversity available — just return top-k by score
        return ranked[:k]

    remaining_slots = k
    for src_type in available_types:
        ideal = int(math.floor(weights.get(src_type, 1 / len(available_types)) * k))
        ideal = min(ideal, len(buckets[src_type]))
        slots[src_type] = ideal
        remaining_slots -= ideal

    # Distribute leftover slots to the highest-scoring remaining chunks
    result: list[dict] = []
    pointers: dict[str, int] = {t: 0 for t in buckets}

    # First: fill allocated diversity slots
    for src_type, count in slots.items():
        bucket = buckets[src_type]
        for _ in range(count):
            if pointers[src_type] < len(bucket):
                result.append(bucket[pointers[src_type]])
                pointers[src_type] += 1

    # Second: fill remaining slots from the global ranked list (already sorted)
    result_ids = {id(c) for c in result}
    for chunk in ranked:
        if len(result) >= k:
            break
        if id(chunk) not in result_ids:
            result.append(chunk)
            result_ids.add(id(chunk))

    # Re-sort the final set by final_score so the LLM sees best context first
    result.sort(key=lambda c: c["final_score"], reverse=True)
    return result[:k]


# ── diagnostics ────────────────────────────────────────────────────────────────

def _build_diagnostics(
    candidates: list[dict],
    final: list[dict],
    query: str,
    cfg: RetrievalConfig,
    t_start: float,
    note: str = "",
) -> dict:
    elapsed = time.perf_counter() - t_start
    return {
        "query": query,
        "elapsed_ms": round(elapsed * 1000, 1),
        "config": {
            "recall_k": cfg.recall_k,
            "top_k": cfg.top_k,
            "min_similarity": cfg.min_similarity,
            "alpha": cfg.alpha,
            "reranker": cfg.reranker_model_name,
        },
        "candidate_count": len(candidates),
        "final_count": len(final),
        "note": note,
        "candidates": [
            {
                "source": c["metadata"].get("source", "?"),
                "id": c["metadata"].get("uid", c["metadata"].get("technique_id", "")),
                "title": (
                    c["metadata"].get("name")
                    or c["metadata"].get("title")
                    or c["metadata"].get("playbook", "")
                ),
                "semantic_score": round(c["semantic_score"], 4),
                "bm25_score": round(c["bm25_score"], 4),
                "hybrid_score": round(c["hybrid_score"], 4),
                "reranker_score": (
                    round(c["reranker_score"], 4) if c.get("reranker_score") is not None else None
                ),
                "final_score": round(c["final_score"], 4),
                "selected": any(id(f) == id(c) for f in final),
            }
            for c in candidates
        ],
        "selected_sources": [
            c["metadata"].get("source", "?") for c in final
        ],
    }


def _log_diagnostics(diag: dict) -> None:
    """Emit a single INFO-level log line with the key retrieval metrics."""
    selected = [d for d in diag["candidates"] if d["selected"]]
    summary = " | ".join(
        f"{d['source']} [{d['title'][:30]}] "
        f"sem={d['semantic_score']:.3f} "
        f"bm25={d['bm25_score']:.3f} "
        f"rnk={d['reranker_score'] if d['reranker_score'] is not None else 'n/a'} "
        f"fin={d['final_score']:.3f}"
        for d in selected
    )
    logger.info(
        "RETRIEVAL [%.0fms] q=%r | candidates=%d→selected=%d | %s",
        diag["elapsed_ms"],
        diag["query"][:80],
        diag["candidate_count"],
        diag["final_count"],
        summary,
    )