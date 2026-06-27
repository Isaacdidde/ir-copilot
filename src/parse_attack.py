"""
parse_attack.py — Parse MITRE ATT&CK STIX bundle into enriched text records.

Expanded metadata now includes: tags, platforms, tactic list, references,
data_sources, and a stable unique ID alongside the technique_id.
The `text` field is deliberately constructed to be dense with ATT&CK-adjacent
vocabulary so that embedding-based retrieval matches analyst queries naturally.
"""

import json
import uuid
from pathlib import Path


def parse_attack(
    filepath: str = "data/raw/cti/enterprise-attack/enterprise-attack.json",
) -> list[dict]:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(
            f"ATT&CK bundle not found at {filepath}. "
            "Run: git clone https://github.com/mitre/cti.git data/raw/cti"
        )

    with open(path, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    records = []
    for obj in bundle["objects"]:
        if obj.get("type") != "attack-pattern" or obj.get("revoked"):
            continue

        # ── stable identifiers ─────────────────────────────────────────────
        technique_id = next(
            (
                r["external_id"]
                for r in obj.get("external_references", [])
                if r.get("source_name") == "mitre-attack"
            ),
            None,
        )
        if not technique_id:
            continue

        stix_id = obj.get("id", "")
        # deterministic UUID so chunk IDs survive re-ingestion unchanged
        chunk_uid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"attack:{technique_id}"))

        # ── structured fields ──────────────────────────────────────────────
        tactics = [p["phase_name"] for p in obj.get("kill_chain_phases", [])]
        platforms = obj.get("x_mitre_platforms", [])
        data_sources = obj.get("x_mitre_data_sources", [])
        detection = obj.get("x_mitre_detection", "")
        is_subtechnique = "." in technique_id

        # External references (URLs only, skip the ATT&CK self-reference)
        references = [
            r.get("url", "")
            for r in obj.get("external_references", [])
            if r.get("url") and r.get("source_name") != "mitre-attack"
        ]

        # Tags: combine tactic names + platforms for faceted filtering later
        tags = list(set(tactics + [p.lower() for p in platforms]))

        # ── embedding text ─────────────────────────────────────────────────
        # Prefix the full body with structured context so the embedding model
        # encodes technique_id, name, tactics, and platforms with high weight.
        tactic_str = ", ".join(tactics) if tactics else "unknown"
        platform_str = ", ".join(platforms) if platforms else "cross-platform"
        description = obj.get("description", "").strip()
        text_parts = [
            f"ATT&CK {technique_id} — {obj.get('name', '')}",
            f"Tactics: {tactic_str}",
            f"Platforms: {platform_str}",
        ]
        if description:
            text_parts.append(description)
        if detection:
            text_parts.append(f"Detection: {detection}")
        if data_sources:
            text_parts.append(f"Data sources: {', '.join(data_sources)}")
        embedding_text = "\n".join(text_parts)

        records.append(
            {
                # ── identity ───────────────────────────────────────────────
                "id": f"attack-{technique_id}",
                "uid": chunk_uid,
                "stix_id": stix_id,
                "source_type": "attack",
                # ── retrieval text (goes into vector store) ────────────────
                "text": embedding_text,
                # ── structured copy (preserved for generation / filtering) ──
                "structured": {
                    "technique_id": technique_id,
                    "name": obj.get("name", ""),
                    "description": description,
                    "detection": detection,
                    "data_sources": data_sources,
                    "is_subtechnique": is_subtechnique,
                },
                # ── flat metadata (stored in ChromaDB, filterable) ─────────
                "metadata": {
                    "technique_id": technique_id,
                    "name": obj.get("name", ""),
                    "tactics": tactic_str,
                    "tactic_list": tactics,          # rich; excluded from chroma flat store
                    "platforms": platform_str,
                    "platform_list": platforms,       # rich; excluded from chroma flat store
                    "tags": ", ".join(tags),
                    "severity": _tactic_to_severity(tactics),
                    "references": "; ".join(references[:5]),  # cap at 5 to keep metadata compact
                    "source": "MITRE ATT&CK",
                    "uid": chunk_uid,
                },
            }
        )

    return records


def _tactic_to_severity(tactics: list[str]) -> str:
    """
    Heuristic severity label based on kill-chain position.
    Impact/exfiltration stages are Critical; early-stage recon is Low.
    Used downstream for prioritising displayed sources.
    """
    high_impact = {"impact", "exfiltration", "command-and-control", "lateral-movement"}
    medium = {"privilege-escalation", "credential-access", "collection"}
    low = {"reconnaissance", "resource-development"}

    tactic_set = {t.lower() for t in tactics}
    if tactic_set & high_impact:
        return "critical"
    if tactic_set & medium:
        return "high"
    if tactic_set & low:
        return "low"
    return "medium"