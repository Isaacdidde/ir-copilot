"""
parse_playbooks.py — Parse markdown IR playbooks into enriched text records.

Each playbook is split by H2 section headings.  Expanded metadata now includes:
tags (derived from ATT&CK IDs found in text), platforms, severity, references,
and a stable unique ID per chunk.
"""

import glob
import re
import uuid
from pathlib import Path

from langchain_text_splitters import MarkdownHeaderTextSplitter


# ATT&CK technique pattern — matches T1234 and T1234.001
_TECHNIQUE_RE = re.compile(r"T\d{4}(?:\.\d{3})?")
# URL pattern for extracting inline references
_URL_RE = re.compile(r"https?://\S+")


def parse_playbooks(playbook_dir: str = "data/raw/playbooks") -> list[dict]:
    playbook_path = Path(playbook_dir)
    if not playbook_path.exists():
        playbook_path.mkdir(parents=True, exist_ok=True)

    headers_to_split_on = [("##", "section")]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)

    records: list[dict] = []

    for filepath in glob.glob(f"{playbook_dir}/*.md"):
        with open(filepath, "r", encoding="utf-8") as f:
            raw_text = f.read()

        # ── playbook-level fields ──────────────────────────────────────────
        title_line = raw_text.split("\n")[0]
        title = title_line.replace("#", "").strip() or Path(filepath).stem

        # Collect ATT&CK IDs mentioned anywhere in the file
        file_technique_ids = list(dict.fromkeys(_TECHNIQUE_RE.findall(raw_text)))
        # Collect URLs for references
        file_references = list(dict.fromkeys(_URL_RE.findall(raw_text)))

        # Infer severity from section content heuristics
        severity = _infer_severity(raw_text)
        platforms = _infer_platforms(raw_text)

        # ── per-section chunks ────────────────────────────────────────────
        chunks = splitter.split_text(raw_text)
        for i, chunk in enumerate(chunks):
            section = chunk.metadata.get("section", "general")
            content = chunk.page_content.strip()
            if not content:
                continue

            # Chunk-level ATT&CK IDs (subset of file-level)
            chunk_technique_ids = list(dict.fromkeys(_TECHNIQUE_RE.findall(content)))
            # Use file-level IDs if chunk has none (common for intro/summary sections)
            effective_ids = chunk_technique_ids or file_technique_ids

            # Stable UID: deterministic per file+section+index
            uid_input = f"playbook:{title}:{section}:{i}"
            chunk_uid = str(uuid.uuid5(uuid.NAMESPACE_URL, uid_input))

            tags = list(set(
                [section.lower().replace(" ", "-")]
                + platforms
                + ([severity] if severity else [])
            ))

            # ── embedding text ─────────────────────────────────────────────
            text_parts = [f"Playbook: {title} — {section}", content]
            if effective_ids:
                text_parts.append(f"Related ATT&CK techniques: {', '.join(effective_ids)}")
            embedding_text = "\n".join(text_parts)

            records.append(
                {
                    # ── identity ───────────────────────────────────────────
                    "id": f"playbook-{title}-{i}",
                    "uid": chunk_uid,
                    "source_type": "playbook",
                    # ── retrieval text ─────────────────────────────────────
                    "text": embedding_text,
                    # ── structured copy ────────────────────────────────────
                    "structured": {
                        "playbook": title,
                        "section": section,
                        "content": content,
                        "technique_ids": effective_ids,
                        "filepath": str(filepath),
                    },
                    # ── flat metadata (stored in ChromaDB) ─────────────────
                    "metadata": {
                        "playbook": title,
                        "section": section,
                        "technique_ids": ", ".join(effective_ids),
                        "tags": ", ".join(tags),
                        "platforms": ", ".join(platforms),
                        "tactic": "",          # playbooks don't map 1:1 to a tactic
                        "severity": severity,
                        "references": "; ".join(file_references[:3]),
                        "source": "Internal runbook",
                        "uid": chunk_uid,
                    },
                }
            )

    return records


def _infer_severity(text: str) -> str:
    """
    Rough severity from escalation / criticality language in the playbook.
    Analysts can override this with explicit frontmatter later.
    """
    lower = text.lower()
    if any(w in lower for w in ["critical", "ransomware", "domain admin", "data exfiltration"]):
        return "critical"
    if any(w in lower for w in ["high", "escalate", "tier 2", "c2", "lateral"]):
        return "high"
    if any(w in lower for w in ["medium", "suspicious", "anomalous"]):
        return "medium"
    return "low"


def _infer_platforms(text: str) -> list[str]:
    """Infer OS/platform tags from keywords in the playbook body."""
    lower = text.lower()
    platforms = []
    if any(w in lower for w in ["windows", "powershell", "wmi", "registry", "event id"]):
        platforms.append("windows")
    if any(w in lower for w in ["linux", "bash", "cron", "auditd", "/etc/"]):
        platforms.append("linux")
    if any(w in lower for w in ["aws", "azure", "gcp", "cloud", "s3", "iam"]):
        platforms.append("cloud")
    if any(w in lower for w in ["macos", "launchd", "plist"]):
        platforms.append("macos")
    return platforms or ["cross-platform"]