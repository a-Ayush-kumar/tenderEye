import re
from datetime import datetime
from app.models import BidderDocument

IAF_MEMBER_BODIES = [
    "tuv", "bv", "bureau veritas", "dqs", "sgs", "intertek",
    "bsi", "lrqa", "nsf", "ul", "dnv", "certification international",
    "tuv sud", "tuv rheinland", "tuv nord", "dekra", "kiwa",
    "sai global", "abs quality evaluations", "aprove", "scsa"
]

IAF_REGISTRY_URL = "https://iafdb.iaf.nu/"  # IAF CertSearch (public lookup, no API key)


async def lookup_iaf_registry(cert_number: str, issuer: str = None) -> dict:
    """
    Verify certificate against IAF CertSearch public registry.
    Returns: {"verified": bool, "status": str, "details": dict}
    NOTE: Real implementation would scrape or use IAF API if available.
    For MVP, we simulate with heuristics and known patterns.
    """
    import httpx
    import os

    if not cert_number or len(cert_number) < 6:
        return {"verified": False, "status": "INVALID_FORMAT", "details": {}}

    # Try IAF CertSearch (public, no auth required)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # IAF search query (simulated — real URL may differ)
            search_url = f"{IAF_REGISTRY_URL}?certificate={cert_number}"
            if issuer:
                search_url += f"&body={issuer.replace(' ', '+')}"

            # For prototype: don't actually call IAF on every request
            # Use cached/stub response based on cert number patterns
            if os.getenv("USE_REAL_IAF_LOOKUP", "false").lower() == "true":
                response = await client.get(search_url, follow_redirects=True)
                if response.status_code == 200:
                    # Parse HTML response (IAF has no JSON API)
                    html = response.text
                    if "not found" in html.lower() or "no results" in html.lower():
                        return {"verified": False, "status": "NOT_FOUND", "details": {}}
                    if "valid" in html.lower() and cert_number in html:
                        return {"verified": True, "status": "VALID", "details": {"source": "IAF"}}

            # Stub verification based on known patterns
            return _stub_verify_certificate(cert_number, issuer)

    except Exception as e:
        print(f"IAF lookup error: {e}")
        return _stub_verify_certificate(cert_number, issuer)


def _stub_verify_certificate(cert_number: str, issuer: str = None) -> dict:
    """Fallback verification using certificate number patterns."""
    # Real cert numbers have specific formats per CB
    known_prefixes = {
        "tuv": ["TUV", "TUVSD"],
        "bv": ["BV", "BVC"],
        "sgs": ["SGS"],
        "dqs": ["DQS"],
        "intertek": ["INT", "ITS"],
        "bsi": ["BSI", "FM"],
        "dnv": ["DNV"],
    }

    cert_upper = cert_number.upper()
    matched_issuer = None

    for body, prefixes in known_prefixes.items():
        for prefix in prefixes:
            if cert_upper.startswith(prefix):
                matched_issuer = body
                break
        if matched_issuer:
            break

    if matched_issuer:
        return {
            "verified": True,
            "status": "PATTERN_MATCH",
            "details": {
                "detected_issuer": matched_issuer,
                "cert_number": cert_number,
                "note": "Pattern-based verification (IAF lookup stubbed)"
            }
        }

    return {
        "verified": False,
        "status": "UNKNOWN_ISSUER",
        "details": {
            "cert_number": cert_number,
            "note": "Certificate number format not recognized"
        }
    }

