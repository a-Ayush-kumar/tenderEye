"""
VIGIL API Routes - Collusion Detection & Risk Monitoring
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.database import get_db
from app.models import VigilAlert, Tender, Bid, Vendor
from app.services.vigil_engine import (
    run_vigil_analysis, 
    generate_cci_referral,
    get_risk_level,
    get_risk_action
)

router = APIRouter()


# ========== Pydantic Models ==========

class AlertResponse(BaseModel):
    id: str
    tender_id: str
    alert_type: str
    confidence: float
    risk_score: float
    description: Optional[str]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class VigilAnalysisRequest(BaseModel):
    tender_id: str


class VigilAnalysisResponse(BaseModel):
    tender_id: str
    alert_count: int
    risk_score: float
    risk_level: str
    action: str
    alerts: List[Dict[str, Any]]


class AlertActionRequest(BaseModel):
    status: str  # ACKNOWLEDGED, DISMISSED, ESCALATED
    acknowledged_by: Optional[str] = None


class CCIReferralResponse(BaseModel):
    tracking_id: str
    package: Dict[str, Any]


class TenderVigilStatus(BaseModel):
    tender_id: str
    tender_title: str
    risk_score: float
    risk_level: str
    alert_count: int
    last_analysis: Optional[datetime]


# ========== API Routes ==========

@router.post("/analyze", response_model=VigilAnalysisResponse)
def analyze_tender(request: VigilAnalysisRequest, db: Session = Depends(get_db)):
    """Run VIGIL analysis on a tender."""
    tender = db.query(Tender).filter(Tender.id == request.tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    result = run_vigil_analysis(request.tender_id, db)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/tenders/{tender_id}/alerts", response_model=List[AlertResponse])
def get_tender_alerts(tender_id: str, db: Session = Depends(get_db)):
    """Get all VIGIL alerts for a specific tender."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    alerts = db.query(VigilAlert).filter(
        VigilAlert.tender_id == tender_id
    ).order_by(VigilAlert.created_at.desc()).all()
    
    return alerts


@router.get("/alerts", response_model=List[AlertResponse])
def get_all_alerts(
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get all VIGIL alerts with optional filtering."""
    query = db.query(VigilAlert)
    
    if status:
        query = query.filter(VigilAlert.status == status)
    
    if risk_level:
        if risk_level == "CRITICAL":
            query = query.filter(VigilAlert.risk_score >= 70)
        elif risk_level == "HIGH":
            query = query.filter(VigilAlert.risk_score >= 40, VigilAlert.risk_score < 70)
        elif risk_level == "MEDIUM":
            query = query.filter(VigilAlert.risk_score >= 20, VigilAlert.risk_score < 40)
        elif risk_level == "LOW":
            query = query.filter(VigilAlert.risk_score < 20)
    
    alerts = query.order_by(VigilAlert.created_at.desc()).limit(limit).all()
    return alerts


@router.post("/alerts/{alert_id}/action")
def alert_action(alert_id: str, request: AlertActionRequest, db: Session = Depends(get_db)):
    """Acknowledge, dismiss, or escalate a VIGIL alert."""
    alert = db.query(VigilAlert).filter(VigilAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    if request.status not in ["ACKNOWLEDGED", "DISMISSED", "ESCALATED"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    alert.status = request.status
    if request.status == "ACKNOWLEDGED" and request.acknowledged_by:
        alert.acknowledged_by = request.acknowledged_by
        alert.acknowledged_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "message": f"Alert {alert_id} marked as {request.status}",
        "alert_id": alert_id,
        "new_status": request.status
    }


@router.post("/tenders/{tender_id}/cci-referral", response_model=CCIReferralResponse)
def create_cci_referral(tender_id: str, db: Session = Depends(get_db)):
    """Generate and send CCI referral package for a tender."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    result = generate_cci_referral(tender_id, db)
    
    if not result:
        raise HTTPException(
            status_code=400, 
            detail="No pending alerts for CCI referral or risk level not critical"
        )
    
    return result


@router.get("/dashboard")
def vigil_dashboard(db: Session = Depends(get_db)):
    """Get VIGIL dashboard summary statistics."""
    # Total alerts by status
    from sqlalchemy import func
    
    status_counts = db.query(
        VigilAlert.status, 
        func.count(VigilAlert.id)
    ).group_by(VigilAlert.status).all()
    
    # Risk level distribution
    all_alerts = db.query(VigilAlert).all()
    risk_distribution = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for alert in all_alerts:
        level = get_risk_level(alert.risk_score)
        risk_distribution[level] = risk_distribution.get(level, 0) + 1
    
    # Recent critical alerts
    critical_alerts = db.query(VigilAlert).filter(
        VigilAlert.risk_score >= 70
    ).order_by(VigilAlert.created_at.desc()).limit(5).all()
    
    # Tender risk status
    tenders_with_alerts = db.query(
        Tender.id, 
        Tender.title,
        func.max(VigilAlert.risk_score).label("max_risk"),
        func.count(VigilAlert.id).label("alert_count")
    ).join(VigilAlert).group_by(Tender.id, Tender.title).all()
    
    tender_status = [
        {
            "tender_id": t.id,
            "title": t.title,
            "risk_score": t.max_risk,
            "risk_level": get_risk_level(t.max_risk),
            "alert_count": t.alert_count
        }
        for t in tenders_with_alerts
    ]
    
    return {
        "summary": {
            "total_alerts": len(all_alerts),
            "status_breakdown": {status: count for status, count in status_counts},
            "risk_distribution": risk_distribution
        },
        "critical_alerts": [
            {
                "id": a.id,
                "tender_id": a.tender_id,
                "type": a.alert_type,
                "risk_score": a.risk_score,
                "description": a.description[:100] + "..." if a.description and len(a.description) > 100 else a.description
            }
            for a in critical_alerts
        ],
        "tender_status": sorted(tender_status, key=lambda x: x["risk_score"], reverse=True)[:10]
    }


@router.get("/network/{tender_id}")
def get_network_graph(tender_id: str, db: Session = Depends(get_db)):
    """Get network graph data for a tender."""
    from app.models import VigilNetworkEdge
    
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    # Get bidders
    bids = db.query(Bid).filter(Bid.tender_id == tender_id).all()
    vendor_ids = list(set(b.vendor_id for b in bids))
    
    # Get vendor details
    vendors = db.query(Vendor).filter(Vendor.id.in_(vendor_ids)).all()
    
    nodes = [
        {
            "id": v.id,
            "name": v.name,
            "kyc_status": v.kyc_status
        }
        for v in vendors
    ]
    
    # Get edges (both from VIGIL analysis and stored edges)
    edges = db.query(VigilNetworkEdge).filter(
        VigilNetworkEdge.tender_id == tender_id
    ).all()
    
    edges_data = [
        {
            "source": e.node_a_id,
            "target": e.node_b_id,
            "weight": e.weight,
            "type": e.edge_type
        }
        for e in edges
    ]
    
    return {
        "tender_id": tender_id,
        "nodes": nodes,
        "edges": edges_data
    }
