"""
Seed script for BidShield Phase 1 - Demo Vendors
Creates 5 vendors with different KYC states for testing.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import SessionLocal
from app.models import Vendor, VendorDocument
from app.services.audit_chain import log_audit_event
from datetime import datetime


def seed_vendors():
    db = SessionLocal()
    
    try:
        # Check if vendors already exist
        existing = db.query(Vendor).first()
        if existing:
            print("Vendors already seeded. Skipping...")
            return
        
        vendors_data = [
            {
                "name": "M/S Royal Builders Ltd",
                "email": "contact@royalbuilders.in",
                "phone": "+91 98765 43210",
                "pan": "AAAPR1234R",
                "gstin": "07AAAPR1234R1Z5",
                "bank_account": "123456789012",
                "bank_ifsc": "SBIN0001234",
                "kyc_status": "VERIFIED",
                "kyc_verified_at": datetime.utcnow(),
            },
            {
                "name": "M/S Apex Constructions",
                "email": "info@apexconstructions.com",
                "phone": "+91 98765 43211",
                "pan": "AAAPC5678C",
                "gstin": "09AAAPC5678C1Z3",
                "bank_account": "987654321098",
                "bank_ifsc": "ICIC0005678",
                "kyc_status": "VERIFIED",
                "kyc_verified_at": datetime.utcnow(),
            },
            {
                "name": "M/S Shady Ventures Ltd",
                "email": "admin@shady.in",
                "phone": "+91 98765 43212",
                "pan": "AAAPS9012S",
                "gstin": "27AAAPS9012S1Z8",
                "bank_account": "555566667777",
                "bank_ifsc": "HDFC0009012",
                "kyc_status": "PENDING",
                "kyc_verified_at": None,
            },
            {
                "name": "M/S Dharma Infrastructure",
                "email": "bids@dharmainfra.org",
                "phone": "+91 98765 43213",
                "pan": "AAAPD3456D",
                "gstin": "33AAAPD3456D1Z2",
                "bank_account": "111122223333",
                "bank_ifsc": "PNB0003456",
                "kyc_status": "VERIFIED",
                "kyc_verified_at": datetime.utcnow(),
            },
            {
                "name": "M/S Eastern Contractors",
                "email": "tenders@easterncontractors.com",
                "phone": "+91 98765 43214",
                "pan": "AAAPE7890E",
                "gstin": "19AAAPE7890E1Z1",
                "bank_account": "444455556666",
                "bank_ifsc": "BOB0007890",
                "kyc_status": "VERIFIED",
                "kyc_verified_at": datetime.utcnow(),
            },
        ]
        
        created_vendors = []
        for vd in vendors_data:
            vendor = Vendor(**vd)
            db.add(vendor)
            db.flush()  # Get the ID
            created_vendors.append(vendor)
            
            log_audit_event("VENDOR_SEEDED", {
                "vendor_id": vendor.id,
                "name": vendor.name,
                "kyc_status": vendor.kyc_status
            }, db)
            
            print(f"Created vendor: {vendor.name} ({vendor.kyc_status})")
        
        db.commit()
        
        print(f"\n✓ Seeded {len(created_vendors)} vendors")
        print(f"  - VERIFIED: {sum(1 for v in created_vendors if v.kyc_status == 'VERIFIED')}")
        print(f"  - PENDING: {sum(1 for v in created_vendors if v.kyc_status == 'PENDING')}")
        
    except Exception as e:
        print(f"Error seeding vendors: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_vendors()