def validate_iso_certificate(document_text: str, tender_publish_date: datetime = None) -> dict:
    """Validate ISO 9001:2015 certification presence and format."""
    if not document_text:
        return {
            "has_certificate": False,
            "certificate_number": None,
            "issue_date": None,
            "expiry_date": None,
            "issuing_body": None,
            "is_iaf_member": False,
            "valid": False,
            "reason": "No document text available"
        }
    
    text_lower = document_text.lower()
    
    # Check for ISO 9001:2015 mention
    iso_pattern = re.compile(
        r'iso\s*9001[:\s]*2015|iso\s*9001|quality\s*management\s*system',
        re.IGNORECASE
    )
    has_iso = bool(iso_pattern.search(document_text))
    
    if not has_iso:
        return {
            "has_certificate": False,
            "certificate_number": None,
            "issue_date": None,
            "expiry_date": None,
            "issuing_body": None,
            "is_iaf_member": False,
            "valid": False,
            "reason": "No ISO 9001:2015 certification found in documents"
        }
    
    # Extract certificate number
    cert_patterns = [
        r'certificate\s*(?:no\.?|number|#)[\s:]*([A-Z0-9\-]{6,20})',
        r'cert\.?\s*no\.?[\s:]*([A-Z0-9\-]{6,20})',
        r'registration\s*(?:no\.?|number)[\s:]*([A-Z0-9\-]{6,20})'
    ]
    
    cert_number = None
    for pattern in cert_patterns:
        match = re.search(pattern, document_text, re.IGNORECASE)
        if match:
            cert_number = match.group(1).strip()
            break
    
    # Extract dates
    date_patterns = [
        r'(?:issue|valid\s*from|date\s*of\s*issue)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(?:expiry|valid\s*until|valid\s*till)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*[-–to]\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})'
    ]
    
    issue_date = None
    expiry_date = None
    
    for pattern in date_patterns:
        match = re.search(pattern, document_text, re.IGNORECASE)
        if match:
            if 'expiry' in pattern.lower() or 'until' in pattern.lower():
                expiry_date = match.group(1)
            elif 'issue' in pattern.lower():
                issue_date = match.group(1)
            elif 'to' in pattern:
                issue_date = match.group(1)
                expiry_date = match.group(2)
    
    # Extract issuing body
    issuing_body = None
    for body in IAF_MEMBER_BODIES:
        if body in text_lower:
            issuing_body = body.upper()
            break
    
    is_iaf = issuing_body is not None

    # IAF registry lookup for real verification
    # Note: Real IAF lookup is async and requires USE_REAL_IAF_LOOKUP=true.
    # In sync context, use stub verification which matches cert number patterns.
    iaf_lookup = {"verified": False, "status": "NOT_ATTEMPTED"}
    if cert_number and is_iaf:
        iaf_lookup = _stub_verify_certificate(cert_number, issuing_body)

    # Validate certificate is valid for tender date
    valid_for_tender = True
    if tender_publish_date and expiry_date:
        try:
            # Parse expiry date (best effort)
            for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%y", "%d-%m-%y"]:
                try:
                    exp = datetime.strptime(expiry_date, fmt)
                    if exp < tender_publish_date:
                        valid_for_tender = False
                    break
                except ValueError:
                    continue
        except:
            pass
    
    return {
        "has_certificate": True,
        "certificate_number": cert_number,
        "issue_date": issue_date,
        "expiry_date": expiry_date,
        "issuing_body": issuing_body,
        "is_iaf_member": is_iaf,
        "iaf_verified": iaf_lookup.get("verified", False),
        "iaf_status": iaf_lookup.get("status", "UNKNOWN"),
        "iaf_details": iaf_lookup.get("details", {}),
        "valid_for_tender": valid_for_tender,
        "valid": has_iso and is_iaf and valid_for_tender and iaf_lookup.get("verified", True),
        "reason": None
    }

def evaluate_documentary(bidder_doc: BidderDocument, criterion: dict, tender: object = None) -> dict:
    """Evaluate documentary criterion (ISO 9001:2015 certification)."""
    tender_publish = tender.publish_date if tender else datetime.utcnow()
    
    result = validate_iso_certificate(bidder_doc.extracted_text or "", tender_publish)
    
    if not result["has_certificate"]:
        return {
            "verdict": "NOT_ELIGIBLE",
            "reason": result["reason"],
            "confidence": 1.0,
            "source_page": 1,
            "verbatim_quote": None,
            "computed_value": "MISSING"
        }
    
    issues = []
    
    if not result["certificate_number"]:
        issues.append("Certificate number not found")
    
    if not result["is_iaf_member"]:
        issues.append(f"Issuing body '{result['issuing_body'] or 'unknown'}' is not IAF-accredited")
    
    if not result["valid_for_tender"]:
        issues.append(f"Certificate expired before tender publish date ({tender_publish.strftime('%Y-%m-%d')})")
    
    if issues:
        verdict = "NEEDS_REVIEW" if len(issues) == 1 and "number" in issues[0] else "NOT_ELIGIBLE"
        reason = "; ".join(issues)
    else:
        verdict = "ELIGIBLE"
        reason = f"Valid ISO 9001:2015 certificate #{result['certificate_number']} from IAF-accredited body {result['issuing_body']}"
    
    # Extract verbatim quote
    text = bidder_doc.extracted_text or ""
    iso_match = re.search(r'.{0,50}ISO\s*9001.{0,100}', text, re.IGNORECASE)
    verbatim = iso_match.group(0) if iso_match else None
    
    confidence = 0.9 if result["certificate_number"] and result["is_iaf_member"] else 0.6
    
    return {
        "verdict": verdict,
        "reason": reason,
        "confidence": confidence,
        "source_page": 1,
        "verbatim_quote": verbatim,
        "computed_value": result["certificate_number"] or "PRESENT_BUT_UNREADABLE",
        "certificate_details": result
    }
