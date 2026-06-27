To run each stage, open a terminal in your `ir-copilot` folder with the venv activated, then run these in order:

**Build the knowledge base (one-time setup):**
```powershell
python -m src.build_corpus
python -m src.ingest
```

**Start the backend API:**
```powershell
uvicorn src.api:app --reload-dir src --port 8000
```

**Start the frontend (in a second terminal):**
```powershell
python -m streamlit run src/app.py
```

**Run the eval harness:**
```powershell
python -m eval.run_eval
```

---

A few things that trip people up:

- **Always run from the project root** (`ir-copilot/`), not from inside `src/`. The `python -m` prefix only works when Python can see `src` as a package from the current directory.
- **Venv must be active** in every terminal you open. On Windows: `.venv\Scripts\Activate.ps1`. You'll see `(.venv)` in your prompt when it's working.
- **Ollama must be running** before you start the API. On Windows it runs as a background service after install, so it's usually already up. You can confirm with `ollama list`.
- **Build order matters** — `ingest` depends on `build_corpus` having produced `data/processed/corpus.json` first. If you add new playbooks or re-clone the data, re-run both steps.
- **Two terminals needed** for normal use: one for `uvicorn`, one for `streamlit`. The Streamlit UI talks to the API over `localhost:8000`, so both need to be running simultaneously.



prompt
Host: CORP-WIN10-042 | User: DOMAIN\jsmith
Process: powershell.exe | Parent: winword.exe (PID 4812)
Command: powershell.exe -nop -w hidden -enc JABjAGwAaQBlAG4AdA...
Network: IP: 185.220.101.45 | Domain: update.evil-c2.com | Port: 443 | Direction: outbound
File: C:\Temp\svc32.exe | Hash: d41d8cd98f00b204e9800998ecf8427e
Detection: Alert: Suspicious Encoded PowerShell | Tool: CrowdStrike Falcon