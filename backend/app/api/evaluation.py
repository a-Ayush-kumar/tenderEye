from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Tender, Bidder, BidderDocument, Verdict, VigilAlert
from app.services.financial_matcher import evaluate_financial
from app.services.compliance_matcher import evaluate_compliance
from app.services.technical_matcher import evaluate_technical
from app.services.documentary_matcher import evaluate_documentary
from app.services.audit_chain import log_audit_event
from app.services.report_generator import generate_evaluation_report
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()

class VerdictResponse(BaseModel):
    criterion_id: str
    criterion_type: str
    verdict: str
    reason: Optional[str] = None
    confidence: float

class EvaluationResult(BaseModel):
    bidder_id: str
    bidder_name: str
    overall: str
    verdicts: List[VerdictResponse]
    vigil_risk_score: Optional[float] = None
    vigil_risk_level: Optional[str] = None

@router.post("/{tender_id}/run")
def run_evaluation(tender_id: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    if not tender.criteria_locked:
        raise HTTPException(status_code=400, detail="Criteria must be locked before evaluation")
    
    criteria = tender.criteria
    if not criteria:
        raise HTTPException(status_code=400, detail="No criteria defined")
    
    # Check for VIGIL alerts on this tender
    vigil_alerts = db.query(VigilAlert).filter(VigilAlert.tender_id == tender_id).all()
    max_vigil_risk = max([a.risk_score for a in vigil_alerts], default=0)
    vigil_level = "LOW"
    if max_vigil_risk >= 70:
        vigil_level = "CRITICAL"
    elif max_vigil_risk >= 40:
        vigil_level = "HIGH"
    elif max_vigil_risk >= 20:
        vigil_level = "MEDIUM"
    
    bidders = db.query(Bidder).filter(Bidder.tender_id == tender_id).all()
    results = []

    # Clear prior verdicts for this tender's bidders so re-runs don't accumulate
    # duplicate rows per criterion. Audit chain still preserves the full history.
    bidder_ids = [b.id for b in bidders]
    if bidder_ids:
        db.query(Verdict).filter(Verdict.bidder_id.in_(bidder_ids)).delete(
            synchronize_session=False
        )
        db.commit()

    for bidder in bidders:
        verdicts = []
        docs = db.query(BidderDocument).filter(BidderDocument.bidder_id == bidder.id).all()
        
        for criterion in criteria:
            if criterion.get("type") == "FINANCIAL":
                doc = next((d for d in docs if d.doc_type == "AUDITED_ACCOUNTS"), None)
                result_data = evaluate_financial(doc, criterion) if doc else {
                    "verdict": "NEEDS_REVIEW",
                    "reason": "No audited accounts document",
                    "confidence": 0.3,
                    "source_page": None,
                    "verbatim_quote": None
                }
            elif criterion.get("type") == "COMPLIANCE":
                result_data = evaluate_compliance(bidder, criterion)
            elif criterion.get("type") == "TECHNICAL":
                doc = next((d for d in docs if d.doc_type == "TECHNICAL"), None)
                if doc:
                    import asyncio
                    import concurrent.futures
                    # Run async matcher in a new thread to avoid
                    # "cannot call run_until_complete while loop is running"
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        result_data = pool.submit(
                            asyncio.run, evaluate_technical(doc, criterion)
                        ).result()
                else:
                    result_data = {
                        "verdict": "NEEDS_REVIEW",
                        "reason": "No technical document available",
                        "confidence": 0.3,
                        "source_page": None,
                        "verbatim_quote": None
                    }
            elif criterion.get("type") == "DOCUMENTARY":
                doc = next((d for d in docs if d.doc_type == "AUDITED_ACCOUNTS"), None)
                result_data = evaluate_documentary(doc, criterion, tender) if doc else {
                    "verdict": "NEEDS_REVIEW",
                    "reason": "No document available for documentary evaluation",
                    "confidence": 0.3,
                    "source_page": None,
                    "verbatim_quote": None
                }
            else:
                result_data = {
                    "verdict": "NEEDS_REVIEW",
                    "reason": f"Unknown criterion type: {criterion.get('type')}",
                    "confidence": 0.5,
                    "source_page": None,
                    "verbatim_quote": None
                }
            
            # Only pass known Verdict columns — matchers may return extra keys
            verdict = Verdict(
                bidder_id=bidder.id,
                criterion_id=criterion.get("id", "UNKNOWN"),
                criterion_type=criterion.get("type", "UNKNOWN"),
                verdict=result_data["verdict"],
                reason=result_data.get("reason"),
                confidence=result_data.get("confidence", 0.5),
                source_page=result_data.get("source_page") if isinstance(result_data.get("source_page"), int) else None,
                verbatim_quote=result_data.get("verbatim_quote")
            )
            db.add(verdict)
            verdicts.append(verdict)
        
        statuses = [v.verdict for v in verdicts]
        overall = "NOT_ELIGIBLE" if "NOT_ELIGIBLE" in statuses else "NEEDS_REVIEW" if "NEEDS_REVIEW" in statuses else "ELIGIBLE"
        
        # Override to COLLUSION_RISK if VIGIL risk >= 40
        if max_vigil_risk >= 40:
            overall = "COLLUSION_RISK"
        
        db.commit()
        
        log_audit_event("VERDICT_COMPUTED", {
            "tender_id": str(tender_id),
            "bidder_id": str(bidder.id),
            "overall_verdict": overall,
            "criteria_verdicts": [{"criterion_id": v.criterion_id, "verdict": v.verdict} for v in verdicts]
        }, db)
        
        results.append(EvaluationResult(
            bidder_id=str(bidder.id),
            bidder_name=bidder.name,
            overall=overall,
            verdicts=[
                VerdictResponse(
                    criterion_id=v.criterion_id,
                    criterion_type=v.criterion_type,
                    verdict=v.verdict,
                    reason=v.reason,
                    confidence=v.confidence
                ) for v in verdicts
            ],
            vigil_risk_score=max_vigil_risk,
            vigil_risk_level=vigil_level
        ))
    
    # Log VIGIL override if applied
    if max_vigil_risk >= 40:
        log_audit_event("VIGIL_OVERRIDE_APPLIED", {
            "tender_id": tender_id,
            "max_risk_score": max_vigil_risk,
            "risk_level": vigil_level,
            "affected_bidders": len(bidders)
        }, db)
    
    return {"tender_id": tender_id, "results": results, "vigil_summary": {
        "max_risk_score": max_vigil_risk,
        "risk_level": vigil_level,
        "alert_count": len(vigil_alerts)
    }}

@router.get("/{tender_id}/results")
def get_results(tender_id: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    bidders = db.query(Bidder).filter(Bidder.tender_id == tender_id).all()
    results = []
    
    for bidder in bidders:
        verdicts = db.query(Verdict).filter(Verdict.bidder_id == bidder.id).all()
        
        if verdicts:
            statuses = [v.verdict for v in verdicts]
            overall = "NOT_ELIGIBLE" if "NOT_ELIGIBLE" in statuses else "NEEDS_REVIEW" if "NEEDS_REVIEW" in statuses else "ELIGIBLE"
            
            results.append(EvaluationResult(
                bidder_id=str(bidder.id),
                bidder_name=bidder.name,
                overall=overall,
                verdicts=[
                    VerdictResponse(
                        criterion_id=v.criterion_id,
                        criterion_type=v.criterion_type,
                        verdict=v.verdict,
                        reason=v.reason,
                        confidence=v.confidence
                    ) for v in verdicts
                ]
            ))
    
    return {"tender_id": tender_id, "results": results}

@router.get("/{tender_id}/report")
def get_report(tender_id: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    bidders = db.query(Bidder).filter(Bidder.tender_id == tender_id).all()
    
    report_data = {"tender": tender, "bidders": []}
    
    for bidder in bidders:
        verdicts = db.query(Verdict).filter(Verdict.bidder_id == bidder.id).all()
        statuses = [v.verdict for v in verdicts] if verdicts else []
        overall = "PENDING"
        if verdicts:
            overall = "NOT_ELIGIBLE" if "NOT_ELIGIBLE" in statuses else "NEEDS_REVIEW" if "NEEDS_REVIEW" in statuses else "ELIGIBLE"
        
        report_data["bidders"].append({
            "bidder": bidder,
            "verdicts": verdicts,
            "overall": overall
        })
    
    pdf = generate_evaluation_report(report_data)
    from fastapi.responses import Response
    return Response(content=pdf, media_type="application/pdf")
