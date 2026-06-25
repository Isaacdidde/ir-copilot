# src/extract.py
import re
import json
from src.llm import call_ollama

IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
HASH_REGEX = re.compile(r"\b[a-fA-F0-9]{64}\b|\b[a-fA-F0-9]{32}\b")

EXTRACTION_PROMPT = """Extract these fields from the alert text below.
Return ONLY valid JSON, no explanation, no markdown formatting, with exactly these keys:
alert_name, host, user, process, command_line, file_path, network, indicators
Use an empty string "" for any field not mentioned in the text. Do not guess or invent values.

Alert text:
{raw_text}

JSON:"""

def regex_extract(text: str) -> dict:
    """Pattern-matchable fields the LLM shouldn't be trusted to transcribe exactly."""
    ips = dict.fromkeys(IP_REGEX.findall(text))
    hashes = dict.fromkeys(HASH_REGEX.findall(text))
    return {"network": ", ".join(ips), "file_path": ", ".join(hashes)}

def llm_extract(text: str, model_name: str = "llama3.1:8b") -> dict:
    prompt = EXTRACTION_PROMPT.format(raw_text=text)
    raw = call_ollama(prompt, model_name).strip()
    raw = raw.replace("```json", "").replace("```", "").strip()  # local models often ignore "no markdown"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}

def extract_fields(raw_text: str, model_name: str = "llama3.1:8b") -> dict:
    fields = llm_extract(raw_text, model_name)
    regex_hits = regex_extract(raw_text)

    # regex wins for IPs/hashes if the LLM missed or altered them
    for key, value in regex_hits.items():
        if value and not fields.get(key):
            fields[key] = value

    fields["notes"] = raw_text  # keep the original text as a safety net either way
    return fields