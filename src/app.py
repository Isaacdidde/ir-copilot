from __future__ import annotations
import re
import html
import streamlit as st
import requests

st.set_page_config(
    page_title="IR Copilot",
    page_icon="🛡️",
    layout="centered",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;0,500;0,600;1,400&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg:        #0b0c0f;
    --bg-2:      #111317;
    --surface:   #16181d;
    --surface-2: #1c1f26;
    --border:    #2a2d35;
    --border-2:  #34373f;
    --text:      #e8e9ec;
    --text-dim:  #9a9ea8;
    --text-faint:#6b6f78;
    --accent:    #5b8def;
    --accent-2:  #7ea6f4;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }

html, body,
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"] {
    background: var(--bg) !important;
    color: var(--text) !important;
}

.block-container {
    padding: 4rem 2rem 6rem;
    max-width: 760px;
}

.ir-brand {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 0.35rem;
}
.ir-shield {
    width: 36px; height: 36px;
    background: var(--surface-2);
    border: 1px solid var(--border-2);
    border-radius: 9px;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px;
    flex-shrink: 0;
}
.ir-brand h1 {
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--text);
    margin: 0;
    letter-spacing: -0.01em;
}
.ir-sub {
    font-size: 0.85rem;
    color: var(--text-dim);
    margin: 0 0 2.5rem 48px;
}

div[data-testid="stTextArea"] {
    background: var(--surface) !important;
    border: 1.5px solid var(--border-2) !important;
    border-radius: 14px !important;
    padding: 4px !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.30) !important;
    transition: border-color 0.15s, box-shadow 0.15s;
}

div[data-testid="stTextArea"]:has(textarea:focus) {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(91,141,239,0.15), 0 4px 20px rgba(0,0,0,0.30) !important;
}

div[data-baseweb="base-input"] {
    background-color: transparent !important;
    border: none !important;
}

textarea {
    color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9rem !important;
    line-height: 1.6 !important;
    padding: 12px 14px !important;
    resize: none !important;
    background: transparent !important;
}
textarea::placeholder { color: var(--text-faint) !important; }

div[data-testid="stButton"] {
    transform: none !important;
    margin: 0.65rem 0 0 0 !important;
    margin-bottom: 0 !important;
    display: flex !important;
    justify-content: flex-end !important;
}

div[data-testid="stButton"] > button {
    background: var(--accent) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 999px !important;
    padding: 0.5rem 1.4rem !important;
    font-size: 0.875rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.01em !important;
    box-shadow: 0 2px 8px rgba(91,141,239,0.35) !important;
    transition: background 0.15s, box-shadow 0.15s !important;
    cursor: pointer !important;
}

div[data-testid="stButton"] > button:hover {
    background: var(--accent-2) !important;
    box-shadow: 0 4px 14px rgba(91,141,239,0.50) !important;
}

.ir-hint {
    font-size: 0.72rem;
    color: var(--text-faint);
    margin: 0.45rem 0.2rem 0;
    text-align: right;
}

.ir-divider {
    border: none;
    border-top: 1px solid var(--border);
    margin: 2.25rem 0;
}

