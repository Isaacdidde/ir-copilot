# Building an LLM-Powered Incident Response Copilot
### A step-by-step guide using a 100% free, open-source stack

This guide builds the project in ascending order — each phase produces something testable before you move to the next. Don't skip the "checkpoint" tests; debugging a broken retrieval pipeline is much easier when you already know your embeddings work.

**Total tech stack (no paid APIs, no subscriptions):**

| Layer | Tool | 
|---|---|
| LLM | Ollama + Llama 3.1-8B / Mistral-7B / Phi-3-mini |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector DB | ChromaDB |
| Keyword search (hybrid) | rank_bm25 |
| Chunking | LangChain text splitters |
| Backend | FastAPI |
| Frontend | Streamlit |
| Knowledge sources | MITRE ATT&CK (CTI repo), Sigma rules, NIST SP 800-61, your own playbooks |

**Suggested pacing:** Phases 0–4 (week 1), Phases 5–8 (week 2), Phases 9–11 (week 3).

---

## Phase 0 — Environment setup

**Hardware check:** 8GB RAM minimum, 16GB recommended if you want to run Llama 3.1-8B comfortably. CPU-only is fine — it'll just be slower per response (a few seconds instead of under one second). No GPU required.

```bash
mkdir ir-copilot && cd ir-copilot
mkdir -p data/raw data/processed src

python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

pip install chromadb sentence-transformers langchain langchain-community \
            langchain-text-splitters fastapi uvicorn streamlit pyyaml \
            requests rank-bm25 tqdm
```

**Checkpoint:** `python -c "import chromadb, sentence_transformers; print('ok')"` should print `ok` with no errors.

---

## Phase 1 — Install and run the local LLM

```bash
# Linux / macOS
curl -fsSL https://ollama.com/install.sh | sh

# Windows: download the installer from ollama.com
```

Pull a model. Pick based on your RAM:

```bash
ollama pull phi3:mini      # ~3.8B params, runs on 8GB RAM, good for demos
ollama pull mistral:7b     # ~7B params, needs ~8-10GB RAM, better reasoning
ollama pull llama3.1:8b    # ~8B params, best quality of the three, needs ~10GB RAM
```

**Checkpoint:** test it responds:

```bash
ollama run llama3.1:8b "In one sentence, what is MITRE ATT&CK?"
```

Then confirm the REST API (this is what your Python code will call) is reachable:

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "Say hello in 5 words.",
  "stream": false
}'
```

You should get back JSON with a `"response"` field.

---

## Phase 2 — Collect free knowledge sources

```bash
cd data/raw
git clone https://github.com/mitre/cti.git
git clone https://github.com/SigmaHQ/sigma.git
cd ../..
```

This gives you:
- `data/raw/cti/enterprise-attack/enterprise-attack.json` — the full ATT&CK Enterprise dataset (STIX 2.0 format)
- `data/raw/sigma/rules/` — thousands of community detection rules, already tagged with ATT&CK technique IDs

Also download [NIST SP 800-61 Rev 2](https://csrc.nist.gov/pubs/sp/800/61/r2/final) (PDF) into `data/raw/` for general IR procedure grounding.

**Write 5–8 of your own playbooks** as markdown files in `data/raw/playbooks/`. This is also one of the strongest resume signals in the whole project — it shows you understand IR procedure, not just ML tooling. Use a consistent template:

```markdown
# Suspicious PowerShell Execution Response

## Detection criteria
Encoded or obfuscated PowerShell commands, unusual parent process,
execution outside business hours, EncodedCommand flag present.

## Immediate actions
1. Isolate the affected host from the network (do not power off — preserve memory)
2. Capture a memory image using a forensics tool before any reboot
3. Pull PowerShell Operational logs (Event ID 4104) for the decoded command
4. Check the destination IP/domain against threat intel feeds

## Escalation criteria
Escalate to Tier 2 if outbound C2-like traffic is observed or if the
host has access to domain admin credentials.

