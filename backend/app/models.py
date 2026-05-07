from sqlalchemy import Column, String, DateTime, Float, Integer, JSON, Text, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
import uuid

def gen_uuid():
    return str(uuid.uuid4()).replace("-", "")

class Tender(Base):
    __tablename__ = "tenders"
    id = Column(String(32), primary_key=True, default=gen_uuid)
    title = Column(String(255), nullable=False)
    department = Column(String(100), nullable=False)
    publish_date = Column(DateTime, default=datetime.utcnow)
    closing_date = Column(DateTime, nullable=True)
    status = Column(String(20), default="DRAFT")
    criteria = Column(JSON, default=list)
    criteria_locked = Column(DateTime, nullable=True)

class TenderDocument(Base):
    __tablename__ = "tender_documents"
    id = Column(String(32), primary_key=True, default=gen_uuid)
    tender_id = Column(String(32), ForeignKey("tenders.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    minio_path = Column(String(500), nullable=True)
    extracted_text = Column(Text, nullable=True)
    ocr_confidence = Column(Float, default=1.0)

class Bidder(Base):
    __tablename__ = "bidders"
    id = Column(String(32), primary_key=True, default=gen_uuid)
    tender_id = Column(String(32), ForeignKey("tenders.id"), nullable=False)
    name = Column(String(255), nullable=False)
    pan = Column(String(10), nullable=True)
    gstin = Column(String(15), nullable=True)
    status = Column(String(20), default="REGISTERED")

class BidderDocument(Base):
    __tablename__ = "bidder_documents"
    id = Column(String(32), primary_key=True, default=gen_uuid)
    bidder_id = Column(String(32), ForeignKey("bidders.id"), nullable=False)
    doc_type = Column(String(50), nullable=False)
    filename = Column(String(255), nullable=False)
    minio_path = Column(String(500), nullable=True)
    extracted_text = Column(Text, nullable=True)
    extracted_json = Column(JSON, nullable=True)
    ocr_confidence = Column(Float, default=1.0)
    page_count = Column(Integer, default=0)

class Verdict(Base):
    __tablename__ = "verdicts"
    id = Column(String(32), primary_key=True, default=gen_uuid)
    bidder_id = Column(String(32), ForeignKey("bidders.id"), nullable=False)
    criterion_id = Column(String(20), nullable=False)
    criterion_type = Column(String(20), nullable=False)
    verdict = Column(String(20), nullable=False)
    reason = Column(Text, nullable=True)
    confidence = Column(Float, default=0.5)
    source_page = Column(Integer, nullable=True)
    source_bbox = Column(JSON, nullable=True)
    verbatim_quote = Column(Text, nullable=True)
    computed_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_log"
    index = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(String(50), nullable=False)
    actor = Column(String(100), nullable=True)
    data = Column(JSON, nullable=True)
    prev_hash = Column(String(64), nullable=True)
    this_hash = Column(String(64), nullable=False)


# ========== BIDSHIELD PHASE 1: VENDOR IDENTITY & KYC ==========

class Vendor(Base):
    __tablename__ = "vendors"
    id = Column(String(32), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    
    # KYC Fields
    aadhaar_hash = Column(String(64), nullable=True)  # SHA-256 of masked Aadhaar
    pan = Column(String(10), nullable=True)
    gstin = Column(String(15), nullable=True)
    bank_account = Column(String(20), nullable=True)
    bank_ifsc = Column(String(11), nullable=True)
    
    # KYC Status
    kyc_status = Column(String(20), default="PENDING")  # PENDING, VERIFIED, REJECTED
    kyc_verified_at = Column(DateTime, nullable=True)
    
    # DSC Binding
    dsc_bound = Column(DateTime, nullable=True)  # When DSC was bound
    dsc_certificate = Column(Text, nullable=True)  # PEM format certificate
    
    # Risk Scoring (Phase 4)
    risk_score = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VendorDocument(Base):
    __tablename__ = "vendor_documents"
    id = Column(String(32), primary_key=True, default=gen_uuid)
    vendor_id = Column(String(32), ForeignKey("vendors.id"), nullable=False)
    doc_type = Column(String(50), nullable=False)  # AADHAAR, PAN, GSTIN_CERT, BANK_PROOF, DSC
    filename = Column(String(255), nullable=False)
    minio_path = Column(String(500), nullable=True)
    verification_status = Column(String(20), default="PENDING")  # PENDING, VERIFIED, REJECTED
    verified_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


class Bid(Base):
    __tablename__ = "bids"
    id = Column(String(32), primary_key=True, default=gen_uuid)
    tender_id = Column(String(32), ForeignKey("tenders.id"), nullable=False)
    vendor_id = Column(String(32), ForeignKey("vendors.id"), nullable=False)
    
    # Bid Details
    bid_amount = Column(Float, nullable=True)  # Financial bid amount
    technical_score = Column(Float, nullable=True)  # If applicable
    
    # File Hashing (Client-side computed)
    file_hash = Column(String(64), nullable=False)  # SHA-256 of encrypted bid file
    file_hash_algorithm = Column(String(10), default="SHA-256")
    
    # Blockchain Anchoring
    blockchain_tx_hash = Column(String(64), nullable=True)  # Hyperledger Fabric tx hash
    blockchain_anchor_status = Column(String(20), default="PENDING")  # PENDING, CONFIRMED, FAILED
    anchored_at = Column(DateTime, nullable=True)
    
    # Bid Status
    status = Column(String(20), default="SUBMITTED")  # SUBMITTED, OPENED, REJECTED, AWARDED
    submitted_at = Column(DateTime, default=datetime.utcnow)
    opened_at = Column(DateTime, nullable=True)
    
    # IP Address for geo-fencing (Phase 4)
    submission_ip = Column(String(45), nullable=True)  # IPv6 compatible


class BidAnchor(Base):
    """Separate table for blockchain anchor receipts"""
    __tablename__ = "bid_anchors"
    id = Column(String(32), primary_key=True, default=gen_uuid)
    bid_id = Column(String(32), ForeignKey("bids.id"), nullable=False)
    
    # Blockchain Details
    chaincode_name = Column(String(50), default="bidshield")
    channel_name = Column(String(50), default="vigil-channel")
    transaction_id = Column(String(64), nullable=False)
    block_number = Column(BigInteger, nullable=True)
    
    # Anchor Data
    anchored_data = Column(JSON, nullable=False)  # {tender_id, vendor_id, file_hash, timestamp}
    merkle_root = Column(String(64), nullable=True)
    
    # Receipt
    receipt_json = Column(JSON, nullable=True)  # Full blockchain receipt
    created_at = Column(DateTime, default=datetime.utcnow)


# ========== VIGIL PHASE 3: COLLUSION DETECTION ==========

class VigilAlert(Base):
    __tablename__ = "vigil_alerts"
    id = Column(String(32), primary_key=True, default=gen_uuid)
    tender_id = Column(String(32), ForeignKey("tenders.id"), nullable=False)
    alert_type = Column(String(50), nullable=False)
    # COVER_PRICING, IDENTICAL_BIDS, BID_ROTATION, NETWORK_COMMUNITY,
    # TEMPORAL_ANOMALY, HONEYPOT_HIT, FAVORITISM_RISK, SPLITTING_RISK
    
    confidence = Column(Float, default=0.0)  # 0.0 - 1.0
    risk_score = Column(Float, default=0.0)  # 0 - 100
    
    # Alert Details
    description = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)  # structured evidence per alert type
    
    # Status
    status = Column(String(20), default="NEW")  # NEW, ACKNOWLEDGED, DISMISSED, ESCALATED
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    
    # CCI Referral
    cci_referral = Column(String(20), default="NONE")  # NONE, PENDING, SENT
    cci_tracking_id = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VigilNetworkEdge(Base):
    __tablename__ = "vigil_network_edges"
    id = Column(String(32), primary_key=True, default=gen_uuid)
    tender_id = Column(String(32), ForeignKey("tenders.id"), nullable=False)

    # Edge connects two bidders/vendors
    node_a_id = Column(String(32), nullable=False)  # vendor/bidder id
    node_b_id = Column(String(32), nullable=False)

    # Edge type and weight
    edge_type = Column(String(50), nullable=False)
    # SHARED_DIRECTOR, SHARED_ADDRESS, SHARED_IP, SHARED_PHONE

    weight = Column(Float, default=0.0)  # 0.0 - 1.0
    evidence = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


# ========== OFFICERGUARD PHASE 4: AUTH & SESSIONS ==========

class User(Base):
    __tablename__ = "users"
    id = Column(String(32), primary_key=True, default=gen_uuid)
    email = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # Officer profile
    department = Column(String(100), nullable=True)
    designation = Column(String(100), nullable=True)
    role = Column(String(20), default="OFFICER")  # ADMIN, OFFICER, AUDITOR

    # DSC (Digital Signature Certificate) for Class 3 login
    dsc_serial = Column(String(255), nullable=True)
    dsc_issuer = Column(String(255), nullable=True)
    dsc_valid_until = Column(DateTime, nullable=True)

    # Security
    is_active = Column(String(1), default="Y")  # Y/N
    last_login = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    failed_logins = Column(Integer, default=0)

    # Geo-fencing: allowed office IPs (JSON array)
    allowed_ips = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
