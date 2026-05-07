"""
FULL DEMO SEEDER - Adds all fake data to test every system module.
Adds: vendors, bids (with VIGIL collusion patterns), additional tenders.
Idempotent: safe to run multiple times.

Run: python backend/scripts/seed_full_demo.py
"""
import sys
import os
import hashlib
import secrets
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import SessionLocal, engine, Base
from app.models import (
    Tender, Bidder, BidderDocument,
    Vendor, VendorDocument,
    Bid, BidAnchor,
    VigilAlert, VigilNetworkEdge,
    User, AuditLog
)
from app.services.audit_chain import log_audit_event
from app.core.security import get_password_hash
from datetime import datetime, timedelta


def seed_users(db):
    """Seed officer/admin/auditor users."""
    print("\n--- Seeding Users ---")
    users_data = [
        {"email": "admin@vigil.gov.in", "password": "admin123", "name": "System Admin",
         "department": "Ministry of Finance", "designation": "CTO", "role": "ADMIN"},
        {"email": "officer1@crpf.gov.in", "password": "officer123", "name": "Rajan Sharma",
         "department": "CRPF", "designation": "Procurement Officer", "role": "OFFICER"},
        {"email": "officer2@cpwd.gov.in", "password": "officer123", "name": "Priya Singh",
         "department": "CPWD", "designation": "Tender Officer", "role": "OFFICER"},
        {"email": "auditor@cag.gov.in", "password": "auditor123", "name": "Vikram Mehta",
         "department": "CAG India", "designation": "Senior Auditor", "role": "AUDITOR"},
        {"email": "cvo@vigilance.gov.in", "password": "cvo123", "name": "Anita Desai",
         "department": "CVC", "designation": "Chief Vigilance Officer", "role": "OFFICER"},
    ]

    for ud in users_data:
        existing = db.query(User).filter(User.email == ud["email"]).first()
        if existing:
            print(f"  [SKIP] {ud['email']} (exists)")
            continue
        user = User(
            email=ud["email"],
            name=ud["name"],
            hashed_password=get_password_hash(ud["password"]),
            department=ud["department"],
            designation=ud["designation"],
            role=ud["role"],
            allowed_ips=[],
        )
        db.add(user)
        print(f"  [+] {ud['email']} / {ud['password']} ({ud['role']})")
    db.commit()


