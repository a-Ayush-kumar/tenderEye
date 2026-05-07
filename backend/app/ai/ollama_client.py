import httpx
import json
import os
from typing import Optional

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

def _clean_json_response(text: str) -> str:
    """Clean up LLM response to extract valid JSON."""
    text = text.strip()
    # Remove markdown code blocks
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

async def extract_criteria_from_text(document_text: str, max_chars: int = 8000) -> list:
    """Use local LLM to extract criteria from tender document text.
    Falls back to mock criteria if Ollama is unavailable."""
    from app.ai.prompts import get_criteria_prompt
    
    truncated_text = document_text[:max_chars]
    prompt = get_criteria_prompt(truncated_text)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": os.getenv("OLLAMA_MODEL", "deepseek-r1"),
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 2048
                    }
                }
            )
        
        if response.status_code != 200:
            return _mock_criteria()
        
        result = response.json()
        raw_response = result.get("response", "")
        cleaned = _clean_json_response(raw_response)
        
        try:
            criteria = json.loads(cleaned)
            if isinstance(criteria, dict) and "criteria" in criteria:
                return criteria["criteria"]
            if isinstance(criteria, list):
                return criteria
            return _mock_criteria()
        except json.JSONDecodeError:
            # Fallback: try to find JSON array in the text
            start = cleaned.find("[")
            end = cleaned.rfind("]")
            if start != -1 and end != -1:
                try:
                    return json.loads(cleaned[start:end+1])
                except json.JSONDecodeError:
                    pass
            return _mock_criteria()
            
    except Exception as e:
        print(f"Ollama unavailable ({e}), using mock criteria")
        return _mock_criteria()

def _mock_criteria() -> list:
    """Return default criteria for prototype when LLM is unavailable."""
    return [
        {
            "id": "C-01",
            "type": "FINANCIAL",
            "description": "Minimum average annual turnover of Rs. 5 Crore over last 3 years",
            "threshold": 50000000,
            "currency": "INR",
            "time_window_years": 3
        },
        {
            "id": "C-02",
            "type": "COMPLIANCE",
            "description": "Valid GSTIN with matching PAN",
            "threshold": None,
            "currency": None,
            "time_window_years": None
        }
    ]

async def generate_embedding(text: str) -> Optional[list]:
    """Generate text embedding using Ollama's nomic-embed-text model."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_HOST}/api/embeddings",
                json={
                    "model": os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
                    "prompt": text[:512]  # Truncate to model limit
                }
            )
        
        if response.status_code != 200:
            return None
        
        result = response.json()
        return result.get("embedding")
        
    except Exception as e:
        print(f"Embedding error: {e}")
        return None
