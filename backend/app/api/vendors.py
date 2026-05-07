"""
BidShield Phase 1: Vendor Identity & KYC API
Vendor registration, KYC verification, and document management
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Vendor, VendorDocument
from app.services.audit_chain import log_audit_event
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import os
import hashlib
import re

router = APIRouter(prefix="/vendors", tags=["vendors"])


# ============ Pydantic Models ============

class VendorCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: Optional[str] = None
    phone: Optional[str] = None
    pan: Optional[str] = None
    gstin: Optional[str] = None


class VendorResponse(BaseModel):
    id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    pan: Optional[str]
    gstin: Optional[str]
    kyc_status: str
    kyc_verified_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class KYCStatusResponse(BaseModel):
    vendor_id: str
    kyc_status: str
    aadhaar_verified: bool
    pan_verified: bool
    gstin_verified: bool
    bank_verified: bool
    dsc_bound: bool
    progress_percent: int


class AadhaarKYCRequest(BaseModel):
    aadhaar_number: str = Field(..., pattern=r"^\d{12}$")
    otp: Optional[str] = None  # For step 2


# ============ GSTIN Validation (Deterministic Checksum) ============

GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
MULTIPLIERS = [1, 2, 1, 2, 1, 2, 4, 1, 2, 1, 2, 4, 1, 2]
VALID_STATE_CODES = {f"{i:02d}" for i in range(1, 38)}  # 01-37


def validate_gstin(gstin: str) -> dict:
    """
    Validate GSTIN using deterministic checksum algorithm.
    No LLM calls - 100% algorithmic as per implementation plan.
    """
    gstin = gstin.upper().strip()
    
    if len(gstin) != 15:
        return {"valid": False, "reason": "GSTIN must be 15 characters"}
    
    # Check state code
    state_code = gstin[:2]
    if state_code not in VALID_STATE_CODES:
        return {"valid": False, "reason": f"Invalid state code: {state_code}"}
    
    # Check PAN format (positions 2-11)
    pan_part = gstin[2:12]
    if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", pan_part):
        return {"valid": False, "reason": "Invalid PAN format in GSTIN"}
    
    # Check entity number (position 13)
    entity_number = gstin[12]
    if not entity_number.isdigit():
        return {"valid": False, "reason": "Entity number must be digit"}
    
    # Check default digit (position 14) - should be 'Z'
    if gstin[13] != 'Z':
        return {"valid": False, "reason": "14th character should be Z"}
    
    # Checksum calculation
    total = 0
    for i, char in enumerate(gstin[:14]):
        value = GSTIN_CHARS.index(char)
        product = value * MULTIPLIERS[i]
        total += (product // 10) + (product % 10)
    
    check_digit = GSTIN_CHARS[(10 - (total % 10)) % 10]
    if gstin[14] != check_digit:
        return {"valid": False, "reason": f"Checksum failed. Expected {check_digit}, got {gstin[14]}"}
    
    # Extract PAN from GSTIN for cross-check
    extracted_pan = gstin[2:12]
    
    return {
        "valid": True, 
        "reason": "Valid GSTIN",
        "state_code": state_code,
        "pan": extracted_pan,
        "entity_number": entity_number
    }


# ============ API Endpoints ============

@router.post("/", response_model=VendorResponse)
def create_vendor(vendor: VendorCreate, db: Session = Depends(get_db)):
    """Register a new vendor. KYC starts as PENDING."""
    # Check for duplicate PAN or GSTIN if provided
    if vendor.pan:
        existing = db.query(Vendor).filter(Vendor.pan == vendor.pan.upper()).first()
        if existing:
            raise HTTPException(status_code=400, detail="PAN already registered")
    
    if vendor.gstin:
        gstin_check = validate_gstin(vendor.gstin)
        if not gstin_check["valid"]:
            raise HTTPException(status_code=400, detail=f"Invalid GSTIN: {gstin_check['reason']}")
        
        existing = db.query(Vendor).filter(Vendor.gstin == vendor.gstin.upper()).first()
        if existing:
            raise HTTPException(status_code=400, detail="GSTIN already registered")
    
    # Create vendor
    db_vendor = Vendor(
        name=vendor.name,
        email=vendor.email,
        phone=vendor.phone,
        pan=vendor.pan.upper() if vendor.pan else None,
        gstin=vendor.gstin.upper() if vendor.gstin else None,
        kyc_status="PENDING"
    )
    db.add(db_vendor)
    db.commit()
    db.refresh(db_vendor)
    
    # Log to audit chain
    log_audit_event("VENDOR_REGISTERED", {
        "vendor_id": db_vendor.id,
        "name": db_vendor.name,
        "pan": db_vendor.pan,
        "gstin": db_vendor.gstin
    }, db)
    
    return db_vendor


@router.get("/", response_model=List[VendorResponse])
def list_vendors(
    kyc_status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all vendors with optional KYC status filter."""
    query = db.query(Vendor)
    if kyc_status:
        query = query.filter(Vendor.kyc_status == kyc_status.upper())
    return query.offset(skip).limit(limit).all()


