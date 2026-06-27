"""
generate.py — Grounded generation with hallucination controls and confidence scoring.

Pipeline
--------
1.  Retrieval      : hybrid_retrieve pipeline → top-k chunks with full score history.
2.  Prompting      : structured system prompt distinguishing Confirmed / Likely /
                     Possible / Unknown evidence tiers.
3.  Post-processing:
    a. ATT&CK technique name correction (corpus ground truth).
    b. Citation validation — every cited source must appear in retrieved chunks.
    c. Unverified quote detection.
4.  Confidence scoring — composite metric from:
    a. Mean reranker score of final chunks.
    b. Source agreement (how many retrieved source types agree on the same techniques).
    c. Citation coverage (fraction of answer citations that match a real retrieved chunk).
    d. Semantic similarity of the best chunk.

All original hallucination detection, citation validation, and ATT&CK name
correction logic is preserved and extended to work with the new retrieval API.
"""

from __future__ import annotations

import json
import logging
import re
import statistics
from functools import lru_cache
from typing import Optional

from src.llm import OllamaError, call_ollama
from src.hybrid_retrieve import RetrievalConfig, retrieve as _retrieve

logger = logging.getLogger(__name__)

# ── system prompt ──────────────────────────────────────────────────────────────

SYSTEM_TEMPLATE = """You are a SOC incident response assistant powered by a retrieval-augmented knowledge base.
Answer ONLY using the context passages below. You may ONLY cite these source types, and only when they actually appear in the provided context:
  • MITRE ATT&CK
  • Sigma detection rules
  • Internal runbook (your own playbooks)

NEVER cite external frameworks (NIST, SANS, CIS, etc.) unless their exact text appears in the context — if no relevant source exists, say "no matching internal guidance found" instead.
Use the EXACT technique name shown in the context next to each ATT&CK ID — never paraphrase or invent a name.
Cite every source in this exact format: [Source: <exact title from context>]. Do not use any other citation style.
Make sure the source TYPE in your citation matches the actual type in context — never label a MITRE ATT&CK technique as a Playbook, or a Sigma rule as ATT&CK, or vice versa.

EVIDENCE TIERS — you must classify every technique and finding using one of these four labels:
  • Confirmed       : direct evidence in the context AND in the incident description (e.g. the exact process name, hash, or indicator is present in both)
  • Likely          : strong contextual alignment — multiple context sources agree and the incident details are consistent
  • Possible        : single source match or weak alignment — treat as a hypothesis to investigate
  • Insufficient evidence : the technique is plausible but the available context does not provide enough grounding to include it — state "Insufficient evidence to confirm this technique." and omit it from recommendations

Always state which tier applies next to each technique finding.  Example: "T1059.001 — PowerShell (Likely): …"

Context:
{context}

Incident description:
{query}

Respond in this exact format:
1. Likely ATT&CK techniques (with IDs and evidence tier)
2. Risk assessment
3. Recommended next steps (cite source for each step — only steps grounded in the context)
4. A 2–3 sentence draft incident summary as plain text (no quotation marks)
"""

# ── incident field normalisation (unchanged from Phase 7) ──────────────────────

FIELD_LABELS = {
    "alert_name": "Alert Name",
    "host": "Host",
    "user": "User",
    "process": "Process",
    "command_line": "Command Line",
    "file_path": "File Path / Hash",
    "network": "Network Activity",
    "indicators": "Observed Indicators",
    "notes": "Additional Notes",
}


def format_incident(fields: dict) -> str:
    """Turn structured incident fields into a normalised text block."""
    lines = []
    for key, label in FIELD_LABELS.items():
        value = str(fields.get(key) or "").strip()
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


# ── post-generation grounding checks ──────────────────────────────────────────

CITATION_PATTERN = re.compile(
    r"[\[\(]\s*(Source|Playbook|Detection rule|Sigma(?:\s+detection\s+rule)?|"
    r"Internal\s+runbook|Runbook|ATT&CK)\s*:?\s*([^\]\)]*)[\]\)]",
    re.IGNORECASE,
)
QUOTE_PATTERN = re.compile(r'["\u201c]([^"\u201d]{8,})["\u201d]')

TYPE_TO_SOURCE = {
    "playbook": "internal runbook",
    "runbook": "internal runbook",
    "internal runbook": "internal runbook",
    "sigma": "sigma",
    "detection rule": "sigma",
    "sigma detection rule": "sigma",
    "att&ck": "mitre att&ck",
}


