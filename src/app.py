# src/app.py
import streamlit as st
import requests
import time

API_URL = "http://localhost:8000/query"

# ── Design tokens ─────────────────────────────────────────────────────────────
# Palette: deep navy base, electric cyan accent, threat-level reds/ambers
# Typography: monospace data labels + clean sans body — terminal meets dashboard
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Reset & base ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: #0a0e1a;
    color: #c9d1e0;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding: 0 !important;
    max-width: 100% !important;
}

/* ── Top nav bar ── */
.ir-navbar {
    background: #0d1220;
    border-bottom: 1px solid #1e2d4a;
    padding: 14px 32px;
    display: flex;
    align-items: center;
    gap: 12px;
    position: sticky;
    top: 0;
    z-index: 100;
}

.ir-navbar-logo {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 500;
    color: #00d4ff;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.ir-navbar-sep {
    color: #1e2d4a;
    font-size: 18px;
}

.ir-navbar-title {
    font-size: 13px;
    color: #5a7394;
    font-weight: 400;
}

.ir-status-dot {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: #5a7394;
    font-family: 'JetBrains Mono', monospace;
}

.ir-status-dot::before {
    content: '';
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #00d4ff;
    box-shadow: 0 0 6px #00d4ff;
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

/* ── Main layout ── */
.ir-layout {
    display: grid;
    grid-template-columns: 260px 1fr;
    min-height: 100vh;
}

.ir-sidebar {
    background: #0d1220;
    border-right: 1px solid #1e2d4a;
    padding: 24px 20px;
}

.ir-main {
    padding: 32px 40px;
}

/* ── Section labels ── */
.ir-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #00d4ff;
    margin-bottom: 12px;
}

/* ── Input box ── */
.stTextArea textarea {
    background: #0d1220 !important;
    border: 1px solid #1e2d4a !important;
    border-radius: 6px !important;
    color: #c9d1e0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
    padding: 14px !important;
    transition: border-color 0.2s !important;
    resize: vertical !important;
}

.stTextArea textarea:focus {
    border-color: #00d4ff !important;
    box-shadow: 0 0 0 1px #00d4ff20 !important;
    outline: none !important;
}

.stTextArea textarea::placeholder {
    color: #3a4d66 !important;
}

/* ── Primary button ── */
.stButton > button[kind="primary"] {
    background: #00d4ff !important;
    color: #0a0e1a !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    letter-spacing: 0.08em !important;
    padding: 12px 24px !important;
    text-transform: uppercase !important;
    transition: all 0.15s !important;
    width: 100% !important;
}

.stButton > button[kind="primary"]:hover {
    background: #33ddff !important;
    box-shadow: 0 0 20px #00d4ff40 !important;
    transform: translateY(-1px) !important;
}

/* ── Secondary (example) buttons ── */
.stButton > button:not([kind="primary"]) {
    background: transparent !important;
    border: 1px solid #1e2d4a !important;
    border-radius: 4px !important;
    color: #5a7394 !important;
    font-size: 11px !important;
    font-family: 'Inter', sans-serif !important;
    padding: 8px 12px !important;
    text-align: left !important;
    transition: all 0.15s !important;
    width: 100% !important;
    white-space: normal !important;
    height: auto !important;
    min-height: 44px !important;
}

.stButton > button:not([kind="primary"]):hover {
    border-color: #00d4ff !important;
    color: #00d4ff !important;
    background: #00d4ff08 !important;
}

/* ── Selectbox ── */
.stSelectbox > div > div {
    background: #0d1220 !important;
    border: 1px solid #1e2d4a !important;
    border-radius: 6px !important;
    color: #c9d1e0 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
}

/* ── Slider ── */
.stSlider > div > div > div > div {
    background: #00d4ff !important;
}

/* ── Result card ── */
.ir-result-card {
    background: #0d1220;
    border: 1px solid #1e2d4a;
    border-radius: 8px;
    padding: 24px;
    margin-bottom: 16px;
}

.ir-result-card.accent {
    border-left: 3px solid #00d4ff;
}