.conf-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 1.5rem;
}
.conf-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 0.3rem 0.85rem 0.3rem 0.6rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border: 1px solid transparent;
}
.conf-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.grade-high   { background: rgba(34,197,94,0.12);  color: #4ade80; border-color: rgba(34,197,94,0.25); }
.grade-high   .conf-dot { background: #4ade80; }
.grade-medium { background: rgba(234,179,8,0.12);  color: #facc15; border-color: rgba(234,179,8,0.25); }
.grade-medium .conf-dot { background: #facc15; }
.grade-low    { background: rgba(239,68,68,0.12);  color: #f87171; border-color: rgba(239,68,68,0.25); }
.grade-low    .conf-dot { background: #f87171; }
.grade-insufficient { background: rgba(148,163,184,0.10); color: #a1a1aa; border-color: rgba(148,163,184,0.2); }
.grade-insufficient .conf-dot { background: #a1a1aa; }
.conf-pct { font-size: 0.8rem; color: var(--text-dim); font-weight: 500; }

.score-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-top: 1rem;
}
.score-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.65rem 0.75rem;
    text-align: center;
}
.score-val {
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    display: block;
}
.score-key {
    font-size: 0.65rem;
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 2px;
}

.warn-strip {
    background: rgba(234,88,12,0.10);
    border: 1px solid rgba(234,88,12,0.3);
    border-radius: 10px;
    padding: 0.75rem 1rem;
    margin-bottom: 1.25rem;
}
.warn-strip-title {
    font-size: 0.75rem;
    font-weight: 600;
    color: #fb923c;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.4rem;
}
.warn-item {
    font-size: 0.8rem;
    color: #fdba74;
    margin: 0.2rem 0;
    display: flex;
    align-items: flex-start;
    gap: 6px;
}

.fields-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 1.5rem;
}
.field-chip {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.5rem 0.75rem;
}
.field-chip-label {
    font-size: 0.68rem;
    font-weight: 600;
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 2px;
}
.field-chip-value {
    font-size: 0.8rem;
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    word-break: break-all;
}

.response-panels {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    margin-top: 0.5rem;
}

.resp-panel {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--border);
}

.resp-panel-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0.7rem 1.1rem;
    border-bottom: 1px solid var(--border);
}
.resp-panel-icon {
    font-size: 15px;
    line-height: 1;
    flex-shrink: 0;
}
.resp-panel-title {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    flex: 1;
}
.resp-panel-body {
    padding: 1rem 1.1rem;
    font-size: 0.875rem;
    line-height: 1.75;
    color: var(--text);
}

.panel-summary .resp-panel-header { background: rgba(91,141,239,0.10); }
.panel-summary { background: var(--surface); }
.panel-summary .resp-panel-title  { color: var(--accent-2); }

.panel-mitre .resp-panel-header { background: rgba(167,139,250,0.10); }
.panel-mitre { background: var(--surface); }
.panel-mitre .resp-panel-title  { color: #c4b5fd; }

.mitre-table { width: 100%; border-collapse: collapse; margin: 0; }
.mitre-table th {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-faint);
    padding: 0 0 0.5rem 0;
    text-align: left;
    border-bottom: 1px solid var(--border);
}
.mitre-table td {
    padding: 0.5rem 0;
    font-size: 0.82rem;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
}
.mitre-table tr:last-child td { border-bottom: none; }

.mitre-tid {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: var(--accent-2);
    background: rgba(91,141,239,0.12);
    border: 1px solid rgba(91,141,239,0.25);
    border-radius: 5px;
    padding: 0.15em 0.45em;
    display: inline-block;
    white-space: nowrap;
}
.mitre-tactic {
    font-size: 0.72rem;
    color: #c4b5fd;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.mitre-name { color: var(--text); font-weight: 500; }
.mitre-desc { color: var(--text-dim); font-size: 0.8rem; margin-top: 2px; }

.td-id  { width: 120px; padding-right: 12px; }
.td-tactic { width: 130px; padding-right: 12px; }

.panel-playbook .resp-panel-header { background: rgba(52,211,153,0.08); }
.panel-playbook { background: var(--surface); }
.panel-playbook .resp-panel-title  { color: #6ee7b7; }

.playbook-steps { display: flex; flex-direction: column; gap: 0; }
.playbook-step {
    display: flex;
    gap: 14px;
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--border);
}
.playbook-step:last-child { border-bottom: none; }
.step-num {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: rgba(52,211,153,0.15);
    border: 1px solid rgba(52,211,153,0.3);
    color: #6ee7b7;
    font-size: 0.7rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 1px;
}
.step-body { flex: 1; }
.step-title {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 3px;
}
.step-detail {
    font-size: 0.8rem;
    color: var(--text-dim);
    line-height: 1.6;
}
.step-detail code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78em;
    background: var(--surface-2);
    border: 1px solid var(--border-2);
    border-radius: 4px;
    padding: 0.1em 0.35em;
    color: var(--accent-2);
}

.answer-wrap { display: flex; flex-direction: column; gap: 1rem; }
.answer-section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
}
.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0.75rem 1.1rem;
    border-bottom: 1px solid var(--border);
    background: var(--surface-2);
}
.section-num {
    width: 22px; height: 22px;
    background: var(--accent);
    color: #fff;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.section-title {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.section-body {
    padding: 1rem 1.1rem;
    font-size: 0.875rem;
    line-height: 1.75;
    color: var(--text);
    white-space: pre-wrap;
    word-break: break-word;
}
.section-body code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8em;
    background: var(--surface-2);
    border: 1px solid var(--border-2);
    border-radius: 4px;
    padding: 0.1em 0.35em;
    color: var(--accent-2);
}

