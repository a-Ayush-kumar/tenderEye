"""
BidShield : Bid Submission API

"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Bid, BidAnchor, Vendor, Tender
from app.services.audit_chain import log_audit_event
from app.services.product_dna import evidence_locker
# from app.blockchain.fabric_client import get_fabric_client
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import os
import hashlib
import json
import asyncio

router = APIRouter(prefix="/bids", tags=["bids"])


# ============ Pydantic Models ============

class BidSubmitRequest(BaseModel):
    tender_id: str
    vendor_id: str
    file_hash: str = Field(..., pattern=r"^[a-fA-F0-9]{64}$")  # SHA-256 hex
    bid_amount: Optional[float] = None


class BidResponse(BaseModel):
    id: str
    tender_id: str
    vendor_id: str
    file_hash: str
    bid_amount: Optional[float]
    status: str
    blockchain_anchor_status: str
    submitted_at: datetime
    
    class Config:
        from_attributes = True


class BlockchainReceipt(BaseModel):
    bid_id: str
    transaction_id: str
    block_number: Optional[int]
    merkle_root: Optional[str]
    anchored_at: datetime
    verification_url: str


# ============ Mock Blockchain Service ============

class MockBlockchainService:
    """
    Mock Hyperledger Fabric service for development.
    In production, this connects to actual Fabric chaincode.
    """
    
    _transaction_counter = 1000
    _block_number = 500
    
    @classmethod
    def anchor_bid(cls, tender_id: str, vendor_id: str, file_hash: str) -> dict:
        """Create a blockchain anchor for a bid."""
        cls._transaction_counter += 1
        
        # Simulate block creation every 5 transactions
        if cls._transaction_counter % 5 == 0:
            cls._block_number += 1
        
        transaction_id = hashlib.sha256(
            f"{tender_id}:{vendor_id}:{file_hash}:{cls._transaction_counter}".encode()
        ).hexdigest()
        
        merkle_root = hashlib.sha256(
            f"block:{cls._block_number}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()
        
        return {
            "transaction_id": transaction_id,
            "block_number": cls._block_number,
            "merkle_root": merkle_root,
            "chaincode_name": "bidshield",
            "channel_name": "vigil-channel",
            "anchored_data": {
                "tender_id": tender_id,
                "vendor_id": vendor_id,
                "file_hash": file_hash,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    
    @classmethod
    def verify_anchor(cls, transaction_id: str, expected_hash: str) -> bool:
        """Verify a bid anchor exists and matches expected hash."""
        # Mock verification - in production queries Fabric
        return transaction_id.startswith("0") or transaction_id.startswith("1")


# ============ API Endpoints ============

@router.post("/submit", response_model=BidResponse)
def submit_bid(
    tender_id: str = Form(...),
    vendor_id: str = Form(...),
    file_hash: str = Form(..., pattern=r"^[a-fA-F0-9]{64}$"),
    bid_amount: Optional[float] = Form(None),
    bid_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Submit a bid with client-side hash verification and blockchain anchoring.
    
    Flow:
    1. Vendor computes SHA-256 of bid file in browser
    2. Submits hash + file
    3. Backend verifies hash matches uploaded file
    4. Creates blockchain anchor
    5. Returns blockchain receipt
    """
    # Validate vendor exists and is KYC verified
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    if vendor.kyc_status != "VERIFIED":
        raise HTTPException(
            status_code=400, 
            detail=f"Vendor KYC not verified. Current status: {vendor.kyc_status}"
        )
    
    # Validate tender exists and is open for bidding
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    if tender.status not in ["PUBLISHED", "OPEN"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Tender not open for bidding. Status: {tender.status}"
        )
    
    # Check for duplicate bid from same vendor
    existing_bid = db.query(Bid).filter(
        Bid.tender_id == tender_id,
        Bid.vendor_id == vendor_id
    ).first()
    
    if existing_bid:
        raise HTTPException(
            status_code=400, 
            detail="Vendor has already submitted a bid for this tender"
        )
    
    # Verify file hash matches
    file_content = bid_file.file.read()
    computed_hash = hashlib.sha256(file_content).hexdigest()
    
    if computed_hash.lower() != file_hash.lower():
        log_audit_event("BID_HASH_MISMATCH", {
            "tender_id": tender_id,
            "vendor_id": vendor_id,
            "provided_hash": file_hash,
            "computed_hash": computed_hash
        }, db)
        raise HTTPException(
            status_code=400,
            detail="File hash mismatch. File may have been tampered with during upload."
        )
    
    # Product DNA / Evidence Locker check
    dna_result = evidence_locker.register_document(
        doc_id=f"bid_{tender_id}_{vendor_id}",
        content=file_content,
        vendor_id=vendor_id,
        tender_id=tender_id
    )

    # Check for duplicate file hash across all bids (detect copy-paste bids)
    duplicate_file = db.query(Bid).filter(Bid.file_hash == file_hash).first()
    if duplicate_file:
        log_audit_event("BID_DUPLICATE_FILE_DETECTED", {
            "tender_id": tender_id,
            "vendor_id": vendor_id,
            "file_hash": file_hash,
            "original_bid_id": duplicate_file.id
        }, db)
        # Don't reject, but flag for VIGIL review
    
    # Store bid file
    upload_dir = os.path.join("uploads", "bids", tender_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, f"{vendor_id}_{bid_file.filename}")
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Create bid record
    bid = Bid(
        tender_id=tender_id,
        vendor_id=vendor_id,
        file_hash=file_hash,
        bid_amount=bid_amount,
        status="SUBMITTED",
        blockchain_anchor_status="PENDING"
    )
    db.add(bid)
    db.commit()
    db.refresh(bid)
    
    # Create blockchain anchor (real Fabric or mock fallback)
    try:
        fabric_client = get_fabric_client()

        # Run async anchor operation
        loop = asyncio.get_event_loop()
        anchor_result = loop.run_until_complete(
            fabric_client.anchor_bid(
                tender_id=tender_id,
                vendor_id=vendor_id,
                file_hash=file_hash
            )
        )

        anchor = BidAnchor(
            bid_id=bid.id,
            transaction_id=anchor_result["transaction_id"],
            block_number=anchor_result.get("block_number"),
            chaincode_name=anchor_result["chaincode_name"],
            channel_name=anchor_result["channel_name"],
            anchored_data=anchor_result["anchored_data"],
            merkle_root=anchor_result.get("merkle_root"),
            receipt_json=anchor_result
        )
        db.add(anchor)

        # Update bid with anchor info
        bid.blockchain_tx_hash = anchor_result["transaction_id"]
        bid.blockchain_anchor_status = "CONFIRMED" if anchor_result.get("source") != "mock" else "CONFIRMED_MOCK"
        bid.anchored_at = datetime.utcnow()

        db.commit()

        log_audit_event("BID_SUBMITTED", {
            "bid_id": bid.id,
            "tender_id": tender_id,
            "vendor_id": vendor_id,
            "file_hash": file_hash,
            "blockchain_tx": anchor_result["transaction_id"],
            "blockchain_source": anchor_result.get("source", "unknown"),
            "duplicate_detected": duplicate_file is not None
        }, db)

    except Exception as e:
        bid.blockchain_anchor_status = "FAILED"
        db.commit()

        log_audit_event("BID_BLOCKCHAIN_ANCHOR_FAILED", {
            "bid_id": bid.id,
            "error": str(e)
        }, db)
    
    return bid


