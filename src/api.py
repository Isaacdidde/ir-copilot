# src/api.py
from fastapi import FastAPI
from pydantic import BaseModel
from src.generate import generate_answer

app = FastAPI(title="IR Copilot API")

class IncidentQuery(BaseModel):
    incident_description: str

@app.post("/query")
def query_copilot(q: IncidentQuery):
    return generate_answer(q.incident_description)