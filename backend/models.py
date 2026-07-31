"""Typed data models shared across the IR-Copilot backend."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    MITRE = "mitre"
    SIGMA = "sigma"
    NIST = "nist"
    PLAYBOOK = "playbook"


class Chunk(BaseModel):
    """A single retrievable unit of knowledge."""

    chunk_id: str
    text: str
    source_type: SourceType
    source_name: str
    file_path: str
    metadata: dict = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    chunk: Chunk
    dense_score: float = 0.0
    bm25_score: float = 0.0
    hybrid_score: float = 0.0
    rerank_score: Optional[float] = None


class IncidentRequest(BaseModel):
    incident_description: str = Field(..., min_length=10, max_length=8000)
    top_k: Optional[int] = None
    filters: Optional[dict] = None


class IRPhase(str, Enum):
    IDENTIFICATION = "Identification"
    CONTAINMENT = "Containment"
    ERADICATION = "Eradication"
    RECOVERY = "Recovery"


# --- 1. Summary ---
class Summary(BaseModel):
    what_happened: str = ""
    why_it_matches: str = ""


# --- 2. Evidence Used ---
class EvidenceItem(BaseModel):
    source_type: SourceType
    source_name: str
    why_it_supports: str = ""


# --- 3. MITRE ATT&CK Mapping ---
class MitreMapping(BaseModel):
    technique_id: str
    technique_name: str
    tactic: str
    confidence: float
    evidence_source: str = ""


# --- 4. Incident Response Steps ---
class IRStep(BaseModel):
    phase: IRPhase
    action: str


# --- 5. Confidence Assessment ---
class ConfidenceAssessment(BaseModel):
    explanation: str = ""
    conflicting_evidence: List[str] = Field(default_factory=list)


class IncidentResponse(BaseModel):
    # 1. Summary — plain-language explanation of the scenario
    summary: Summary = Field(default_factory=Summary)
    # 2. MITRE ATT&CK Mapping
    mitre_mapping: List[MitreMapping] = Field(default_factory=list)
    # 3. Evidence Used
    evidence: List[EvidenceItem] = Field(default_factory=list)
    # 4. Incident Response Steps (Identification / Containment / Eradication / Recovery)
    incident_response_steps: List[IRStep] = Field(default_factory=list)
    # 5. Missing Evidence
    missing_evidence: List[str] = Field(default_factory=list)
    # 6. Confidence Assessment
    confidence_assessment: ConfidenceAssessment = Field(default_factory=ConfidenceAssessment)

    # Top-level meta
    confidence_score: float = 0.0
    insufficient_evidence: bool = False
    tokens_used_estimate: int = 0
    retrieval_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0


class KBStatus(BaseModel):
    indexed_documents: int
    mitre_count: int
    sigma_count: int
    nist_count: int
    playbook_count: int
    llm_model: str
    embedding_model: str
    vector_db_status: str
    last_indexed_at: Optional[str] = None