# src/api.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from src.generate import generate_answer, format_incident

app = FastAPI(title="IR Copilot API")

class IncidentFields(BaseModel):
    alert_name: Optional[str] = ""
    host: Optional[str] = ""
    user: Optional[str] = ""
    process: Optional[str] = ""
    command_line: Optional[str] = ""
    file_path: Optional[str] = ""
    network: Optional[str] = ""
    indicators: Optional[str] = ""
    notes: Optional[str] = ""

@app.post("/query")
def query_copilot(fields: IncidentFields):
    incident_description = format_incident(fields.dict())
    return generate_answer(incident_description)