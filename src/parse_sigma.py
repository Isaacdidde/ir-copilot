"""
parse_sigma.py — Parse Sigma YAML detection rules into enriched text records.

Expanded metadata now includes: tags, platforms, tactic, severity, references,
log source fields, and a stable unique ID.  The embedding text is structured
so that keyword-heavy rule content (logsource, detection keywords) is surface-
readable by both BM25 and dense retrievers.
"""

import glob
import uuid
from pathlib import Path

import yaml


def parse_sigma(rules_dir: str = "data/raw/sigma/rules") -> list[dict]:
    rules_path = Path(rules_dir)
    if not rules_path.exists():
        raise FileNotFoundError(
            f"Sigma rules directory not found at {rules_dir}. "
            "Run: git clone https://github.com/SigmaHQ/sigma.git data/raw/sigma"
        )

    records = []
    for filepath in glob.glob(f"{rules_dir}/**/*.yml", recursive=True):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                rule = yaml.safe_load(f)
        except (yaml.YAMLError, UnicodeDecodeError):
            continue

        if not rule or "title" not in rule:
            continue

        # ── stable identifiers ─────────────────────────────────────────────
        rule_id = rule.get("id", filepath)
        chunk_uid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"sigma:{rule_id}"))

        # ── ATT&CK cross-references ────────────────────────────────────────
        raw_tags: list[str] = rule.get("tags", []) or []
        attack_ids = [
            t.replace("attack.", "").upper()
            for t in raw_tags
            if t.lower().startswith("attack.t")
        ]
        attack_tactics = [
            t.replace("attack.", "").lower()
            for t in raw_tags
            if t.lower().startswith("attack.")
            and not t.lower().startswith("attack.t")
        ]
        non_attack_tags = [t for t in raw_tags if not t.lower().startswith("attack.")]

        # ── structured logsource ───────────────────────────────────────────
        logsource: dict = rule.get("logsource", {}) or {}
        logsource_str = ", ".join(
            f"{k}={v}" for k, v in logsource.items() if v
        )
        platforms = _logsource_to_platforms(logsource)

        # ── detection body (stringify for keyword retrieval) ───────────────
        detection = rule.get("detection", {})
        detection_keywords = _extract_detection_keywords(detection)

        # ── references ────────────────────────────────────────────────────
        references: list[str] = rule.get("references", []) or []

        # ── severity mapping ───────────────────────────────────────────────
        level = rule.get("level", "medium")
        severity = _sigma_level_to_severity(level)

        # ── tags for faceted filtering ─────────────────────────────────────
        tags = list(set(attack_tactics + platforms + non_attack_tags + [level]))

        # ── embedding text ─────────────────────────────────────────────────
        description = (rule.get("description") or "").strip()
        text_parts = [
            f"Detection rule: {rule.get('title', '')}",
            f"Level: {level}",
        ]
        if logsource_str:
            text_parts.append(f"Log source: {logsource_str}")
        if description:
            text_parts.append(description)
        if attack_ids:
            text_parts.append(f"Maps to ATT&CK: {', '.join(attack_ids)}")
        if attack_tactics:
            text_parts.append(f"Tactics: {', '.join(attack_tactics)}")
        if detection_keywords:
            text_parts.append(f"Detection keywords: {', '.join(detection_keywords[:30])}")
        embedding_text = "\n".join(text_parts)

        records.append(
            {
                # ── identity ───────────────────────────────────────────────
                "id": f"sigma-{rule_id}",
                "uid": chunk_uid,
                "source_type": "sigma",
                # ── retrieval text ─────────────────────────────────────────
                "text": embedding_text,
                # ── structured copy ────────────────────────────────────────
                "structured": {
                    "title": rule.get("title", ""),
                    "description": description,
                    "logsource": logsource,
                    "detection": detection,
                    "attack_ids": attack_ids,
                    "attack_tactics": attack_tactics,
                    "references": references,
                },
                # ── flat metadata (stored in ChromaDB) ─────────────────────
                "metadata": {
                    "title": rule.get("title", ""),
                    "level": level,
                    "severity": severity,
                    "attack_ids": ", ".join(attack_ids),
                    "tactic": ", ".join(attack_tactics),
                    "tags": ", ".join(tags),
                    "platforms": ", ".join(platforms),
                    "references": "; ".join(references[:3]),
                    "source": "Sigma",
                    "uid": chunk_uid,
                },
            }
        )

    return records


def _sigma_level_to_severity(level: str) -> str:
    mapping = {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
        "informational": "info",
    }
    return mapping.get((level or "").lower(), "medium")


def _logsource_to_platforms(logsource: dict) -> list[str]:
    """Infer OS/platform hints from Sigma logsource fields."""
    hints = []
    product = (logsource.get("product") or "").lower()
    service = (logsource.get("service") or "").lower()
    category = (logsource.get("category") or "").lower()

    windows_signals = {"windows", "sysmon", "powershell", "wineventlog", "security", "system"}
    linux_signals = {"linux", "auditd", "syslog", "auth"}
    cloud_signals = {"aws", "azure", "gcp", "okta", "office365", "o365"}

    combined = f"{product} {service} {category}"
    if any(s in combined for s in windows_signals):
        hints.append("windows")
    if any(s in combined for s in linux_signals):
        hints.append("linux")
    if any(s in combined for s in cloud_signals):
        hints.append("cloud")

    return hints or ["cross-platform"]


def _extract_detection_keywords(detection: dict) -> list[str]:
    """
    Flatten detection conditions into a list of keyword strings for embedding.
    Sigma detection can contain nested dicts/lists of varying depth.
    """
    if not detection or not isinstance(detection, dict):
        return []

    keywords: list[str] = []

    def _walk(node):
        if isinstance(node, str):
            keywords.append(node)
        elif isinstance(node, list):
            for item in node:
                _walk(item)
        elif isinstance(node, dict):
            for v in node.values():
                _walk(v)

    for key, value in detection.items():
        if key == "condition":
            continue  # condition is a logic expression, not a keyword
        _walk(value)

    # deduplicate while preserving order; drop generic noise
    seen: set[str] = set()
    result: list[str] = []
    for kw in keywords:
        if isinstance(kw, str) and kw not in seen and len(kw) > 2:
            seen.add(kw)
            result.append(kw)
    return result