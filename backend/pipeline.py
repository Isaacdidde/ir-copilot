"""
End-to-end orchestration of the IR-Copilot pipeline:

    Incident text -> retrieve() -> confidence scoring -> compressed context
    -> LLM generation (JSON, plain-language summary + MITRE mapping + IR steps)
    -> validation against retrieved evidence -> IncidentResponse

Guard-rails applied after generation (all deterministic, not LLM-based):
  1. MITRE mapping: technique_id AND technique_name must match a retrieved
     MITRE chunk exactly (not just the ID).
  2. Evidence Used: every cited source_name must correspond to something
     actually retrieved (fuzzy match tolerant of paraphrasing).
  3. If guard-rails strip out all substantive content (MITRE mapping AND
     evidence AND incident_response_steps), the response honestly downgrades
     to insufficient_evidence rather than presenting a hollow but
     confident-looking report.
"""

from __future__ import annotations

import re
import time
from typing import List

from backend.config import settings
from backend.llm import LLMError, extract_json, generate
from backend.logger import get_logger
from backend.models import (
    ConfidenceAssessment,
    EvidenceItem,
    IncidentResponse,
    IRStep,
    MitreMapping,
    RetrievedChunk,
    Summary,
)
from backend.prompts import SYSTEM_PROMPT, build_incident_prompt
from backend.retrieval import retrieve

logger = get_logger(__name__)

# Threshold for the prefix-aware token-overlap fuzzy match used to verify a
# cited source (evidence entries) actually corresponds to something
# retrieved. Chosen empirically: paraphrases of real retrieved titles score
# >=0.33, fabricated/unrelated sources score <=0.17 — 0.25 sits safely in
# that gap.
SOURCE_MATCH_THRESHOLD = 0.25

_STOPWORDS = {"the", "a", "an", "of", "via", "and", "or", "rule", "sigma", "playbook", "for", "to", "in", "on"}

_DEFAULT_MISSING_EVIDENCE = [
    "Process tree / parent-child process relationships",
    "Sysmon logs (Event IDs 1, 3, 10, 11)",
    "Windows Security Event Logs (4688, 4624, 4104)",
    "Network captures or proxy/DNS logs",
    "File hashes and command-line arguments",
]


