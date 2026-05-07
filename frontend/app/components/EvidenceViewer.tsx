"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Configure PDF.js worker — served from /public so the system is fully
// self-hosted (no CDN). The worker file is copied during dev/build setup
// (see frontend/public/pdf.worker.min.mjs).
if (typeof window !== "undefined") {
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
}

interface BBox {
  // Normalized [0..1] coordinates relative to the page (x, y from top-left, w, h)
  x: number;
  y: number;
  w: number;
  h: number;
}

interface Verdict {
  criterion_id: string;
  criterion_type: string;
  verdict: string;
  reason: string | null;
  confidence: number;
  source_page?: number;
  source_bbox?: BBox | null;
  verbatim_quote?: string | null;
  computed_value?: unknown;
}

interface EvidenceViewerProps {
  verdicts: Verdict[];
  bidderName?: string;
  overall?: string;
  /** PDF URL for the bidder document. When provided, the right pane renders the PDF
      and auto-jumps to the verdict's source_page with highlight. */
  pdfUrl?: string | null;
}

const VERDICT_COLORS: Record<string, string> = {
  ELIGIBLE: "bg-green-100 text-green-800 border-green-200",
  NOT_ELIGIBLE: "bg-red-100 text-red-800 border-red-200",
  NEEDS_REVIEW: "bg-amber-100 text-amber-800 border-amber-200",
};

const TYPE_ICONS: Record<string, string> = {
  FINANCIAL: "",
  COMPLIANCE: "",
  TECHNICAL: "",
  DOCUMENTARY: "",
};

