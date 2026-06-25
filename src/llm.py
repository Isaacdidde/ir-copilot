# src/llm.py
import requests

class OllamaError(Exception):
    """Raised when Ollama responds but doesn't return a normal generation result —
    most commonly because the requested model was never pulled."""
    pass

def call_ollama(prompt: str, model_name: str = "llama3.1:8b", timeout: int = 90) -> str:
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model_name, "prompt": prompt, "stream": False},
        timeout=timeout
    )
    data = response.json()
    if "response" not in data:
        raise OllamaError(
            f"{data.get('error', 'Unexpected Ollama response: ' + str(data))} "
            f"— is '{model_name}' actually pulled? Run: ollama pull {model_name}"
        )
    return data["response"]