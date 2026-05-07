"""
VIGIL Evaluation Report Generator
Primary: WeasyPrint (Linux/Docker with GTK).
Fallback: fpdf2 (pure Python, works everywhere including Windows).
"""

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    WEASYPRINT_AVAILABLE = False

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

from datetime import datetime
from typing import Dict, Any


def _generate_with_fpdf(report_data: Dict[str, Any]) -> bytes:
    """Generate a real PDF report using fpdf2 (pure Python, no GTK needed)."""
    tender = report_data["tender"]
    bidders = report_data["bidders"]

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 12, "VIGIL Tender Evaluation Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 6, "CAG-Compliant Format | Hash Chain Verified", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Tender Info
    pdf.set_draw_color(26, 54, 93)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 8, "Tender Information", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)

    info_rows = [
        ("Tender ID", str(tender.id)),
        ("Title", str(tender.title)),
        ("Department", str(tender.department)),
        ("Status", str(tender.status)),
        ("Evaluation Date", datetime.utcnow().strftime('%d-%b-%Y %H:%M UTC')),
        ("Criteria Locked", tender.criteria_locked.strftime('%d-%b-%Y %H:%M UTC') if tender.criteria_locked else 'Not locked'),
    ]
    for label, value in info_rows:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(45, 7, f"{label}:", border=0)
        pdf.set_font("Helvetica", "", 10)
        # Truncate long values to prevent overflow
        display_value = value[:80] + "..." if len(value) > 80 else value
        pdf.cell(0, 7, display_value, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Criteria Table
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 8, "Evaluation Criteria", new_x="LMARGIN", new_y="NEXT")

    criteria = tender.criteria or []
    if criteria:
        # Table header
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(26, 54, 93)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(15, 7, "ID", border=1, fill=True)
        pdf.cell(25, 7, "Type", border=1, fill=True)
        pdf.cell(110, 7, "Description", border=1, fill=True)
        pdf.cell(40, 7, "Threshold", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

        # Table rows
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        for c in criteria:
            pdf.set_fill_color(248, 250, 252)
            cid = str(c.get("id", "N/A"))[:10]
            ctype = str(c.get("type", "N/A"))[:15]
            desc = str(c.get("description", "N/A"))[:65]
            thresh = str(c.get("threshold", "N/A"))[:20]
            pdf.cell(15, 7, cid, border=1)
            pdf.cell(25, 7, ctype, border=1)
            pdf.cell(110, 7, desc, border=1)
            pdf.cell(40, 7, thresh, border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Bidder Results Table
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 8, "Bidder Evaluation Results", new_x="LMARGIN", new_y="NEXT")

    # Table header
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(26, 54, 93)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(45, 7, "Bidder", border=1, fill=True)
    pdf.cell(25, 7, "PAN", border=1, fill=True)
    pdf.cell(35, 7, "GSTIN", border=1, fill=True)
    pdf.cell(25, 7, "Overall", border=1, fill=True)
    pdf.cell(60, 7, "Details", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    for b_data in bidders:
        bidder = b_data["bidder"]
        verdicts = b_data["verdicts"]
        overall = b_data["overall"]

        # Color-code overall verdict
        if overall == "ELIGIBLE":
            pdf.set_text_color(22, 101, 52)
        elif overall == "NOT_ELIGIBLE":
            pdf.set_text_color(153, 27, 27)
        elif overall == "NEEDS_REVIEW":
            pdf.set_text_color(146, 64, 14)
        else:
            pdf.set_text_color(0, 0, 0)

        details = "; ".join(f"{v.criterion_type}: {v.verdict}" for v in verdicts) if verdicts else "Not evaluated"
        details_short = details[:35] + "..." if len(details) > 35 else details

        name_short = str(bidder.name)[:25]
        pdf.cell(45, 7, name_short, border=1)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(25, 7, str(bidder.pan or "N/A"), border=1)
        pdf.cell(35, 7, str(bidder.gstin or "N/A")[:15], border=1)

        # Overall cell with color
        if overall == "ELIGIBLE":
            pdf.set_text_color(22, 101, 52)
        elif overall == "NOT_ELIGIBLE":
            pdf.set_text_color(153, 27, 27)
        elif overall == "NEEDS_REVIEW":
            pdf.set_text_color(146, 64, 14)
        else:
            pdf.set_text_color(0, 0, 0)
        pdf.cell(25, 7, overall[:12], border=1)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(60, 7, details_short, border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)

    # Footer
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.cell(0, 5, f"Generated by VIGIL v0.1.0 | {datetime.utcnow().strftime('%d-%b-%Y %H:%M UTC')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, "Audit Verification: GET /api/v1/audit/verify", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, "This report is hash-chain verified. All verdicts are traceable to source documents.", new_x="LMARGIN", new_y="NEXT")

    # fpdf2 returns bytearray; convert to bytes for Starlette Response compatibility
    return bytes(pdf.output())


def _build_html(report_data: Dict[str, Any]) -> str:
    """Build the HTML report content."""
    tender = report_data["tender"]
    bidders = report_data["bidders"]

    criteria_rows = ""
    for c in tender.criteria or []:
        criteria_rows += f"""
        <tr>
            <td>{c.get('id', 'N/A')}</td>
            <td>{c.get('type', 'N/A')}</td>
            <td>{c.get('description', 'N/A')}</td>
            <td>{c.get('threshold', 'N/A')}</td>
        </tr>"""

    bidder_rows = ""
    for b_data in bidders:
        bidder = b_data["bidder"]
        verdicts = b_data["verdicts"]
        overall = b_data["overall"]
        overall_class = overall.lower().replace("_", "-")
        criteria_details = "; ".join(
            f"{v.criterion_type}: {v.verdict}" for v in verdicts
        ) if verdicts else "Not evaluated"

        bidder_rows += f"""
        <tr>
            <td>{bidder.name}</td>
            <td>{bidder.pan or 'N/A'}</td>
            <td>{bidder.gstin or 'N/A'}</td>
            <td class="{overall_class}">{overall}</td>
            <td>{criteria_details}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Noto Sans', Arial, sans-serif; margin: 40px; font-size: 11pt; line-height: 1.5; }}
        h1 {{ font-size: 18pt; border-bottom: 2px solid #1a365d; padding-bottom: 8px; color: #1a365d; }}
        h2 {{ font-size: 14pt; color: #1a365d; margin-top: 24px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 10pt; }}
        th {{ background: #1a365d; color: white; padding: 8px; text-align: left; font-weight: bold; }}
        td {{ padding: 8px; border-bottom: 1px solid #e2e8f0; }}
        tr:nth-child(even) {{ background: #f8fafc; }}
        .eligible {{ color: #166534; font-weight: bold; }}
        .not-eligible {{ color: #991b1b; font-weight: bold; }}
        .needs-review {{ color: #92400e; font-weight: bold; }}
        .footer {{ margin-top: 40px; font-size: 9pt; color: #64748b; border-top: 1px solid #e2e8f0; padding-top: 8px; }}
    </style>
</head>
<body>
    <h1>VIGIL Tender Evaluation Report</h1>
    <h2>Tender Information</h2>
    <table>
        <tr><td><strong>Tender ID:</strong></td><td>{tender.id}</td></tr>
        <tr><td><strong>Title:</strong></td><td>{tender.title}</td></tr>
        <tr><td><strong>Department:</strong></td><td>{tender.department}</td></tr>
        <tr><td><strong>Evaluation Date:</strong></td><td>{datetime.utcnow().strftime('%d-%b-%Y %H:%M UTC')}</td></tr>
        <tr><td><strong>Criteria Locked:</strong></td><td>{tender.criteria_locked.strftime('%d-%b-%Y %H:%M UTC') if tender.criteria_locked else 'Not locked'}</td></tr>
    </table>

    <h2>Evaluation Criteria</h2>
    <table>
        <tr><th>ID</th><th>Type</th><th>Description</th><th>Threshold</th></tr>
        {criteria_rows}
    </table>

    <h2>Bidder Evaluation Results</h2>
    <table>
        <tr><th>Bidder</th><th>PAN</th><th>GSTIN</th><th>Overall</th><th>Details</th></tr>
        {bidder_rows}
    </table>

    <h2>Audit Verification</h2>
    <p>This report was generated from a cryptographically verified audit chain.</p>
    <p><strong>Verification Endpoint:</strong> <code>GET /api/v1/audit/verify</code></p>

    <div class="footer">
        <p>Generated by VIGIL v0.1.0 | Hash Chain Verified | CAG-Compliant Format</p>
    </div>
</body>
</html>"""


def generate_evaluation_report(report_data: Dict[str, Any]) -> bytes:
    """Generate a CAG-formatted evaluation report PDF.
    
    Uses WeasyPrint if available (Linux/Docker), falls back to fpdf2 (Windows/anywhere).
    """
    if WEASYPRINT_AVAILABLE:
        html_content = _build_html(report_data)
        return HTML(string=html_content).write_pdf()
    
    if FPDF_AVAILABLE:
        return _generate_with_fpdf(report_data)
    
    # Last resort: return a minimal valid PDF with error message
    # This should never happen if requirements are installed
    raise RuntimeError(
        "No PDF generator available. Install fpdf2: pip install fpdf2"
    )