@lru_cache(maxsize=1)
def _load_attack_name_lookup(corpus_path: str = "data/processed/corpus.json") -> dict:
    """Technique_id → real name from the full ATT&CK corpus, cached for process lifetime."""
    with open(corpus_path, "r", encoding="utf-8") as f:
        records = json.load(f)
    return {
        r["metadata"]["technique_id"]: r["metadata"]["name"]
        for r in records
        if r.get("source_type") == "attack" and r["metadata"].get("technique_id")
    }


def correct_technique_names(answer_text: str, retrieved_chunks: list[dict] | None = None) -> str:
    """Replace garbled / abbreviated ATT&CK names with ground-truth names from corpus."""
    name_by_id = _load_attack_name_lookup()
    cited_ids = set(re.findall(r"T\d{4}(?:\.\d{3})?", answer_text))
    for tid in cited_ids:
        correct_name = name_by_id.get(tid)
        if not correct_name:
            continue
        pattern = re.compile(rf"({re.escape(tid)}[\s\-:]+)([^\n.\[\]]+)")
        answer_text = pattern.sub(lambda m: f"{m.group(1)}{correct_name}", answer_text)
    return answer_text


def check_source_citations(answer_text: str, retrieved_chunks: list[dict]) -> list[str]:
    """
    Flag any citation where:
    (a) the cited content doesn't match anything actually retrieved, OR
    (b) the cited source TYPE is wrong (e.g. ATT&CK technique labelled as 'Playbook').

    Returns a list of human-readable flag strings (empty = no issues found).
    """
    flagged: list[str] = []

    for match in CITATION_PATTERN.finditer(answer_text):
        keyword = re.sub(r"\s+", " ", match.group(1).strip().lower())
        detail = match.group(2).strip().lower()
        full_text = match.group(0)

        # Try to find a retrieved chunk whose metadata aligns with the cited detail
        matched_chunk: Optional[dict] = None
        for c in retrieved_chunks:
            meta = c["metadata"]
            meta_values = [
                str(v).lower()
                for v in (
                    meta.get("title"),
                    meta.get("playbook"),
                    meta.get("technique_id"),
                    meta.get("name"),
                )
                if v
            ]
            if detail and any(v in detail or detail in v for v in meta_values):
                matched_chunk = c
                break

        if matched_chunk is None:
            flagged.append(f"{full_text} — no matching retrieved source")
            continue

        expected_source = TYPE_TO_SOURCE.get(keyword)
        actual_source = matched_chunk["metadata"].get("source", "").lower()
        if expected_source and expected_source not in actual_source:
            flagged.append(
                f"{full_text} — real content, but mislabeled: actually from "
                f"{matched_chunk['metadata'].get('source')}, not {match.group(1)}"
            )

    return flagged


def check_quoted_claims(answer_text: str, retrieved_chunks: list[dict]) -> list[str]:
    """
    Flag directly-quoted phrases that don't appear verbatim in any retrieved chunk.
    Excludes the draft incident summary (model's own synthesis — not a sourced claim).
    """
    checkable_text = re.split(
        r"draft incident summary", answer_text, flags=re.IGNORECASE
    )[0]
    source_texts = [c["text"].lower() for c in retrieved_chunks]
    flagged: list[str] = []
    for quote in QUOTE_PATTERN.findall(checkable_text):
        quote_clean = quote.strip().lower()
        if not any(quote_clean in text for text in source_texts):
            flagged.append(quote.strip())
    return flagged


# ── confidence scoring ─────────────────────────────────────────────────────────