@router.get("/{vendor_id}", response_model=VendorResponse)
def get_vendor(vendor_id: str, db: Session = Depends(get_db)):
    """Get vendor details by ID."""
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


@router.get("/{vendor_id}/kyc-status", response_model=KYCStatusResponse)
def get_kyc_status(vendor_id: str, db: Session = Depends(get_db)):
    """Get detailed KYC status for a vendor."""
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Calculate progress
    checks = [
        vendor.aadhaar_hash is not None,
        vendor.pan is not None,
        vendor.gstin is not None and validate_gstin(vendor.gstin)["valid"],
        vendor.bank_account is not None,
        vendor.dsc_bound is not None
    ]
    progress = int(sum(checks) / len(checks) * 100)
    
    return KYCStatusResponse(
        vendor_id=vendor.id,
        kyc_status=vendor.kyc_status,
        aadhaar_verified=vendor.aadhaar_hash is not None,
        pan_verified=vendor.pan is not None,
        gstin_verified=vendor.gstin is not None and validate_gstin(vendor.gstin)["valid"],
        bank_verified=vendor.bank_account is not None,
        dsc_bound=vendor.dsc_bound is not None,
        progress_percent=progress
    )


@router.post("/{vendor_id}/kyc/aadhaar")
def initiate_aadhaar_kyc(
    vendor_id: str,
    request: AadhaarKYCRequest,
    db: Session = Depends(get_db)
):
    """
    Initiate Aadhaar eKYC (Mock implementation).
    Step 1: Send OTP to Aadhaar-linked mobile
    """
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Mock Aadhaar verification - in production, call NIC/UIDAI API
    # For demo: accept any 12-digit Aadhaar and mock OTP "123456"
    masked_aadhaar = request.aadhaar_number[-4:].rjust(12, 'X')
    
    # Store hash only (never store plaintext Aadhaar)
    aadhaar_hash = hashlib.sha256(request.aadhaar_number.encode()).hexdigest()
    vendor.aadhaar_hash = aadhaar_hash
    
    # Check if all KYC is now complete
    check_kyc_completion(vendor)
    
    db.commit()
    
    log_audit_event("KYC_AADHAAR_VERIFIED", {
        "vendor_id": vendor_id,
        "masked_aadhaar": masked_aadhaar
    }, db)
    
    return {
        "status": "OTP_SENT",
        "message": f"OTP sent to Aadhaar-linked mobile (XXXXX{request.aadhaar_number[-4:]})",
        "mock_otp": "123456",  # Only for demo
        "session_id": hashlib.sha256(f"{vendor_id}{datetime.utcnow()}".encode()).hexdigest()[:16]
    }


@router.post("/{vendor_id}/kyc/aadhaar/verify")
def verify_aadhaar_otp(
    vendor_id: str,
    session_id: str = Form(...),
    otp: str = Form(...),
    db: Session = Depends(get_db)
):
    """Step 2: Verify OTP and complete Aadhaar KYC."""
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Mock OTP verification
    if otp != "123456":
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # Mark Aadhaar as verified
    if not vendor.aadhaar_hash:
        raise HTTPException(status_code=400, detail="Aadhaar KYC not initiated")
    
    log_audit_event("KYC_AADHAAR_CONFIRMED", {
        "vendor_id": vendor_id,
        "session_id": session_id
    }, db)
    
    return {
        "status": "VERIFIED",
        "message": "Aadhaar KYC completed successfully"
    }


