"""Hybrid retrieval pipeline: dense + BM25 fusion, reranking, dedup, compression."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from rank_bm25 import BM25Okapi

from backend.cache import retrieval_cache
from backend.config import settings
from backend.logger import get_logger
from backend.models import Chunk, RetrievedChunk, SourceType
from backend.vectorstore import get_vector_store

logger = get_logger(__name__)

_reranker = None

_EXPANSION_TERMS = {
    "powershell": ["encoded command", "script block", "T1059.001"],
    "ransomware": ["shadow copy deletion", "file encryption", "T1486"],
    "phishing": ["spearphishing attachment", "malicious attachment", "T1566"],
    "credential": ["lsass", "mimikatz", "credential dumping", "T1003"],
    "lateral movement": ["rdp", "psexec", "remote desktop", "T1021"],
    "persistence": ["scheduled task", "run key", "startup folder", "service"],
    "c2": ["command and control", "beaconing", "T1071"],
    "exfiltration": ["data staging", "outbound transfer"],
    "kerberoast": ["TGS request", "service account", "T1558.003"],
}


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_.]+", text.lower())


def expand_query(query: str) -> str:
    lower = query.lower()
    additions: List[str] = []
    for key, terms in _EXPANSION_TERMS.items():
        if key in lower:
            additions.extend(terms)
    if additions:
        expanded = f"{query} " + " ".join(dict.fromkeys(additions))
        logger.debug("Expanded query: %s", expanded)
        return expanded
    return query


def _get_reranker():
    global _reranker
    if _reranker is not None:
        return _reranker
    try:
        from sentence_transformers import CrossEncoder

        logger.info("Loading reranker model: %s", settings.reranker_model)
        _reranker = CrossEncoder(settings.reranker_model)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Reranker unavailable (%s); falling back to hybrid score ordering", exc)
        _reranker = False
    return _reranker


def _bm25_search(query: str, top_k: int, source_type_filter: Optional[List[SourceType]]) -> List[Dict]:
    store = get_vector_store()
    documents = store.get_all_documents()
    if source_type_filter:
        allowed = {s.value for s in source_type_filter}
        documents = [d for d in documents if d["metadata"].get("source_type") in allowed]

    if not documents:
        return []

    corpus_tokens = [_tokenize(d["text"]) for d in documents]
    bm25 = BM25Okapi(corpus_tokens)
    scores = bm25.get_scores(_tokenize(query))

    max_score = max(scores) if len(scores) and max(scores) > 0 else 1.0
    ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)[:top_k]
    return [
        {
            "chunk_id": doc["chunk_id"],
            "text": doc["text"],
            "metadata": doc["metadata"],
            "bm25_score": float(score / max_score) if max_score > 0 else 0.0,
        }
        for doc, score in ranked
        if score > 0
    ]


def _fuse(dense_hits: List[Dict], bm25_hits: List[Dict]) -> List[RetrievedChunk]:
    by_id: Dict[str, Dict] = {}

    for hit in dense_hits:
        by_id[hit["chunk_id"]] = {**hit, "bm25_score": 0.0}

    for hit in bm25_hits:
        if hit["chunk_id"] in by_id:
            by_id[hit["chunk_id"]]["bm25_score"] = hit["bm25_score"]
        else:
            by_id[hit["chunk_id"]] = {**hit, "dense_score": 0.0}

    alpha = settings.hybrid_alpha
    fused: List[RetrievedChunk] = []
    for chunk_id, data in by_id.items():
        hybrid_score = alpha * data.get("dense_score", 0.0) + (1 - alpha) * data.get("bm25_score", 0.0)
        meta = data["metadata"]
        chunk = Chunk(
            chunk_id=chunk_id,
            text=data["text"],
            source_type=SourceType(meta.get("source_type", "playbook")),
            source_name=meta.get("source_name", "Unknown"),
            file_path=meta.get("file_path", ""),
            metadata=meta,
        )
        fused.append(
            RetrievedChunk(
                chunk=chunk,
                dense_score=data.get("dense_score", 0.0),
                bm25_score=data.get("bm25_score", 0.0),
                hybrid_score=hybrid_score,
            )
        )

    fused.sort(key=lambda r: r.hybrid_score, reverse=True)
    return fused


def _rerank(query: str, candidates: List[RetrievedChunk], top_n: int) -> List[RetrievedChunk]:
    reranker = _get_reranker()
    if not candidates:
        return candidates

    if reranker in (None, False):
        return candidates[:top_n]

    pairs = [(query, c.chunk.text) for c in candidates]
    scores = reranker.predict(pairs)
    for c, score in zip(candidates, scores):
        c.rerank_score = float(score)

    candidates.sort(key=lambda c: c.rerank_score if c.rerank_score is not None else c.hybrid_score, reverse=True)
    return candidates[:top_n]


def _deduplicate(chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
    seen_hashes = set()
    deduped: List[RetrievedChunk] = []
    for c in chunks:
        h = c.chunk.metadata.get("content_hash", c.chunk.chunk_id)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        deduped.append(c)
    return deduped


def compress_context(chunks: List[RetrievedChunk], max_chars: int) -> List[RetrievedChunk]:
    total = 0
    compressed: List[RetrievedChunk] = []
    for c in chunks:
        remaining = max_chars - total
        if remaining <= 0:
            break
        text = c.chunk.text
        if len(text) > remaining:
            text = text[:remaining].rsplit(" ", 1)[0] + " …[truncated]"
        c.chunk.text = text
        total += len(text)
        compressed.append(c)
    return compressed


def retrieve(
    query: str,
    source_type_filter: Optional[List[SourceType]] = None,
    top_k: Optional[int] = None,
) -> List[RetrievedChunk]:
    top_k = top_k or settings.final_top_k

    cache_key = f"{query}|{source_type_filter}|{top_k}"
    if settings.enable_retrieval_cache:
        cached = retrieval_cache.get(cache_key)
        if cached is not None:
            logger.info("Retrieval cache hit")
            return cached

    expanded = expand_query(query)

    store = get_vector_store()
    dense_hits = store.dense_search(expanded, top_k=settings.dense_top_k, source_type_filter=source_type_filter)
    bm25_hits = _bm25_search(expanded, top_k=settings.bm25_top_k, source_type_filter=source_type_filter)

    fused = _fuse(dense_hits, bm25_hits)
    deduped = _deduplicate(fused)
    reranked = _rerank(query, deduped, top_n=max(top_k, settings.rerank_top_n))
    final = compress_context(reranked[:top_k], max_chars=settings.max_context_chars)

    if settings.enable_retrieval_cache:
        retrieval_cache.set(cache_key, final)

    logger.info(
        "Retrieval complete: %d dense, %d bm25, %d fused, %d final",
        len(dense_hits), len(bm25_hits), len(fused), len(final),
    )
    return final
