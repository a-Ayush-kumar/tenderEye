from typing import Optional
import os
import tempfile
import logging

try:
    import pdfplumber  # type: ignore[import-untyped]
except ImportError:
    pdfplumber = None  # type: ignore[assignment]
    logging.warning("pdfplumber not installed – PDF text extraction will be limited.")


import re

def normalize_amount(text: str) -> float:
    """Normalize Indian currency strings into standard float amounts."""
    text = text.lower().replace("rs.", "").replace("rupees", "").replace(",", "").strip()
    
    # Try to extract numbers
    match = re.search(r"(\d+(\.\d+)?)", text)
    if not match:
        return 0.0
        
    num = float(match.group(1))
    
    if "crore" in text or "cr" in text:
        return num * 10000000.0
    elif "lakh" in text or "lac" in text:
        return num * 100000.0
    
    return num

def extract_turnover(text: str, time_window: int = 3) -> dict:
    """Extract turnover values from text and compute average."""
    if not text:
        return {"average": 0.0, "matches": [], "verdict": "NEEDS_REVIEW"}
        
    # Find all patterns like "Rs. X Crore", "X Lac", "Rs. X"
    pattern = r"(?:rs\.?|rupees)?\s*(\d+(?:\.\d+)?)\s*(?:crore|cr|lakh|lac)?"
    matches = re.finditer(pattern, text, re.IGNORECASE)
    
    extracted = []
    for m in matches:
        val = normalize_amount(m.group(0))
        if val > 0:
            extracted.append(val)
            
    if not extracted:
        return {"average": 0.0, "matches": [], "verdict": "NEEDS_REVIEW"}
        
    # Take the latest `time_window` matches if there are more
    relevant = extracted[-time_window:] if len(extracted) > time_window else extracted
    avg = sum(relevant) / len(relevant)
    
    verdict = "OK" if len(extracted) >= time_window else "NEEDS_REVIEW"
    
    return {
        "average": avg,
        "matches": extracted,
        "verdict": verdict
    }

def evaluate_financial(bidder_doc, criterion: dict) -> dict:
    """Evaluate financial compliance of a document."""
    if not bidder_doc or not bidder_doc.extracted_text:
        return {
            "verdict": "NEEDS_REVIEW",
            "reason": "Missing document or extracted text.",
            "confidence": 0.0,
            "source_page": None,
            "verbatim_quote": None,
        }
        
    threshold = criterion.get("threshold", 0)
    time_window = criterion.get("time_window_years", 3)
    
    turnover_data = extract_turnover(bidder_doc.extracted_text, time_window)
    
    if turnover_data["verdict"] == "NEEDS_REVIEW" and turnover_data["average"] == 0:
        return {
            "verdict": "NEEDS_REVIEW",
            "reason": "Could not extract sufficient turnover data.",
            "confidence": 0.3,
            "source_page": None,
            "verbatim_quote": None,
        }
        
    if turnover_data["average"] >= threshold:
        return {
            "verdict": "ELIGIBLE",
            "reason": f"Average turnover Rs. {turnover_data['average']/10000000:.2f} Cr meets threshold of Rs. {threshold/10000000:.2f} Cr.",
            "confidence": 0.8,
            "source_page": None,
            "verbatim_quote": None,
        }
    else:
        return {
            "verdict": "NOT_ELIGIBLE",
            "reason": f"Average turnover Rs. {turnover_data['average']/10000000:.2f} Cr is below threshold of Rs. {threshold/10000000:.2f} Cr.",
            "confidence": 0.8,
            "source_page": None,
            "verbatim_quote": None,
        }

# PaddleOCR lazy import — only loaded when needed (heavy dependency)
try:
    from paddleocr import PaddleOCR  # type: ignore[import-untyped]
except ImportError:
    PaddleOCR = None  # type: ignore[assignment,misc]

_paddle_ocr = None

def _get_paddle_ocr():
    """Lazy-load PaddleOCR to avoid startup cost."""
    global _paddle_ocr
    if _paddle_ocr is None:
        if PaddleOCR is not None:
            _paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
        else:
            _paddle_ocr = False  # Mark as unavailable
    return _paddle_ocr if _paddle_ocr is not False else None


