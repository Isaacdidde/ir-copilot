"""
Loads MITRE ATT&CK, Sigma rules, NIST guidance, and custom playbooks from disk,
normalizes them into `Chunk` objects, and computes a content hash so unchanged
files are never re-embedded.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import List

import yaml
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import settings
from backend.logger import get_logger
from backend.models import Chunk, SourceType

logger = get_logger(__name__)


def _make_splitter() -> RecursiveCharacterTextSplitter:
    chunk_size_chars = settings.chunk_size_tokens * 4
    overlap_chars = settings.chunk_overlap_tokens * 4
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size_chars,
        chunk_overlap=overlap_chars,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _find_stix_bundle(directory: Path) -> "Path | None":
    """Content-sniff for a STIX bundle among any .json files in `directory`,
    catching downloads saved under a different filename (e.g. a browser
    saving it as "enterprise-attack (1).json")."""
    for path in sorted(directory.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as f:
                snippet = f.read(4096)
            if '"type"' in snippet and '"bundle"' in snippet and '"objects"' in snippet:
                logger.info("Detected MITRE STIX bundle at %s (via content sniff, not exact filename)", path)
                return path
        except OSError:
            continue
    return None


def load_mitre_chunks() -> List[Chunk]:
    chunks: List[Chunk] = []
    for path in sorted(settings.mitre_dir.glob("*.json")):
        if path.name == "enterprise-attack.json":
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to parse MITRE file %s: %s", path, exc)
            continue

        if not isinstance(data, list):
            logger.error(
                "Skipping %s: expected a JSON list of technique objects (sample "
                "MITRE format) but got %s. If this is a full STIX bundle, rename "
                "it to exactly 'enterprise-attack.json'.",
                path, type(data).__name__,
            )
            continue

        for technique in data:
            if not isinstance(technique, dict):
                logger.warning("Skipping malformed technique entry in %s: %r", path, technique)
                continue
            required_keys = {"technique_id", "name", "tactic", "description"}
            missing = required_keys - technique.keys()
            if missing:
                logger.warning(
                    "Skipping technique in %s missing required field(s) %s: %r",
                    path, missing, technique,
                )
                continue

            text = (
                f"MITRE ATT&CK Technique {technique['technique_id']}: {technique['name']}\n"
                f"Tactic: {technique['tactic']}\n"
                f"Description: {technique['description']}\n"
                f"Detection: {technique.get('detection', '')}\n"
                f"Mitigation: {technique.get('mitigation', '')}"
            )
            chunk_id = f"mitre_{technique['technique_id']}_{_hash_text(text)}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    text=text,
                    source_type=SourceType.MITRE,
                    source_name=f"{technique['technique_id']} - {technique['name']}",
                    file_path=str(path),
                    metadata={
                        "technique_id": technique["technique_id"],
                        "tactic": technique["tactic"],
                        "content_hash": _hash_text(text),
                    },
                )
            )
    logger.info("Loaded %d MITRE technique chunks", len(chunks))
    return chunks


def load_sigma_chunks() -> List[Chunk]:
    chunks: List[Chunk] = []
    for path in sorted(settings.sigma_dir.glob("*.yml")) + sorted(settings.sigma_dir.glob("*.yaml")):
        try:
            rule = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            logger.error("Failed to parse Sigma rule %s: %s", path, exc)
            continue
        if not rule:
            continue

        actions = "; ".join(rule.get("recommended_actions", []))
        text = (
            f"Sigma Rule: {rule.get('title')}\n"
            f"Description: {rule.get('description', '').strip()}\n"
            f"MITRE Technique: {rule.get('mitre_technique', 'N/A')}\n"
            f"Log Source: {rule.get('logsource', {})}\n"
            f"Severity: {rule.get('level', 'unknown')}\n"
            f"Recommended Actions: {actions}"
        )
        chunk_id = f"sigma_{path.stem}_{_hash_text(text)}"
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                text=text,
                source_type=SourceType.SIGMA,
                source_name=rule.get("title", path.stem),
                file_path=str(path),
                metadata={
                    "mitre_technique": rule.get("mitre_technique", ""),
                    "level": rule.get("level", "unknown"),
                    "content_hash": _hash_text(text),
                },
            )
        )
    logger.info("Loaded %d Sigma rule chunks", len(chunks))
    return chunks


def _load_markdown_chunks(directory: Path, source_type: SourceType) -> List[Chunk]:
    chunks: List[Chunk] = []
    splitter = _make_splitter()
    for path in sorted(directory.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("Failed to read %s: %s", path, exc)
            continue

        source_name = path.stem.replace("_", " ").title()
        for line in text.splitlines():
            if line.strip().startswith("# "):
                source_name = line.strip("# ").strip()
                break

        splits = splitter.split_text(text)
        for i, split_text in enumerate(splits):
            chunk_id = f"{source_type.value}_{path.stem}_{i}_{_hash_text(split_text)}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    text=split_text,
                    source_type=source_type,
                    source_name=source_name,
                    file_path=str(path),
                    metadata={
                        "chunk_index": i,
                        "content_hash": _hash_text(split_text),
                    },
                )
            )
    logger.info("Loaded %d chunks from %s (%s)", len(chunks), directory, source_type.value)
    return chunks


def load_nist_chunks() -> List[Chunk]:
    return _load_markdown_chunks(settings.nist_dir, SourceType.NIST)


def load_playbook_chunks() -> List[Chunk]:
    return _load_markdown_chunks(settings.playbooks_dir, SourceType.PLAYBOOK)


def load_all_chunks() -> List[Chunk]:
    """Load and chunk every configured knowledge source, preferring full
    real-world sources (STIX bundle, cloned Sigma repo, NIST PDF) when
    present, falling back to bundled samples otherwise."""
    all_chunks: List[Chunk] = []

    # --- MITRE: prefer full STIX bundle if present ---
    mitre_stix_path = settings.mitre_dir / "enterprise-attack.json"
    if not mitre_stix_path.exists():
        mitre_stix_path = _find_stix_bundle(settings.mitre_dir)

    if mitre_stix_path is not None:
        from backend.mitre_stix_loader import load_mitre_stix_chunks

        all_chunks.extend(load_mitre_stix_chunks(mitre_stix_path))
    else:
        all_chunks.extend(load_mitre_chunks())

    # --- Sigma: prefer a cloned SigmaHQ/sigma repo if present ---
    sigma_repo_path = settings.sigma_dir / "sigma-repo"
    if sigma_repo_path.exists() and (sigma_repo_path / "rules").exists():
        from backend.sigma_bulk_loader import load_sigma_bulk_chunks

        all_chunks.extend(load_sigma_bulk_chunks(sigma_repo_path))
    else:
        all_chunks.extend(load_sigma_chunks())

    # --- NIST: prefer the full PDF if present ---
    nist_pdf_candidates = list(settings.nist_dir.glob("*.pdf"))
    if nist_pdf_candidates:
        from backend.nist_pdf_loader import load_nist_pdf_chunks

        for pdf_path in nist_pdf_candidates:
            all_chunks.extend(load_nist_pdf_chunks(pdf_path))
    else:
        all_chunks.extend(load_nist_chunks())

    # --- Playbooks: always the local markdown files ---
    all_chunks.extend(load_playbook_chunks())

    logger.info("Total chunks loaded across all sources: %d", len(all_chunks))
    return all_chunks
