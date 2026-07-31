import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.llm import LLMError, extract_json  # noqa: E402
from backend.prompts import build_incident_prompt  # noqa: E402


def test_extract_json_plain():
    text = '{"a": 1, "b": "two"}'
    assert extract_json(text) == {"a": 1, "b": "two"}


def test_extract_json_with_markdown_fences():
    text = '```json\n{"a": 1}\n```'
    assert extract_json(text) == {"a": 1}


def test_extract_json_with_surrounding_commentary():
    text = 'Here is the result:\n{"a": 1}\nHope that helps!'
    assert extract_json(text) == {"a": 1}


def test_extract_json_raises_on_no_json():
    with pytest.raises(LLMError):
        extract_json("no json here at all")


def test_extract_json_raises_on_malformed_json():
    with pytest.raises(LLMError):
        extract_json("{a: 1,}")


def test_build_incident_prompt_contains_key_sections():
    prompt = build_incident_prompt("test incident", "some context", 0.8)
    assert "CONTEXT" in prompt
    assert "INCIDENT DESCRIPTION" in prompt
    assert "test incident" in prompt
    assert "insufficient_evidence" in prompt
