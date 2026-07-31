"""Bulk loader for the official SigmaHQ Sigma rule repository."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List

import yaml

from backend.logger import get_logger
from backend.models import Chunk, SourceType

logger = get_logger(__name__)

_SKIP_DIR_NAMES = {"rules-deprecated", ".git", "tests", "images"}
_SKIP_STATUSES = {"deprecated", "unsupported"}


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _mitre_technique_from_tags(tags: list) -> str:
    for tag in tags or []:
        tag_str = str(tag).lower()
        if tag_str.startswith("attack.t") and tag_str.split(".", 1)[1][1:].replace(".", "").isdigit():
            return tag_str.split(".", 1)[1].upper()
    return ""


def _iter_yaml_files(root: Path, include_emerging_threats: bool):
    for pattern in ("*.yml", "*.yaml"):
        for path in sorted(root.rglob(pattern)):
            relative_parts = path.relative_to(root).parts
            if any(part in _SKIP_DIR_NAMES for part in relative_parts):
                continue
            if not include_emerging_threats and "rules-emerging-threats" in relative_parts:
                continue
            yield path


def load_sigma_bulk_chunks(
    repo_root: Path,
    include_emerging_threats: bool = True,
) -> List[Chunk]:
    if not repo_root.exists():
        logger.warning("Sigma repo root not found at %s; skipping", repo_root)
        return []

    chunks: List[Chunk] = []
    skipped_deprecated = 0
    skipped_malformed = 0

    for path in _iter_yaml_files(repo_root, include_emerging_threats):
        try:
            raw = path.read_text(encoding="utf-8")
            docs = [d for d in yaml.safe_load_all(raw) if d]
        except yaml.YAMLError as exc:
            logger.debug("Skipping malformed Sigma file %s: %s", path, exc)
            skipped_malformed += 1
            continue
        except OSError as exc:
            logger.debug("Could not read %s: %s", path, exc)
            skipped_malformed += 1
            continue

        for rule in docs:
            if not isinstance(rule, dict) or "title" not in rule:
                continue

            status = str(rule.get("status", "")).lower()
            if status in _SKIP_STATUSES:
                skipped_deprecated += 1
                continue

            title = rule.get("title", path.stem)
            description = (rule.get("description") or "").strip()
            level = rule.get("level", "unknown")
            logsource = rule.get("logsource", {}) or {}
            logsource_str = ", ".join(f"{k}={v}" for k, v in logsource.items())
            tags = rule.get("tags", []) or []
            technique_id = _mitre_technique_from_tags(tags)
            falsepositives = rule.get("falsepositives", [])
            fp_str = "; ".join(falsepositives) if isinstance(falsepositives, list) else str(falsepositives)

            text = (
                f"Sigma Rule: {title}\n"
                f"Status: {status or 'stable'}\n"
                f"Description: {description}\n"
                f"MITRE Technique: {technique_id or 'N/A'}\n"
                f"Log Source: {logsource_str}\n"
                f"Severity: {level}\n"
                f"Tags: {', '.join(str(t) for t in tags)}\n"
                f"False Positives: {fp_str or 'None documented'}"
            )

            chunk_hash = _content_hash(text)
            rule_id = rule.get("id", path.stem)
            chunks.append(
                Chunk(
                    chunk_id=f"sigma_{rule_id}_{chunk_hash}",
                    text=text,
                    source_type=SourceType.SIGMA,
                    source_name=title,
                    file_path=str(path),
                    metadata={
                        "mitre_technique": technique_id,
                        "level": level,
                        "status": status or "stable",
                        "content_hash": chunk_hash,
                    },
                )
            )

    logger.info(
        "Loaded %d Sigma rules from %s (skipped %d deprecated/unsupported, %d malformed)",
        len(chunks), repo_root, skipped_deprecated, skipped_malformed,
    )
    return chunks
