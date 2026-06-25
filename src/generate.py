# src/generate.py
import re
import json
from functools import lru_cache
from src.retrieve import retrieve
from src.llm import call_ollama
from functools import lru_cache
from src.retrieve import retrieve

SYSTEM_TEMPLATE = """You are a SOC incident response assistant. Answer ONLY using the context below.
You may ONLY cite these source types, and only when they actually appear in the context:
MITRE ATT&CK, Sigma detection rules, or Internal runbook (your own playbooks).
NEVER cite external frameworks (NIST, SANS, CIS, etc.) unless their exact text appears in the context below —
if no relevant source exists, say "no matching internal guidance found" instead of citing one.
Use the EXACT technique name shown in the context next to each ATT&CK ID — never paraphrase or invent a name.
Cite every source in this exact format: [Source: <exact title from context>]. Do not use any other citation style.

Context:
{context}

Incident description:
{query}

Respond in this format:
1. Likely ATT&CK techniques (with IDs)
2. Risk assessment
3. Recommended next steps (cite source for each)
4. A 2-3 sentence draft incident summary
"""

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
    """Turn structured incident fields into a normalized text block.
    Empty fields are dropped — this keeps the embedded query clean and
    avoids diluting retrieval with blank labels."""
    lines = []
    for key, label in FIELD_LABELS.items():
        value = (fields.get(key) or "").strip()
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


# ---- Post-generation grounding checks ----
# Telling the model to use one citation format doesn't guarantee it will —
# testing showed at least three different styles in the wild. These checks
# work off the actual retrieved chunks, not the model's compliance.

CITATION_PATTERN = re.compile(
    r"[\[\(]\s*(?:Source|Playbook|Detection rule|Sigma(?:\s+detection\s+rule)?|"
    r"Internal\s+runbook|Runbook|ATT&CK)\b[^\]\)]*[\]\)]",
    re.IGNORECASE
)
QUOTE_PATTERN = re.compile(r'["\u201c]([^"\u201d]{8,})["\u201d]')

@lru_cache(maxsize=1)
def _load_attack_name_lookup(corpus_path: str = "data/processed/corpus.json") -> dict:
    """Build a technique_id -> real_name map from the FULL ATT&CK corpus, once,
    cached for the process lifetime. This is the ground truth correction runs
    against — independent of what any single query happens to retrieve."""
    with open(corpus_path, "r", encoding="utf-8") as f:
        records = json.load(f)
    return {
        r["metadata"]["technique_id"]: r["metadata"]["name"]
        for r in records if r.get("source_type") == "attack"
    }

def correct_technique_names(answer_text: str, retrieved_chunks: list = None) -> str:
    """Replace any ATT&CK technique name in the answer with its real name.
    Uses the FULL ATT&CK corpus as ground truth, not just whatever chunks were
    retrieved for this query — this matters because Sigma rules tag technique
    IDs under a different metadata key (attack_ids) than ATT&CK chunks do
    (technique_id), so a query that only retrieves Sigma rules would otherwise
    have no ground-truth name to correct against even when the cited ID is real."""
    name_by_id = _load_attack_name_lookup()
    cited_ids = set(re.findall(r"T\d{4}(?:\.\d{3})?", answer_text))
    for tid in cited_ids:
        correct_name = name_by_id.get(tid)
        if not correct_name:
            continue
        pattern = re.compile(rf"({re.escape(tid)}[\s\-:]+)([^\n.\[\]]+)")
        answer_text = pattern.sub(lambda m: f"{m.group(1)}{correct_name}", answer_text)
    return answer_text

def check_source_citations(answer_text: str, retrieved_chunks: list) -> list:
    """Flag any citation — regardless of bracket/paren style — that doesn't
    match anything actually retrieved for this specific query."""
    signatures = set()
    for c in retrieved_chunks:
        meta = c["metadata"]
        for key in ("title", "playbook", "technique_id", "name", "source", "attack_ids"):
            value = meta.get(key)
            if value:
                signatures.add(value.lower())

    flagged = []
    for match in CITATION_PATTERN.finditer(answer_text):
        citation_text = match.group(0).strip("[]() ").lower()
        if not any(sig in citation_text or citation_text in sig for sig in signatures):
            flagged.append(match.group(0))
    return flagged

def check_quoted_claims(answer_text: str, retrieved_chunks: list) -> list:
    """Flag any directly-quoted phrase that doesn't appear verbatim in any
    retrieved chunk's actual text. Catches invented details (like a fabricated
    step number) even when the cited source TYPE is genuinely real."""
    source_texts = [c["text"].lower() for c in retrieved_chunks]
    flagged = []
    for quote in QUOTE_PATTERN.findall(answer_text):
        quote_clean = quote.strip().lower()
        if not any(quote_clean in text for text in source_texts):
            flagged.append(quote.strip())
    return flagged


def generate_answer(query, model_name="llama3.1:8b", k=5):
    chunks = retrieve(query, k=k)
    context = "\n\n---\n\n".join(c["text"] for c in chunks)
    prompt = SYSTEM_TEMPLATE.format(context=context, query=query)

    answer = call_ollama(prompt, model_name)
    answer = correct_technique_names(answer, chunks)  # silently fix before the analyst sees it

    return {
        "answer": answer,
        "sources": [c["metadata"] for c in chunks],
        "flagged_citations": check_source_citations(answer, chunks),
        "unverified_quotes": check_quoted_claims(answer, chunks),
    }