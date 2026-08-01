# IR-Copilot

**Evidence-grounded, RAG-based incident response assistant for SOC analysts.**

IR-Copilot takes a plain-language incident description and returns a concise, strictly
evidence-grounded analysis: what's likely happening, the matching MITRE ATT&CK technique,
the exact Sigma rules / MITRE entries / NIST guidance / playbooks that support the
conclusion, and concrete incident response steps — grouped by Identification,
Containment, Eradication, and Recovery.

It is deliberately conservative: if the retrieved evidence doesn't confidently match the
incident, it says so (`insufficient_evidence: true`) instead of guessing. Every claim in
the response is checked against what was actually retrieved before being shown to the
analyst — nothing is generated purely from the model's own training knowledge.

---

## How it works

```
Incident description
        │
        ▼
  Hybrid retrieval (dense + BM25) over the knowledge base
        │
        ▼
  Rerank + deterministic confidence scoring
        │
        ▼
  Below threshold? ──► return insufficient-evidence response, no LLM call
        │
        ▼ (above threshold)
  LLM generation (Groq or local Ollama) — strict JSON schema, grounded prompt
        │
        ▼
  Guard-rails (deterministic, not LLM-based):
    • MITRE mapping must match a retrieved technique ID + name exactly
    • Evidence citations must correspond to something actually retrieved
    • Response steps must not be empty when insufficient_evidence=false
    • If verification strips out all substance, honestly downgrade to
      insufficient_evidence rather than show a hollow report
        │
        ▼
  Structured response → Streamlit UI
```

**Knowledge base:**
- **MITRE ATT&CK** — full Enterprise STIX bundle (~700 techniques)
- **Sigma rules** — SigmaHQ's public detection rule set (~3,700+ rules)
- **NIST SP 800-61r2** — Computer Security Incident Handling Guide
- **Internal playbooks** — your own markdown/text playbooks (bring your own)

**Stack:** FastAPI backend, Streamlit frontend, ChromaDB vector store, hybrid dense +
BM25 retrieval with a BGE reranker, and a pluggable LLM layer (Groq hosted API or local
Ollama).

---

## Project structure

```
ir-copilot/
├── backend/
│   ├── main.py              # FastAPI app entrypoint
│   ├── pipeline.py          # Retrieval → generation → guard-rails orchestration
│   ├── prompts.py           # System prompt + JSON schema + grounding rules
│   ├── models.py            # Pydantic schemas (request/response)
│   ├── llm.py                # Groq / Ollama LLM client
│   ├── retrieval.py         # Hybrid dense + BM25 retrieval, reranking
│   ├── embeddings.py        # Embedding model loading + caching
│   ├── vectorstore.py       # ChromaDB wrapper, indexing
│   ├── mitre_stix_loader.py
│   ├── sigma_bulk_loader.py
│   ├── nist_pdf_loader.py
│   ├── ingestion.py          # Chunk loading across all sources
│   └── config.py             # Central settings (env-driven)
├── frontend/
│   └── app.py                 # Streamlit UI
├── knowledge/
│   ├── mitre/                 # MITRE STIX bundle (not committed — see setup)
│   ├── sigma/sigma-repo/      # SigmaHQ clone (not committed — see setup)
│   └── nist/                  # NIST SP 800-61 PDF (not committed — see setup)
├── playbooks/                  # Your internal playbooks (markdown/text)
├── .env.example
├── .gitignore
└── requirements.txt
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Isaacdidde/ir-copilot.git
cd ir-copilot
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### 3. Fetch the knowledge base

This repo does **not** include the knowledge base or vector store — it's too large for
git and is fully regenerable. Fetch each source locally:

**Sigma rules:**
```bash
git clone https://github.com/SigmaHQ/sigma.git knowledge/sigma/sigma-repo
```

**MITRE ATT&CK Enterprise STIX bundle:**
```bash
curl -o knowledge/mitre/enterprise-attack.json ^
  https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json
```

**NIST SP 800-61r2:**
```bash
curl -o knowledge/nist/NIST.SP.800-61r2.pdf ^
  https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r2.pdf
```

**Playbooks:** drop your own incident response playbooks (markdown or text) into
`playbooks/`. A handful of examples are recommended to start.

### 4. Configure environment variables

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
```