.sources-wrap { margin-top: 1.25rem; }
.sources-label {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-faint);
    margin-bottom: 0.5rem;
}
.source-pills { display: flex; flex-wrap: wrap; gap: 6px; }
.source-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.25rem 0.6rem;
    font-size: 0.75rem;
    color: var(--text-dim);
}
.pill-type {
    font-weight: 600;
    color: var(--accent-2);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.pill-sep { color: var(--border-2); }

div[data-testid="stAlert"] {
    background: var(--surface) !important;
    border: 1px solid var(--border-2) !important;
    color: var(--text) !important;
    border-radius: 10px !important;
}
div[data-testid="stAlert"] p { color: var(--text) !important; }
.stSpinner > div { color: var(--text-dim) !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="ir-brand">
  <div class="ir-shield">🛡️</div>
  <h1>IR Copilot</h1>
</div>
<p class="ir-sub">Local, grounded incident analysis — no data leaves your machine.</p>
""", unsafe_allow_html=True)

incident = st.text_area(
    "Incident description",
    height=140,
    placeholder=(
        "Describe what happened. Include host name, username, process name, "
        "command line, IP addresses, alert name, and any file hashes…\n\n"
        "e.g.  Host WS-105 | User: CORP\\jsmith | powershell.exe -enc SGVs… "
        "connected to 185.23.41.6:443 | Alert: Suspicious PowerShell | Tool: Defender"
    ),
    label_visibility="collapsed",
)

analyze_btn = st.button("Analyze →")
st.markdown('<p class="ir-hint">Runs entirely on-device via your local Ollama model.</p>', unsafe_allow_html=True)


def extract_section(text: str, *keywords: str) -> str:
    pattern = r"(?i)(?:^|\n)#{0,3}\s*(?:" + "|".join(re.escape(k) for k in keywords) + r")[:\s]*\n(.*?)(?=\n#{0,3}\s*[A-Z][^a-z\n]{2,}|\Z)"
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""

def parse_mitre_entries(text: str) -> list[dict]:
    entries = []
    for line in text.splitlines():
        line = line.strip().lstrip("•-*|").strip()
        m = re.search(r"(T\d{4}(?:\.\d{3})?)", line)
        if not m:
            continue
        tid = m.group(1)
        rest = line[m.end():].strip(" –-:|*")
        tactic_m = re.search(r"\(([^)]+)\)\s*$", rest)
        tactic = tactic_m.group(1) if tactic_m else ""
        name_desc = rest[:tactic_m.start()].strip(" –-|") if tactic_m else rest
        nd_parts = re.split(r"\s[–-]\s", name_desc, maxsplit=1)
        name = nd_parts[0].strip()
        desc = nd_parts[1].strip() if len(nd_parts) > 1 else ""
        entries.append({"tid": tid, "tactic": tactic, "name": name, "desc": desc})

    # The same technique ID is often mentioned more than once across the
    # model's answer (e.g. named in "Likely ATT&CK techniques" AND
    # referenced again in "Recommended next steps"). Without dedup each
    # mention becomes its own table row. Keep one row per ID — the mention
    # carrying the most information (tactic + description present).
    def completeness(e: dict) -> int:
        return (1 if e["tactic"] else 0) + (1 if e["desc"] else 0) + (1 if e["name"] else 0)

    best_by_tid: dict[str, dict] = {}
    order: list[str] = []
    for e in entries:
        tid = e["tid"]
        if tid not in best_by_tid:
            best_by_tid[tid] = e
            order.append(tid)
        elif completeness(e) > completeness(best_by_tid[tid]):
            best_by_tid[tid] = e

    return [best_by_tid[tid] for tid in order]

def parse_playbook_steps(text: str) -> list[dict]:
    steps = []
    numbered = re.findall(r"^\s*(\d+)[.)]\s+(.+?)(?=\n\s*\d+[.)]|\Z)", text, re.MULTILINE | re.DOTALL)
    if numbered:
        for _, content in numbered:
            lines = content.strip().splitlines()
            title = lines[0].strip()
            detail = " ".join(l.strip() for l in lines[1:]).strip()
            steps.append({"title": title, "detail": detail})
        return steps
    for line in text.splitlines():
        line = line.strip().lstrip("•-*").strip()
        if len(line) > 10:
            steps.append({"title": line, "detail": ""})
    return steps

def render_mitre_panel(entries: list[dict]) -> str:
    if not entries:
        return ""
    rows = ""
    for e in entries:
        # Escape every model-derived field. The LLM's answer text is not
        # trusted HTML — a stray '<', '>', or quote inside a technique name,
        # tactic, or description will otherwise break out of the surrounding
        # tag and corrupt everything rendered after it on the page.
        tid    = html.escape(e['tid'])
        tactic = html.escape(e['tactic']) if e['tactic'] else '—'
        name   = html.escape(e['name'])
        desc   = html.escape(e['desc']) if e['desc'] else ''
        rows += f"""
        <tr>
          <td class="td-id"><span class="mitre-tid">{tid}</span></td>
          <td class="td-tactic"><span class="mitre-tactic">{tactic}</span></td>
          <td>
            <div class="mitre-name">{name}</div>
            {"<div class='mitre-desc'>" + desc + "</div>" if desc else ""}
          </td>
        </tr>"""
    return f"""
    <div class="resp-panel panel-mitre">
      <div class="resp-panel-header">
        <span class="resp-panel-icon">🎯</span>
        <span class="resp-panel-title">MITRE ATT&amp;CK Techniques</span>
      </div>
      <div class="resp-panel-body">
        <table class="mitre-table">
          <thead><tr>
            <th class="td-id">Technique</th>
            <th class="td-tactic">Tactic</th>
            <th>Name / Description</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>"""

def render_playbook_panel(steps: list[dict]) -> str:
    if not steps:
        return ""
    items = ""
    for i, s in enumerate(steps, 1):
        title = html.escape(s["title"])
        # Escape first, then re-apply backtick code-span formatting on the
        # escaped text, so a `code span` still renders but nothing else
        # the model wrote can break out of the surrounding markup.
        detail_escaped = html.escape(s["detail"]) if s["detail"] else ""
        detail_html = re.sub(r"`([^`]+)`", r"<code>\1</code>", detail_escaped) if detail_escaped else ""
        items += f"""
        <div class="playbook-step">
          <div class="step-num">{i}</div>
          <div class="step-body">
            <div class="step-title">{title}</div>
            {"<div class='step-detail'>" + detail_html + "</div>" if detail_html else ""}
          </div>
        </div>"""
    return f"""
    <div class="resp-panel panel-playbook">
      <div class="resp-panel-header">
        <span class="resp-panel-icon">📋</span>
        <span class="resp-panel-title">Playbook Steps</span>
      </div>
      <div class="resp-panel-body">
        <div class="playbook-steps">{items}</div>
      </div>
    </div>"""

def render_summary_panel(text: str) -> str:
    if not text:
        return ""
    escaped = html.escape(text)
    body_html = re.sub(r"(T\d{4}(?:\.\d{3})?)", r'<code style="font-family:\'JetBrains Mono\',monospace;font-size:0.8em;background:var(--surface-2);border:1px solid var(--border-2);border-radius:4px;padding:0.1em 0.35em;color:var(--accent-2)">\1</code>', escaped)
    return f"""
    <div class="resp-panel panel-summary">
      <div class="resp-panel-header">
        <span class="resp-panel-icon">📝</span>
        <span class="resp-panel-title">Summary &amp; Assessment</span>
      </div>
      <div class="resp-panel-body" style="white-space:pre-wrap;word-break:break-word">{body_html}</div>
    </div>"""

def split_answer_fallback(text: str) -> list[tuple[str, str, str]]:
    pattern = re.compile(r"^\s*(\d+)\.\s+(.*?)(?=\n\s*\d+\.\s+|\Z)", re.MULTILINE | re.DOTALL)
    sections = []
    for m in pattern.finditer(text):
        num  = m.group(1)
        rest = m.group(2).strip()
        lines = rest.split("\n", 1)
        title = lines[0].strip().rstrip(":")
        body  = lines[1].strip() if len(lines) > 1 else ""
        sections.append((num, title, body))
    return sections


if analyze_btn and incident.strip():
    with st.spinner("Retrieving context and generating analysis…"):
        try:
            resp = requests.post(
                "http://localhost:8000/query",
                json={"raw_text": incident},
                params={
                    "model_name": "llama3.1:8b",
                    "top_k": 5, "recall_k": 20, "min_similarity": 0.30,
                    "alpha": 0.65, "reranker": "cross-encoder/ms-marco-MiniLM-L-6-v2",
                },
                timeout=180,
            )
        except requests.exceptions.ConnectionError:
            st.error(
                "**Backend not reachable.** "
                "Run: `uvicorn src.api:app --reload --port 8000`"
            )
            st.stop()

    if resp.status_code != 200:
        st.error(f"Backend returned status {resp.status_code}. Check the uvicorn terminal.")
        st.code(resp.text[:500])
        st.stop()

    data  = resp.json()
    conf  = data.get("confidence", {})
    grade = conf.get("grade", "unknown")
    pct   = conf.get("overall", 0.0)

    st.markdown('<hr class="ir-divider">', unsafe_allow_html=True)

    grade_cls = grade if grade in ("high", "medium", "low", "insufficient") else "insufficient"
    pct_label = f"{pct:.0%}"

    st.markdown(f"""
    <div class="conf-row">
      <div class="conf-badge grade-{grade_cls}">
        <div class="conf-dot"></div>
        {grade_cls.upper()} CONFIDENCE
      </div>
      <span class="conf-pct">{pct_label} overall</span>
    </div>
    """, unsafe_allow_html=True)

    rq  = conf.get("retrieval_quality", 0.0)
    cc  = conf.get("citation_coverage", 0.0)
    sa  = conf.get("source_agreement", 0.0)
    sb  = conf.get("semantic_best", 0.0)
    st.markdown(f"""
    <div class="score-grid">
      <div class="score-card"><span class="score-val">{rq:.0%}</span><div class="score-key">Retrieval</div></div>
      <div class="score-card"><span class="score-val">{cc:.0%}</span><div class="score-key">Citations</div></div>
      <div class="score-card"><span class="score-val">{sa:.0%}</span><div class="score-key">Agreement</div></div>
      <div class="score-card"><span class="score-val">{sb:.0%}</span><div class="score-key">Semantic</div></div>
    </div>
    """, unsafe_allow_html=True)

    flagged = data.get("flagged_citations", [])
    quotes  = data.get("unverified_quotes", [])
    if flagged or quotes:
        items = "".join(f'<div class="warn-item">⚠ {html.escape(c)}</div>' for c in flagged)
        items += "".join(f'<div class="warn-item">⚠ Unverified quote: "{html.escape(q)}"</div>' for q in quotes)
        st.markdown(f"""
        <div class="warn-strip">
          <div class="warn-strip-title">Hallucination flags</div>
          {items}
        </div>
        """, unsafe_allow_html=True)

    fields = data.get("extracted_fields", {})
    FIELD_LABELS = {
        "alert_name": "Alert", "host": "Host", "user": "User",
        "process": "Process", "command_line": "Command", "file_path": "File / Hash",
        "network": "Network", "indicators": "Indicators",
    }
    visible = {k: v for k, v in fields.items() if v and k in FIELD_LABELS}
    if visible:
        chips = "".join(
            f'<div class="field-chip">'
            f'<div class="field-chip-label">{html.escape(FIELD_LABELS[k])}</div>'
            f'<div class="field-chip-value">{html.escape(str(v)[:80])}{"…" if len(str(v)) > 80 else ""}</div>'
            f'</div>'
            for k, v in visible.items()
        )
        st.markdown('<hr class="ir-divider">', unsafe_allow_html=True)
        st.markdown(f'<div class="fields-grid">{chips}</div>', unsafe_allow_html=True)

    raw_answer: str = data.get("answer", "")

    summary_text = extract_section(raw_answer, "summary", "assessment", "overview", "analysis")
    mitre_text   = extract_section(raw_answer, "mitre", "att&ck", "techniques", "ttps")
    playbook_text= extract_section(raw_answer, "playbook", "remediation", "response steps",
                                   "recommended steps", "containment", "investigation steps")

    if not mitre_text:
        mitre_text = raw_answer

    mitre_entries  = parse_mitre_entries(mitre_text)
    playbook_steps = parse_playbook_steps(playbook_text) if playbook_text else []

    has_structure = bool(summary_text or mitre_entries or playbook_steps)

    st.markdown('<hr class="ir-divider">', unsafe_allow_html=True)

    if has_structure:
        panels = ""
        panels += render_summary_panel(summary_text or "")
        panels += render_mitre_panel(mitre_entries)
        panels += render_playbook_panel(playbook_steps)

        st.markdown(f'<div class="response-panels">{panels}</div>', unsafe_allow_html=True)
    else:
        sections = split_answer_fallback(raw_answer)
        if sections:
            parts = ""
            for num, title, body in sections:
                body_escaped = html.escape(body)
                body_html = re.sub(r"(T\d{4}(?:\.\d{3})?)", r"<code>\1</code>", body_escaped)
                parts += f"""
                <div class="answer-section">
                  <div class="section-header">
                    <div class="section-num">{html.escape(num)}</div>
                    <div class="section-title">{html.escape(title)}</div>
                  </div>
                  <div class="section-body">{body_html}</div>
                </div>"""
            st.markdown(f'<div class="answer-wrap">{parts}</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="answer-section"><div class="section-body">{html.escape(raw_answer)}</div></div>',
                unsafe_allow_html=True
            )

    sources = data.get("sources", [])
    if sources:
        pills = ""
        for s in sources:
            src   = s.get("source", "?")
            name  = (s.get("name") or s.get("title") or s.get("playbook") or
                     s.get("technique_id") or "")
            label = name[:45] + ("…" if len(name) > 45 else "")
            pills += (
                f'<div class="source-pill">'
                f'<span class="pill-type">{html.escape(str(src))}</span>'
                f'<span class="pill-sep">·</span>'
                f'{html.escape(label)}'
                f'</div>'
            )
        st.markdown(f"""
        <div class="sources-wrap">
          <div class="sources-label">Retrieved sources</div>
          <div class="source-pills">{pills}</div>
        </div>
        """, unsafe_allow_html=True)

elif analyze_btn:
    st.warning("Enter an incident description before analyzing.")