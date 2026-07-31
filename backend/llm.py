"""
LLM client for IR-Copilot, supporting two interchangeable providers:

- "ollama" (default): local Ollama server, e.g. http://localhost:11434
- "groq": Groq's hosted, OpenAI-compatible API (free tier available),
  offloading inference entirely off the local machine — no local GPU/CPU
  strain, no CUDA/driver issues, no model downloads.

Switch providers via IRCOPILOT_LLM_PROVIDER in .env ("ollama" or "groq").
The rest of the pipeline (backend/pipeline.py) is provider-agnostic — it
only calls generate() and extract_json(), so no other file needs to change
when switching providers.
"""

from __future__ import annotations

import json
import time
from typing import Optional, Tuple

import httpx

from backend.config import settings
from backend.logger import get_logger

logger = get_logger(__name__)


class LLMError(RuntimeError):
    pass


def _generate_ollama(prompt: str, system: Optional[str]) -> Tuple[str, float, int]:
    payload = {
        "model": settings.llm_model,
        "prompt": prompt,
        "system": system or "",
        "stream": False,
        "options": {
            "temperature": settings.llm_temperature,
            "num_predict": settings.llm_max_tokens,
            "num_ctx": settings.llm_context_window,
        },
    }

    start = time.perf_counter()
    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(f"{settings.ollama_base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.error("Ollama request failed: %s", exc)
        raise LLMError(
            f"Could not reach Ollama at {settings.ollama_base_url}. "
            f"Is `ollama serve` running with model '{settings.llm_model}' pulled?"
        ) from exc

    latency_ms = (time.perf_counter() - start) * 1000
    text = data.get("response", "")

    tokens_used = int(data.get("prompt_eval_count", 0)) + int(data.get("eval_count", 0))
    if tokens_used == 0:
        tokens_used = (len(prompt) + len(text)) // 4

    return text, latency_ms, tokens_used


def _generate_groq(prompt: str, system: Optional[str]) -> Tuple[str, float, int]:
    if not settings.groq_api_key:
        raise LLMError(
            "IRCOPILOT_GROQ_API_KEY is not set. Get a free API key at "
            "https://console.groq.com/keys and add it to .env."
        )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
        # Groq supports OpenAI-style JSON mode; the model still receives our
        # own explicit schema instructions in the prompt, this just adds a
        # server-side guarantee the output parses as JSON.
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    start = time.perf_counter()
    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(
                f"{settings.groq_base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500] if exc.response is not None else ""
        logger.error("Groq request failed: %s | %s", exc, body)
        raise LLMError(f"Groq API request failed ({exc.response.status_code}): {body}") from exc
    except httpx.HTTPError as exc:
        logger.error("Groq request failed: %s", exc)
        raise LLMError(
            f"Could not reach Groq at {settings.groq_base_url}. Check your internet "
            f"connection and IRCOPILOT_GROQ_API_KEY."
        ) from exc

    latency_ms = (time.perf_counter() - start) * 1000

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        logger.error("Unexpected Groq response shape: %s", data)
        raise LLMError(f"Unexpected Groq response shape: {exc}") from exc

    usage = data.get("usage", {})
    tokens_used = int(usage.get("total_tokens", 0))
    if tokens_used == 0:
        tokens_used = (len(prompt) + len(text)) // 4

    return text, latency_ms, tokens_used


def generate(prompt: str, system: Optional[str] = None) -> Tuple[str, float, int]:
    """Generate a completion using the configured provider.

    Returns (response_text, latency_ms, estimated_tokens_used).
    """
    provider = settings.llm_provider.lower().strip()

    if provider == "groq":
        return _generate_groq(prompt, system)
    elif provider == "ollama":
        return _generate_ollama(prompt, system)
    else:
        raise LLMError(
            f"Unknown IRCOPILOT_LLM_PROVIDER '{settings.llm_provider}'. "
            f"Must be 'ollama' or 'groq'."
        )


def extract_json(text: str) -> dict:
    """Extract a JSON object from an LLM response that may contain markdown
    fences or leading/trailing commentary."""
    cleaned = text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise LLMError(f"No JSON object found in LLM response: {text[:200]}")

    json_str = cleaned[start : end + 1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM JSON output: %s", exc)
        raise LLMError(f"LLM returned malformed JSON: {exc}") from exc
