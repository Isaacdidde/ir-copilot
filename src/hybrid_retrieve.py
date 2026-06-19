# src/hybrid_retrieve.py
from rank_bm25 import BM25Okapi
import json

with open("data/processed/corpus.json") as f:
    _records = json.load(f)
_tokenized = [r["text"].lower().split() for r in _records]
_bm25 = BM25Okapi(_tokenized)

def hybrid_retrieve(query, k=5, alpha=0.5):
    from src.retrieve import retrieve as semantic_retrieve
    semantic_results = semantic_retrieve(query, k=k * 2)

    bm25_scores = _bm25.get_scores(query.lower().split())
    bm25_by_id = {r["id"]: s for r, s in zip(_records, bm25_scores)}

    for r in semantic_results:
        # combine normalized semantic score with bm25 score
        r["combined_score"] = alpha * r["score"] + (1 - alpha) * bm25_by_id.get(r["metadata"].get("id", ""), 0)

    return sorted(semantic_results, key=lambda x: x["combined_score"], reverse=True)[:k]