def _ocr_from_pdf_images(file_path: str) -> dict:
    """Fallback: convert PDF pages to images and run PaddleOCR."""
    ocr = _get_paddle_ocr()
    if ocr is None:
        return {
            "pages": [],
            "page_count": 0,
            "full_text": "",
            "ocr_confidence": 0.0,
            "error": "PaddleOCR not installed — cannot process scanned PDFs"
        }

    from PIL import Image
    import io

    text_chunks = []
    confidences = []

    try:
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                # Convert page to image
                img = page.to_image(resolution=200)
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="PNG")
                img_bytes.seek(0)

                # Save temp image for PaddleOCR
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(img_bytes.read())
                    tmp_path = tmp.name

                try:
                    result = ocr.ocr(tmp_path, cls=True)
                    page_text_parts = []
                    page_confidences = []

                    if result and result[0]:
                        for line in result[0]:
                            text = line[1][0]
                            conf = line[1][1]
                            page_text_parts.append(text)
                            page_confidences.append(conf)

                    page_text = "\n".join(page_text_parts)
                    avg_conf = sum(page_confidences) / len(page_confidences) if page_confidences else 0.0

                    if page_text.strip():
                        text_chunks.append({
                            "page": i + 1,
                            "text": page_text,
                            "bbox": page.bbox,
                            "ocr_confidence": avg_conf
                        })
                        confidences.append(avg_conf)
                finally:
                    os.unlink(tmp_path)

    except Exception as e:
        return {
            "pages": [],
            "page_count": 0,
            "full_text": "",
            "ocr_confidence": 0.0,
            "error": f"PaddleOCR processing failed: {str(e)}"
        }

    full_text = "\n".join(t["text"] for t in text_chunks)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "pages": text_chunks,
        "page_count": len(text_chunks),
        "full_text": full_text,
        "ocr_confidence": round(avg_confidence, 3),
        "method": "paddleocr"
    }


async def extract_text_from_pdf(file_path: str) -> dict:
    """Extract text and metadata from PDF.
    
    Primary: Docling (IBM) — best for complex layouts, tables, and multi-column PDFs.
    Fallback 1: pdfplumber — fast fallback for simple digital PDFs.
    Fallback 2: PaddleOCR — for scanned/image PDFs if digital extraction yields little text.
    """
    try:
        from docling.document_converter import DocumentConverter  # type: ignore[import-untyped]
        import asyncio
        import concurrent.futures
        
        # Run docling (it's synchronous and heavy, must run in thread pool)
        converter = DocumentConverter()
        
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, converter.convert, file_path)
        
        full_text = result.document.export_to_markdown()
        # Create a single "page" chunk for now since markdown represents the whole doc
        text_chunks = [{"page": 1, "text": full_text, "bbox": None}]
        
        # Better extraction means higher confidence
        confidence = 0.95
        
        return {
            "pages": text_chunks,
            "page_count": len(list(result.document.pages)) if hasattr(result.document, "pages") else 1,
            "full_text": full_text,
            "ocr_confidence": confidence,
            "method": "docling"
        }
    except Exception as docling_err:
        print(f"Docling conversion failed: {docling_err}. Falling back to pdfplumber.")
        
        # Fallback to pdfplumber
        text_chunks = []
        page_count = 0
        full_text_parts = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_chunks.append({
                            "page": i + 1,
                            "text": page_text,
                            "bbox": page.bbox
                        })
                        full_text_parts.append(page_text)
                    page_count += 1
        except Exception as e:
            return {
                "pages": [],
                "page_count": 0,
                "full_text": "",
                "ocr_confidence": 0.0,
                "error": str(e)
            }
        
        full_text = "\n".join(full_text_parts)
        
        # If pdfplumber extracted very little text, try PaddleOCR fallback
        if page_count > 0 and len(full_text.strip()) < 50:
            ocr_result = _ocr_from_pdf_images(file_path)
            if ocr_result.get("full_text"):
                return ocr_result
        
        # Simple confidence heuristic
        confidence = 0.90 if page_count > 0 and len(full_text) > 100 else 0.5
        
        return {
            "pages": text_chunks,
            "page_count": page_count,
            "full_text": full_text,
            "ocr_confidence": confidence,
            "method": "pdfplumber"
        }