Edit `.env` and set at minimum:

```dotenv
IRCOPILOT_LLM_PROVIDER=groq
IRCOPILOT_GROQ_API_KEY=your_key_here     # free tier: https://console.groq.com/keys
IRCOPILOT_GROQ_MODEL=openai/gpt-oss-20b
IRCOPILOT_LLM_MAX_TOKENS=2800
```

Or, to run fully local with no external API calls:

```dotenv
IRCOPILOT_LLM_PROVIDER=ollama
IRCOPILOT_OLLAMA_BASE_URL=http://localhost:11434
IRCOPILOT_LLM_MODEL=llama3.1:8b
```
(requires `ollama serve` running locally with the model pulled)

See `.env.example` for the full list of tunable settings — retrieval thresholds,
top-k, embedding/reranker models, etc.

### 5. Start the backend

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

On first startup, this will chunk and index the entire knowledge base into ChromaDB.
With the full MITRE + Sigma + NIST set (~4,600+ chunks), initial indexing typically
takes a few minutes. Subsequent restarts skip re-indexing unless the source content
changed.

### 6. Start the frontend

In a separate terminal:

```bash
streamlit run frontend/app.py
```

Open the URL Streamlit prints (typically `http://localhost:8501`).

---

## Usage

Paste an incident description into the text box and click **Analyze incident**. Example:

```
Detected multiple Kerberos ticket-granting service requests (Event ID 4769) using
RC4 encryption (etype 0x17) for privileged service accounts, requested by a single
non-privileged user account within a short time window. This pattern is consistent
with Kerberoasting, an offline password-cracking technique targeting service account
credentials via their Kerberos service tickets.
```

The response includes:
- **Situation Report** — plain-language explanation with a confidence stamp
- **MITRE ATT&CK Mapping** — technique ID, name, tactic, confidence, evidence source
- **Evidence Used** — the specific Sigma rules / MITRE entries / NIST sections / playbooks that support the finding
- **Response Sequence** — concrete steps grouped by Identification → Containment → Eradication → Recovery
- **Missing Evidence** — what would improve confidence, when applicable
- **Confidence Assessment** — plain-language reasoning, including any caveats (e.g. a scheduled maintenance window that could indicate a false positive)

If the retrieved evidence doesn't confidently match the incident, IR-Copilot returns an
honest **insufficient evidence** response rather than a confident-looking guess.

---

## Configuration reference

Key environment variables (see `.env.example` for the complete list):

| Variable | Purpose |
|---|---|
| `IRCOPILOT_LLM_PROVIDER` | `groq` or `ollama` |
| `IRCOPILOT_GROQ_API_KEY` | Required if using Groq |
| `IRCOPILOT_LLM_MAX_TOKENS` | Completion token budget — raise if you see `max completion tokens reached` errors |
| `IRCOPILOT_MIN_CONFIDENCE_THRESHOLD` | Retrieval confidence floor below which the pipeline returns `insufficient_evidence` without calling the LLM. Tune down if using a small/sample knowledge base rather than the full set. |
| `IRCOPILOT_FINAL_TOP_K` | Number of retrieved chunks passed to the LLM as context |

**Note on Groq's free tier:** the free tier enforces an 8,000 tokens-per-minute limit.
If you see `400` errors mentioning `rate_limit_exceeded` or `max completion tokens
reached before generating a valid document`, either raise `IRCOPILOT_LLM_MAX_TOKENS`
(if generation is being cut off) or reduce `IRCOPILOT_FINAL_TOP_K` / your prompt size
(if you're hitting the per-minute cap), or space out requests.

---

## Known issues

- ChromaDB's PostHog telemetry occasionally logs harmless
  `Failed to send telemetry event... capture() takes 1 positional argument but 3 were
  given` warnings on startup. This is a version mismatch in ChromaDB's telemetry client
  and does not affect functionality — safe to ignore, or disable telemetry in your
  Chroma client settings.

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.

This repository references external cybersecurity knowledge sources. These resources retain their own licenses and are not redistributed as part of this repository:

- SigmaHQ Rules — Detection Rule License (DRL) 1.1
- MITRE ATT&CK® — Creative Commons Attribution 4.0 (CC BY 4.0)
- NIST SP 800-61 Revision 2 — U.S. Government publication (Public Domain)
