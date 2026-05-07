"""Stub AI router. Real implementation would call Ollama / DeepSeek."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def ai_health():
    return {"status": "ok", "note": "AI router stub - no model backend connected."}
