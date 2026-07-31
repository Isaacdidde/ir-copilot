#!/usr/bin/env bash
# Starts the FastAPI backend and Streamlit frontend for local development.
# Assumes `ollama serve` is already running with the configured model pulled, e.g.:
#   ollama pull llama3.1:8b
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

echo "Starting FastAPI backend on :8000 ..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

trap "kill $BACKEND_PID" EXIT

sleep 3
echo "Starting Streamlit frontend on :8501 ..."
streamlit run frontend/app.py --server.address=0.0.0.0 --server.port=8501

# python -m uvicorn backend.main:app --host 0.0.0.0 --port 8010
# cd I:\Downloads\ir-copilot-updated\ir-copilot
# .venv\Scripts\Activate.ps1
# $env:IRCOPILOT_API_URL = "http://localhost:8010"
# python -m streamlit run frontend/app.py --server.port=8501
