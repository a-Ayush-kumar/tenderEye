#!/bin/bash
# ============================================================================
# VIGIL Prototype — End-to-End Test Script
# ============================================================================
# Usage: bash tests/e2e.sh
# Prerequisites: Backend running on localhost:8000, jq installed
# ============================================================================
set -e

BASE="http://localhost:8000/api/v1"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}✓ $1${NC}"; }
fail() { echo -e "${RED}✗ $1${NC}"; exit 1; }
info() { echo -e "${YELLOW}→ $1${NC}"; }

echo ""
echo "============================================"
echo "  VIGIL Prototype — End-to-End Test"
echo "============================================"
echo ""

# ------------------------------------------------------------------
# 0. Health Check
# ------------------------------------------------------------------
info "Checking backend health..."
HEALTH=$(curl -sf "$BASE/../health" || echo "FAIL")
if echo "$HEALTH" | grep -q "ok"; then
  pass "Backend is healthy"
else
  fail "Backend health check failed. Is it running on port 8000?"
fi

# ------------------------------------------------------------------
# 1. Create Tender
# ------------------------------------------------------------------
info "Creating tender..."
TENDER=$(curl -sf -X POST "$BASE/tenders" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "E2E Test Tender - Road Construction Phase II",
    "department": "PWD",
    "criteria": [
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
        "description": "Valid GSTIN with matching PAN"
      }
    ]
  }')

TENDER_ID=$(echo "$TENDER" | jq -r '.id')
if [ "$TENDER_ID" != "null" ] && [ -n "$TENDER_ID" ]; then
  pass "Tender created: $TENDER_ID"
else
  fail "Failed to create tender"
fi

# ------------------------------------------------------------------
# 2. Verify Tender Retrieval
# ------------------------------------------------------------------
info "Fetching tender..."
FETCHED=$(curl -sf "$BASE/tenders/$TENDER_ID")
FETCHED_TITLE=$(echo "$FETCHED" | jq -r '.title')
if [ "$FETCHED_TITLE" = "E2E Test Tender - Road Construction Phase II" ]; then
  pass "Tender retrieved successfully"
else
  fail "Tender title mismatch: $FETCHED_TITLE"
fi

# ------------------------------------------------------------------
# 3. Lock Criteria
# ------------------------------------------------------------------
info "Locking criteria..."
LOCK=$(curl -sf -X POST "$BASE/tenders/$TENDER_ID/lock")
if echo "$LOCK" | grep -q "locked"; then
  pass "Criteria locked"
else
  fail "Failed to lock criteria"
fi

# ------------------------------------------------------------------
# 4. Create Bidders
# ------------------------------------------------------------------
info "Creating bidders..."

# Bidder A — should be ELIGIBLE
BIDDER_A=$(curl -sf -X POST "$BASE/tenders/$TENDER_ID/bidders" \
  -H "Content-Type: application/json" \
  -d '{"name": "Alpha Infra Pvt Ltd", "pan": "AADCA1234A", "gstin": "07AADCA1234A1Z5"}')
BIDDER_A_ID=$(echo "$BIDDER_A" | jq -r '.id')
pass "Bidder A (Alpha Infra): $BIDDER_A_ID"

# Bidder B — should be NOT_ELIGIBLE (low turnover)
BIDDER_B=$(curl -sf -X POST "$BASE/tenders/$TENDER_ID/bidders" \
  -H "Content-Type: application/json" \
  -d '{"name": "Beta Builders", "pan": "BBBPB5678B", "gstin": "09BBBPB5678B1Z3"}')
BIDDER_B_ID=$(echo "$BIDDER_B" | jq -r '.id')
pass "Bidder B (Beta Builders): $BIDDER_B_ID"

# ------------------------------------------------------------------
# 5. Run Evaluation
# ------------------------------------------------------------------
info "Running evaluation..."
EVAL=$(curl -sf -X POST "$BASE/evaluation/$TENDER_ID/run")
RESULT_COUNT=$(echo "$EVAL" | jq '.results | length')
if [ "$RESULT_COUNT" -ge 1 ]; then
  pass "Evaluation completed: $RESULT_COUNT bidder(s) evaluated"
else
  fail "Evaluation returned no results"
fi

# Print results summary
echo ""
echo "  --- Results Summary ---"
echo "$EVAL" | jq -r '.results[] | "  \(.bidder_name): \(.overall)"'
echo ""

# ------------------------------------------------------------------
# 6. Get Stored Results
# ------------------------------------------------------------------
info "Fetching stored results..."
STORED=$(curl -sf "$BASE/evaluation/$TENDER_ID/results")
STORED_COUNT=$(echo "$STORED" | jq '.results | length')
if [ "$STORED_COUNT" -ge 1 ]; then
  pass "Stored results retrieved: $STORED_COUNT bidder(s)"
else
  fail "No stored results found"
fi

# ------------------------------------------------------------------
# 7. Verify Audit Chain
# ------------------------------------------------------------------
info "Verifying audit chain..."
VERIFY=$(curl -sf "$BASE/audit/verify")
VALID=$(echo "$VERIFY" | jq -r '.valid')
BLOCKS=$(echo "$VERIFY" | jq -r '.blocks')
if [ "$VALID" = "true" ]; then
  pass "Audit chain verified: $BLOCKS blocks, chain valid"
else
  fail "Audit chain broken: $(echo $VERIFY | jq -r '.reason')"
fi

# ------------------------------------------------------------------
# 8. Download Report
# ------------------------------------------------------------------
info "Downloading evaluation report..."
REPORT_FILE="/tmp/vigil_e2e_report.pdf"
HTTP_CODE=$(curl -sf -o "$REPORT_FILE" -w "%{http_code}" "$BASE/evaluation/$TENDER_ID/report")
if [ "$HTTP_CODE" = "200" ]; then
  REPORT_SIZE=$(wc -c < "$REPORT_FILE")
  pass "Report downloaded: $REPORT_SIZE bytes → $REPORT_FILE"
else
  fail "Report download failed with HTTP $HTTP_CODE"
fi

# ------------------------------------------------------------------
# 9. List Audit Logs
# ------------------------------------------------------------------
info "Fetching audit logs..."
LOGS=$(curl -sf "$BASE/audit/logs")
LOG_COUNT=$(echo "$LOGS" | jq 'length')
if [ "$LOG_COUNT" -ge 1 ]; then
  pass "Audit logs retrieved: $LOG_COUNT entries"
else
  fail "No audit logs found"
fi

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
echo ""
echo "============================================"
echo -e "  ${GREEN}All E2E tests passed!${NC}"
echo "============================================"
echo ""
echo "  Tender ID:    $TENDER_ID"
echo "  Bidders:      2"
echo "  Audit Blocks: $BLOCKS"
echo "  Report:       $REPORT_FILE"
echo ""
