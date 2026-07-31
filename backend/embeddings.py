"""Embedding generation with an on-disk cache keyed by content hash."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import numpy as np

from backend.config import settings
from backend.logger import get_logger

logger = get_logger(__name__)

_model = None
_model_name_loaded: Optional[str] = None


def _get_model():
    global _model, _model_name_loaded
    if _model is not None:
        return _model

    from sentence_transformers import SentenceTransformer

    for candidate in (settings.embedding_model, settings.embedding_fallback_model):
        try:
            logger.info("Loading embedding model: %s", candidate)
            _model = SentenceTransformer(candidate)
            _model_name_loaded = candidate
            return _model
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load embedding model %s: %s", candidate, exc)

    raise RuntimeError(
        "Failed to load both primary and fallback embedding models. "
        "Check network access / local model cache."
    )


def get_active_embedding_model_name() -> str:
    if _model_name_loaded:
        return _model_name_loaded
    return settings.embedding_model


class EmbeddingCache:
    def __init__(self) -> None:
        self.path: Path = settings.cache_dir / "embedding_cache.json"
        self._store: dict[str, List[float]] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._store = json.loads(self.path.read_text(encoding="utf-8"))
                logger.info("Loaded embedding cache with %d entries", len(self._store))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not load embedding cache, starting fresh: %s", exc)
                self._store = {}

    def _save(self) -> None:
        try:
            self.path.write_text(json.dumps(self._store), encoding="utf-8")
        except OSError as exc:
            logger.error("Failed to persist embedding cache: %s", exc)

    def get(self, content_hash: str) -> Optional[List[float]]:
        return self._store.get(content_hash)

    def set(self, content_hash: str, vector: List[float]) -> None:
        self._store[content_hash] = vector

    def flush(self) -> None:
        self._save()


_cache = EmbeddingCache() if settings.enable_embedding_cache else None


def embed_texts(texts: List[str], content_hashes: Optional[List[str]] = None) -> np.ndarray:
    model = _get_model()

    if not settings.enable_embedding_cache or content_hashes is None:
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors, dtype=np.float32)

    results: List[Optional[List[float]]] = [None] * len(texts)
    miss_indices: List[int] = []
    miss_texts: List[str] = []

    for i, (text, h) in enumerate(zip(texts, content_hashes)):
        cached = _cache.get(h)
        if cached is not None:
            results[i] = cached
        else:
            miss_indices.append(i)
            miss_texts.append(text)

    if miss_texts:
        logger.info("Embedding cache miss for %d/%d chunks", len(miss_texts), len(texts))
        new_vectors = model.encode(miss_texts, normalize_embeddings=True, show_progress_bar=False)
        for idx, vec in zip(miss_indices, new_vectors):
            vec_list = vec.tolist()
            results[idx] = vec_list
            _cache.set(content_hashes[idx], vec_list)
        _cache.flush()
    else:
        logger.info("Embedding cache hit for all %d chunks", len(texts))

    return np.asarray(results, dtype=np.float32)


def embed_query(query: str) -> np.ndarray:
    model = _get_model()
    vector = model.encode([query], normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vector[0], dtype=np.float32)
