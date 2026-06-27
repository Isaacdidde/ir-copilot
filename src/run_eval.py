"""
run_eval.py — Recall-@k evaluation harness for the enhanced retrieval pipeline.

Metrics computed
----------------
- recall@k          : fraction of expected ATT&CK IDs surfaced in top-k chunks
- mean_semantic     : average best-chunk semantic similarity across queries
- mean_reranker     : average best-chunk reranker score (when reranker enabled)
- mean_confidence   : average overall confidence score from generate_answer
- source_diversity  : average number of distinct source types in top-k results
- threshold_empties : queries where ALL candidates fell below min_similarity

Usage
-----
    python -m eval.run_eval                     # default golden set
    python -m eval.run_eval --k 10 --no-reranker

The golden_set.json format has been extended to support optional
``severity`` and ``expected_source_types`` fields per item.
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
from pathlib import Path

from src.hybrid_retrieve import RetrievalConfig, retrieve
from src.generate import generate_answer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

GOLDEN_SET_PATH = "eval/golden_set.json"


def recall_at_k(
    golden_path: str = GOLDEN_SET_PATH,
    k: int = 5,
    min_similarity: float = 0.30,
    use_reranker: bool = True,
    verbose: bool = False,
) -> dict:
    golden_file = Path(golden_path)
    if not golden_file.exists():
        raise FileNotFoundError(
            f"Golden set not found at {golden_path}. Create it first (see eval/golden_set.json)."
        )

    with open(golden_file, "r", encoding="utf-8") as f:
        golden_set: list[dict] = json.load(f)

    cfg = RetrievalConfig(
        top_k=k,
        min_similarity=min_similarity,
        reranker_model_name=(
            "cross-encoder/ms-marco-MiniLM-L-6-v2" if use_reranker else ""
        ),
    )

    total_expected = 0
    total_hit = 0
    semantic_scores: list[float] = []
    reranker_scores: list[float] = []
    diversity_counts: list[int] = []
    threshold_empties = 0

    for item in golden_set:
        query = item["query"]
        expected_ids = set(item.get("expected_techniques", []))

        chunks, diag = retrieve(query, cfg=cfg)

        if not chunks:
            threshold_empties += 1
            if verbose:
                logger.warning("EMPTY RESULT for query: %r", query)
            total_expected += len(expected_ids)
            continue

        retrieved_ids = {
            c["metadata"].get("technique_id", "")
            for c in chunks
            if c["metadata"].get("technique_id")
        }
        # Also check attack_ids field (from Sigma chunks)
        for c in chunks:
            ids_str = c["metadata"].get("attack_ids", "")
            if ids_str:
                retrieved_ids.update(t.strip() for t in ids_str.split(",") if t.strip())

        hits = len(retrieved_ids & expected_ids)
        total_hit += hits
        total_expected += len(expected_ids)

        # Score tracking
        best_sem = max((c.get("semantic_score", 0.0) for c in chunks), default=0.0)
        semantic_scores.append(best_sem)

        best_rnk = max(
            (c["reranker_score"] for c in chunks if c.get("reranker_score") is not None),
            default=None,
        )
        if best_rnk is not None:
            reranker_scores.append(best_rnk)

        src_types = {c["metadata"].get("source", "?") for c in chunks}
        diversity_counts.append(len(src_types))

        if verbose:
            logger.info(
                "  Query: %r | expected=%s | retrieved=%s | hits=%d | sem=%.3f",
                query[:60],
                sorted(expected_ids),
                sorted(retrieved_ids),
                hits,
                best_sem,
            )

    recall = total_hit / total_expected if total_expected else 0.0

    results = {
        f"recall@{k}": round(recall, 4),
        "mean_best_semantic": round(statistics.mean(semantic_scores), 4) if semantic_scores else None,
        "mean_best_reranker": round(statistics.mean(reranker_scores), 4) if reranker_scores else None,
        "mean_source_diversity": round(statistics.mean(diversity_counts), 2) if diversity_counts else None,
        "threshold_empties": threshold_empties,
        "queries_evaluated": len(golden_set),
        "total_expected_ids": total_expected,
        "total_hits": total_hit,
    }

    print("\n─── Retrieval Evaluation Results ───")
    for k_name, v in results.items():
        print(f"  {k_name:30s}: {v}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IR Copilot retrieval eval harness")
    parser.add_argument("--k", type=int, default=5, help="Top-k chunks to retrieve")
    parser.add_argument("--min-similarity", type=float, default=0.30)
    parser.add_argument("--no-reranker", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    recall_at_k(
        k=args.k,
        min_similarity=args.min_similarity,
        use_reranker=not args.no_reranker,
        verbose=args.verbose,
    )