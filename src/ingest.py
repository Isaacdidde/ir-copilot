"""
ingest.py — Embed corpus chunks and persist them into ChromaDB.

Key behaviours
--------------
- Uses r["text"] for embedding (the cleaned, structured embedding surface).
- Stores r["metadata"] in ChromaDB for filtering and citation validation.
- Skips chunks that already exist in the collection (idempotent re-runs).
- Flat-serialises any list-valued metadata fields that ChromaDB can't store
  natively (it only accepts str/int/float/bool).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

logger = logging.getLogger(__name__)


def _flatten_metadata(meta: dict) -> dict:
    """
    ChromaDB metadata values must be str, int, float, or bool.
    Convert list fields to comma-separated strings, drop None values.
    """
    flat: dict = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, list):
            flat[k] = ", ".join(str(x) for x in v)
        elif isinstance(v, (str, int, float, bool)):
            flat[k] = v
        else:
            flat[k] = str(v)
    return flat


def ingest(
    corpus_path: str = "data/processed/corpus.json",
    chroma_path: str = "./chroma_db",
    collection_name: str = "ir_knowledge",
    embedding_model: str = "all-MiniLM-L6-v2",
    batch_size: int = 64,
    skip_existing: bool = True,
) -> None:
    corpus_file = Path(corpus_path)
    if not corpus_file.exists():
        raise FileNotFoundError(
            f"Corpus not found at {corpus_path}. Run: python -m src.build_corpus"
        )

    with open(corpus_file, "r", encoding="utf-8") as f:
        records: list[dict] = json.load(f)

    logger.info("Loaded %d records from corpus.", len(records))

    model = SentenceTransformer(embedding_model)
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_or_create_collection(name=collection_name)

    # Optionally skip already-ingested chunks to make re-runs fast
    existing_ids: set[str] = set()
    if skip_existing:
        try:
            existing = collection.get(include=[])
            existing_ids = set(existing["ids"])
            logger.info(
                "Collection already contains %d chunks — skipping duplicates.",
                len(existing_ids),
            )
        except Exception:
            pass

    to_ingest = [r for r in records if r["id"] not in existing_ids]
    logger.info("Ingesting %d new chunks (skipping %d existing).", len(to_ingest), len(records) - len(to_ingest))

    if not to_ingest:
        logger.info("Nothing to ingest — collection is up to date.")
        return

    for i in tqdm(range(0, len(to_ingest), batch_size), desc="Ingesting"):
        batch = to_ingest[i : i + batch_size]
        texts = [r["text"] for r in batch]
        embeddings = model.encode(texts, show_progress_bar=False).tolist()

        flat_metas = [_flatten_metadata(r["metadata"]) for r in batch]

        collection.add(
            ids=[r["id"] for r in batch],
            embeddings=embeddings,
            documents=texts,
            metadatas=flat_metas,
        )

    logger.info(
        "Ingestion complete. Collection now contains %d chunks.",
        collection.count(),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ingest()