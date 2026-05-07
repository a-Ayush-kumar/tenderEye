"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import EvidenceViewer from "../../../../components/EvidenceViewer";

interface BidderDetail {
  id: string;
  name: string;
  pan: string | null;
  gstin: string | null;
  status: string;
}

interface BidderDoc {
  id: string;
  doc_type: string;
  filename: string;
  extracted_text: string | null;
  ocr_confidence: number;
}

interface Verdict {
  criterion_id: string;
  criterion_type: string;
  verdict: string;
  reason: string | null;
  confidence: number;
  source_page: number | null;
  verbatim_quote: string | null;
}

export default function BidderEvidencePage() {
  const params = useParams();
  const tenderId = params.id as string;
  const bidderId = params.bidderId as string;

  const [bidder, setBidder] = useState<BidderDetail | null>(null);
  const [documents, setDocuments] = useState<BidderDoc[]>([]);
  const [verdicts, setVerdicts] = useState<Verdict[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (tenderId && bidderId) {
      fetchAll();
    }
  }, [tenderId, bidderId]);

  async function fetchAll() {
    setLoading(true);
    try {
      const [bidderRes, docsRes, resultsRes] = await Promise.all([
        fetch(`/api/v1/bidders/${bidderId}`),
        fetch(`/api/v1/bidders/${bidderId}/documents`),
        fetch(`/api/v1/evaluation/${tenderId}/results`),
      ]);

      if (bidderRes.ok) setBidder(await bidderRes.json());
      if (docsRes.ok) setDocuments(await docsRes.json());

      if (resultsRes.ok) {
        const data = await resultsRes.json();
        // Find verdicts for this specific bidder
        const bidderResult = data.results?.find(
          (r: { bidder_id: string }) => r.bidder_id === bidderId
        );
        if (bidderResult) {
          setVerdicts(bidderResult.verdicts || []);
        }
      }
    } catch (err) {
      setError("Failed to load bidder evidence data");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        <span className="ml-3 text-gray-500">Loading evidence...</span>
      </div>
    );
  }

  if (!bidder) {
    return (
      <div className="text-center py-16 text-red-500">
        Bidder not found.{" "}
        <Link href={`/tenders/${tenderId}`} className="underline">
          Go back
        </Link>
      </div>
    );
  }

  // Build a PDF download URL if a document exists
  const firstDoc = documents.find((d) => d.doc_type === "AUDITED_ACCOUNTS") || documents[0];
  const pdfUrl = firstDoc
    ? `/api/v1/bidders/${bidderId}/documents/${firstDoc.id}/download`
    : null;

  // Compute overall verdict
  const statuses = verdicts.map((v) => v.verdict);
  const overall = statuses.includes("NOT_ELIGIBLE")
    ? "NOT_ELIGIBLE"
    : statuses.includes("NEEDS_REVIEW")
    ? "NEEDS_REVIEW"
    : statuses.length > 0
    ? "ELIGIBLE"
    : "PENDING";

  const overallColor =
    overall === "ELIGIBLE"
      ? "bg-green-100 text-green-800 border-green-300"
      : overall === "NOT_ELIGIBLE"
      ? "bg-red-100 text-red-800 border-red-300"
      : overall === "NEEDS_REVIEW"
      ? "bg-yellow-100 text-yellow-800 border-yellow-300"
      : "bg-gray-100 text-gray-600 border-gray-300";

  return (
    <div className="space-y-4">
      {/* Breadcrumb + Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
            <Link href="/" className="hover:text-primary-600 transition">
              Dashboard
            </Link>
            <span>/</span>
            <Link
              href={`/tenders/${tenderId}`}
              className="hover:text-primary-600 transition"
            >
              Tender
            </Link>
            <span>/</span>
            <span className="text-gray-700 font-medium">Evidence Viewer</span>
          </div>
          <h1 className="flex items-center gap-3">
            {bidder.name}
            <span
              className={`px-3 py-1 rounded-full text-xs font-bold border ${overallColor}`}
            >
              {overall.replace("_", " ")}
            </span>
          </h1>
          <div className="text-sm text-gray-500 mt-1">
            PAN: {bidder.pan || "N/A"} &nbsp;|&nbsp; GSTIN:{" "}
            {bidder.gstin || "N/A"}
            {firstDoc && (
              <>
                &nbsp;|&nbsp; Document: {firstDoc.filename}
                &nbsp;|&nbsp; OCR Confidence:{" "}
                {(firstDoc.ocr_confidence * 100).toFixed(0)}%
              </>
            )}
          </div>
        </div>

        <Link
          href={`/tenders/${tenderId}`}
          className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-100 transition"
        >
          ← Back to Tender
        </Link>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Evidence Viewer Component */}
      <EvidenceViewer
        pdfUrl={pdfUrl}
        verdicts={verdicts}
        bidderName={bidder.name}
      />
    </div>
  );
}
