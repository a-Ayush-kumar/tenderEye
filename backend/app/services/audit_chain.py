"""Stub audit chain service. Logs events to stdout instead of a real chain."""
import json
from datetime import datetime
from typing import Any, Optional


def log_audit_event(event_type: str, data: dict, db: Optional[Any] = None) -> dict:
    """Stub: log an audit event. Real implementation would anchor to a chain."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "data": data,
    }
    try:
        print(f"[AUDIT] {json.dumps(entry, default=str)}")
    except Exception:
        print(f"[AUDIT] {event_type}")
    return entry
