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