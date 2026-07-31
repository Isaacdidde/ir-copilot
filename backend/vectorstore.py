"""ChromaDB-backed persistent vector store for IR-Copilot."""

from __future__ import annotations

from typing import Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from backend.config import settings
from backend.embeddings import embed_query, embed_texts
from backend.ingestion import load_all_chunks
from backend.logger import get_logger
from backend.models import Chunk, SourceType

logger = get_logger(__name__)


class VectorStore:
    def __init__(self) -> None:
        self._client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def index_chunks(self, chunks: List[Chunk], force: bool = False) -> int:
        if not chunks:
            return 0

        existing_ids = set(self._collection.get(include=[])["ids"])

        to_index: List[Chunk] = chunks if force else [c for c in chunks if c.chunk_id not in existing_ids]
        if not to_index:
            logger.info("No new/changed chunks to index; skipping embedding step")
            return 0

        texts = [c.text for c in to_index]
        content_hashes = [c.metadata.get("content_hash", c.chunk_id) for c in to_index]
        vectors = embed_texts(texts, content_hashes)

        metadatas = []
        for c in to_index:
            meta = {"source_type": c.source_type.value, "source_name": c.source_name, "file_path": c.file_path}
            for k, v in c.metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v
                else:
                    meta[k] = str(v)
            metadatas.append(meta)

        self._collection.upsert(
            ids=[c.chunk_id for c in to_index],
            embeddings=vectors.tolist(),
            documents=texts,
            metadatas=metadatas,
        )
        logger.info("Indexed %d new/changed chunks into ChromaDB", len(to_index))
        return len(to_index)

    def reindex_all(self, force: bool = False) -> int:
        chunks = load_all_chunks()
        return self.index_chunks(chunks, force=force)

    def dense_search(
        self,
        query: str,
        top_k: int,
        source_type_filter: Optional[List[SourceType]] = None,
    ) -> List[Dict]:
        where = None
        if source_type_filter:
            values = [s.value for s in source_type_filter]
            where = {"source_type": {"$in": values}} if len(values) > 1 else {"source_type": values[0]}

        query_vector = embed_query(query)
        result = self._collection.query(
            query_embeddings=[query_vector.tolist()],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        hits: List[Dict] = []
        if not result["ids"] or not result["ids"][0]:
            return hits

        for i, chunk_id in enumerate(result["ids"][0]):
            distance = result["distances"][0][i]
            similarity = 1.0 - distance
            hits.append(
                {
                    "chunk_id": chunk_id,
                    "text": result["documents"][0][i],
                    "metadata": result["metadatas"][0][i],
                    "dense_score": float(max(0.0, similarity)),
                }
            )
        return hits

    def get_all_documents(self) -> List[Dict]:
        raw = self._collection.get(include=["documents", "metadatas"])
        docs = []
        for i, chunk_id in enumerate(raw["ids"]):
            docs.append(
                {
                    "chunk_id": chunk_id,
                    "text": raw["documents"][i],
                    "metadata": raw["metadatas"][i],
                }
            )
        return docs

    def count(self) -> int:
        return self._collection.count()

    def count_by_source(self, source_type: SourceType) -> int:
        result = self._collection.get(where={"source_type": source_type.value}, include=[])
        return len(result["ids"])


_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
