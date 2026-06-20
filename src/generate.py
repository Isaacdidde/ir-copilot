# src/generate.py
import re

import requests
from src.retrieve import retrieve

SYSTEM_TEMPLATE = """You are a SOC incident response assistant. Answer ONLY using the context below.
You may ONLY cite these source types, and only when they actually appear in the context: 
MITRE ATT&CK, Sigma detection rules, or Internal runbook (your own playbooks).
NEVER cite external frameworks (NIST, SANS, CIS, etc.) unless their exact text appears in the context below — 
if no relevant source exists, say "no matching internal guidance found" instead of citing one.

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

def generate_answer(query, model_name="llama3.1:8b", k=5):
    chunks = retrieve(query, k=k)
    context = "\n\n---\n\n".join(c["text"] for c in chunks)
    prompt = SYSTEM_TEMPLATE.format(context=context, query=query)

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model_name, "prompt": prompt, "stream": False}
    )
    answer = response.json()["response"]

    return {"answer": answer, "sources": [c["metadata"] for c in chunks]}

ALLOWED_SOURCES = {"MITRE ATT&CK", "Sigma", "Internal runbook"}

def check_source_citations(answer_text: str) -> list:
    """Flag any cited source that isn't one of the three actually-ingested source types."""
    cited = re.findall(r"\[(?:Source|Playbook):\s*([^\]]+)\]", answer_text)
    return [c for c in cited if not any(allowed in c for allowed in ALLOWED_SOURCES)]