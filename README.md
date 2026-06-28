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