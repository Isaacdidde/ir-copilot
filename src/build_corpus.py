"""
build_corpus.py — Assemble all parsed sources into a single corpus JSON.

Each record now contains three parallel representations:
    text       : clean, structured string fed to the embedding model and BM25
    structured : full parsed content preserved for future metadata filtering,
                 reranker context, and citation validation
    metadata   : flat dict stored in ChromaDB (str/int/float/bool values only)

Run
---
    python -m src.build_corpus
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.parse_attack import parse_attack
from src.parse_sigma import parse_sigma
from src.parse_playbooks import parse_playbooks

logger = logging.getLogger(__name__)


def build_corpus(
    attack_path: str = "data/raw/cti/enterprise-attack/enterprise-attack.json",
    sigma_dir: str = "data/raw/sigma/rules",
    playbook_dir: str = "data/raw/playbooks",
    output_path: str = "data/processed/corpus.json",
) -> list[dict]:
    records: list[dict] = []

    # ── ATT&CK ────────────────────────────────────────────────────────────
    try:
        attack_records = parse_attack(attack_path)
        logger.info("Parsed %d ATT&CK technique records.", len(attack_records))
        records.extend(attack_records)
    except FileNotFoundError as exc:
        logger.warning("Skipping ATT&CK: %s", exc)

    # ── Sigma ─────────────────────────────────────────────────────────────
    try:
        sigma_records = parse_sigma(sigma_dir)
        logger.info("Parsed %d Sigma rule records.", len(sigma_records))
        records.extend(sigma_records)
    except FileNotFoundError as exc:
        logger.warning("Skipping Sigma: %s", exc)

    # ── Playbooks ─────────────────────────────────────────────────────────
    playbook_records = parse_playbooks(playbook_dir)
    logger.info("Parsed %d playbook chunk records.", len(playbook_records))
    records.extend(playbook_records)

    if not records:
        raise RuntimeError(
            "Corpus is empty. Make sure at least one data source is present in data/raw/."
        )

    # ── deduplication by id ────────────────────────────────────────────────
    seen_ids: set[str] = set()
    deduped: list[dict] = []
    for r in records:
        if r["id"] not in seen_ids:
            seen_ids.add(r["id"])
            deduped.append(r)
        else:
            logger.debug("Duplicate chunk id skipped: %s", r["id"])

    logger.info("Total corpus size after deduplication: %d chunks.", len(deduped))

    # ── write output ───────────────────────────────────────────────────────
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=2, ensure_ascii=False)

    # ── corpus stats ───────────────────────────────────────────────────────
    type_counts: dict[str, int] = {}
    for r in deduped:
        t = r.get("source_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    logger.info("Corpus breakdown: %s", type_counts)

    return deduped


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    build_corpus()