@router.post("/{vendor_id}/kyc/gstin")
def verify_gstin_kyc(vendor_id: str, gstin: str = Form(...), db: Session = Depends(get_db)):
    """Verify GSTIN and cross-check with PAN."""
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Validate GSTIN
    result = validate_gstin(gstin)
    if not result["valid"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    
    # Cross-check PAN from GSTIN with vendor PAN
    if vendor.pan and result["pan"] != vendor.pan:
        log_audit_event("KYC_GSTIN_PAN_MISMATCH", {
            "vendor_id": vendor_id,
            "vendor_pan": vendor.pan,
            "gstin_derived_pan": result["pan"]
        }, db)
        raise HTTPException(
            status_code=400, 
            detail=f"PAN mismatch: GSTIN-derived PAN {result['pan']} vs registered PAN {vendor.pan}"
        )
    
    # Store GSTIN
    vendor.gstin = gstin.upper()
    
    # Check KYC completion
    check_kyc_completion(vendor)
    db.commit()
    
    log_audit_event("KYC_GSTIN_VERIFIED", {
        "vendor_id": vendor_id,
        "gstin": gstin.upper(),
        "state_code": result["state_code"],
        "pan_match": vendor.pan == result["pan"] if vendor.pan else True
    }, db)
    
    return {
        "status": "VERIFIED",
        "gstin": gstin.upper(),
        "state_code": result["state_code"],
        "extracted_pan": result["pan"],
        "pan_cross_check": "PASSED" if (vendor.pan == result["pan"] if vendor.pan else True) else "MANUAL_REVIEW"
    }


@router.post("/{vendor_id}/kyc/bank")
def verify_bank_account(
    vendor_id: str,
    account_number: str = Form(...),
    ifsc_code: str = Form(...),
    account_holder_name: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Bank account verification with fuzzy name matching.
    Mock implementation - production uses NPCI/NIC API.
    """
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Mock bank verification - accept any valid format
    # In production: call NPCI/NIC bank verification API
    if len(account_number) < 9 or len(ifsc_code) != 11:
        raise HTTPException(status_code=400, detail="Invalid account number or IFSC code")
    
    # Store bank details
    vendor.bank_account = account_number
    vendor.bank_ifsc = ifsc_code.upper()
    
    # Check KYC completion
    check_kyc_completion(vendor)
    db.commit()
    
    log_audit_event("KYC_BANK_VERIFIED", {
        "vendor_id": vendor_id,
        "account_masked": f"XXXX{account_number[-4:]}",
        "ifsc": ifsc_code.upper()
    }, db)
    
    return {
        "status": "VERIFIED",
        "account_masked": f"XXXX{account_number[-4:]}",
        "ifsc": ifsc_code.upper(),
        "name_match": "PENDING_MANUAL"  # Would use RapidFuzz in production
    }


@router.post("/{vendor_id}/documents")
def upload_vendor_document(
    vendor_id: str,
    doc_type: str = Form(...),  # AADHAAR, PAN, GSTIN_CERT, BANK_PROOF, DSC
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload KYC document for vendor."""
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Store file locally
    upload_dir = os.path.join("uploads", "vendors", vendor_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, file.filename)
    content = file.file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Create document record
    doc = VendorDocument(
        vendor_id=vendor_id,
        doc_type=doc_type,
        filename=file.filename,
        minio_path=f"vendors/{vendor_id}/{file.filename}",
        verification_status="PENDING"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    log_audit_event("VENDOR_DOCUMENT_UPLOADED", {
        "vendor_id": vendor_id,
        "document_id": doc.id,
        "doc_type": doc_type,
        "filename": file.filename
    }, db)
    
    return {
        "document_id": doc.id,
        "doc_type": doc_type,
        "filename": file.filename,
        "status": "PENDING_VERIFICATION"
    }


@router.get("/{vendor_id}/documents")
def list_vendor_documents(vendor_id: str, db: Session = Depends(get_db)):
    """List all KYC documents for a vendor."""
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    docs = db.query(VendorDocument).filter(VendorDocument.vendor_id == vendor_id).all()
    return [
        {
            "id": d.id,
            "doc_type": d.doc_type,
            "filename": d.filename,
            "status": d.verification_status,
            "uploaded_at": d.uploaded_at
        }
        for d in docs
    ]


# ============ Helper Functions ============

def check_kyc_completion(vendor: Vendor):
    """Check if all KYC requirements are met and update status."""
    required_fields = [
        vendor.aadhaar_hash,
        vendor.pan,
        vendor.gstin,
        vendor.bank_account
    ]
    
    if all(required_fields):
        vendor.kyc_status = "VERIFIED"
        vendor.kyc_verified_at = datetime.utcnow()
    elif any(required_fields):
        vendor.kyc_status = "IN_PROGRESS"


@router.post("/{vendor_id}/kyc/dsc")
def bind_dsc_certificate(
    vendor_id: str,
    dsc_pem: str = Form(..., description="Class 3 DSC in PEM format"),
    serial_number: str = Form(...),
    issued_by: str = Form(...),
    valid_until: str = Form(...),
    db: Session = Depends(get_db)
):
    """Bind Class 3 Digital Signature Certificate to vendor."""
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Basic PEM validation
    if "BEGIN CERTIFICATE" not in dsc_pem or "END CERTIFICATE" not in dsc_pem:
        raise HTTPException(status_code=400, detail="Invalid PEM certificate format")

    # Check if certificate is Class 3 (look for keywords in issuer/serial)
    is_class3 = any(kw in (dsc_pem + issued_by).lower() for kw in ["class 3", "class3", "signature", "signing"])

    if not is_class3:
        raise HTTPException(status_code=400, detail="Only Class 3 DSC certificates are accepted for bidding")

    vendor.dsc_certificate = dsc_pem
    vendor.dsc_bound = datetime.utcnow()

    check_kyc_completion(vendor)
    db.commit()

    log_audit_event("KYC_DSC_BOUND", {
        "vendor_id": vendor_id,
        "serial": serial_number,
        "issuer": issued_by,
        "valid_until": valid_until
    }, db)

    return {
        "status": "DSC_BOUND",
        "serial_number": serial_number,
        "issuer": issued_by,
        "valid_until": valid_until,
        "kyc_status": vendor.kyc_status,
        "class3_verified": is_class3
    }


@router.get("/market-depth/{tender_id}")
def get_market_depth(tender_id: str, db: Session = Depends(get_db)):
    """
    Market depth widget: Show how many KYC-verified vendors are eligible
    to bid on a tender, broken down by category/region.
    """
    from app.models import Tender

    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Count eligible vendors (KYC verified + DSC bound)
    total_verified = db.query(Vendor).filter(Vendor.kyc_status == "VERIFIED").count()

    # Count with DSC (minimum for bidding)
    dsc_ready = db.query(Vendor).filter(
        Vendor.kyc_status == "VERIFIED",
        Vendor.dsc_bound.isnot(None)
    ).count()

    # Count by state (from GSTIN prefix)
    from sqlalchemy import func
    state_distribution = {}
    for vendor in db.query(Vendor).filter(Vendor.kyc_status == "VERIFIED", Vendor.gstin.isnot(None)).all():
        state_code = vendor.gstin[:2] if vendor.gstin and len(vendor.gstin) >= 2 else "UNKNOWN"
        state_distribution[state_code] = state_distribution.get(state_code, 0) + 1

    # Already bid on this tender
    existing_bids = db.query(Bid).filter(Bid.tender_id == tender_id).count()
    bidding_vendors = db.query(Bid.vendor_id).filter(Bid.tender_id == tender_id).distinct().count()

    return {
        "tender_id": tender_id,
        "tender_title": tender.title,
        "market_depth": {
            "total_kyc_verified": total_verified,
            "dsc_ready": dsc_ready,
            "eligible_to_bid": dsc_ready,
            "already_submitted_bids": existing_bids,
            "unique_vendors_bidded": bidding_vendors,
            "competition_ratio": round(existing_bids / max(dsc_ready, 1), 2)
        },
        "state_distribution": state_distribution,
        "health_indicators": {
            "sufficient_competition": existing_bids >= 3,
            "single_vendor_dominance": any(
                count > total_verified * 0.5 for count in state_distribution.values()
            ) if state_distribution else False
        }
    }
