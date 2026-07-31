import requests
from src.retrieve import retrieve

SYSTEM_TEMPLATE = """You are a SOC incident response assistant. Answer ONLY using the context below.
If the context doesn't contain enough information, say so explicitly rather than guessing.
For every recommendation, cite its source in brackets, e.g. [ATT&CK T1059.001] or [Playbook: Suspicious PowerShell Execution].

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