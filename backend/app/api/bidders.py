from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Bidder, BidderDocument
from app.services.document_processor import extract_text_from_pdf
from pydantic import BaseModel
from typing import Optional
import os
import tempfile

router = APIRouter()

class DocumentResponse(BaseModel):
    id: str
    doc_type: str
    filename: str
    extracted_text: Optional[str] = None
    ocr_confidence: float
    page_count: int = 0

    class Config:
        from_attributes = True

USE_LOCAL_STORAGE = os.getenv("USE_LOCAL_STORAGE", "true").lower() == "true"

# MinIO client (optional)
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
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
UPLOADS_DIR = os.path.join(BACKEND_DIR, "uploads")


@router.post("/bidders/{bidder_id}/documents")
async def upload_bidder_document(
    bidder_id: str,
    doc_type: str = Form("AUDITED_ACCOUNTS"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a bidder PDF, extract text via pdfplumber/OCR, save to BidderDocument.extracted_text."""
    bidder = db.query(Bidder).filter(Bidder.id == bidder_id).first()
    if not bidder:
        raise HTTPException(status_code=404, detail="Bidder not found")
    
    file_key = f"bidders/{bidder_id}/{file.filename}"
    
    # Step 1: Save the file
    if USE_LOCAL_STORAGE:
        full_dir = os.path.join(UPLOADS_DIR, "bidders", bidder_id)
        os.makedirs(full_dir, exist_ok=True)
        saved_path = os.path.join(full_dir, file.filename)
        content = file.file.read()
        with open(saved_path, "wb") as f:
            f.write(content)
    else:
        # Save temp for processing, upload to MinIO
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
    ocr_confidence = extraction.get("ocr_confidence", 0.0)
    page_count = extraction.get("page_count", 0)
    
    # Step 3: Save document record with extracted text
    doc = BidderDocument(
        bidder_id=bidder_id,
        doc_type=doc_type,
        filename=file.filename,
        minio_path=file_key,
        extracted_text=extracted_text if extracted_text.strip() else None,
        ocr_confidence=ocr_confidence,
        page_count=page_count,
        extracted_json=extraction.get("pages")  # store per-page breakdown
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    # Clean up temp file if MinIO mode
    if not USE_LOCAL_STORAGE and os.path.exists(saved_path):
        os.unlink(saved_path)
    
    return {
        "id": doc.id,
        "doc_type": doc.doc_type,
        "filename": doc.filename,
        "ocr_confidence": ocr_confidence,
        "page_count": page_count,
        "text_length": len(extracted_text),
        "extraction_method": extraction.get("method", "unknown"),
        "message": "Document uploaded and text extracted" if extracted_text.strip() else "Document uploaded but no text could be extracted"
    }

@router.get("/bidders/{bidder_id}/documents", response_model=list[DocumentResponse])
def get_bidder_documents(bidder_id: str, db: Session = Depends(get_db)):
    return db.query(BidderDocument).filter(BidderDocument.bidder_id == bidder_id).all()

@router.get("/bidders/{bidder_id}/documents/{doc_id}/download")
def download_bidder_document(bidder_id: str, doc_id: str, db: Session = Depends(get_db)):
    """Stream the PDF file for the Evidence Viewer."""
    doc = db.query(BidderDocument).filter(
        BidderDocument.id == doc_id,
        BidderDocument.bidder_id == bidder_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if USE_LOCAL_STORAGE:
        file_path = os.path.join(UPLOADS_DIR, doc.minio_path) if doc.minio_path else None
        if not file_path or not os.path.exists(file_path):
            # Return a dummy PDF instead of 404 so Evidence Viewer doesn't crash
            dummy_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>\nendobj\n4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n5 0 obj\n<< /Length 76 >>\nstream\nBT\n/F1 24 Tf\n100 700 Td\n(Mock Document: File not uploaded locally) Tj\nET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000229 00000 n \n0000000317 00000 n \ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n444\n%%EOF"
            from fastapi.responses import Response
            return Response(content=dummy_pdf, media_type="application/pdf")
            
        from fastapi.responses import FileResponse
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=doc.filename or "document.pdf"
        )
    else:
        # Stream from MinIO
        if not minio_client:
            raise HTTPException(status_code=503, detail="Storage not configured")
        try:
            obj = minio_client.get_object(Bucket=BUCKET_NAME, Key=doc.minio_path)
            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                obj["Body"],
                media_type="application/pdf",
                headers={"Content-Disposition": f'inline; filename="{doc.filename}"'}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@router.get("/bidders/{bidder_id}")
def get_bidder(bidder_id: str, db: Session = Depends(get_db)):
    bidder = db.query(Bidder).filter(Bidder.id == bidder_id).first()
    if not bidder:
        raise HTTPException(status_code=404, detail="Bidder not found")
    return bidder
