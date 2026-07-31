"""
Central configuration for IR-Copilot.

All tunable values live here (or in environment variables / .env) so that
no other module hardcodes paths, model names, thresholds, etc.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ---------------------------------------------------------------- paths
    base_dir: Path = BASE_DIR
    knowledge_dir: Path = BASE_DIR / "knowledge"
    mitre_dir: Path = BASE_DIR / "knowledge" / "mitre"
    sigma_dir: Path = BASE_DIR / "knowledge" / "sigma"
    nist_dir: Path = BASE_DIR / "knowledge" / "nist"
    playbooks_dir: Path = BASE_DIR / "playbooks"
    chroma_dir: Path = BASE_DIR / "data" / "chroma"
    cache_dir: Path = BASE_DIR / "embeddings" / "cache"
    log_dir: Path = BASE_DIR / "logs"

    # ---------------------------------------------------------------- LLM
    # "ollama" (local, default) or "groq" (hosted, free tier, no local GPU/CPU strain)
    llm_provider: str = Field(default="ollama")

    # --- Ollama-specific ---
    ollama_base_url: str = Field(default="http://localhost:11434")
    llm_model: str = Field(default="llama3.1:8b")
    llm_context_window: int = Field(default=8192)

    # --- Groq-specific ---
    groq_api_key: str = Field(default="")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1")
    groq_model: str = Field(default="openai/gpt-oss-20b")

    # --- shared generation params ---
    llm_temperature: float = Field(default=0.1)
    llm_max_tokens: int = Field(default=900)
    llm_timeout_seconds: int = Field(default=90)

    # ---------------------------------------------------------------- embeddings
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5")
    embedding_fallback_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    embedding_dim: int = Field(default=384)

    # ---------------------------------------------------------------- reranker
    reranker_model: str = Field(default="BAAI/bge-reranker-base")
    rerank_top_n: int = Field(default=5)

    # ---------------------------------------------------------------- chunking
    chunk_size_tokens: int = Field(default=500)
    chunk_overlap_tokens: int = Field(default=65)

    # ---------------------------------------------------------------- retrieval
    dense_top_k: int = Field(default=15)
    bm25_top_k: int = Field(default=15)
    hybrid_alpha: float = Field(default=0.55)
    final_top_k: int = Field(default=5)
    min_confidence_threshold: float = Field(default=0.35)
    max_context_chars: int = Field(default=6000)

    # ---------------------------------------------------------------- caching
    enable_embedding_cache: bool = Field(default=True)
    enable_retrieval_cache: bool = Field(default=True)
    retrieval_cache_ttl_seconds: int = Field(default=3600)
    retrieval_cache_max_entries: int = Field(default=256)

    # ---------------------------------------------------------------- app
    app_name: str = Field(default="IR-Copilot")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")
    conversation_memory_enabled: bool = Field(default=False)
    collection_name: str = Field(default="ir_copilot_kb")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="IRCOPILOT_", extra="ignore")


def get_settings() -> "Settings":
    """Return a cached Settings singleton."""
    global _settings_instance
    try:
        return _settings_instance
    except NameError:
        _settings_instance = Settings()
        for d in (
            _settings_instance.knowledge_dir,
            _settings_instance.mitre_dir,
            _settings_instance.sigma_dir,
            _settings_instance.nist_dir,
            _settings_instance.playbooks_dir,
            _settings_instance.chroma_dir,
            _settings_instance.cache_dir,
            _settings_instance.log_dir,
        ):
            os.makedirs(d, exist_ok=True)
        return _settings_instance


settings = get_settings()