def seed_vendors(db):
    """Seed vendors with various KYC states."""
    print("\n--- Seeding Vendors (BidShield) ---")
    vendors_data = [
        {"name": "M/S Royal Builders Ltd", "email": "contact@royalbuilders.in",
         "phone": "+919876543210", "pan": "AAAPR1234R", "gstin": "07AAAPR1234R1Z5",
         "bank_account": "123456789012", "bank_ifsc": "SBIN0001234",
         "kyc_status": "VERIFIED", "risk_score": 12.5},
        {"name": "M/S Apex Constructions", "email": "info@apexconstructions.com",
         "phone": "+919876543211", "pan": "AAAPC5678C", "gstin": "09AAAPC5678C1Z3",
         "bank_account": "987654321098", "bank_ifsc": "ICIC0005678",
         "kyc_status": "VERIFIED", "risk_score": 8.0},
        {"name": "M/S Shady Ventures Ltd", "email": "admin@shady.in",
         "phone": "+919876543212", "pan": "AAAPS9012S", "gstin": "27AAAPS9012S1Z8",
         "bank_account": "555566667777", "bank_ifsc": "HDFC0009012",
         "kyc_status": "PENDING", "risk_score": 65.0},
        {"name": "M/S Dharma Infrastructure", "email": "bids@dharmainfra.org",
         "phone": "+919876543213", "pan": "AAAPD3456D", "gstin": "33AAAPD3456D1Z2",
         "bank_account": "111122223333", "bank_ifsc": "PNB0003456",
         "kyc_status": "VERIFIED", "risk_score": 22.0},
        {"name": "M/S Eastern Contractors", "email": "tenders@easterncontractors.com",
         "phone": "+919876543214", "pan": "AAAPE7890E", "gstin": "19AAAPE7890E1Z1",
         "bank_account": "444455556666", "bank_ifsc": "BOB0007890",
         "kyc_status": "VERIFIED", "risk_score": 5.0},
        {"name": "M/S Cartel Corp A", "email": "a@cartel.com",
         "phone": "+919999900001", "pan": "AAACA1111A", "gstin": "07AAACA1111A1Z9",
         "bank_account": "100000000001", "bank_ifsc": "SBIN0001001",
         "kyc_status": "VERIFIED", "risk_score": 78.0},
        {"name": "M/S Cartel Corp B", "email": "b@cartel.com",
         "phone": "+919999900002", "pan": "AAACB2222B", "gstin": "07AAACB2222B1Z7",
         "bank_account": "100000000002", "bank_ifsc": "SBIN0001001",  # same IFSC!
         "kyc_status": "VERIFIED", "risk_score": 82.0},
        {"name": "M/S Cartel Corp C", "email": "c@cartel.com",
         "phone": "+919999900003", "pan": "AAACC3333C", "gstin": "07AAACC3333C1Z5",
         "bank_account": "100000000003", "bank_ifsc": "SBIN0001001",  # same IFSC!
         "kyc_status": "VERIFIED", "risk_score": 85.0},
    ]

    created = {}
    for vd in vendors_data:
        existing = db.query(Vendor).filter(Vendor.pan == vd["pan"]).first()
        if existing:
            created[vd["name"]] = existing
            print(f"  [SKIP] {vd['name']} (exists)")
            continue
        # Compute aadhaar hash for some
        v = Vendor(
            **vd,
            aadhaar_hash=hashlib.sha256(f"AADHAAR_{vd['pan']}".encode()).hexdigest(),
            kyc_verified_at=datetime.utcnow() if vd["kyc_status"] == "VERIFIED" else None,
        )
        db.add(v)
        db.flush()
        created[vd["name"]] = v
        print(f"  [+] {vd['name']} | KYC: {vd['kyc_status']} | Risk: {vd['risk_score']}")
    db.commit()
    return created


def seed_collusion_tender(db, vendors):
    """
    Create a 2nd tender with bids that trigger VIGIL collusion patterns:
    - Cover pricing (CV < 0.02)
    - Identical bids
    - Same IFSC clustering
    """
    print("\n--- Seeding Collusion Test Tender ---")

    existing = db.query(Tender).filter(Tender.title.like("%COLLUSION DEMO%")).first()
    if existing:
        print(f"  [SKIP] Collusion tender exists: {existing.id}")
        return existing

    tender = Tender(
        title="CPWD Office Building 2026 [COLLUSION DEMO]",
        department="CPWD",
        criteria=[
            {"id": "C-01", "type": "FINANCIAL",
             "description": "Min turnover Rs. 2 Crore",
             "threshold": 20000000, "currency": "INR", "time_window_years": 3},
            {"id": "C-02", "type": "COMPLIANCE",
             "description": "Valid GSTIN", "threshold": None},
        ],
        status="EVALUATING",
        criteria_locked=datetime.utcnow(),
    )
    db.add(tender)
    db.flush()
    print(f"  [+] Tender: {tender.title} ({tender.id})")

    # Create cover-pricing bids (CV < 0.02)
    # Mean ~ Rs. 5 Cr, all within Rs. 50K of each other
    bid_amounts = [
        ("M/S Cartel Corp A", 50_005_000),
        ("M/S Cartel Corp B", 50_010_000),
        ("M/S Cartel Corp C", 50_015_000),
        ("M/S Royal Builders Ltd", 49_500_000),  # legitimate competitor
        ("M/S Apex Constructions", 48_200_000),  # legitimate competitor
    ]

    for vendor_name, amount in bid_amounts:
        vendor = vendors.get(vendor_name)
        if not vendor:
            continue
        file_hash = hashlib.sha256(f"{vendor.id}{amount}".encode()).hexdigest()
        bid = Bid(
            tender_id=tender.id,
            vendor_id=vendor.id,
            bid_amount=float(amount),
            file_hash=file_hash,
            file_hash_algorithm="SHA-256",
            blockchain_anchor_status="CONFIRMED",
            blockchain_tx_hash=secrets.token_hex(32),
            anchored_at=datetime.utcnow(),
            status="OPENED",
            submitted_at=datetime.utcnow() - timedelta(hours=2),
            opened_at=datetime.utcnow() - timedelta(hours=1),
            submission_ip="192.168.1.50" if "Cartel" in vendor_name else f"10.0.0.{hash(vendor_name) % 254 + 1}",
        )
        db.add(bid)
        print(f"  [+] Bid: {vendor_name} -> Rs. {amount/10_000_000:.2f} Cr")

    # Add identical-bid pair for IDENTICAL_BIDS detection (separate tender)
    db.commit()
    return tender


