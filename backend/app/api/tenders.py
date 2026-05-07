from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models import Tender, Bidder, BidderDocument, TenderDocument
from app.services.document_processor import extract_text_from_pdf
from app.ai.ollama_client import extract_criteria_from_text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import os
import tempfile
import asyncio

router = APIRouter()

class TenderCreate(BaseModel):
    title: str
    department: str
    criteria: Optional[List[dict]] = None

class TenderResponse(BaseModel):
    id: str
    title: str
    department: str
    status: str
    criteria: list
    criteria_locked: Optional[datetime] = None

    class Config:
        from_attributes = True

class BidderCreate(BaseModel):
    name: str
    pan: Optional[str] = None
    gstin: Optional[str] = None

class BidderResponse(BaseModel):
    id: str
    name: str
    pan: Optional[str] = None
    gstin: Optional[str] = None
    status: str

    class Config:
        from_attributes = True

USE_LOCAL_STORAGE = os.getenv("USE_LOCAL_STORAGE", "true").lower() == "true"

# MinIO client (optional, only when not using local storage)
minio_client = None
if not USE_LOCAL_STORAGE:
    import boto3
    try:
        minio_client = boto3.client(
            "s3",
            endpoint_url=f"http://{os.getenv('MINIO_ENDPOINT', 'minio:9000')}",
            aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            region_name="us-east-1",
        )
    except Exception:
        minio_client = None

BUCKET_NAME = "tender-docs"

# Get a stable uploads directory relative to the backend folder
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
UPLOADS_DIR = os.path.join(BACKEND_DIR, "uploads")


def _save_file_locally(file: UploadFile, sub_path: str) -> str:
    """Save uploaded file to local uploads directory. Returns absolute file path."""
    full_dir = os.path.join(UPLOADS_DIR, os.path.dirname(sub_path))
    os.makedirs(full_dir, exist_ok=True)
    full_path = os.path.join(UPLOADS_DIR, sub_path)
    content = file.file.read()
    with open(full_path, "wb") as f:
        f.write(content)
    return full_path


@router.get("", response_model=list[TenderResponse])
@router.get("/", response_model=list[TenderResponse])
def list_tenders(db: Session = Depends(get_db)):
    return db.query(Tender).order_by(Tender.publish_date.desc()).all()

@router.post("", response_model=TenderResponse)
@router.post("/", response_model=TenderResponse)
def create_tender(tender: TenderCreate, db: Session = Depends(get_db)):
    db_tender = Tender(
        title=tender.title,
        department=tender.department,
        criteria=tender.criteria or []
    )
    db.add(db_tender)
    db.commit()
    db.refresh(db_tender)
    return db_tender

@router.get("/{tender_id}", response_model=TenderResponse)
def get_tender(tender_id: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender

@router.put("/{tender_id}/criteria")
def update_criteria(tender_id: str, criteria: List[dict], db: Session = Depends(get_db)):
    """Allow officer to edit extracted criteria before locking."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    if tender.criteria_locked:
        raise HTTPException(status_code=400, detail="Criteria already locked — cannot edit")
    
    tender.criteria = criteria
    db.commit()
    db.refresh(tender)
    return {"message": "Criteria updated", "criteria": tender.criteria}

@router.post("/{tender_id}/lock")
def lock_criteria(tender_id: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    if tender.criteria_locked:
        raise HTTPException(status_code=400, detail="Criteria already locked")
    
    tender.criteria_locked = datetime.utcnow()
    tender.status = "PUBLISHED"
    db.commit()
    db.refresh(tender)
    return {"message": "Criteria locked", "locked_at": tender.criteria_locked}

@router.post("/{tender_id}/documents")
async def upload_tender_document(
    tender_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a tender PDF, extract text, run Ollama criteria extraction, update tender.criteria."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    if tender.criteria_locked:
        raise HTTPException(status_code=400, detail="Criteria already locked — cannot upload new documents")
    
    file_key = f"tenders/{tender_id}/{file.filename}"
    
    # Step 1: Save the file
    if USE_LOCAL_STORAGE:
        saved_path = _save_file_locally(file, file_key)
    else:
        # Save to temp file for processing, then upload to MinIO
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = file.file.read()
            tmp.write(content)
            saved_path = tmp.name
        try:
            file.file.seek(0)
            minio_client.upload_fileobj(file.file, BUCKET_NAME, file_key)
        except Exception:
            try:
                minio_client.create_bucket(Bucket=BUCKET_NAME)
                file.file.seek(0)
                minio_client.upload_fileobj(file.file, BUCKET_NAME, file_key)
            except Exception as e:
                os.unlink(saved_path)
                raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    # Step 2: Extract text from PDF
    extraction = await extract_text_from_pdf(saved_path)
    extracted_text = extraction.get("full_text", "")
    
    # Save the TenderDocument record
    tender_doc = TenderDocument(
        tender_id=tender_id,
        filename=file.filename,
        minio_path=file_key,
        extracted_text=extracted_text,
        ocr_confidence=extraction.get("ocr_confidence", 0.0)
    )
    db.add(tender_doc)
    
    # Step 3: Extract criteria via Ollama (or fallback mock)
    criteria = []
    if extracted_text.strip():
        criteria = await extract_criteria_from_text(extracted_text)
    
    # Step 4: Update tender criteria (merge with existing if any)
    if criteria:
        tender.criteria = criteria
        tender.status = "CRITERIA_EXTRACTED"
    
    db.commit()
    db.refresh(tender)
    
    # Clean up temp file if MinIO mode
    if not USE_LOCAL_STORAGE and os.path.exists(saved_path):
        os.unlink(saved_path)
    
    return {
        "message": "Document processed",
        "filename": file.filename,
        "path": file_key,
        "pages_extracted": extraction.get("page_count", 0),
        "text_length": len(extracted_text),
        "ocr_confidence": extraction.get("ocr_confidence", 0.0),
        "extraction_method": extraction.get("method", "unknown"),
        "criteria_count": len(criteria),
        "criteria": criteria
    }

@router.post("/{tender_id}/bidders", response_model=BidderResponse)
def create_bidder(
    tender_id: str,
    bidder: BidderCreate,
    db: Session = Depends(get_db)
):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    db_bidder = Bidder(
        tender_id=tender_id,
        name=bidder.name,
        pan=bidder.pan,
        gstin=bidder.gstin
    )
    db.add(db_bidder)
    db.commit()
    db.refresh(db_bidder)
    return db_bidder

@router.get("/{tender_id}/bidders", response_model=List[BidderResponse])
def get_bidders(tender_id: str, db: Session = Depends(get_db)):
    return db.query(Bidder).filter(Bidder.tender_id == tender_id).all()