def compute_confidence(
    chunks: list[dict],
    diagnostics: dict,
    flagged_citations: list[str],
    answer_text: str,
) -> dict:
    """
    Return a composite confidence dict with sub-scores and an overall [0–1] value.

    Sub-scores
    ----------
    retrieval_quality : mean final_score of the top chunks (proxy for relevance)
    source_agreement  : fraction of chunks from ≥2 distinct source types that
                        mention at least one common ATT&CK ID (higher = more
                        independent corroboration)
    citation_coverage : (valid citations) / (total citations found) — penalises
                        hallucinated source references
    semantic_best     : best semantic score in the result set
    """
    if not chunks:
        return {
            "overall": 0.0,
            "retrieval_quality": 0.0,
            "source_agreement": 0.0,
            "citation_coverage": 0.0,
            "semantic_best": 0.0,
            "grade": "insufficient",
        }

    # ── retrieval quality: mean final score ───────────────────────────────
    final_scores = [c.get("final_score", c.get("semantic_score", 0.0)) for c in chunks]
    retrieval_quality = statistics.mean(final_scores)

    # ── source agreement: ATT&CK ID co-occurrence across source types ─────
    id_by_source: dict[str, set[str]] = {}
    for c in chunks:
        src = c["metadata"].get("source", "?")
        ids_str = c["metadata"].get("technique_id") or c["metadata"].get("attack_ids") or ""
        if ids_str:
            ids = {t.strip() for t in re.split(r"[,;]", ids_str) if re.match(r"T\d{4}", t.strip())}
            id_by_source.setdefault(src, set()).update(ids)

    if len(id_by_source) >= 2:
        sources = list(id_by_source.values())
        shared_ids = sources[0]
        for other in sources[1:]:
            shared_ids = shared_ids & other
        source_agreement = min(1.0, len(shared_ids) / 3.0)  # 3 shared IDs ≈ high agreement
    else:
        source_agreement = 0.3  # single-source answers get a modest baseline

    # ── citation coverage ─────────────────────────────────────────────────
    total_citations = len(list(CITATION_PATTERN.finditer(answer_text)))
    bad_citations = len([f for f in flagged_citations if "no matching retrieved source" in f])
    if total_citations > 0:
        citation_coverage = max(0.0, (total_citations - bad_citations) / total_citations)
    else:
        citation_coverage = 0.5  # no citations at all — neutral score

    # ── semantic best ─────────────────────────────────────────────────────
    semantic_best = max((c.get("semantic_score", 0.0) for c in chunks), default=0.0)

    # ── weighted composite ────────────────────────────────────────────────
    overall = (
        0.40 * retrieval_quality
        + 0.25 * citation_coverage
        + 0.20 * source_agreement
        + 0.15 * semantic_best
    )
    overall = round(min(1.0, max(0.0, overall)), 3)

    grade = (
        "high" if overall >= 0.70
        else "medium" if overall >= 0.45
        else "low"
    )

    return {
        "overall": overall,
        "retrieval_quality": round(retrieval_quality, 3),
        "source_agreement": round(source_agreement, 3),
        "citation_coverage": round(citation_coverage, 3),
        "semantic_best": round(semantic_best, 3),
        "grade": grade,
    }


# ── main generation entry point ────────────────────────────────────────────────

def generate_answer(
    query: str,
    model_name: str = "llama3.1:8b",
    retrieval_cfg: Optional[RetrievalConfig] = None,
    k: int = 5,
) -> dict:
    """
    Full pipeline: retrieval → prompt → generate → post-process → confidence.

    Parameters
    ----------
    query          : Incident description (structured text from format_incident).
    model_name     : Ollama model identifier.
    retrieval_cfg  : Optional RetrievalConfig (defaults applied if None).
    k              : Number of chunks to return from the retrieval pipeline.

    Returns
    -------
    dict with keys:
        answer, sources, flagged_citations, unverified_quotes,
        confidence, retrieval_diagnostics, extracted_fields (populated upstream).
    """
    cfg = retrieval_cfg or RetrievalConfig(top_k=k)
    cfg.top_k = k

    # ── Stage 1: retrieval ─────────────────────────────────────────────────
    chunks, diagnostics = _retrieve(query, cfg=cfg)

    if not chunks:
        return {
            "answer": (
                "No sufficiently relevant context was found in the knowledge base "
                "for this incident description. Please provide more detail or verify "
                "that the corpus has been ingested."
            ),
            "sources": [],
            "flagged_citations": [],
            "unverified_quotes": [],
            "confidence": {
                "overall": 0.0,
                "grade": "insufficient",
                "retrieval_quality": 0.0,
                "source_agreement": 0.0,
                "citation_coverage": 0.0,
                "semantic_best": 0.0,
            },
            "retrieval_diagnostics": diagnostics,
        }

    # ── Stage 2: prompt construction ──────────────────────────────────────
    context = "\n\n---\n\n".join(c["text"] for c in chunks)
    prompt = SYSTEM_TEMPLATE.format(context=context, query=query)

    # ── Stage 3: LLM generation ────────────────────────────────────────────
    answer = call_ollama(prompt, model_name)

    # ── Stage 4: post-processing ───────────────────────────────────────────
    answer = correct_technique_names(answer, chunks)
    flagged_citations = check_source_citations(answer, chunks)
    unverified_quotes = check_quoted_claims(answer, chunks)

    # ── Stage 5: confidence scoring ────────────────────────────────────────
    confidence = compute_confidence(chunks, diagnostics, flagged_citations, answer)

    logger.info(
        "GENERATE confidence=%.3f grade=%s flagged_citations=%d unverified_quotes=%d",
        confidence["overall"],
        confidence["grade"],
        len(flagged_citations),
        len(unverified_quotes),
    )

    return {
        "answer": answer,
        "sources": [c["metadata"] for c in chunks],
        "flagged_citations": flagged_citations,
        "unverified_quotes": unverified_quotes,
        "confidence": confidence,
        "retrieval_diagnostics": diagnostics,
    }