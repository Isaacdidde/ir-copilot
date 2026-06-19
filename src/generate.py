# src/generate.py
import requests
from src.retrieve import retrieve

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.1:8b"

SYSTEM_TEMPLATE = """You are a SOC incident response assistant. 

STRICT RULES:
- Answer ONLY using the context provided below. 
- Do NOT cite any source that does not appear in the context.
- If the context lacks enough information, say: "Insufficient context to assess this fully."
- Every recommended action MUST include a citation in brackets from the context only.
  Valid citation formats: [ATT&CK T1059.001] or [Sigma: Rule Title] or [Playbook: Title]

=== CONTEXT START ===
{context}
=== CONTEXT END ===

Incident Description:
{query}

Respond strictly in this format — no extra sections:

1. LIKELY ATT&CK TECHNIQUES
   - <Technique ID> (<tactic>): <brief reason>

2. RISK ASSESSMENT
   <2-3 sentences: severity, blast radius, urgency>

3. RECOMMENDED NEXT STEPS
   - <Action> [Source]
   - <Action> [Source]

4. INCIDENT SUMMARY
   <2-3 sentence draft for ticket/escalation>
"""

def build_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into a clean numbered context block."""
    sections = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        source_label = (
            f"ATT&CK {meta.get('technique_id', '')}"
            if meta.get("source") == "MITRE ATT&CK"
            else f"Sigma: {meta.get('title', '')}"
            if meta.get("source") == "Sigma"
            else f"Playbook: {meta.get('playbook', '')}"
        )
        sections.append(f"[{i}] {source_label}\n{chunk['text']}")
    return "\n\n---\n\n".join(sections)


def call_ollama(prompt: str, model: str, timeout: int = 120) -> str:
    """Call Ollama API with error handling and timeout."""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return "ERROR: Cannot connect to Ollama. Is it running? Run: ollama serve"
    except requests.exceptions.Timeout:
        return f"ERROR: Ollama timed out after {timeout}s. Try a smaller model like phi3:mini."
    except requests.exceptions.HTTPError as e:
        return f"ERROR: Ollama returned HTTP {e.response.status_code}. Check model name."
    except (KeyError, ValueError):
        return "ERROR: Unexpected response format from Ollama."


def generate_answer(
    query: str,
    model_name: str = DEFAULT_MODEL,
    k: int = 5
) -> dict:
    """
    Retrieve relevant chunks and generate a grounded incident response.

    Returns:
        {
            "answer": str,
            "sources": list[dict],
            "query": str,
            "chunks_used": int,
            "error": bool
        }
    """
    chunks = retrieve(query, k=k)

    if not chunks:
        return {
            "answer": "No relevant context found in the knowledge base for this query.",
            "sources": [],
            "query": query,
            "chunks_used": 0,
            "error": True
        }

    context = build_context(chunks)
    prompt = SYSTEM_TEMPLATE.format(context=context, query=query)
    answer = call_ollama(prompt, model=model_name)

    return {
        "answer": answer,
        "sources": [c["metadata"] for c in chunks],
        "query": query,
        "chunks_used": len(chunks),
        "error": answer.startswith("ERROR:")
    }