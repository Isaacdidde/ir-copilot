# src/app.py
import streamlit as st
import requests

st.set_page_config(page_title="IR Copilot")
st.title("Incident Response Copilot")
st.caption("Free, local, RAG-grounded — no data leaves your machine")

incident = st.text_area(
    "Paste the alert, log snippet, or describe what happened",
    height=160,
    placeholder="e.g. Host WS-105 ran powershell.exe -enc... then connected to 185.x.x.x:443. "
                 "Defender flagged Trojan:Win32/Agent."
)

if st.button("Analyze") and incident:
    with st.spinner("Extracting details and analyzing..."):
        resp = requests.post("http://localhost:8000/query", json={"raw_text": incident}, timeout=120)

    if resp.status_code != 200 or not resp.text:
        st.error(f"Backend returned an unusable response (status {resp.status_code}). "
                  f"Check the uvicorn terminal for errors.")
        st.code(resp.text[:500])
        st.stop()

    data = resp.json()

    st.markdown(data["answer"])

    flagged = data.get("flagged_citations", [])
    quotes = data.get("unverified_quotes", [])
    if flagged or quotes:
        with st.expander("⚠️ Possible grounding issues — verify before acting on these", expanded=True):
            for c in flagged:
                st.write(f"- Citation not matched to anything retrieved: `{c}`")
            for q in quotes:
                st.write(f'- Quoted text not found in any source: "{q}"')

    with st.expander(f"Sources used ({len(data['sources'])})"):
        for s in data["sources"]:
            st.json(s)

    with st.expander("What the system understood from your input"):
        st.json(data.get("extracted_fields", {}))