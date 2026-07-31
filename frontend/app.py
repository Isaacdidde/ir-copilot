"""IR-Copilot — Streamlit frontend (case-file dossier styling)."""

from __future__ import annotations

import os

import requests
import streamlit as st

API_BASE_URL = os.environ.get("IRCOPILOT_API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="IR COPILOT",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root {
    --bg: #0a0e13;
    --panel: #12181f;
    --panel-raised: #161d26;
    --line: #212a34;
    --line-soft: #1a2129;
    --text: #e4e9ee;
    --text-dim: #8391a1;
    --text-faint: #566173;
    --cyan: #4fc3d9;
    --amber: #e8a33d;
    --green: #5cd6a0;
    --red: #e5565c;
    --violet: #a78bfa;
}

.stApp { background-color: var(--bg); }
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }

.dossier-header { border-bottom: 1px solid var(--line); padding-bottom: 14px; margin-bottom: 6px; }
.dossier-eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; letter-spacing: 0.18em; color: var(--text-faint); text-transform: uppercase; margin-bottom: 2px; }
.dossier-title { font-family: 'JetBrains Mono', monospace; font-size: 1.9rem; font-weight: 700; color: var(--text); letter-spacing: -0.01em; margin: 0; }
.dossier-sub { color: var(--text-dim); font-size: 0.92rem; margin-top: 6px; max-width: 720px; }

section[data-testid="stSidebar"] { background-color: var(--panel); border-right: 1px solid var(--line); }
.sidebar-title { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 1.05rem; color: var(--text); letter-spacing: 0.02em; }
.sidebar-caption { color: var(--text-faint); font-size: 0.78rem; }