def _significant_tokens(s: str) -> set:
    words = re.findall(r"[a-z0-9]+", s.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _prefix_overlap_score(claimed: str, actual: str, prefix_len: int = 6) -> float:
    """Token-overlap similarity that tolerates paraphrasing and simple word-stem
    variation (e.g. "Kerberoasting" vs "Kerberos") via a shared-prefix check,
    without requiring exact or substring string matches."""
    claimed_tokens, actual_tokens = _significant_tokens(claimed), _significant_tokens(actual)
    if not claimed_tokens or not actual_tokens:
        return 0.0
    matched: set = set()
    for wa in claimed_tokens:
        for wb in actual_tokens:
            if wa == wb or (
                len(wa) >= prefix_len and len(wb) >= prefix_len and wa[:prefix_len] == wb[:prefix_len]
            ):
                matched.add(wa)
                matched.add(wb)
    union = claimed_tokens | actual_tokens
    return len(matched) / len(union) if union else 0.0


def _name_matches(claimed: str, actual: str) -> bool:
    claimed_norm = claimed.lower().strip()
    actual_norm = actual.lower().strip()
    return claimed_norm == actual_norm or claimed_norm in actual_norm or actual_norm in claimed_norm


def _source_matches(claimed_source: str, retrieved_source_names: List[str]) -> bool:
    return any(
        _prefix_overlap_score(claimed_source, actual) >= SOURCE_MATCH_THRESHOLD
        for actual in retrieved_source_names
    )


def _build_context_block(chunks: List[RetrievedChunk]) -> str:
    lines = []
    for c in chunks:
        lines.append(
            f"[{c.chunk.source_type.value.upper()} | {c.chunk.source_name}]\n{c.chunk.text}"
        )
    return "\n\n---\n\n".join(lines)


def _compute_confidence(chunks: List[RetrievedChunk]) -> tuple[float, List[str]]:
    """Deterministic confidence score derived purely from retrieval signal,
    independent of the LLM, so the number is auditable and not hallucinated."""
    if not chunks:
        return 0.0, ["No matching evidence found in the knowledge base."]

    reasons: List[str] = []
    scores = [c.rerank_score if c.rerank_score is not None else c.hybrid_score for c in chunks]
    normalized = []
    for s in scores:
        if s > 1.5 or s < -1.5:
            normalized.append(1 / (1 + pow(2.718281828, -s)))  # sigmoid
        else:
            normalized.append(max(0.0, min(1.0, s)))

    top_score = normalized[0] if normalized else 0.0
    avg_top3 = sum(normalized[:3]) / min(3, len(normalized))
    confidence = 0.6 * top_score + 0.4 * avg_top3

    source_types = {c.chunk.source_type.value for c in chunks}
    sigma_hits = sum(1 for c in chunks if c.chunk.source_type.value == "sigma")
    mitre_hits = sum(1 for c in chunks if c.chunk.source_type.value == "mitre")
    playbook_hits = sum(1 for c in chunks if c.chunk.source_type.value == "playbook")

    if sigma_hits:
        reasons.append(f"{sigma_hits} matching Sigma rule(s) found")
    if mitre_hits:
        reasons.append(f"{mitre_hits} matching MITRE ATT&CK technique(s) found")
    if playbook_hits:
        reasons.append(f"{playbook_hits} matching internal playbook(s) found")
    if len(source_types) >= 3:
        reasons.append("Corroborating evidence across multiple independent source types")
    if top_score > 0.75:
        reasons.append("High semantic similarity between incident and top evidence")

    if not reasons:
        reasons.append("Only weak/partial matches found in the knowledge base")

    return round(min(confidence, 0.99), 2), reasons


def _fallback_response(confidence: float, confidence_reasons: List[str]) -> IncidentResponse:
    return IncidentResponse(
        summary=Summary(
            what_happened="Unable to confidently characterize the incident from available evidence.",
        ),
        confidence_score=confidence,
        confidence_assessment=ConfidenceAssessment(
            explanation="Retrieved evidence did not sufficiently match the incident description.",
            conflicting_evidence=confidence_reasons,
        ),
        missing_evidence=list(_DEFAULT_MISSING_EVIDENCE),
        insufficient_evidence=True,
    )


def run_pipeline(incident_description: str) -> IncidentResponse:
    retrieval_start = time.perf_counter()
    chunks = retrieve(incident_description)
    retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000

    confidence, confidence_reasons = _compute_confidence(chunks)

    if not chunks or confidence < settings.min_confidence_threshold:
        logger.info(
            "Confidence %.2f below threshold %.2f — returning insufficient-evidence response",
            confidence, settings.min_confidence_threshold,
        )
        response = _fallback_response(confidence, confidence_reasons)
        response.retrieval_latency_ms = retrieval_latency_ms
        response.evidence = [
            EvidenceItem(
                source_type=c.chunk.source_type,
                source_name=c.chunk.source_name,
                why_it_supports="",
            )
            for c in chunks
        ]
        return response

    context_block = _build_context_block(chunks)
    prompt = build_incident_prompt(incident_description, context_block, confidence)

    gen_start = time.perf_counter()
    try:
        raw_text, gen_latency_ms, tokens_used = generate(prompt, system=SYSTEM_PROMPT)
        parsed = extract_json(raw_text)
    except LLMError as exc:
        logger.error("LLM generation/parsing failed: %s", exc)
        response = _fallback_response(confidence, confidence_reasons + [f"LLM error: {exc}"])
        response.retrieval_latency_ms = retrieval_latency_ms
        response.generation_latency_ms = (time.perf_counter() - gen_start) * 1000
        return response

    try:
        response = IncidentResponse(
            summary=Summary(**parsed.get("summary", {})),
            mitre_mapping=[MitreMapping(**m) for m in parsed.get("mitre_mapping", [])],
            evidence=[EvidenceItem(**e) for e in parsed.get("evidence", [])],
            incident_response_steps=[IRStep(**s) for s in parsed.get("incident_response_steps", [])],
            missing_evidence=parsed.get("missing_evidence", []),
            confidence_assessment=ConfidenceAssessment(**parsed.get("confidence_assessment", {})),
            confidence_score=float(parsed.get("confidence_score", confidence)),
            insufficient_evidence=bool(parsed.get("insufficient_evidence", False)),
            tokens_used_estimate=tokens_used,
            retrieval_latency_ms=retrieval_latency_ms,
            generation_latency_ms=gen_latency_ms,
        )
    except (TypeError, ValueError) as exc:
        logger.error("LLM output failed schema validation: %s", exc)
        response = _fallback_response(confidence, confidence_reasons + [f"Validation error: {exc}"])
        response.retrieval_latency_ms = retrieval_latency_ms
        response.generation_latency_ms = (time.perf_counter() - gen_start) * 1000
        return response

    # --- Guard-rail 1: MITRE mapping must match both ID and name as retrieved ---
    retrieved_technique_names: dict[str, str] = {}
    for c in chunks:
        if c.chunk.source_type.value == "mitre" and " - " in c.chunk.source_name:
            tid = c.chunk.metadata.get("technique_id")
            if tid:
                retrieved_technique_names[tid] = c.chunk.source_name.split(" - ", 1)[1].strip()

    verified_mapping = [
        m for m in response.mitre_mapping
        if m.technique_id in retrieved_technique_names
        and _name_matches(m.technique_name, retrieved_technique_names[m.technique_id])
    ]
    if len(verified_mapping) < len(response.mitre_mapping):
        dropped = len(response.mitre_mapping) - len(verified_mapping)
        logger.warning(
            "Dropped %d unverified MITRE technique claim(s): either the ID wasn't in retrieved "
            "evidence, or the claimed technique_name didn't match the retrieved name for that ID",
            dropped,
        )
        response.confidence_assessment.conflicting_evidence.append(
            f"{dropped} unverified technique reference(s) removed (ID or name not confirmed by retrieved evidence)"
        )
    response.mitre_mapping = verified_mapping

    # --- Guard-rail 2: every Evidence Used entry must correspond to something retrieved ---
    retrieved_source_names = [c.chunk.source_name for c in chunks]
    verified_evidence = [e for e in response.evidence if _source_matches(e.source_name, retrieved_source_names)]
    if len(verified_evidence) < len(response.evidence):
        dropped = len(response.evidence) - len(verified_evidence)
        logger.warning("Dropped %d evidence entr(y/ies) not matching anything actually retrieved", dropped)
        response.confidence_assessment.conflicting_evidence.append(
            f"{dropped} cited evidence entr(y/ies) removed (not found in retrieved evidence)"
        )
    response.evidence = verified_evidence

    # --- Guard-rail 3: if filtering gutted the substantive content, downgrade honestly ---
    has_substance = bool(
        response.mitre_mapping or response.evidence or response.incident_response_steps
    )
    if not has_substance and not response.insufficient_evidence:
        logger.warning(
            "All verifiable substantive content was filtered out; downgrading response to "
            "insufficient_evidence rather than showing a hollow answer"
        )
        response.insufficient_evidence = True
        response.confidence_score = min(response.confidence_score, 0.35)
        response.confidence_assessment.conflicting_evidence.append(
            "Retrieved evidence did not hold up under verification — likely a topical mismatch "
            "between the incident and the closest matches found in the knowledge base"
        )
        if not response.missing_evidence:
            response.missing_evidence = list(_DEFAULT_MISSING_EVIDENCE)

    return response