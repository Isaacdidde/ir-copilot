# src/app.py
import streamlit as st
import requests

st.set_page_config(page_title="IR Copilot")
st.title("Incident Response Copilot")
st.caption("Free, local, RAG-grounded — no data leaves your machine")

with st.form("incident_form"):
    col1, col2 = st.columns(2)
    with col1:
        alert_name = st.text_input("Alert Name", placeholder="e.g. Suspicious PowerShell Execution")
        host = st.text_input("Affected Host", placeholder="e.g. WS-105")
        user = st.text_input("User", placeholder="e.g. jsmith")
        process = st.text_input("Process / File Name", placeholder="e.g. invoice.exe")
    with col2:
        command_line = st.text_input("Command Line", placeholder="e.g. powershell.exe -enc ...")
        file_path = st.text_input("File Path / Hash", placeholder="e.g. SHA256 or full path")
        network = st.text_input("Network Activity", placeholder="e.g. 185.x.x.x:443")
        indicators = st.text_input("Observed Indicators", placeholder="e.g. encoded command, outbound connection")

    notes = st.text_area("Additional Notes / Raw Alert", height=100,
                          placeholder="Paste raw SIEM alert text or anything not covered above")

    submitted = st.form_submit_button("Analyze")

if submitted:
    fields = {
        "alert_name": alert_name, "host": host, "user": user, "process": process,
        "command_line": command_line, "file_path": file_path,
        "network": network, "indicators": indicators, "notes": notes,
    }
    if not any(fields.values()):
        st.warning("Fill in at least one field before analyzing.")
    else:
        with st.spinner("Retrieving context and reasoning..."):
            resp = requests.post("http://localhost:8000/query", json=fields)
            data = resp.json()

        st.markdown(data["answer"])
        with st.expander(f"Sources used ({len(data['sources'])})"):
            for s in data["sources"]:
                st.json(s)