def seed_identical_bid_tender(db, vendors):
    """Tender with two identical bids."""
    print("\n--- Seeding Identical-Bid Tender ---")
    existing = db.query(Tender).filter(Tender.title.like("%IDENTICAL DEMO%")).first()
    if existing:
        print(f"  [SKIP] exists: {existing.id}")
        return existing

    tender = Tender(
        title="Railway Station Renovation 2026 [IDENTICAL DEMO]",
        department="Indian Railways",
        criteria=[
            {"id": "C-01", "type": "FINANCIAL",
             "description": "Min turnover Rs. 1 Crore",
             "threshold": 10000000, "currency": "INR"},
        ],
        status="EVALUATING",
        criteria_locked=datetime.utcnow(),
    )
    db.add(tender)
    db.flush()

    bid_data = [
        ("M/S Cartel Corp A", 75_500_000.00),  # identical
        ("M/S Cartel Corp B", 75_500_000.00),  # identical!
        ("M/S Cartel Corp C", 78_900_000.00),
        ("M/S Eastern Contractors", 72_300_000.00),
        ("M/S Dharma Infrastructure", 80_100_000.00),
    ]
    for vendor_name, amount in bid_data:
        vendor = vendors.get(vendor_name)
        if not vendor:
            continue
        bid = Bid(
            tender_id=tender.id, vendor_id=vendor.id, bid_amount=amount,
            file_hash=hashlib.sha256(f"{vendor.id}{amount}".encode()).hexdigest(),
            blockchain_anchor_status="CONFIRMED",
            blockchain_tx_hash=secrets.token_hex(32),
            status="OPENED",
            submitted_at=datetime.utcnow() - timedelta(hours=3),
            opened_at=datetime.utcnow() - timedelta(hours=1),
            submission_ip=f"10.0.0.{hash(vendor_name) % 254 + 1}",
        )
        db.add(bid)
        print(f"  [+] Bid: {vendor_name} -> Rs. {amount/10_000_000:.2f} Cr")
    db.commit()
    print(f"  Tender: {tender.title} ({tender.id})")
    return tender


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_users(db)
        vendors = seed_vendors(db)
        seed_collusion_tender(db, vendors)
        seed_identical_bid_tender(db, vendors)

        print("\n" + "=" * 60)
        print("FULL DEMO SEED COMPLETE")
        print("=" * 60)
        print("\nTotals:")
        print(f"  Tenders: {db.query(Tender).count()}")
        print(f"  Bidders: {db.query(Bidder).count()}")
        print(f"  Vendors: {db.query(Vendor).count()}")
        print(f"  Bids:    {db.query(Bid).count()}")
        print(f"  Users:   {db.query(User).count()}")
        print("\nNext: run VIGIL analysis on the collusion tenders to generate alerts:")
        print("  POST /api/v1/vigil/analyze  with {tender_id: <id>}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