## Related ATT&CK techniques
T1059.001, T1027, T1071.001
```

**Checkpoint:** you should have ~3 source types sitting in `data/raw/`: ATT&CK JSON, Sigma YAML rules, your markdown playbooks.

---

## Phase 3 — Parse each source into plain text records

Create `src/parse_attack.py`:

```python
import json

def parse_attack(filepath="data/raw/cti/enterprise-attack/enterprise-attack.json"):
    with open(filepath, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    records = []
    for obj in bundle["objects"]:
        if obj.get("type") != "attack-pattern" or obj.get("revoked"):
            continue

        technique_id = next(
            (r["external_id"] for r in obj.get("external_references", [])
             if r.get("source_name") == "mitre-attack"),
            None
        )
        if not technique_id:
            continue

        tactics = [p["phase_name"] for p in obj.get("kill_chain_phases", [])]

        records.append({
            "id": f"attack-{technique_id}",
            "source_type": "attack",
            "technique_id": technique_id,
            "text": f"ATT&CK {technique_id} ({', '.join(tactics)}): "
                    f"{obj.get('name')}\n{obj.get('description', '')}",
            "metadata": {
                "technique_id": technique_id,
                "name": obj.get("name"),
                "tactics": ", ".join(tactics),
                "source": "MITRE ATT&CK"
            }
        })
    return records
```

Create `src/parse_sigma.py`:

```python
import yaml, glob

def parse_sigma(rules_dir="data/raw/sigma/rules"):
    records = []
    for filepath in glob.glob(f"{rules_dir}/**/*.yml", recursive=True):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                rule = yaml.safe_load(f)
        except yaml.YAMLError:
            continue
        if not rule or "title" not in rule:
            continue

        tags = rule.get("tags", [])
        attack_ids = [t.replace("attack.", "").upper() for t in tags if t.startswith("attack.t")]

        records.append({
            "id": f"sigma-{rule.get('id', filepath)}",
            "source_type": "sigma",
            "text": f"Detection rule: {rule.get('title')}\n"
                    f"{rule.get('description', '')}\n"
                    f"Log source: {rule.get('logsource', {})}\n"
                    f"Maps to: {', '.join(attack_ids) if attack_ids else 'unmapped'}",
            "metadata": {
                "title": rule.get("title"),
                "level": rule.get("level", "unknown"),
                "attack_ids": ", ".join(attack_ids),
                "source": "Sigma"
            }
        })
    return records
```

Create `src/parse_playbooks.py`:

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter
import glob

def parse_playbooks(playbook_dir="data/raw/playbooks"):
    headers_to_split_on = [("##", "section")]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)

    records = []
    for filepath in glob.glob(f"{playbook_dir}/*.md"):
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        title = text.split("\n")[0].replace("#", "").strip()
        chunks = splitter.split_text(text)

        for i, chunk in enumerate(chunks):
            section = chunk.metadata.get("section", "general")
            records.append({
                "id": f"playbook-{title}-{i}",
                "source_type": "playbook",
                "text": f"Playbook: {title} — {section}\n{chunk.page_content}",
                "metadata": {
                    "playbook": title,
                    "section": section,
                    "source": "Internal runbook"
                }
            })
    return records
```

**Checkpoint:**
```python
from src.parse_attack import parse_attack
records = parse_attack()
print(len(records), records[0])
```
You should see several hundred ATT&CK technique records.

---

## Phase 4 — Chunking and combining all sources

ATT&CK entries and Sigma rules are already atomic (one technique / one rule = one chunk). Playbooks are chunked by the markdown splitter above. Now combine everything:

```python
# src/build_corpus.py
from src.parse_attack import parse_attack
from src.parse_sigma import parse_sigma
from src.parse_playbooks import parse_playbooks
import json

def build_corpus():
    records = parse_attack() + parse_sigma() + parse_playbooks()
    with open("data/processed/corpus.json", "w") as f:
        json.dump(records, f, indent=2)
    print(f"Built corpus with {len(records)} chunks")
    return records

if __name__ == "__main__":
    build_corpus()
```

```bash
python -m src.build_corpus
```

**Checkpoint:** `data/processed/corpus.json` should exist with a few hundred to a few thousand records, depending on how many Sigma rules you included.

---

## Phase 5 — Embedding and vector store ingestion

```python
# src/ingest.py
import json
import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

def ingest():
    with open("data/processed/corpus.json") as f:
        records = json.load(f)

    model = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection(name="ir_knowledge")

    batch_size = 64
    for i in tqdm(range(0, len(records), batch_size)):
        batch = records[i:i + batch_size]
        texts = [r["text"] for r in batch]
        embeddings = model.encode(texts).tolist()

        collection.add(
            ids=[r["id"] for r in batch],
            embeddings=embeddings,
            documents=texts,
            metadatas=[r["metadata"] for r in batch]
        )

    print(f"Ingested {len(records)} chunks into ChromaDB")

if __name__ == "__main__":
    ingest()
```

```bash
python -m src.ingest
```

**Checkpoint:** run a manual query to sanity-check retrieval before building anything else on top of it:

```python
import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("ir_knowledge")

query = "encoded powershell command followed by outbound connection"
results = collection.query(query_embeddings=[model.encode(query).tolist()], n_results=5)
for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
    print(meta, "→", doc[:80])
```

If the top results are about PowerShell/execution/C2, your embedding pipeline works. If they're irrelevant, revisit chunk size or metadata prefixing before moving on.

---

## Phase 6 — Retrieval (with optional hybrid search)

```python
# src/retrieve.py
import chromadb
from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("all-MiniLM-L6-v2")
_client = chromadb.PersistentClient(path="./chroma_db")
_collection = _client.get_collection("ir_knowledge")

def retrieve(query, k=5):
    query_embedding = _model.encode(query).tolist()
    results = _collection.query(query_embeddings=[query_embedding], n_results=k)

    chunks = []
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        chunks.append({"text": doc, "metadata": meta, "score": 1 - dist})
    return chunks
```

**Optional hybrid search** — add this if your test queries involve exact identifiers (CVE numbers, hashes, IPs) that pure semantic search handles poorly:

```python
# src/hybrid_retrieve.py
from rank_bm25 import BM25Okapi
import json

with open("data/processed/corpus.json") as f:
    _records = json.load(f)
_tokenized = [r["text"].lower().split() for r in _records]
_bm25 = BM25Okapi(_tokenized)

def hybrid_retrieve(query, k=5, alpha=0.5):
    from src.retrieve import retrieve as semantic_retrieve
    semantic_results = semantic_retrieve(query, k=k * 2)

    bm25_scores = _bm25.get_scores(query.lower().split())
    bm25_by_id = {r["id"]: s for r, s in zip(_records, bm25_scores)}

    for r in semantic_results:
        # combine normalized semantic score with bm25 score
        r["combined_score"] = alpha * r["score"] + (1 - alpha) * bm25_by_id.get(r["metadata"].get("id", ""), 0)

    return sorted(semantic_results, key=lambda x: x["combined_score"], reverse=True)[:k]
```

---

## Phase 7 — Grounded generation via the local LLM

The prompt design here is what prevents hallucination — be explicit that the model must only use the provided context.

```python
# src/generate.py
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
```

**Checkpoint:**
```python
from src.generate import generate_answer
result = generate_answer("Encoded PowerShell command on a workstation at 2am, followed by an outbound connection to an unfamiliar IP")
print(result["answer"])
```

---

## Phase 8 — Backend API

```python
# src/api.py
from fastapi import FastAPI
from pydantic import BaseModel
from src.generate import generate_answer

app = FastAPI(title="IR Copilot API")

class IncidentQuery(BaseModel):
    incident_description: str

@app.post("/query")
def query_copilot(q: IncidentQuery):
    return generate_answer(q.incident_description)
```

```bash
uvicorn src.api:app --reload --port 8000
```

---

## Phase 9 — Frontend

```python
# src/app.py
import streamlit as st
import requests

st.set_page_config(page_title="IR Copilot")
st.title("Incident Response Copilot")
st.caption("Free, local, RAG-grounded — no data leaves your machine")

incident = st.text_area("Describe the alert or incident", height=120)

if st.button("Analyze") and incident:
    with st.spinner("Retrieving context and reasoning..."):
        resp = requests.post("http://localhost:8000/query", json={"incident_description": incident})
        data = resp.json()

    st.markdown(data["answer"])
    with st.expander(f"Sources used ({len(data['sources'])})"):
        for s in data["sources"]:
            st.json(s)
```

```bash
streamlit run src/app.py
```

You now have a working end-to-end local copilot: type an incident, get a grounded, citable response.

---

## Phase 10 — Evaluation harness

This is the step that turns "I built a chatbot" into "I built and measured a system" — the difference that matters in interviews.

```python
# eval/golden_set.json
[
  {"query": "encoded powershell command then outbound connection to unknown ip", "expected_techniques": ["T1059.001", "T1071.001"]},
  {"query": "phishing email with malicious macro-enabled attachment", "expected_techniques": ["T1566.001", "T1204.002"]},
  {"query": "scheduled task created for persistence after reboot", "expected_techniques": ["T1053.005"]}
]
```

```python
# eval/run_eval.py
import json
from src.retrieve import retrieve

def recall_at_k(golden_path="eval/golden_set.json", k=5):
    with open(golden_path) as f:
        golden_set = json.load(f)

    total_expected = 0
    total_hit = 0
    for item in golden_set:
        retrieved = retrieve(item["query"], k=k)
        retrieved_ids = {c["metadata"].get("technique_id") for c in retrieved if c["metadata"].get("technique_id")}
        expected = set(item["expected_techniques"])

        total_hit += len(retrieved_ids & expected)
        total_expected += len(expected)

    score = total_hit / total_expected if total_expected else 0
    print(f"Recall@{k}: {score:.2%}")
    return score

if __name__ == "__main__":
    recall_at_k()
```

Expand the golden set to 20–30 examples covering different attack categories. Run this every time you change chunk size, embedding model, or k — track the number over time. That history is itself a great thing to show in your README ("recall@5 improved from 71% to 89% after switching to header-aware chunking").

---

## Phase 11 — Polish for portfolio

**README structure:**
1. One-paragraph problem statement (the SOC pain point this solves)
2. Architecture diagram (you can reuse the structure of the diagrams from this conversation)
3. Tech stack table — emphasize it's 100% free/local, no API keys required
4. Setup instructions (copy from this guide)
5. Eval results table (recall@k before/after tuning)
6. A real example: paste an incident description and the actual output
7. Limitations section — be upfront about what hybrid search doesn't solve, what the local LLM struggles with on complex multi-step reasoning, etc. This signals maturity, not weakness.

**Demo:** record a 60–90 second screen capture of typing an incident and getting a grounded response with visible citations — this is what actually gets watched on LinkedIn, far more than a wall of GitHub code.

**Repo structure:**
```
ir-copilot/
├── data/
│   ├── raw/            # gitignored except your own playbooks
│   └── processed/
├── src/
│   ├── parse_attack.py
│   ├── parse_sigma.py
│   ├── parse_playbooks.py
│   ├── build_corpus.py
│   ├── ingest.py
│   ├── retrieve.py
│   ├── generate.py
│   ├── api.py
│   └── app.py
├── eval/
│   ├── golden_set.json
│   └── run_eval.py
├── requirements.txt
└── README.md
```

**Interview talking points this build earns you:**
- Why RAG over fine-tuning for this use case (cost, freshness, grounding/citability)
- Chunking strategy decisions and how you validated them with recall@k
- Where pure semantic search fails (IOCs, CVEs) and how hybrid search addresses it
- How the system prompt prevents hallucinated playbook steps
- What you'd add with more time (reranking model, conversation memory, SOAR integration for auto-execution with human approval)