"""Loader for the official MITRE ATT&CK Enterprise STIX 2.x bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List

from backend.logger import get_logger
from backend.models import Chunk, SourceType

logger = get_logger(__name__)


def _external_id(obj: dict) -> str | None:
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack" and "external_id" in ref:
            return ref["external_id"]
    return None


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_mitre_stix_chunks(stix_path: Path) -> List[Chunk]:
    if not stix_path.exists():
        logger.warning("MITRE STIX bundle not found at %s; skipping", stix_path)
        return []

    try:
        bundle = json.loads(stix_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to parse MITRE STIX bundle %s: %s", stix_path, exc)
        return []

    objects = bundle.get("objects", [])

    techniques: Dict[str, dict] = {}
    mitigations: Dict[str, dict] = {}
    mitigates_by_technique: Dict[str, List[str]] = {}

    for obj in objects:
        obj_type = obj.get("type")
        if obj_type == "attack-pattern":
            if obj.get("revoked") or obj.get("x_mitre_deprecated"):
                continue
            techniques[obj["id"]] = obj
        elif obj_type == "course-of-action":
            mitigations[obj["id"]] = obj

    for obj in objects:
        if obj.get("type") != "relationship":
            continue
        if obj.get("relationship_type") != "mitigates":
            continue
        source_ref = obj.get("source_ref", "")
        target_ref = obj.get("target_ref", "")
        if source_ref.startswith("course-of-action--") and target_ref in techniques:
            mitigates_by_technique.setdefault(target_ref, []).append(source_ref)

    chunks: List[Chunk] = []
    for stix_id, tech in techniques.items():
        technique_id = _external_id(tech)
        if not technique_id:
            continue

        name = tech.get("name", "Unknown Technique")
        description = (tech.get("description") or "").strip()
        tactics = ", ".join(
            phase.get("phase_name", "").replace("-", " ").title()
            for phase in tech.get("kill_chain_phases", [])
            if phase.get("kill_chain_name") == "mitre-attack"
        ) or "Unknown"
        platforms = ", ".join(tech.get("x_mitre_platforms", [])) or "N/A"
        data_sources = ", ".join(tech.get("x_mitre_data_sources", [])) or "N/A"
        is_subtechnique = bool(tech.get("x_mitre_is_subtechnique", False))

        mitigation_texts = []
        for mit_ref in mitigates_by_technique.get(stix_id, []):
            mit_obj = mitigations.get(mit_ref)
            if mit_obj:
                mit_name = mit_obj.get("name", "")
                mit_desc = (mit_obj.get("description") or "").strip()
                mitigation_texts.append(f"{mit_name}: {mit_desc}")
        mitigation_block = " | ".join(mitigation_texts) if mitigation_texts else "Not documented in this bundle."

        text = (
            f"MITRE ATT&CK Technique {technique_id}: {name}\n"
            f"Tactic(s): {tactics}\n"
            f"Platforms: {platforms}\n"
            f"Sub-technique: {'Yes' if is_subtechnique else 'No'}\n"
            f"Description: {description}\n"
            f"Relevant Data Sources: {data_sources}\n"
            f"Mitigations: {mitigation_block}"
        )

        chunk_hash = _content_hash(text)
        chunks.append(
            Chunk(
                chunk_id=f"mitre_{technique_id}_{chunk_hash}",
                text=text,
                source_type=SourceType.MITRE,
                source_name=f"{technique_id} - {name}",
                file_path=str(stix_path),
                metadata={
                    "technique_id": technique_id,
                    "tactic": tactics,
                    "platforms": platforms,
                    "is_subtechnique": is_subtechnique,
                    "content_hash": chunk_hash,
                },
            )
        )

    logger.info(
        "Loaded %d MITRE ATT&CK techniques from full STIX bundle (%s)",
        len(chunks), stix_path.name,
    )
    return chunks
