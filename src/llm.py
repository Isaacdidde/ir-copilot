"""
llm.py — Centralised Ollama caller with explicit error handling.

OllamaError is raised when Ollama responds with an error body (e.g. model not
pulled) rather than a normal generation result — avoiding silent KeyErrors.
"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """
    Raised when Ollama responds normally (HTTP 200) but without a generation
    result — most commonly because the requested model was never pulled.
    """
    pass


def call_ollama(
    prompt: str,
    model_name: str = "llama3.1:8b",
    timeout: int = 90,
) -> str:
    logger.debug("Calling Ollama model=%s prompt_len=%d", model_name, len(prompt))
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model_name, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    data = response.json()
    if "response" not in data:
        raise OllamaError(
            f"{data.get('error', 'Unexpected Ollama response: ' + str(data))} "
            f"— is '{model_name}' actually pulled? Run: ollama pull {model_name}"
        )
    return data["response"]