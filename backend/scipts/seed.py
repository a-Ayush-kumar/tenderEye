import sys
import os

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import engine, Base
from app.models import Tender, Bidder, BidderDocument
from sqlalchemy.orm import Session
from datetime import datetime

def seed():
    # Create tables if they don't exist (never drop — preserves data)
    Base.metadata.create_all(bind=engine)
    
    db = Session(bind=engine)
    
    # Check if already seeded
    existing = db.query(Tender).first()
    if existing:
        print(f"Database already seeded (found tender: {existing.title}). Skipping.")
        print(f"To re-seed, delete vigil.db first.")
        db.close()
        return
    
    try:
        # 1. Create Tender
        tender = Tender(
            title="CRPF Construction Tender 2026/0847",
            department="CRPF",
            criteria=[
                {
                    "id": "C-01",
                    "type": "FINANCIAL",
                    "description": "Minimum average annual turnover of Rs. 5 Crore over last 3 years",
                    "threshold": 50000000,
                    "currency": "INR",
                    "time_window_years": 3
                },
                {
                    "id": "C-02",
                    "type": "COMPLIANCE",
                    "description": "Valid GSTIN with matching PAN",
                    "threshold": None,
                    "currency": None,
                    "time_window_years": None
                },
                {
                    "id": "C-03",
                    "type": "TECHNICAL",
                    "description": "Minimum 3 similar construction projects completed in last 3 years",
                    "category": "construction",
                    "min_projects": 3,
                    "min_years": 3
                },
                {
                    "id": "C-04",
                    "type": "DOCUMENTARY",
                    "description": "Valid ISO 9001:2015 certification from IAF-accredited body",
                    "required_cert": "ISO_9001_2015"
                }
            ],
            status="PUBLISHED",
            criteria_locked=datetime.utcnow()  # Lock criteria so evaluation can run immediately
        )
        db.add(tender)
        db.commit()
        db.refresh(tender)
        print(f"Created tender: {tender.title} ({tender.id})")
        
        # 2. Create 5 Bidders with mock documents (as per Prototype Plan)
        bidders_data = [
            {
                "name": "Apex Constructions", 
                "pan": "AAAPA1234A", 
                "gstin": "07AAAPA1234A0Z5",
                "text": (
                    "Audited Annual Report FY 2024-2025\n"
                    "M/S Apex Constructions\n\n"
                    "Statement of Revenue & Expenditure\n"
                    "Turnover FY 2022-23: Rs. 7.8 Crore\n"
                    "Turnover FY 2023-24: Rs. 8.9 Crore\n"
                    "Turnover FY 2024-25: Rs. 8.5 Crore\n\n"
                    "Average annual turnover for last 3 years: Rs. 8.4 Crore\n"
                    "Certified by: CA Rajesh Kumar (FCA 12345)\n\n"
                    "--- Similar Projects Completed ---\n\n"
                    "Project Name: CRPF Barrack Complex Jammu\n"
                    "Value: Rs. 4.2 Crore | Client: CRPF\n"
                    "Completion: 2023 | Certificate: CC-2023-0847\n"
                    "Nature: Construction of residential barracks, structural work, building\n\n"
                    "Project Name: BRO Bridge Kargil\n"
                    "Value: Rs. 6.8 Crore | Client: Border Road Organization\n"
                    "Completion: 2022 | Certificate: CC-2022-1102\n"
                    "Nature: Bridge construction, road work, dam access, civil work\n\n"
                    "Project Name: CPWD Office Complex Delhi\n"
                    "Value: Rs. 3.5 Crore | Client: CPWD\n"
                    "Completion: 2024 | Certificate: CC-2024-0312\n"
                    "Nature: Building construction, civil structural work, office building\n\n"
                    "Project Name: Army Residential Quarters Pune\n"
                    "Value: Rs. 5.1 Crore | Client: Military Engineering Services\n"
                    "Completion: 2023 | Certificate: CC-2023-2205\n"
                    "Nature: Residential building construction, barrack style housing\n\n"
                    "--- Certifications ---\n\n"
                    "ISO 9001:2015 Quality Management System\n"
                    "Certificate No: TUV-IND-2023-45678\n"
                    "Issuing Body: TUV India Pvt Ltd (IAF Member)\n"
                    "Valid From: 15/03/2023 | Valid Until: 14/03/2026\n"
                    "Scope: Construction of buildings and civil engineering works\n"
                ),
                "confidence": 0.95,
                "expected": "ELIGIBLE — turnover Rs. 8.4 Cr > threshold Rs. 5 Cr"
            },
            {
                "name": "Bharat Engineering Ltd", 
                "pan": "AABBB5678B", 
                "gstin": "09AABBB5678B0Z7",
                "text": (
                    "Bharat Engineering Ltd — Audited Accounts\n\n"
                    "Revenue Summary:\n"
                    "Turnover FY22-23: Rs. 5.2 Cr\n"
                    "Turnover FY23-24: Rs. 6.1 Cr\n"
                    "Turnover FY24-25: Rs. 7.8 Cr\n\n"
                    "Average: Rs. 6.37 Crore\n"
                    "Total Income: Rs. 6,37,00,000\n\n"
                    "--- Project Experience ---\n\n"
                    "Project: NHAI Highway Extension Mumbai-Pune\n"
                    "Value: Rs. 12.5 Crore | Client: NHAI\n"
                    "Completion: 2023 | Nature: Road construction, highway, bridge\n\n"
                    "Project: Metro Rail Depot Chennai\n"
                    "Value: Rs. 8.9 Crore | Client: CMRL\n"
                    "Completion: 2024 | Nature: Building construction, depot structure\n\n"
                    "Project: Smart City Flyover Jaipur\n"
                    "Value: Rs. 7.2 Crore | Client: JDA\n"
                    "Completion: 2022 | Nature: Bridge, road, structural engineering\n\n"
                    "--- Certifications ---\n\n"
                    "ISO 9001:2015 Certificate\n"
                    "Cert. No: DQS-IND-2022-11223\n"
                    "Issued by: DQS India (IAF Accredited)\n"
                    "Valid: 01/06/2022 to 31/05/2025\n"
                    "Scope: Civil engineering and construction works\n"
                ),
                "confidence": 0.95,
                "expected": "ELIGIBLE — turnover Rs. 6.37 Cr > threshold Rs. 5 Cr"
            },
            {
                "name": "Citadel Works Pvt Ltd", 
                "pan": "AACCC9012C", 
                "gstin": "27AACCC9012C0Z6",
                "text": (
                    "Citadel Works Pvt Ltd\n"
                    "Annual Financial Statement 2024-2025\n\n"
                    "Annual turnover Rs. 3.2 Crore\n"
                    "Net revenue from operations: Rs. 3,20,00,000\n\n"
                    "--- Project History ---\n\n"
                    "Project: Small Office Renovation Bangalore\n"
                    "Value: Rs. 0.8 Crore | Client: Private Ltd\n"
                    "Nature: Interior work, minor civil work\n\n"
                    "--- Certifications ---\n\n"
                    "No ISO certification available\n"
                ),
                "confidence": 0.92,
                "expected": "NOT_ELIGIBLE — turnover Rs. 3.2 Cr < threshold Rs. 5 Cr"
            },
            {
                "name": "Dharma Infra Solutions", 
                "pan": "AADDD3456D", 
                "gstin": "33AADDD3456D0Z6",
                "text": (
                    "[ILLEGIBLE SCAN] turnover figures not readable\n"
                    "...smudged document...\n"
                    "...partial text visible...\n"
                    "...project list partially visible...\n"
                    "...building work done for CPWD...\n"
                    "...ISO certificate present but unreadable...\n"
                    "...TUV certification number blurred...\n"
                ),
                "confidence": 0.45,
                "expected": "NEEDS_REVIEW — illegible scan, OCR confidence 45%"
            },
            {
                "name": "Eastern Contractors Corp", 
                "pan": "AAEEE7890E", 
                "gstin": "19AAEEE7890E0Z0",
                "text": (
                    "Eastern Contractors Corp\n"
                    "Certified Financial Report — FY 2024-25\n\n"
                    "Revenue from operations:\n"
                    "FY 2022-23: Rs. 8.5 Crore\n"
                    "FY 2023-24: Rs. 9.3 Crore\n"
                    "FY 2024-25: Rs. 9.5 Crore\n\n"
                    "Average turnover Rs. 9.1 Crore over 3 years\n"
                    "Auditor: M/s Sharma & Associates\n\n"
                    "--- Completed Similar Projects ---\n\n"
                    "Project: CRPF Training Center Kolkata\n"
                    "Value: Rs. 7.2 Crore | Client: CRPF\n"
                    "Completion: 2023 | Certificate: CC-2023-4456\n"
                    "Nature: Building construction, barrack accommodation, training hall\n\n"
                    "Project: Railway Station Redevelopment Guwahati\n"
                    "Value: Rs. 11.5 Crore | Client: Indian Railways\n"
                    "Completion: 2024 | Certificate: CC-2024-7789\n"
                    "Nature: Civil work, building construction, structural modification\n\n"
                    "Project: Airport Terminal Extension Imphal\n"
                    "Value: Rs. 9.8 Crore | Client: AAI\n"
                    "Completion: 2022 | Certificate: CC-2022-9901\n"
                    "Nature: Building construction, airport terminal, civil engineering\n\n"
                    "Project: Municipal Corporation Hospital Guwahati\n"
                    "Value: Rs. 5.5 Crore | Client: GMC\n"
                    "Completion: 2024 | Certificate: CC-2024-2233\n"
                    "Nature: Hospital building construction, medical facility building\n\n"
                    "--- Quality Certifications ---\n\n"
                    "ISO 9001:2015 Quality Management System Certificate\n"
                    "Certificate Number: SGS-IND-2021-88776\n"
                    "Issued By: SGS India Pvt Ltd (IAF Member)\n"
                    "Valid From: 01/01/2021 | Valid Until: 31/12/2025\n"
                    "Scope: Construction, civil engineering, and building works\n"
                ),
                "confidence": 0.97,
                "expected": "ELIGIBLE — turnover Rs. 9.1 Cr > threshold Rs. 5 Cr"
            },
        ]
        
        for bidder_data in bidders_data:
            bidder = Bidder(
                tender_id=tender.id,
                name=bidder_data["name"],
                pan=bidder_data["pan"],
                gstin=bidder_data["gstin"]
            )
            db.add(bidder)
            db.commit()
            db.refresh(bidder)
            print(f"  Created bidder: {bidder.name}")
            
            # Create mock document with extracted text
            doc = BidderDocument(
                bidder_id=bidder.id,
                doc_type="AUDITED_ACCOUNTS",
                filename=f"{bidder.name.replace(' ', '_')}_FY25.pdf",
                minio_path=f"bidders/{bidder.id}/report.pdf",
                extracted_text=bidder_data["text"],
                extracted_json=None,
                ocr_confidence=bidder_data["confidence"],
                page_count=5
            )
            db.add(doc)
            db.commit()
        
        print(f"\n{'='*60}")
        print(f"Seeded tender {tender.id} with {len(bidders_data)} bidders")
        print(f"Tender title: {tender.title}")
        print(f"{'='*60}")
        print("\nExpected evaluation results:")
        for bd in bidders_data:
            print(f"  • {bd['name']}: {bd['expected']}")
        print(f"\nNext steps:")
        print(f"  1. Lock criteria:  POST /api/v1/tenders/{tender.id}/lock")
        print(f"  2. Run evaluation: POST /api/v1/evaluation/{tender.id}/run")
        print(f"  3. View report:    GET  /api/v1/evaluation/{tender.id}/report")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
