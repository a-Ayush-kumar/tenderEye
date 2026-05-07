from app.models import Bidder

GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
MULTIPLIERS = [1, 2, 1, 2, 1, 2, 4, 1, 2, 1, 2, 4, 1, 2]
VALID_STATE_CODES = {f"{i:02d}" for i in range(1, 39)}

def validate_gstin(gstin: str) -> dict:
    """Validate GSTIN structure, state code, and checksum."""
    if not gstin:
        return {"valid": False, "reason": "No GSTIN provided"}
    
    gstin = gstin.upper().strip()
    
    if len(gstin) != 15:
        return {"valid": False, "reason": f"GSTIN must be 15 characters, got {len(gstin)}"}
    
    # Check state code
    state_code = gstin[:2]
    if state_code not in VALID_STATE_CODES:
        return {"valid": False, "reason": f"Invalid state code: {state_code}"}
    
    # Check characters are valid
    for char in gstin[:14]:
        if char not in GSTIN_CHARS:
            return {"valid": False, "reason": f"Invalid character in GSTIN: {char}"}
    
    # Checksum calculation
    total = 0
    for i, char in enumerate(gstin[:14]):
        value = GSTIN_CHARS.index(char)
        product = value * MULTIPLIERS[i]
        total += (product // 10) + (product % 10)
    
    check_digit = GSTIN_CHARS[(10 - (total % 10)) % 10]
    if gstin[14] != check_digit:
        return {"valid": False, "reason": "Checksum failed"}
    
    return {"valid": True, "reason": "Valid GSTIN"}

def evaluate_compliance(bidder: Bidder, criterion: dict) -> dict:
    """Evaluate compliance criterion (GSTIN validity + PAN cross-check)."""
    if not bidder.gstin:
        return {
            "verdict": "NOT_ELIGIBLE",
            "reason": "No GSTIN provided by bidder",
            "confidence": 1.0
        }
    
    result = validate_gstin(bidder.gstin)
    
    if not result["valid"]:
        return {
            "verdict": "NOT_ELIGIBLE",
            "reason": result["reason"],
            "confidence": 1.0
        }
    
    # PAN cross-check: GSTIN chars 2-12 should match bidder PAN
    gstin_pan = bidder.gstin[2:12]
    if bidder.pan:
        if gstin_pan != bidder.pan.upper():
            return {
                "verdict": "NEEDS_REVIEW",
                "reason": f"PAN mismatch: GSTIN-derived PAN {gstin_pan} vs registered PAN {bidder.pan}",
                "confidence": 0.9
            }
    
    return {
        "verdict": "ELIGIBLE",
        "reason": "Valid GSTIN structure, checksum passed, PAN matches",
        "confidence": 1.0
    }
