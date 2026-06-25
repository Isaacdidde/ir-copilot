# src/api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from src.generate import generate_answer, format_incident
from src.extract import extract_fields
from src.llm import OllamaError

app = FastAPI(title="IR Copilot API")

class IncidentInput(BaseModel):
    raw_text: str

@app.post("/query")
def query_copilot(payload: IncidentInput):
    try:
        fields = extract_fields(payload.raw_text)
        incident_description = format_incident(fields)
        result = generate_answer(incident_description)
    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Local LLM unreachable at localhost:11434. Is Ollama running? Try: ollama serve"
        )
    except OllamaError as e:
        raise HTTPException(status_code=503, detail=str(e))
    result["extracted_fields"] = fields
    return result