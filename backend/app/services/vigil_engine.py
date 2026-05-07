"""Stub VIGIL engine. Returns benign analysis results so the API can run."""
from datetime import datetime
from typing import Any, Optional
import uuid


def get_risk_level(risk_score: Optional[float]) -> str:
    if risk_score is None:
        return "LOW"
    if risk_score >= 70:
        return "CRITICAL"
    if risk_score >= 40:
        return "HIGH"
    if risk_score >= 20:
        return "MEDIUM"
    return "LOW"


def get_risk_action(risk_score: Optional[float]) -> str:
    level = get_risk_level(risk_score)
    return {
        "CRITICAL": "BLOCK_AND_REFER_CCI",
        "HIGH": "MANUAL_REVIEW",
        "MEDIUM": "MONITOR",
        "LOW": "PROCEED",
    }[level]


def run_vigil_analysis(tender_id: str, db: Any) -> dict:
    """Stub: returns zero-risk analysis without scanning bids."""
    return {
        "tender_id": tender_id,
        "alert_count": 0,
        "risk_score": 0.0,
        "risk_level": get_risk_level(0.0),
        "action": get_risk_action(0.0),
        "alerts": [],
    }


def generate_cci_referral(tender_id: str, db: Any) -> Optional[dict]:
    """Stub: returns a placeholder referral package."""
    return {
        "tracking_id": f"CCI-{uuid.uuid4().hex[:8].upper()}",
        "package": {
            "tender_id": tender_id,
            "generated_at": datetime.utcnow().isoformat(),
            "alerts": [],
            "note": "Stub CCI referral - vigil_engine not implemented.",
        },
    }
