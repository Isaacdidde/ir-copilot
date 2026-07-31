<<<<<<< HEAD
# IR-Copilot — Evidence-Grounded RAG Incident Response Assistant

IR-Copilot is a production-oriented, retrieval-augmented (RAG) assistant for SOC
analysts. Given an incident description, it retrieves only the most relevant
knowledge from a local knowledge base (MITRE ATT&CK, Sigma rules, NIST SP 800-61,
and internal playbooks) and generates a structured, evidence-cited response.
It is **not** a chatbot — there is no open-ended conversation, no memory by
default, and every recommendation must trace back to retrieved evidence.

## Why it's built this way

- **Low hallucination**: the LLM is only ever shown the top-K compressed,
  reranked chunks and is instructed to cite a source for every claim. A
  post-generation guard-rail (`backend/pipeline.py`) strips any MITRE technique
  the model claims that isn't actually present in the retrieved evidence.
- **Low token usage**: query expansion is done with a local keyword map (no LLM
  call), retrieval uses hybrid dense+BM25 search with a cross-encoder reranker
  to aggressively narrow to Top-5 chunks, context is deduplicated and truncated
  to a character budget, and embeddings/retrieval results are cached so
  repeated or unchanged content is never re-processed.
- **Fast retrieval**: ChromaDB (persistent, local) for dense search, `rank_bm25`
  for keyword search, fused with a configurable weighting, then reranked with
  `bge-reranker-base`.
- **Deterministic confidence score**: the confidence percentage shown to the
  analyst is computed directly from retrieval signal (rerank/hybrid scores,
  number of matching source types), not from the LLM — so it's auditable and
  can't be hallucinated.

## Architecture

```
backend/        FastAPI app, RAG pipeline, retrieval, embeddings, vector store, LLM client
frontend/       Streamlit UI (dark theme, cards, badges, progress bars)
knowledge/      MITRE ATT&CK techniques (JSON), Sigma rules (YAML), NIST summary (Markdown)
playbooks/      Custom incident response playbooks (Markdown)
embeddings/     On-disk embedding cache (content-hash keyed)
data/chroma/    Persistent ChromaDB store
evaluation/     Recall@K / Precision@K / Faithfulness / Hallucination-rate harness
tests/          Unit tests (ingestion, cache, LLM JSON parsing)
```

### Processing pipeline

```
Incident text
   -> Query Expansion (local keyword map, no LLM call)
   -> Hybrid Retrieval (ChromaDB dense search + BM25 keyword search)
   -> Metadata Filtering (optional source_type filters)
   -> Fusion (weighted dense/BM25 combination)
   -> Deduplication (content-hash based)
   -> Reranking (bge-reranker-base cross-encoder)
   -> Context Compression (char budget truncation)
   -> Deterministic Confidence Scoring
   -> LLM Generation (JSON-only, evidence-constrained prompt)
   -> Schema Validation + Hallucination Guard-rail
   -> Structured IncidentResponse
```

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) running locally with a pulled model (default: `llama3.1:8b`)
- ~2GB disk for the embedding + reranker models on first run (downloaded from
  Hugging Face the first time `backend/embeddings.py` / `backend/retrieval.py`
  load them; cached locally afterward, and re-embedding is skipped for unchanged
  content thereafter)

## Setup

```bash
git clone <this-repo> && cd ir-copilot
cp .env.example .env         # adjust model names / ports as needed
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# In a separate terminal:
ollama pull llama3.1:8b
ollama serve

# Then, from the project root:
./run_local.sh
```

This starts:
- FastAPI backend at `http://localhost:8000` (docs at `/docs`)
- Streamlit frontend at `http://localhost:8501`

On backend startup, the knowledge base is automatically indexed into ChromaDB
(unchanged content is skipped on subsequent restarts thanks to content-hash
based caching).

### Docker

```bash
docker compose up --build
```

Pulls/starts Ollama, the FastAPI backend, and the Streamlit frontend as three
containers. After the stack is up, pull the model into the Ollama container:

```bash
docker exec -it ir-copilot-ollama ollama pull llama3.1:8b
```

## API

| Method | Path           | Description                                      |
|--------|----------------|---------------------------------------------------|
| GET    | `/health`      | Liveness check                                     |
| GET    | `/kb/status`   | Indexed document counts, model names, DB status    |
| POST   | `/kb/reindex`  | Re-scan knowledge sources; only embeds new/changed |
| POST   | `/analyze`     | `{"incident_description": "..."}` → structured IR response |

## Adding knowledge

- **MITRE**: add entries to `knowledge/mitre/techniques.json` (or additional
  `.json` files in that directory) following the existing schema.
- **Sigma**: drop `.yml`/`.yaml` rule files into `knowledge/sigma/`. Include a
  `mitre_technique` and `recommended_actions` field so the pipeline can cite
  and cross-verify them.
- **NIST / general guidance**: Markdown files in `knowledge/nist/`.
- **Playbooks**: Markdown files in `playbooks/`.

Call `POST /kb/reindex` (or restart the backend) after adding files. Only
new or changed content is embedded — existing chunks are detected by content
hash and skipped.

## Evaluation

```bash
python3 evaluation/evaluate.py
```

Reports Recall@K, Precision@K, Context Precision, Faithfulness, and
Hallucination Rate against the hand-labeled cases in `evaluation/gold_set.json`.
Extend that file with more (query, relevant_source_names) pairs as the
knowledge base grows.

## Tests

```bash
pytest
```

Unit tests cover ingestion/chunking correctness, TTL/LRU cache behavior, and
LLM JSON-extraction robustness. These run without requiring Ollama or a
downloaded embedding model. Retrieval- and pipeline-level integration tests
require network access to Hugging Face (to fetch `BAAI/bge-small-en-v1.5` and
`BAAI/bge-reranker-base` on first run) and a running Ollama instance.

## Hallucination-prevention guarantees

- The model is only shown retrieved evidence — never asked to answer from
  general knowledge.
- Every `mitre_mapping` entry is cross-checked against the technique IDs
  actually present in the retrieved context; unverified entries are silently
  dropped and logged.
- If retrieval confidence falls below `IRCOPILOT_MIN_CONFIDENCE_THRESHOLD`
  (default 0.55), the LLM is skipped entirely and the app returns an
  "insufficient evidence" response asking the analyst for more data —
  it never fabricates a plausible-sounding answer under uncertainty.
=======
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
>>>>>>> 326706cccf9f786f08d08bf1ba939322089287f0
