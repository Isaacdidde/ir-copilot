"""
extract.py — Auto-extract structured incident fields from free-text alert descriptions.

Two-pass approach:
1. Regex for 100%-pattern-matchable fields (IPs, file hashes) — never trust an LLM
   to transcribe an IP or SHA256 exactly.
2. Local LLM call for everything else (host, process, command line, indicators).

The output of extract_fields() feeds directly into generate.format_incident(),
so nothing downstream (retrieval, generation) needs to change when the analyst
pastes raw text instead of filling a form.
"""

from __future__ import annotations

import json
import logging
import re

from src.llm import call_ollama

logger = logging.getLogger(__name__)

IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
HASH_REGEX = re.compile(r"\b[a-fA-F0-9]{64}\b|\b[a-fA-F0-9]{32}\b")

EXTRACTION_PROMPT = """Extract these fields from the alert text below.
Return ONLY valid JSON, no explanation, no markdown formatting, with exactly these keys:
alert_name, host, user, process, command_line, file_path, network, indicators
network means IP addresses, domains, or ports only — NOT HTTP status codes, which belong in indicators instead.
Use an empty string "" for any field not mentioned in the text. Do not guess or invent values.

Alert text:
{raw_text}

JSON:"""


def regex_extract(text: str) -> dict:
    """Pattern-matchable fields the LLM shouldn't be trusted to transcribe exactly."""
    ips = dict.fromkeys(IP_REGEX.findall(text))
    hashes = dict.fromkeys(HASH_REGEX.findall(text))
    return {
        "network": ", ".join(ips),
        "file_path": ", ".join(hashes),
    }


def llm_extract(text: str, model_name: str = "llama3.1:8b") -> dict:
    prompt = EXTRACTION_PROMPT.format(raw_text=text)
    raw = call_ollama(prompt, model_name).strip()
    # Local models often ignore "no markdown" — strip fences defensively
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM extraction returned non-JSON output; falling back to empty fields.")
        return {}


def extract_fields(raw_text: str, model_name: str = "llama3.1:8b") -> dict:
    """
    Return a structured field dict from a free-text alert or incident description.

    Regex results override LLM results for IPs and hashes — these should never
    be left to the LLM's discretion.
    The original raw text is preserved in ``notes`` as a safety net.
    """
    fields = llm_extract(raw_text, model_name)
    regex_hits = regex_extract(raw_text)

    for key, value in regex_hits.items():
        if value and not fields.get(key):
            fields[key] = value

    fields["notes"] = raw_text
    return fields