/* ── Technique badge ── */
.ir-badge {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    padding: 3px 8px;
    border-radius: 3px;
    margin: 2px 3px 2px 0;
}

.ir-badge-red   { background: #ff334420; color: #ff6677; border: 1px solid #ff334430; }
.ir-badge-amber { background: #ffaa0020; color: #ffbb44; border: 1px solid #ffaa0030; }
.ir-badge-cyan  { background: #00d4ff20; color: #00d4ff; border: 1px solid #00d4ff30; }
.ir-badge-gray  { background: #1e2d4a;   color: #5a7394; border: 1px solid #2a3d5a; }

/* ── Source pill ── */
.ir-source-pill {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 14px;
    border: 1px solid #1e2d4a;
    border-radius: 6px;
    margin-bottom: 8px;
    transition: border-color 0.15s;
    cursor: default;
}

.ir-source-pill:hover { border-color: #2a3d5a; }

.ir-source-icon {
    font-size: 14px;
    margin-top: 1px;
    flex-shrink: 0;
}

.ir-source-body { flex: 1; min-width: 0; }

.ir-source-name {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    color: #c9d1e0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.ir-source-meta {
    font-size: 10px;
    color: #3a4d66;
    margin-top: 2px;
    font-family: 'JetBrains Mono', monospace;
}

/* ── Stats row ── */
.ir-stats-row {
    display: flex;
    gap: 12px;
    margin-bottom: 24px;
}

.ir-stat {
    flex: 1;
    background: #0d1220;
    border: 1px solid #1e2d4a;
    border-radius: 6px;
    padding: 14px 16px;
    text-align: center;
}

.ir-stat-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-weight: 500;
    color: #00d4ff;
    line-height: 1;
}

.ir-stat-label {
    font-size: 10px;
    color: #3a4d66;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 4px;
}

/* ── Analysis prose ── */
.ir-analysis {
    font-size: 14px;
    line-height: 1.75;
    color: #c9d1e0;
}

.ir-analysis h1, .ir-analysis h2, .ir-analysis h3 {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #00d4ff;
    margin: 20px 0 10px;
}

.ir-analysis ul, .ir-analysis ol {
    padding-left: 20px;
}

.ir-analysis li {
    margin-bottom: 6px;
}

.ir-analysis strong { color: #e8edf5; }
.ir-analysis code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    background: #1e2d4a;
    padding: 1px 5px;
    border-radius: 3px;
    color: #00d4ff;
}

/* ── Expander (copy area) ── */
.streamlit-expanderHeader {
    background: #0d1220 !important;
    border: 1px solid #1e2d4a !important;
    border-radius: 6px !important;
    color: #5a7394 !important;
    font-size: 12px !important;
    font-family: 'JetBrains Mono', monospace !important;
}

.stTextArea[data-testid] textarea {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    color: #5a7394 !important;
    background: #080c14 !important;
}

/* ── Alerts ── */
.stAlert {
    border-radius: 6px !important;
    font-size: 13px !important;
}

/* ── Spinner ── */
.stSpinner > div { border-top-color: #00d4ff !important; }

/* ── Sidebar Streamlit override ── */
[data-testid="stSidebar"] {
    background: #0d1220 !important;
    border-right: 1px solid #1e2d4a !important;
}

[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown span {
    color: #5a7394 !important;
    font-size: 12px !important;
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #c9d1e0 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}

/* ── Divider ── */
hr { border-color: #1e2d4a !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0a0e1a; }
::-webkit-scrollbar-thumb { background: #1e2d4a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2a3d5a; }
</style>
"""

# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IR Copilot",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Top nav ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="ir-navbar">
    <span class="ir-navbar-logo">🛡️ IR Copilot</span>
    <span class="ir-navbar-sep">|</span>
    <span class="ir-navbar-title">Incident Response Assistant</span>
    <span class="ir-status-dot">LOCAL · NO DATA LEAVES YOUR MACHINE</span>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="ir-label">Model</div>', unsafe_allow_html=True)
    model_name = st.selectbox(
        "LLM",
        ["llama3.1:8b", "mistral:7b", "phi3:mini"],
        label_visibility="collapsed",
        help="phi3:mini is fastest on low RAM. llama3.1:8b gives best quality."
    )

    st.markdown('<div class="ir-label" style="margin-top:20px">Retrieval depth</div>', unsafe_allow_html=True)
    k = st.slider("k", min_value=3, max_value=10, value=5,
                  label_visibility="collapsed",
                  help="Chunks pulled from ChromaDB. Higher = more context, slower response.")

    st.markdown(f"""
    <div style="margin-top:8px; padding:10px 12px; background:#080c14;
                border:1px solid #1e2d4a; border-radius:6px;">
        <div style="font-family:'JetBrains Mono',monospace; font-size:10px;
                    color:#3a4d66; letter-spacing:0.1em;">CHUNKS</div>
        <div style="font-family:'JetBrains Mono',monospace; font-size:20px;
                    color:#00d4ff; font-weight:500;">{k}</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown('<div class="ir-label">Knowledge base</div>', unsafe_allow_html=True)
    for icon, label in [("🔴", "MITRE ATT&CK"), ("🟡", "Sigma Rules"), ("🟢", "IR Playbooks")]:
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:8px; padding:6px 0;
                    font-size:12px; color:#5a7394;">
            <span>{icon}</span><span>{label}</span>
        </div>""", unsafe_allow_html=True)

    st.divider()

    st.markdown('<div class="ir-label">Stack</div>', unsafe_allow_html=True)
    for line in ["ChromaDB · sentence-transformers", f"Ollama · {model_name}", "FastAPI · Streamlit"]:
        st.markdown(f"""
        <div style="font-family:'JetBrains Mono',monospace; font-size:10px;
                    color:#3a4d66; padding:3px 0;">{line}</div>
        """, unsafe_allow_html=True)

# ── Main content ──────────────────────────────────────────────────────────────
st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)

col_left, col_right = st.columns([3, 2], gap="large")

with col_left:
    st.markdown('<div class="ir-label">Incident description</div>', unsafe_allow_html=True)

    # Example query buttons
    EXAMPLES = [
        "Encoded PowerShell at 2am → outbound connection to unknown IP",
        "Phishing email with macro attachment opened by finance user",
        "/etc/passwd and /etc/shadow dump attempt returning HTTP 200",
        "Scheduled task created for persistence on domain controller",
    ]

    ex_cols = st.columns(2)
    for i, ex in enumerate(EXAMPLES):
        if ex_cols[i % 2].button(ex, key=f"ex_{i}"):
            st.session_state["incident_input"] = ex
            st.rerun()

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

    incident = st.text_area(
        "incident",
        value=st.session_state.get("incident_input", ""),
        height=140,
        placeholder="Describe the alert or anomaly in plain language — e.g. 'Suspicious outbound DNS from workstation after user opened email attachment at 03:14 UTC'",
        label_visibility="collapsed"
    )

    analyze_clicked = st.button("Run Analysis →", type="primary", use_container_width=True)

with col_right:
    st.markdown('<div class="ir-label">How it works</div>', unsafe_allow_html=True)
    for step, desc in [
        ("01  RETRIEVE", "Your query is embedded and matched against ATT&CK techniques, Sigma detection rules, and IR playbooks in ChromaDB."),
        ("02  GROUND", "The top-k chunks are injected into the prompt as the only allowed citation sources."),
        ("03  GENERATE", "Ollama reasons over the grounded context and returns a structured triage response."),
    ]:
        st.markdown(f"""
        <div style="padding:14px 16px; border:1px solid #1e2d4a; border-radius:6px;
                    margin-bottom:10px;">
            <div style="font-family:'JetBrains Mono',monospace; font-size:10px;
                        color:#00d4ff; letter-spacing:0.12em; margin-bottom:6px;">{step}</div>
            <div style="font-size:12px; color:#5a7394; line-height:1.6;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

# ── Analysis ──────────────────────────────────────────────────────────────────
if analyze_clicked:
    if not incident.strip():
        st.warning("Enter an incident description before running analysis.")
        st.stop()

    with st.spinner("Retrieving context and generating response..."):
        t_start = time.perf_counter()
        try:
            resp = requests.post(
                API_URL,
                json={"incident_description": incident, "model_name": model_name, "k": k},
                timeout=120
            )
            resp.raise_for_status()
            data = resp.json()
            elapsed = round(time.perf_counter() - t_start, 1)

        except requests.exceptions.ConnectionError:
            st.error("Cannot reach the API at `localhost:8000`. Start it with:")
            st.code("uvicorn src.api:app --reload --port 8000", language="bash")
            st.stop()
        except requests.exceptions.Timeout:
            st.error("Request timed out after 120s. Switch to `phi3:mini` or reduce k.")
            st.stop()
        except requests.exceptions.HTTPError as e:
            st.error(f"API returned HTTP {e.response.status_code}. Check uvicorn logs.")
            st.stop()
        except Exception as e:
            st.error(f"Unexpected error: {e}")
            st.stop()

    if data.get("error"):
        st.error(data["answer"])
        st.stop()

    st.divider()

    # ── Stats row ─────────────────────────────────────────────────────────────
    sources = data.get("sources", [])
    attack_count = sum(1 for s in sources if s.get("source") == "MITRE ATT&CK")
    sigma_count  = sum(1 for s in sources if s.get("source") == "Sigma")
    pb_count     = sum(1 for s in sources if s.get("source") == "Internal runbook")

    st.markdown(f"""
    <div class="ir-stats-row">
        <div class="ir-stat">
            <div class="ir-stat-value">{data.get('chunks_used', len(sources))}</div>
            <div class="ir-stat-label">Chunks used</div>
        </div>
        <div class="ir-stat">
            <div class="ir-stat-value" style="color:#ff6677">{attack_count}</div>
            <div class="ir-stat-label">ATT&CK hits</div>
        </div>
        <div class="ir-stat">
            <div class="ir-stat-value" style="color:#ffbb44">{sigma_count}</div>
            <div class="ir-stat-label">Sigma rules</div>
        </div>
        <div class="ir-stat">
            <div class="ir-stat-value" style="color:#00d4ff">{elapsed}s</div>
            <div class="ir-stat-label">Latency</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Two-column results ────────────────────────────────────────────────────
    res_left, res_right = st.columns([3, 2], gap="large")

    with res_left:
        st.markdown('<div class="ir-label">Analysis</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="ir-result-card accent"><div class="ir-analysis">{data["answer"]}</div></div>',
            unsafe_allow_html=True
        )

        with st.expander("📄 Copy for ticket / report"):
            st.text_area("raw", value=data["answer"], height=180, label_visibility="collapsed")

    with res_right:
        st.markdown(f'<div class="ir-label">Sources ({len(sources)})</div>', unsafe_allow_html=True)

        for source in sources:
            src_type = source.get("source", "Unknown")
            if src_type == "MITRE ATT&CK":
                icon  = "🔴"
                name  = f"ATT&CK {source.get('technique_id', '')}"
                meta  = source.get("tactics", "")
                badge = "ir-badge-red"
            elif src_type == "Sigma":
                icon  = "🟡"
                name  = source.get("title", "Sigma Rule")
                meta  = f"level: {source.get('level', '?')}  ·  {source.get('attack_ids', '')}"
                badge = "ir-badge-amber"
            else:
                icon  = "🟢"
                name  = source.get("playbook", "Playbook")
                meta  = source.get("section", "")
                badge = "ir-badge-cyan"

            st.markdown(f"""
            <div class="ir-source-pill">
                <span class="ir-source-icon">{icon}</span>
                <div class="ir-source-body">
                    <div class="ir-source-name">{name}</div>
                    <div class="ir-source-meta">{meta}</div>
                </div>
                <span class="ir-badge {badge}">{src_type.split()[0].upper()}</span>
            </div>
            """, unsafe_allow_html=True)