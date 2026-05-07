"""
Regression tests for compliance_matcher.py
"""

import pytest
from app.services.compliance_matcher import (
    validate_gstin,
    evaluate_compliance,
)
from app.models import Bidder


# ========== validate_gstin_checksum ==========

class TestValidateGSTINChecksum:
    def test_valid_gstin(self):
        # This is a real valid GSTIN format (format-wise valid, checksum may vary)
        # Testing with known valid checksum examples
        assert validate_gstin("22AAAAA0000A1Z5")["valid"] == True

    def test_invalid_length(self):
        assert validate_gstin("SHORT")["valid"] == False

    def test_invalid_format(self):
        assert validate_gstin("INVALIDGSTIN1234")["valid"] == False

    def test_none_input(self):
        assert validate_gstin(None)["valid"] == False

    def test_checksum_failure(self):
        # Change last digit to make checksum invalid
        assert validate_gstin("22AAAAA0000A1Z0")["valid"] == False


# ========== evaluate_compliance ==========

class TestEvaluateCompliance:
    def test_valid_gstin_matching_pan(self):
        bidder = Bidder(
            id="test-1",
            tender_id="t-1",
            name="Test Corp",
            pan="AAAAA0000A",
            gstin="07AAAAA0000A1Z5"
        )
        criterion = {"type": "COMPLIANCE"}
        result = evaluate_compliance(bidder, criterion)
        assert result["verdict"] == "ELIGIBLE"
        assert result["confidence"] > 0.8

    def test_gstin_pan_mismatch(self):
        bidder = Bidder(
            id="test-2",
            tender_id="t-1",
            name="Test Corp",
            pan="BBBBB1111B",
            gstin="07AAAAA0000A1Z5"
        )
        criterion = {"type": "COMPLIANCE"}
        result = evaluate_compliance(bidder, criterion)
        assert result["verdict"] == "NOT_ELIGIBLE"
        assert "PAN mismatch" in result["reason"]

    def test_missing_gstin(self):
        bidder = Bidder(
            id="test-3",
            tender_id="t-1",
            name="Test Corp",
            pan="AAAAA0000A",
            gstin=None
        )
        criterion = {"type": "COMPLIANCE"}
        result = evaluate_compliance(bidder, criterion)
        assert result["verdict"] == "NOT_ELIGIBLE"

    def test_missing_pan(self):
        bidder = Bidder(
            id="test-4",
            tender_id="t-1",
            name="Test Corp",
            pan=None,
            gstin="07AAAAA0000A1Z5"
        )
        criterion = {"type": "COMPLIANCE"}
        result = evaluate_compliance(bidder, criterion)
        assert result["verdict"] == "NEEDS_REVIEW"
