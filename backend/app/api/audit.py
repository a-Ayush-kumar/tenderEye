from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AuditLog
import hashlib
import json

router = APIRouter()

@router.get("/verify")
def verify_audit_chain(db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.index).all()
    
    if not logs:
        return {"valid": True, "blocks": 0, "message": "No audit records"}
    
    # Verify chain linkage
    for i in range(1, len(logs)):
        current = logs[i]
        previous = logs[i-1]
        
        if current.prev_hash != previous.this_hash:
            return {
                "valid": False,
                "broken_at_index": current.index,
                "reason": "Hash chain linkage broken",
                "expected_prev_hash": previous.this_hash,
                "actual_prev_hash": current.prev_hash
            }
        
        # Recompute hash
        payload = {
            "timestamp": current.timestamp.isoformat() if current.timestamp else "",
            "event_type": current.event_type,
            "actor": current.actor,
            "data": current.data,
            "prev_hash": current.prev_hash
        }
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        recomputed = hashlib.sha256(payload_str.encode()).hexdigest()
        
        if current.this_hash != recomputed:
            return {
                "valid": False,
                "broken_at_index": current.index,
                "reason": "Hash mismatch",
                "expected": recomputed,
                "actual": current.this_hash
            }
    
    return {
        "valid": True,
        "blocks": len(logs),
        "from": logs[0].timestamp.isoformat() if logs[0].timestamp else None,
        "to": logs[-1].timestamp.isoformat() if logs[-1].timestamp else None
    }

@router.get("/logs")
def get_audit_logs(db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.index).all()
    return [
        {
            "index": log.index,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "event_type": log.event_type,
            "actor": log.actor,
            "data": log.data,
            "prev_hash": log.prev_hash,
            "this_hash": log.this_hash
        }
        for log in logs
    ]