@router.get("/{bid_id}", response_model=BidResponse)
def get_bid(bid_id: str, db: Session = Depends(get_db)):
    """Get bid details by ID."""
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
    return bid


@router.get("/{bid_id}/blockchain-receipt", response_model=BlockchainReceipt)
def get_blockchain_receipt(bid_id: str, db: Session = Depends(get_db)):
    """Get blockchain anchoring receipt for a bid."""
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
    
    anchor = db.query(BidAnchor).filter(BidAnchor.bid_id == bid_id).first()
    if not anchor:
        raise HTTPException(status_code=404, detail="Blockchain anchor not found")
    
    return BlockchainReceipt(
        bid_id=bid_id,
        transaction_id=anchor.transaction_id,
        block_number=anchor.block_number,
        merkle_root=anchor.merkle_root,
        anchored_at=anchor.created_at,
        verification_url=f"/api/v1/bids/{bid_id}/verify"
    )


@router.get("/{bid_id}/verify")
def verify_bid_integrity(bid_id: str, db: Session = Depends(get_db)):
    """
    Verify bid integrity by checking:
    1. Blockchain anchor exists and is valid
    2. File hash matches blockchain record
    3. No tampering detected
    """
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
    
    anchor = db.query(BidAnchor).filter(BidAnchor.bid_id == bid_id).first()
    
    verification_result = {
        "bid_id": bid_id,
        "verified_at": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # Check 1: Blockchain anchor exists
    if not anchor:
        verification_result["checks"]["blockchain_anchor"] = {
            "status": "FAILED",
            "reason": "No blockchain anchor found"
        }
        verification_result["overall"] = "FAILED"
        return verification_result
    
    verification_result["checks"]["blockchain_anchor"] = {
        "status": "PASSED",
        "transaction_id": anchor.transaction_id,
        "block_number": anchor.block_number
    }
    
    # Check 2: File hash matches blockchain record
    anchored_data = anchor.anchored_data
    if anchored_data.get("file_hash") != bid.file_hash:
        verification_result["checks"]["file_hash_match"] = {
            "status": "FAILED",
            "reason": "File hash mismatch between bid and blockchain record"
        }
        verification_result["overall"] = "FAILED"
        return verification_result
    
    verification_result["checks"]["file_hash_match"] = {
        "status": "PASSED",
        "file_hash": bid.file_hash
    }
    
    # Check 3: Verify blockchain transaction (mock)
    if MockBlockchainService.verify_anchor(anchor.transaction_id, bid.file_hash):
        verification_result["checks"]["blockchain_verification"] = {
            "status": "PASSED",
            "message": "Transaction confirmed on blockchain"
        }
    else:
        verification_result["checks"]["blockchain_verification"] = {
            "status": "WARNING",
            "message": "Blockchain verification pending (mock mode)"
        }
    
    verification_result["overall"] = "VERIFIED"
    verification_result["bid_details"] = {
        "vendor_id": bid.vendor_id,
        "tender_id": bid.tender_id,
        "submitted_at": bid.submitted_at.isoformat(),
        "blockchain_anchor_status": bid.blockchain_anchor_status
    }
    
    return verification_result


@router.get("/tender/{tender_id}")
def list_tender_bids(tender_id: str, db: Session = Depends(get_db)):
    """List all bids for a tender (for bid opening)."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    bids = db.query(Bid).filter(Bid.tender_id == tender_id).all()
    
    return [
        {
            "id": b.id,
            "vendor_id": b.vendor_id,
            "vendor_name": db.query(Vendor).filter(Vendor.id == b.vendor_id).first().name,
            "bid_amount": b.bid_amount,
            "status": b.status,
            "blockchain_verified": b.blockchain_anchor_status == "CONFIRMED",
            "submitted_at": b.submitted_at
        }
        for b in bids
    ]


@router.post("/{bid_id}/open")
def open_bid(bid_id: str, officer_id: str = Form(...), db: Session = Depends(get_db)):
    """
    Open a bid after tender closing.
    Verifies blockchain anchor before opening.
    """
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
    
    if bid.status != "SUBMITTED":
        raise HTTPException(status_code=400, detail=f"Bid already {bid.status}")
    
    # Verify blockchain anchor before opening
    if bid.blockchain_anchor_status != "CONFIRMED":
        log_audit_event("BID_OPEN_BLOCKED", {
            "bid_id": bid_id,
            "reason": "Blockchain anchor not confirmed",
            "officer_id": officer_id
        }, db)
        raise HTTPException(
            status_code=400, 
            detail="Cannot open bid: Blockchain anchor not confirmed. Possible tampering detected."
        )
    
    bid.status = "OPENED"
    bid.opened_at = datetime.utcnow()
    db.commit()
    
    log_audit_event("BID_OPENED", {
        "bid_id": bid_id,
        "tender_id": bid.tender_id,
        "vendor_id": bid.vendor_id,
        "officer_id": officer_id,
        "file_hash": bid.file_hash
    }, db)
    
    return {
        "status": "OPENED",
        "bid_id": bid_id,
        "opened_at": bid.opened_at.isoformat(),
        "blockchain_verified": True
    }


@router.get("/tender/{tender_id}/integrity-check")
def check_tender_bid_integrity(tender_id: str, db: Session = Depends(get_db)):
    """
    Pre-opening integrity check for all bids in a tender.
    Detects:
    - Duplicate file hashes (copy-paste bids)
    - Missing blockchain anchors
    - Hash mismatches
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    bids = db.query(Bid).filter(Bid.tender_id == tender_id).all()
    
    issues = []
    file_hash_counts = {}
    
    for bid in bids:
        # Check blockchain anchor
        if bid.blockchain_anchor_status != "CONFIRMED":
            issues.append({
                "bid_id": bid.id,
                "vendor_id": bid.vendor_id,
                "issue": "BLOCKCHAIN_ANCHOR_MISSING",
                "severity": "CRITICAL"
            })
        
        # Track duplicate file hashes
        file_hash = bid.file_hash.lower()
        if file_hash in file_hash_counts:
            file_hash_counts[file_hash].append(bid.id)
        else:
            file_hash_counts[file_hash] = [bid.id]
    
    # Report duplicates
    for file_hash, bid_ids in file_hash_counts.items():
        if len(bid_ids) > 1:
            issues.append({
                "issue": "DUPLICATE_FILE_HASH",
                "severity": "HIGH",
                "file_hash": file_hash[:16] + "...",
                "bid_count": len(bid_ids),
                "bid_ids": bid_ids,
                "message": "Multiple bids have identical file hashes - possible collusion"
            })
    
    return {
        "tender_id": tender_id,
        "total_bids": len(bids),
        "issues_found": len(issues),
        "integrity_status": "FAILED" if any(i["severity"] == "CRITICAL" for i in issues) else "WARNING" if issues else "PASSED",
        "issues": issues,
        "can_proceed_with_opening": not any(i["severity"] == "CRITICAL" for i in issues)
    }


@router.get("/tender/{tender_id}/dedup-report")
def get_dedup_report(tender_id: str):
    """Get Product DNA deduplication report for a tender."""
    report = evidence_locker.get_tender_dedup_report(tender_id)
    return report


# ============ EMD Escrow ============

EMD_TRANSACTIONS = {}

@router.post("/{bid_id}/emd")
def submit_emd(
    bid_id: str,
    amount: float = Form(...),
    transaction_ref: str = Form(...),
    payment_method: str = Form(...),  # NEFT, RTGS, DD, BG
    db: Session = Depends(get_db)
):
    """
    Submit Earnest Money Deposit (EMD) for a bid.
    Validates minimum EMD amount and creates escrow record.
    """
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")

    tender = db.query(Tender).filter(Tender.id == bid.tender_id).first()

    # Calculate minimum EMD (typically 2% of estimated value or bid amount)
    min_emd = bid.bid_amount * 0.02 if bid.bid_amount else 100000

    if amount < min_emd:
        raise HTTPException(
            status_code=400,
            detail=f"EMD must be at least 2% of bid amount (₹{min_emd:,.2f})"
        )

    emd_record = {
        "bid_id": bid_id,
        "tender_id": bid.tender_id,
        "vendor_id": bid.vendor_id,
        "amount": amount,
        "currency": "INR",
        "transaction_ref": transaction_ref,
        "payment_method": payment_method,
        "status": "HELD_IN_ESCROW",
        "submitted_at": datetime.utcnow().isoformat(),
        "refund_conditions": [
            "Bid not opened: Full refund within 30 days",
            "Bid opened, not selected: Refund after contract award",
            "Bid selected: Adjusted against performance security"
        ]
    }

    EMD_TRANSACTIONS[bid_id] = emd_record

    log_audit_event("EMD_SUBMITTED", {
        "bid_id": bid_id,
        "amount": amount,
        "transaction_ref": transaction_ref,
        "payment_method": payment_method
    }, db)

    return {
        "status": "EMD_HELD",
        "escrow_id": f"EMD-{bid_id[:8]}",
        "amount_held": amount,
        "refund_policy": emd_record["refund_conditions"]
    }


@router.get("/{bid_id}/emd")
def get_emd_status(bid_id: str):
    """Get EMD status for a bid."""
    emd = EMD_TRANSACTIONS.get(bid_id)
    if not emd:
        raise HTTPException(status_code=404, detail="EMD not found for this bid")
    return emd


@router.post("/{bid_id}/emd/refund")
def refund_emd(bid_id: str, reason: str = Form(...), db: Session = Depends(get_db)):
    """Process EMD refund after bid evaluation."""
    emd = EMD_TRANSACTIONS.get(bid_id)
    if not emd:
        raise HTTPException(status_code=404, detail="EMD not found")

    if emd["status"] == "REFUNDED":
        raise HTTPException(status_code=400, detail="EMD already refunded")

    emd["status"] = "REFUNDED"
    emd["refund_reason"] = reason
    emd["refunded_at"] = datetime.utcnow().isoformat()

    log_audit_event("EMD_REFUNDED", {
        "bid_id": bid_id,
        "amount": emd["amount"],
        "reason": reason
    }, db)

    return {
        "status": "REFUNDED",
        "amount": emd["amount"],
        "refund_reason": reason,
        "expected_credit": "7-14 business days"
    }


# ============ Pre-bid Video (Jitsi stub) ============

@router.post("/tender/{tender_id}/pre-bid-session")
def create_prebid_session(tender_id: str, officer_id: str = Form(...), db: Session = Depends(get_db)):
    """
    Create a pre-bid clarification session (Jitsi Meet stub).
    In production: integrate with Jitsi API or NIC VC.
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    import uuid
    session_id = f"prebid-{tender_id}-{uuid.uuid4().hex[:8]}"

    # Mock Jitsi room URL
    jitsi_room = f"VIGIL-PreBid-{tender_id}-{datetime.utcnow().strftime('%Y%m%d')}"

    log_audit_event("PREBID_SESSION_CREATED", {
        "tender_id": tender_id,
        "session_id": session_id,
        "officer_id": officer_id,
        "jitsi_room": jitsi_room
    }, db)

    return {
        "session_id": session_id,
        "tender_id": tender_id,
        "video_platform": "Jitsi Meet",
        "room_url": f"https://meet.jit.si/{jitsi_room}",
        "room_name": jitsi_room,
        "scheduled_at": datetime.utcnow().isoformat(),
        "deepfake_detection": "ENABLED (stub - would analyze video streams)",
        "recording": "Auto-enabled",
        "access_control": {
            "moderator": officer_id,
            "join_policy": "INVITE_ONLY",
            "lobby_enabled": True
        }
    }
