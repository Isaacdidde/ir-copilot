"""Evaluation harness for IR-Copilot: Recall@K, Precision@K, Faithfulness, Hallucination Rate."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.pipeline import run_pipeline  # noqa: E402
from backend.retrieval import retrieve  # noqa: E402

GOLD_SET_PATH = Path(__file__).parent / "gold_set.json"


def load_gold_set() -> List[Dict]:
    return json.loads(GOLD_SET_PATH.read_text(encoding="utf-8"))


def recall_precision_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> tuple[float, float]:
    top_k = retrieved_ids[:k]
    hits = len(set(top_k) & set(relevant_ids))
    recall = hits / len(relevant_ids) if relevant_ids else 0.0
    precision = hits / k if k else 0.0
    return recall, precision


def evaluate_retrieval(k: int = 5) -> Dict:
    gold_set = load_gold_set()
    recalls, precisions = [], []

    for case in gold_set:
        results = retrieve(case["query"], top_k=k)
        retrieved_ids = [r.chunk.metadata.get("technique_id") or r.chunk.source_name for r in results]
        recall, precision = recall_precision_at_k(retrieved_ids, case["relevant_source_names"], k)
        recalls.append(recall)
        precisions.append(precision)

    return {
        "k": k,
        "avg_recall_at_k": round(sum(recalls) / len(recalls), 3) if recalls else 0.0,
        "avg_precision_at_k": round(sum(precisions) / len(precisions), 3) if precisions else 0.0,
        "num_cases": len(gold_set),
    }


def evaluate_faithfulness() -> Dict:
    gold_set = load_gold_set()
    total_claims = 0
    unsupported_claims = 0

    for case in gold_set:
        response = run_pipeline(case["query"])
        evidence_sources = {e.source_name for e in response.evidence}

        for e in response.evidence:
            total_claims += 1
            if e.source_name not in evidence_sources:
                unsupported_claims += 1

        for mapping in response.mitre_mapping:
            total_claims += 1
            if not any(mapping.technique_id in name for name in evidence_sources):
                unsupported_claims += 1

    faithfulness = 1 - (unsupported_claims / total_claims) if total_claims else 1.0
    return {
        "total_claims": total_claims,
        "unsupported_claims": unsupported_claims,
        "faithfulness": round(faithfulness, 3),
        "hallucination_rate": round(1 - faithfulness, 3),
    }


def evaluate_context_precision(k: int = 5) -> Dict:
    gold_set = load_gold_set()
    precisions = []

    for case in gold_set:
        results = retrieve(case["query"], top_k=k)
        relevant = case["relevant_source_names"]
        relevant_hits = sum(
            1 for r in results if r.chunk.source_name in relevant
            or (r.chunk.metadata.get("technique_id") in relevant)
        )
        precisions.append(relevant_hits / len(results) if results else 0.0)

    return {"avg_context_precision": round(sum(precisions) / len(precisions), 3) if precisions else 0.0}


def run_all(k: int = 5) -> Dict:
    return {
        "retrieval": evaluate_retrieval(k),
        "context_precision": evaluate_context_precision(k),
        "faithfulness": evaluate_faithfulness(),
    }


if __name__ == "__main__":
    results = run_all()
    print(json.dumps(results, indent=2))