.panel { background-color: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 22px 26px; margin-bottom: 18px; position: relative; }
.panel-label { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; letter-spacing: 0.16em; text-transform: uppercase; color: var(--text-faint); margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
.panel-label::after { content: ""; flex: 1; height: 1px; background: var(--line); }

.stamp { position: absolute; top: 20px; right: 24px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 0.82rem; letter-spacing: 0.06em; text-transform: uppercase; padding: 8px 14px; border: 2px solid; border-radius: 4px; transform: rotate(3deg); white-space: nowrap; }
.stamp-high { color: var(--green); border-color: var(--green); box-shadow: 0 0 0 1px rgba(92,214,160,0.15) inset; }
.stamp-medium { color: var(--amber); border-color: var(--amber); box-shadow: 0 0 0 1px rgba(232,163,61,0.15) inset; }
.stamp-low { color: var(--red); border-color: var(--red); box-shadow: 0 0 0 1px rgba(229,86,92,0.15) inset; }

.situation-text { color: var(--text); font-size: 0.98rem; line-height: 1.65; max-width: 88%; }
.situation-why { color: var(--text-dim); font-size: 0.9rem; line-height: 1.6; margin-top: 12px; max-width: 88%; }
.situation-why b { color: var(--text); }

.insufficient-flag { margin-top: 16px; padding: 10px 14px; background: rgba(229,86,92,0.08); border: 1px solid rgba(229,86,92,0.35); border-left: 3px solid var(--red); border-radius: 4px; color: #f0a3a6; font-size: 0.85rem; }

.mitre-row { display: grid; grid-template-columns: 110px 1fr 160px 70px; gap: 16px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--line-soft); }
.mitre-row:last-child { border-bottom: none; }
.mitre-id { font-family: 'JetBrains Mono', monospace; font-weight: 600; color: var(--cyan); font-size: 0.88rem; }
.mitre-name { color: var(--text); font-size: 0.92rem; }
.mitre-tactic { font-family: 'JetBrains Mono', monospace; color: var(--text-dim); font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.04em; }
.mitre-conf { font-family: 'JetBrains Mono', monospace; color: var(--text-dim); font-size: 0.82rem; text-align: right; }
.mitre-src { color: var(--text-faint); font-size: 0.78rem; margin-top: 2px; grid-column: 1 / -1; }

.evidence-item { border-left: 3px solid var(--line); padding: 10px 0 10px 14px; margin-bottom: 10px; }
.evidence-item.type-mitre { border-left-color: var(--cyan); }
.evidence-item.type-sigma { border-left-color: var(--amber); }
.evidence-item.type-nist { border-left-color: var(--green); }
.evidence-item.type-playbook { border-left-color: var(--violet); }
.evidence-tag { font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; letter-spacing: 0.08em; text-transform: uppercase; margin-right: 8px; }
.tag-mitre { color: var(--cyan); }
.tag-sigma { color: var(--amber); }
.tag-nist { color: var(--green); }
.tag-playbook { color: var(--violet); }
.evidence-name { color: var(--text); font-size: 0.92rem; font-weight: 500; }
.evidence-why { color: var(--text-dim); font-size: 0.84rem; margin-top: 3px; line-height: 1.5; }

.phase-track { position: relative; padding-left: 28px; }
.phase-track::before { content: ""; position: absolute; left: 7px; top: 6px; bottom: 6px; width: 2px; background: var(--line); }
.phase-step { position: relative; padding-bottom: 20px; }
.phase-step:last-child { padding-bottom: 0; }
.phase-dot { position: absolute; left: -28px; top: 3px; width: 14px; height: 14px; border-radius: 50%; border: 2px solid; background: var(--bg); }
.phase-step.p-identification .phase-dot { border-color: var(--cyan); }
.phase-step.p-containment .phase-dot { border-color: var(--amber); }
.phase-step.p-eradication .phase-dot { border-color: var(--red); }
.phase-step.p-recovery .phase-dot { border-color: var(--green); }
.phase-label { font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 600; margin-bottom: 3px; }
.phase-step.p-identification .phase-label { color: var(--cyan); }
.phase-step.p-containment .phase-label { color: var(--amber); }
.phase-step.p-eradication .phase-label { color: var(--red); }
.phase-step.p-recovery .phase-label { color: var(--green); }
.phase-action { color: var(--text); font-size: 0.92rem; line-height: 1.5; }

.note-line { color: var(--text-dim); font-size: 0.88rem; padding: 4px 0; }
.note-line::before { content: "— "; color: var(--text-faint); }

.empty-state { color: var(--text-faint); font-size: 0.86rem; font-style: italic; padding: 6px 0; }

div[data-testid="stExpander"] { border: 1px solid var(--line); border-radius: 6px; background: var(--panel); }
</style>
""",
    unsafe_allow_html=True,
)


def source_badge(source_type: str) -> tuple[str, str]:
    return f"type-{source_type}", f"tag-{source_type}"


def confidence_stamp(score: float) -> tuple[str, str]:
    if score >= 0.75:
        return "stamp-high", "VERIFIED"
    if score >= 0.5:
        return "stamp-medium", "PARTIAL MATCH"
    return "stamp-low", "UNVERIFIED"


with st.sidebar:
    st.markdown('<div class="sidebar-title">🗂️ IR-Copilot</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-caption">Evidence-grounded incident response assistant</div>', unsafe_allow_html=True)
    st.divider()
    st.subheader("Knowledge Base")

    try:
        status = requests.get(f"{API_BASE_URL}/kb/status", timeout=5).json()
        st.metric("Indexed Chunks", status["indexed_documents"])
        col1, col2 = st.columns(2)
        col1.metric("MITRE", status["mitre_count"])
        col2.metric("Sigma", status["sigma_count"])
        col3, col4 = st.columns(2)
        col3.metric("NIST", status["nist_count"])
        col4.metric("Playbooks", status["playbook_count"])
        st.caption(f"LLM: `{status['llm_model']}`")
        st.caption(f"Embeddings: `{status['embedding_model']}`")
        st.success(f"Vector DB: {status['vector_db_status']}")
        if status.get("last_indexed_at"):
            st.caption(f"Last indexed: {status['last_indexed_at']}")
        backend_online = True
    except requests.RequestException:
        st.error("Backend unreachable. Is FastAPI running?")
        backend_online = False

    st.divider()
    if st.button("🔄 Reindex Knowledge Base", use_container_width=True):
        with st.spinner("Reindexing..."):
            try:
                r = requests.post(f"{API_BASE_URL}/kb/reindex", timeout=120)
                r.raise_for_status()
                st.success(f"Indexed {r.json()['newly_indexed_chunks']} new/changed chunks")
            except requests.RequestException as exc:
                st.error(f"Reindex failed: {exc}")

st.markdown(
    '<div class="dossier-header">'
    '<div class="dossier-eyebrow">Incident Analysis</div>'
    '<p class="dossier-title">IR-Copilot</p>'
    '<p class="dossier-sub">Paste an incident description below. Findings are grounded strictly in retrieved '
    'evidence — MITRE ATT&CK, Sigma rules, NIST SP 800-61, and internal playbooks.</p>'
    '</div>',
    unsafe_allow_html=True,
)

incident_text = st.text_area(
    "Incident description",
    height=140,
    placeholder=(
        "e.g. We observed powershell.exe launched with an encoded command from winword.exe "
        "on a finance workstation, followed by an outbound connection to an unknown IP..."
    ),
    label_visibility="collapsed",
)

analyze_clicked = st.button("Analyze incident", type="primary", use_container_width=False)

st.write("")

if analyze_clicked:
    if not incident_text or len(incident_text.strip()) < 10:
        st.warning("Please enter a more detailed incident description (at least 10 characters).")
    elif not backend_online:
        st.error("Cannot analyze — backend is unreachable.")
    else:
        with st.spinner("Retrieving evidence and generating findings..."):
            try:
                resp = requests.post(
                    f"{API_BASE_URL}/analyze",
                    json={"incident_description": incident_text},
                    timeout=120,
                )
                resp.raise_for_status()
                result = resp.json()
            except requests.RequestException as exc:
                st.error(f"Analysis request failed: {exc}")
                result = None

        if result:
            confidence_score = result.get("confidence_score", 0.0)
            stamp_class, stamp_label = confidence_stamp(confidence_score)
            pct = int(round(confidence_score * 100))

            # --- Situation report ---
            summary = result.get("summary", {})
            parts = [
                '<div class="panel">',
                f'<div class="stamp {stamp_class}">{pct}% · {stamp_label}</div>',
                '<div class="panel-label">Situation Report</div>',
                f'<div class="situation-text">{summary.get("what_happened", "No summary available.")}</div>',
            ]
            if summary.get("why_it_matches"):
                parts.append(f'<div class="situation-why"><b>Why this matches:</b> {summary["why_it_matches"]}</div>')
            if result.get("insufficient_evidence"):
                parts.append('<div class="insufficient-flag">Insufficient evidence for a high-confidence determination.</div>')
            parts.append('</div>')
            st.markdown("".join(parts), unsafe_allow_html=True)

            # --- MITRE mapping ---
            mapping = result.get("mitre_mapping", [])
            if mapping:
                rows = []
                for m in mapping:
                    rows.append(
                        '<div class="mitre-row">'
                        f'<div class="mitre-id">{m["technique_id"]}</div>'
                        f'<div class="mitre-name">{m["technique_name"]}</div>'
                        f'<div class="mitre-tactic">{m["tactic"]}</div>'
                        f'<div class="mitre-conf">{int(m["confidence"] * 100)}%</div>'
                        f'<div class="mitre-src">via {m.get("evidence_source", "—")}</div>'
                        '</div>'
                    )
                rows_html = "".join(rows)
            else:
                rows_html = '<div class="empty-state">No verified MITRE technique mapping available.</div>'
            st.markdown(
                f'<div class="panel"><div class="panel-label">MITRE ATT&amp;CK Mapping</div>{rows_html}</div>',
                unsafe_allow_html=True,
            )

            # --- Evidence used ---
            evidence = result.get("evidence", [])
            if evidence:
                items = []
                for e in evidence:
                    type_cls, tag_cls = source_badge(e["source_type"])
                    why_html = f'<div class="evidence-why">{e["why_it_supports"]}</div>' if e.get("why_it_supports") else ""
                    items.append(
                        f'<div class="evidence-item {type_cls}">'
                        f'<span class="evidence-tag {tag_cls}">{e["source_type"]}</span>'
                        f'<span class="evidence-name">{e["source_name"]}</span>'
                        f'{why_html}'
                        '</div>'
                    )
                ev_html = "".join(items)
            else:
                ev_html = '<div class="empty-state">No evidence retrieved.</div>'
            st.markdown(
                f'<div class="panel"><div class="panel-label">Evidence Used</div>{ev_html}</div>',
                unsafe_allow_html=True,
            )

            # --- Response steps ---
            steps = result.get("incident_response_steps", [])
            phase_order = {"Identification": 0, "Containment": 1, "Eradication": 2, "Recovery": 3}
            steps_sorted = sorted(steps, key=lambda s: phase_order.get(s.get("phase", ""), 99))
            if steps_sorted:
                step_items = []
                for s in steps_sorted:
                    phase = s.get("phase", "")
                    step_items.append(
                        f'<div class="phase-step p-{phase.lower()}">'
                        '<div class="phase-dot"></div>'
                        f'<div class="phase-label">{phase}</div>'
                        f'<div class="phase-action">{s.get("action", "")}</div>'
                        '</div>'
                    )
                steps_html = f'<div class="phase-track">{"".join(step_items)}</div>'
            else:
                steps_html = '<div class="empty-state">No response steps available.</div>'
            st.markdown(
                f'<div class="panel"><div class="panel-label">Response Sequence</div>{steps_html}</div>',
                unsafe_allow_html=True,
            )

            # --- Missing evidence ---
            missing = result.get("missing_evidence", [])
            if missing:
                notes_html = "".join(f'<div class="note-line">{m}</div>' for m in missing)
                st.markdown(
                    '<div class="panel">'
                    '<div class="panel-label">Missing Evidence</div>'
                    '<div style="color: var(--text-dim); font-size: 0.86rem; margin-bottom: 8px;">'
                    'Provide the following to improve analysis confidence:</div>'
                    f'{notes_html}'
                    '</div>',
                    unsafe_allow_html=True,
                )

            # --- Confidence assessment ---
            ca = result.get("confidence_assessment", {})
            explanation = ca.get("explanation", "")
            conflicting = ca.get("conflicting_evidence", [])
            if explanation or conflicting:
                conflict_html = ""
                if conflicting:
                    conflict_html = (
                        '<div style="margin-top:10px; color: var(--text-dim); font-size:0.8rem; '
                        'letter-spacing:0.06em; text-transform:uppercase; font-family:\'JetBrains Mono\', monospace;">'
                        'Caveats</div>'
                    )
                    conflict_html += "".join(f'<div class="note-line">{c}</div>' for c in conflicting)
                explanation_html = f'<div class="situation-text" style="max-width:100%;">{explanation}</div>' if explanation else ""
                st.markdown(
                    f'<div class="panel"><div class="panel-label">Confidence Assessment</div>{explanation_html}{conflict_html}</div>',
                    unsafe_allow_html=True,
                )

            with st.expander("Pipeline diagnostics"):
                st.json(
                    {
                        "tokens_used_estimate": result.get("tokens_used_estimate"),
                        "retrieval_latency_ms": result.get("retrieval_latency_ms"),
                        "generation_latency_ms": result.get("generation_latency_ms"),
                    }
                )