/** Escape HTML special characters so injected highlight markup is safe. */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export default function EvidenceViewer({
  verdicts: rawVerdicts,
  bidderName,
  overall,
  pdfUrl,
}: EvidenceViewerProps) {
  // Defend against backend duplicates: keep only the latest verdict per
  // criterion_id (the backend currently appends a new row per re-evaluation).
  // This also eliminates React's "duplicate key" warning.
  const verdicts = useMemo<Verdict[]>(() => {
    const map = new Map<string, Verdict>();
    for (const v of rawVerdicts) {
      map.set(v.criterion_id, v); // last write wins → preserves latest order
    }
    return Array.from(map.values());
  }, [rawVerdicts]);

  const [selectedCriterion, setSelectedCriterion] = useState<string | null>(
    verdicts[0]?.criterion_id ?? null,
  );
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageWidth, setPageWidth] = useState<number>(560);
  const [pdfError, setPdfError] = useState<string | null>(null);

  const selectedVerdict = verdicts.find(
    (v) => v.criterion_id === selectedCriterion,
  );

  // Auto-jump to the verdict's source page when selection changes.
  useEffect(() => {
    if (selectedVerdict?.source_page && numPages > 0) {
      const target = Math.min(
        Math.max(1, selectedVerdict.source_page),
        numPages,
      );
      setCurrentPage(target);
    }
  }, [selectedVerdict, numPages]);

  // Build the search tokens used for in-page text highlighting.
  // We strip down to a 4-12 word window from verbatim_quote — long
  // quotes rarely match exactly across PDF.js's text-layer tokenization.
  const highlightTokens = useMemo<string[]>(() => {
    if (!selectedVerdict?.verbatim_quote) return [];
    const cleaned = selectedVerdict.verbatim_quote
      .replace(/\s+/g, " ")
      .trim();
    // Take first 8 words and last 8 words as anchor phrases
    const words = cleaned.split(" ").filter((w) => w.length > 1);
    if (words.length === 0) return [];
    if (words.length <= 8) return [cleaned];
    return [
      words.slice(0, 8).join(" "),
      words.slice(-8).join(" "),
    ];
  }, [selectedVerdict?.verbatim_quote]);

  // PDF.js text layer renders span-per-token; we wrap matching tokens
  // with a yellow highlight by returning HTML for matched substrings.
  const customTextRenderer = useCallback(
    ({ str }: { str: string }) => {
      if (!str || highlightTokens.length === 0) return str;
      const lower = str.toLowerCase();
      for (const token of highlightTokens) {
        const t = token.toLowerCase();
        const idx = lower.indexOf(t);
        if (idx === -1) continue;
        const before = str.slice(0, idx);
        const match = str.slice(idx, idx + token.length);
        const after = str.slice(idx + token.length);
        // Returning a string with HTML — react-pdf's textRenderer accepts this.
        return `${escapeHtml(before)}<mark class="vigil-evidence-highlight">${escapeHtml(match)}</mark>${escapeHtml(after)}`;
      }
      return str;
    },
    [highlightTokens],
  );

  // Compute container width responsively (desktop: 560, mobile: card width).
  useEffect(() => {
    function resize() {
      if (typeof window === "undefined") return;
      const w = Math.min(720, window.innerWidth - 64);
      setPageWidth(w);
    }
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  return (
    <div className="bg-white rounded-lg shadow border border-gray-200">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">Evidence Viewer</h3>
          {bidderName && (
            <p className="text-sm text-gray-500">{bidderName}</p>
          )}
        </div>
        {overall && (
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium border ${
              VERDICT_COLORS[overall] || "bg-gray-100 text-gray-800"
            }`}
          >
            {overall.replace("_", " ")}
          </span>
        )}
      </div>

      <div
        className={`grid grid-cols-1 ${
          pdfUrl ? "lg:grid-cols-3" : "lg:grid-cols-2"
        } divide-y lg:divide-y-0 lg:divide-x divide-gray-200`}
      >
        {/* Verdict List */}
        <div className="p-4 space-y-2 max-h-96 overflow-y-auto">
          <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
            Criterion Verdicts
          </h4>
          {verdicts.map((v) => (
            <button
              key={v.criterion_id}
              onClick={() => setSelectedCriterion(v.criterion_id)}
              className={`w-full text-left p-3 rounded-lg border transition-all ${
                selectedCriterion === v.criterion_id
                  ? "border-blue-500 bg-blue-50 shadow-sm"
                  : "border-gray-100 hover:border-gray-300 hover:bg-gray-50"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-gray-500">
                  {v.criterion_type}
                </span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${VERDICT_COLORS[v.verdict] || ""}`}>
                  {v.verdict.replace("_", " ")}
                </span>
              </div>
              <p className="text-sm text-gray-700 font-medium">
                {v.reason?.substring(0, 80)}{v.reason && v.reason.length > 80 ? "..." : ""}
              </p>
              <div className="mt-1 flex items-center gap-2">
                <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                  <div
                    className={`h-1.5 rounded-full ${
                      v.confidence >= 0.8 ? "bg-green-500" : v.confidence >= 0.6 ? "bg-amber-500" : "bg-red-500"
                    }`}
                    style={{ width: `${(v.confidence || 0.5) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-gray-500">
                  {(v.confidence * 100).toFixed(0)}%
                </span>
              </div>
            </button>
          ))}
        </div>

        {/* Evidence Detail */}
        <div className="p-4">
          {selectedVerdict ? (
            <div className="space-y-4">
              <div>
                <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                  {selectedVerdict.criterion_type} — {selectedVerdict.criterion_id}
                </h4>
                <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium border ${VERDICT_COLORS[selectedVerdict.verdict] || ""}`}>
                  {selectedVerdict.verdict.replace("_", " ")}
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-sm text-gray-700 leading-relaxed">
                  {selectedVerdict.reason}
                </p>
              </div>

              {selectedVerdict.verbatim_quote && (
                <div>
                  <h5 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                    Source Evidence
                  </h5>
                  <div className="bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded-r-lg">
                    <p className="text-sm text-gray-700 font-mono leading-relaxed whitespace-pre-wrap">
                      {selectedVerdict.verbatim_quote}
                    </p>
                    {selectedVerdict.source_page && (
                      <p className="text-xs text-gray-500 mt-2">
                        Page {selectedVerdict.source_page}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {selectedVerdict.computed_value !== undefined && (
                <div>
                  <h5 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                    Computed Value
                  </h5>
                  <div className="bg-blue-50 rounded-lg p-3 font-mono text-sm text-blue-900">
                    {typeof selectedVerdict.computed_value === "number"
                      ? selectedVerdict.computed_value >= 1000000
                        ? `Rs. ${(selectedVerdict.computed_value / 10000000).toFixed(2)} Crore`
                        : selectedVerdict.computed_value
                      : String(selectedVerdict.computed_value)}
                  </div>
                </div>
              )}

              <div className="flex items-center gap-4 text-xs text-gray-500 pt-2 border-t border-gray-200">
                <div>
                  Confidence: <span className="font-medium">{(selectedVerdict.confidence * 100).toFixed(0)}%</span>
                </div>
                {selectedVerdict.source_page && (
                  <div>
                    Source Page: <span className="font-medium">{selectedVerdict.source_page}</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <svg className="w-12 h-12 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="text-sm">Click a verdict to view evidence</p>
            </div>
          )}
        </div>

        {/* PDF Viewer Pane (only when pdfUrl provided) */}
        {pdfUrl && (
          <div className="p-4 bg-gray-50">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                Source Document
              </h4>
              {numPages > 0 && (
                <div className="flex items-center gap-2 text-xs text-gray-600">
                  <button
                    type="button"
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={currentPage <= 1}
                    className="px-2 py-1 border rounded hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed"
                    aria-label="Previous page"
                  >
                    ←
                  </button>
                  <span className="font-mono">
                    {currentPage} / {numPages}
                  </span>
                  <button
                    type="button"
                    onClick={() =>
                      setCurrentPage((p) => Math.min(numPages, p + 1))
                    }
                    disabled={currentPage >= numPages}
                    className="px-2 py-1 border rounded hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed"
                    aria-label="Next page"
                  >
                    →
                  </button>
                </div>
              )}
            </div>

            {pdfError && (
              <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2 mb-2">
                {pdfError}
              </div>
            )}

            <div className="relative inline-block bg-white shadow border border-gray-200 rounded overflow-hidden max-w-full">
              <Document
                file={pdfUrl}
                onLoadSuccess={({ numPages: n }) => {
                  setNumPages(n);
                  setPdfError(null);
                }}
                onLoadError={(err) => {
                  console.error("PDF load error", err);
                  setPdfError("Could not load PDF document.");
                }}
                loading={
                  <div className="p-8 text-sm text-gray-400">Loading PDF…</div>
                }
                error={
                  <div className="p-8 text-sm text-red-500">
                    Failed to load PDF
                  </div>
                }
              >
                <div className="relative">
                  <Page
                    pageNumber={currentPage}
                    width={pageWidth}
                    renderAnnotationLayer={false}
                    customTextRenderer={customTextRenderer}
                  />
                  {/* Optional bbox overlay (normalized coords) */}
                  {selectedVerdict?.source_bbox &&
                    selectedVerdict.source_page === currentPage && (
                      <div
                        className="absolute pointer-events-none border-2 border-amber-500 bg-amber-300/25 rounded-sm"
                        style={{
                          left: `${selectedVerdict.source_bbox.x * 100}%`,
                          top: `${selectedVerdict.source_bbox.y * 100}%`,
                          width: `${selectedVerdict.source_bbox.w * 100}%`,
                          height: `${selectedVerdict.source_bbox.h * 100}%`,
                        }}
                        aria-label="Evidence bounding box"
                      />
                    )}
                </div>
              </Document>
            </div>

            <p className="mt-2 text-[11px] text-gray-500">
              Auto-jumps to the verdict’s source page. Highlighted text marks
              the verbatim quote extracted by the matcher.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
