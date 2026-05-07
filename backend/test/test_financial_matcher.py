"""
Regression tests for financial_matcher.py
"""

import pytest
from app.services.financial_matcher import (
    normalize_amount,
    extract_turnover,
    evaluate_financial,
)
from app.models import BidderDocument


# ========== normalize_amount ==========

class TestNormalizeAmount:
    def test_crore_format(self):
        assert normalize_amount("Rs. 5 Crore") == 50000000.0
        assert normalize_amount("5.5 Crore") == 55000000.0

    def test_lakh_format(self):
        assert normalize_amount("Rs. 50 Lakh") == 5000000.0
        assert normalize_amount("1.5 Lac") == 150000.0

    def test_numeric_only(self):
        assert normalize_amount("50000000") == 50000000.0

    def test_invalid_text(self):
        assert normalize_amount("not a number") == 0.0


# ========== extract_turnover ==========

class TestExtractTurnover:
    def test_simple_average(self):
        text = "Annual turnover Rs. 10 Crore, Rs. 12 Crore, Rs. 8 Crore"
        result = extract_turnover(text, time_window=3)
        assert result["average"] == 10000000.0
        assert len(result["matches"]) == 3

    def test_insufficient_years(self):
        text = "Turnover Rs. 5 Crore"
        result = extract_turnover(text, time_window=3)
        assert result["average"] == 5000000.0
        assert result["verdict"] == "NEEDS_REVIEW"

    def test_empty_text(self):
        result = extract_turnover("", time_window=3)
        assert result["verdict"] == "NEEDS_REVIEW"
        assert result["average"] == 0


# ========== evaluate_financial ==========

class TestEvaluateFinancial:
    def test_meets_threshold(self):
        doc = BidderDocument(
            id="test-1",
            bidder_id="bid-1",
            doc_type="AUDITED_ACCOUNTS",
            extracted_text="Annual turnover Rs. 10 Crore, Rs. 12 Crore, Rs. 8 Crore"
        )
        criterion = {
            "threshold": 50000000,
            "time_window_years": 3
        }
        result = evaluate_financial(doc, criterion)
        assert result["verdict"] == "ELIGIBLE"
        assert result["confidence"] > 0.7

    def test_below_threshold(self):
        doc = BidderDocument(
            id="test-2",
            bidder_id="bid-2",
            doc_type="AUDITED_ACCOUNTS",
            extracted_text="Annual turnover Rs. 1 Crore, Rs. 1.5 Crore"
        )
        criterion = {
            "threshold": 50000000,
            "time_window_years": 3
        }
        result = evaluate_financial(doc, criterion)
        assert result["verdict"] == "NOT_ELIGIBLE"

    def test_no_document(self):
        result = evaluate_financial(None, {"threshold": 50000000})
        assert result["verdict"] == "NEEDS_REVIEW"

    def test_no_extracted_text(self):
        doc = BidderDocument(id="test-3", bidder_id="bid-3", doc_type="AUDITED_ACCOUNTS")
        result = evaluate_financial(doc, {"threshold": 50000000})
        assert result["verdict"] == "NEEDS_REVIEW"
