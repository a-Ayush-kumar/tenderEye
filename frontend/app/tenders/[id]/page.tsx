"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import EvidenceViewer from "../../components/EvidenceViewer";

interface Tender {
  id: string;
  title: string;
  department: string;
  status: string;
  criteria: Array<{
    id: string;
    type: string;
    description: string;
    threshold?: number;
    time_window_years?: number;
  }>;
  criteria_locked: string | null;
}

interface Bidder {
  id: string;
  name: string;
  pan: string | null;
  gstin: string | null;
  status: string;
}

interface Verdict {
  criterion_id: string;
  criterion_type: string;
  verdict: string;
  reason: string | null;
  confidence: number;
  source_page?: number;
  verbatim_quote?: string;
  computed_value?: number | string;
}

interface EvaluationResult {
  bidder_id: string;
  bidder_name: string;
  overall: string;
  verdicts: Verdict[];
}

export default function TenderDetail() {
  const params = useParams();
  const tenderId = params.id as string;

  const [tender, setTender] = useState<Tender | null>(null);
  const [bidders, setBidders] = useState<Bidder[]>([]);
  const [results, setResults] = useState<EvaluationResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [vigilLoading, setVigilLoading] = useState(false);
  const [vigilAlerts, setVigilAlerts] = useState<any[]>([]);
  const [error, setError] = useState("");

  // Add bidder form
  const [showAddBidder, setShowAddBidder] = useState(false);
  const [newBidderName, setNewBidderName] = useState("");
  const [newBidderPan, setNewBidderPan] = useState("");
  const [newBidderGstin, setNewBidderGstin] = useState("");

  // Bidder document upload
  const [uploadingFor, setUploadingFor] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedBidderForUpload, setSelectedBidderForUpload] = useState<string | null>(null);
  const [expandedEvidence, setExpandedEvidence] = useState<string | null>(null);

  useEffect(() => {
    if (tenderId) fetchData();
  }, [tenderId]);

  async function fetchData() {
    setLoading(true);
    try {
      const [tenderRes, biddersRes] = await Promise.all([
        fetch(`/api/v1/tenders/${tenderId}`),
        fetch(`/api/v1/tenders/${tenderId}/bidders`),
      ]);
      if (tenderRes.ok) setTender(await tenderRes.json());
      if (biddersRes.ok) setBidders(await biddersRes.json());
    } catch {
      setError("Failed to load tender data");
    } finally {
      setLoading(false);
    }
  }

  async function lockCriteria() {
    try {
      const res = await fetch(`/api/v1/tenders/${tenderId}/lock`, { method: "POST" });
      if (res.ok) fetchData();
    } catch {
      setError("Failed to lock criteria");
    }
  }

  async function addBidder(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch(`/api/v1/tenders/${tenderId}/bidders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newBidderName,
          pan: newBidderPan || null,
          gstin: newBidderGstin || null,
        }),
      });
      if (res.ok) {
        setNewBidderName("");
        setNewBidderPan("");
        setNewBidderGstin("");
        setShowAddBidder(false);
        fetchData();
      } else {
        const err = await res.json();
        setError(err.detail || "Failed to add bidder");
      }
    } catch {
      setError("Failed to add bidder");
    }
  }

  function triggerUpload(bidderId: string) {
    setSelectedBidderForUpload(bidderId);
    // Small delay to ensure ref is set
    setTimeout(() => fileInputRef.current?.click(), 50);
  }

  async function handleBidderDocUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !selectedBidderForUpload) return;

    setUploadingFor(selectedBidderForUpload);
    setUploadStatus("Uploading & extracting text...");
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("doc_type", "AUDITED_ACCOUNTS");

      const res = await fetch(`/api/v1/bidders/${selectedBidderForUpload}/documents`, {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setUploadStatus(
          `✓ ${data.filename} — ${data.page_count} pages, ${data.text_length} chars extracted (${data.extraction_method})`
        );
        setTimeout(() => {
          setUploadStatus("");
          setUploadingFor(null);
        }, 4000);
      } else {
        const err = await res.json();
        setError(err.detail || "Upload failed");
        setUploadingFor(null);
        setUploadStatus("");
      }
    } catch {
      setError("Upload failed");
      setUploadingFor(null);
      setUploadStatus("");
    }

    // Reset file input
    if (fileInputRef.current) fileInputRef.current.value = "";
    setSelectedBidderForUpload(null);
  }

  async function runEvaluation() {
    setEvaluating(true);
    setError("");
    try {
      const res = await fetch(`/api/v1/evaluation/${tenderId}/run`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setResults(data.results);
      } else {
        const err = await res.json();
        setError(err.detail || "Evaluation failed");
      }
    } catch {
      setError("Evaluation request failed");
    } finally {
      setEvaluating(false);
    }
  }

  async function runVigilAnalysis() {
    setVigilLoading(true);
    setError("");
    try {
      const res = await fetch("/api/v1/vigil/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tender_id: tenderId }),
      });
      if (res.ok) {
        const data = await res.json();
        setVigilAlerts(data.alerts || []);
        alert(`VIGIL Analysis Complete\nRisk Score: ${data.risk_score}\nLevel: ${data.risk_level}\nAlerts: ${data.alert_count}`);
      } else {
        const err = await res.json();
        setError(err.detail || "VIGIL analysis failed");
      }
    } catch {
      setError("VIGIL request failed");
    } finally {
      setVigilLoading(false);
    }
  }

  function downloadReport() {
    window.open(`/api/v1/evaluation/${tenderId}/report`, "_blank");
  }

  if (loading) return <div className="text-center py-8">Loading...</div>;
  if (!tender) return <div className="text-center py-8 text-red-500">Tender not found</div>;

  return (
    <div>
      {/* Hidden file input for bidder document uploads */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={handleBidderDocUpload}
      />

      <div className="mb-6">
        <Link href="/tenders" className="text-sm text-gray-500 hover:text-primary-600">
          ← Back to Tenders
        </Link>
        <h1 className="mt-2">{tender.title}</h1>
        <p className="text-gray-600">
          {tender.department} | Status: {tender.status} | ID: <span className="font-mono text-xs">{tender.id}</span>
        </p>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
          <button onClick={() => setError("")} className="ml-2 text-sm underline">Dismiss</button>
        </div>
      )}

      {/* Criteria Section */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2>Evaluation Criteria</h2>
          {!tender.criteria_locked ? (
            <button
              onClick={lockCriteria}
              disabled={tender.criteria.length === 0}
              className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              🔒 Lock Criteria
            </button>
          ) : (
            <span className="px-3 py-1 bg-green-100 text-green-800 rounded text-sm font-medium">
              ✓ Locked
            </span>
          )}
        </div>

        {tender.criteria.length === 0 ? (
          <p className="text-gray-500">
            No criteria defined yet.{" "}
            <Link href={`/tenders/new`} className="text-primary-600 hover:underline">
              Upload a tender PDF
            </Link>{" "}
            to extract them automatically.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2 px-3">ID</th>
                <th className="text-left py-2 px-3">Type</th>
                <th className="text-left py-2 px-3">Description</th>
                <th className="text-left py-2 px-3">Threshold</th>
              </tr>
            </thead>
            <tbody>
              {tender.criteria.map((c) => (
                <tr key={c.id} className="border-b last:border-0">
                  <td className="py-2 px-3 font-mono text-xs">{c.id}</td>
                  <td className="py-2 px-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      c.type === "FINANCIAL" ? "bg-blue-100 text-blue-700" :
                      c.type === "COMPLIANCE" ? "bg-purple-100 text-purple-700" :
                      c.type === "TECHNICAL" ? "bg-orange-100 text-orange-700" :
                      "bg-gray-100 text-gray-700"
                    }`}>
                      {c.type}
                    </span>
                  </td>
                  <td className="py-2 px-3">{c.description}</td>
                  <td className="py-2 px-3">
                    {c.threshold ? `₹ ${c.threshold.toLocaleString("en-IN")}` : "N/A"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Bidders Section */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2>Bidders ({bidders.length})</h2>
          <button
            onClick={() => setShowAddBidder(!showAddBidder)}
            className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 transition"
          >
            {showAddBidder ? "Cancel" : "+ Add Bidder"}
          </button>
        </div>

        {/* Add Bidder Form */}
        {showAddBidder && (
          <form onSubmit={addBidder} className="mb-4 p-4 bg-gray-50 rounded-lg border">
            <div className="grid grid-cols-3 gap-3 mb-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Company Name *</label>
                <input
                  required
                  value={newBidderName}
                  onChange={(e) => setNewBidderName(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none"
                  placeholder="M/S Company Ltd"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">PAN</label>
                <input
                  value={newBidderPan}
                  onChange={(e) => setNewBidderPan(e.target.value.toUpperCase())}
                  maxLength={10}
                  className="w-full px-3 py-2 border rounded-lg text-sm font-mono focus:ring-2 focus:ring-primary-500 outline-none"
                  placeholder="ABCDE1234F"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">GSTIN</label>
                <input
                  value={newBidderGstin}
                  onChange={(e) => setNewBidderGstin(e.target.value.toUpperCase())}
                  maxLength={15}
                  className="w-full px-3 py-2 border rounded-lg text-sm font-mono focus:ring-2 focus:ring-primary-500 outline-none"
                  placeholder="07ABCDE1234F1Z5"
                />
              </div>
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition text-sm"
            >
              Register Bidder
            </button>
          </form>
        )}

        {bidders.length === 0 ? (
          <p className="text-gray-500">No bidders registered yet.</p>
        ) : (
          <div className="divide-y">
            {bidders.map((bidder) => (
              <div key={bidder.id} className="py-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium">{bidder.name}</div>
                    <div className="text-sm text-gray-500">
                      PAN: <span className="font-mono">{bidder.pan || "N/A"}</span> | GSTIN: <span className="font-mono">{bidder.gstin || "N/A"}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Upload Document Button */}
                    <button
                      onClick={() => triggerUpload(bidder.id)}
                      disabled={uploadingFor === bidder.id}
                      className="px-3 py-1 text-xs border border-dashed rounded-lg hover:bg-blue-50 hover:border-blue-300 transition text-gray-600 hover:text-blue-700 disabled:opacity-50"
                    >
                      {uploadingFor === bidder.id ? (
                        <span className="flex items-center gap-1">
                          <span className="animate-spin inline-block w-3 h-3 border-b-2 border-primary-600 rounded-full" />
                          Processing...
                        </span>
                      ) : (
                        "📄 Upload PDF"
                      )}
                    </button>
                    <span className="px-2 py-0.5 bg-gray-100 rounded text-xs">
                      {bidder.status}
                    </span>
                    <Link
                      href={`/tenders/${tenderId}/bidders/${bidder.id}`}
                      className="px-3 py-1 text-xs border rounded-lg hover:bg-gray-100 transition text-primary-700"
                    >
                      View Evidence
                    </Link>
                  </div>
                </div>
                {/* Upload status feedback */}
                {uploadingFor === bidder.id && uploadStatus && (
                  <div className="mt-2 text-xs text-green-700 bg-green-50 px-3 py-1.5 rounded">
                    {uploadStatus}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Evaluation Section */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2>Evaluation</h2>
          <div className="flex gap-2">
            <button
              onClick={runEvaluation}
              disabled={!tender.criteria_locked || evaluating || bidders.length === 0}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:opacity-50 disabled:cursor-not-allowed text-sm"
            >
              {evaluating ? (
                <span className="flex items-center gap-2">
                  <span className="animate-spin inline-block w-4 h-4 border-b-2 border-white rounded-full" />
                  Running...
                </span>
              ) : (
                "▶ Run Evaluation"
              )}
            </button>
            <button
              onClick={downloadReport}
              disabled={results.length === 0}
              className="px-4 py-2 border rounded-lg hover:bg-gray-100 transition disabled:opacity-50 text-sm"
            >
              📄 Download Report
            </button>
          </div>
        </div>

        {!tender.criteria_locked && (
          <p className="text-sm text-yellow-600 mb-4">
            ⚠ Lock criteria before running evaluation.
          </p>
        )}

        {results.length === 0 && !evaluating && (
          <p className="text-gray-500">No evaluation results yet.</p>
        )}

        {results.length > 0 && (
          <div className="space-y-4">
            {results.map((result) => (
              <div
                key={result.bidder_id}
                className={`border rounded-lg overflow-hidden ${
                  result.overall === "ELIGIBLE"
                    ? "border-green-300"
                    : result.overall === "NOT_ELIGIBLE"
                    ? "border-red-300"
                    : result.overall === "COLLUSION_RISK"
                    ? "border-purple-300"
                    : "border-yellow-300"
                }`}
              >
                <div
                  className={`p-4 cursor-pointer transition-colors ${
                    result.overall === "ELIGIBLE"
                      ? "bg-green-50 hover:bg-green-100"
                      : result.overall === "NOT_ELIGIBLE"
                      ? "bg-red-50 hover:bg-red-100"
                      : result.overall === "COLLUSION_RISK"
                      ? "bg-purple-50 hover:bg-purple-100"
                      : "bg-yellow-50 hover:bg-yellow-100"
                  }`}
                  onClick={() => setExpandedEvidence(
                    expandedEvidence === result.bidder_id ? null : result.bidder_id
                  )}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{result.bidder_name}</span>
                      <button className="text-xs text-primary-600 hover:underline">
                        {expandedEvidence === result.bidder_id ? "▼ Hide Evidence" : "▶ View Evidence"}
                      </button>
                    </div>
                    <span
                      className={`px-3 py-1 rounded text-sm font-bold ${
                        result.overall === "ELIGIBLE"
                          ? "bg-green-200 text-green-800"
                          : result.overall === "NOT_ELIGIBLE"
                          ? "bg-red-200 text-red-800"
                          : result.overall === "COLLUSION_RISK"
                          ? "bg-purple-200 text-purple-800"
                          : "bg-yellow-200 text-yellow-800"
                      }`}
                    >
                      {result.overall.replace(/_/g, " ")}
                    </span>
                  </div>
                  <div className="space-y-1">
                    {result.verdicts.map((v) => (
                      <div key={v.criterion_id} className="text-sm">
                        <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium mr-2 ${
                          v.criterion_type === "FINANCIAL" ? "bg-blue-100 text-blue-700" :
                          v.criterion_type === "COMPLIANCE" ? "bg-purple-100 text-purple-700" :
                          v.criterion_type === "TECHNICAL" ? "bg-orange-100 text-orange-700" :
                          v.criterion_type === "DOCUMENTARY" ? "bg-teal-100 text-teal-700" :
                          "bg-gray-100 text-gray-700"
                        }`}>
                          {v.criterion_type}
                        </span>
                        <span
                          className={`font-bold ${
                            v.verdict === "ELIGIBLE"
                              ? "text-green-700"
                              : v.verdict === "NOT_ELIGIBLE"
                              ? "text-red-700"
                              : "text-yellow-700"
                          }`}
                        >
                          {v.verdict.replace("_", " ")}
                        </span>
                        {v.reason && (
                          <span className="text-gray-600 ml-2">— {v.reason.substring(0, 60)}{v.reason.length > 60 ? "..." : ""}</span>
                        )}
                        <span className="text-gray-400 ml-2">
                          ({(v.confidence * 100).toFixed(0)}%)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Expanded Evidence Viewer */}
                {expandedEvidence === result.bidder_id && (
                  <div className="border-t border-gray-200">
                    <EvidenceViewer
                      verdicts={result.verdicts}
                      bidderName={result.bidder_name}
                      overall={result.overall}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* VIGIL Section */}
      <div className="bg-white rounded-lg shadow p-6 mb-6 border-l-4 border-purple-500">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="flex items-center gap-2">
              🛡️ VIGIL Collusion Detection
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              Run automated analysis to detect bid rigging, cover pricing, and collusion patterns
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={runVigilAnalysis}
              disabled={vigilLoading || bidders.length === 0}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition disabled:opacity-50 disabled:cursor-not-allowed text-sm"
            >
              {vigilLoading ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Analyzing...
                </span>
              ) : (
                "🔍 Run VIGIL Analysis"
              )}
            </button>
            <Link
              href="/vigil"
              className="px-4 py-2 border rounded-lg hover:bg-gray-100 transition text-sm"
            >
              View Dashboard
            </Link>
          </div>
        </div>

        {vigilAlerts.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-semibold mb-2">Detected Alerts:</h3>
            <div className="space-y-2">
              {vigilAlerts.map((alert, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-lg border-l-4 ${
                    alert.confidence > 0.8
                      ? "bg-red-50 border-red-500"
                      : alert.confidence > 0.5
                      ? "bg-yellow-50 border-yellow-500"
                      : "bg-blue-50 border-blue-500"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{alert.type?.replace(/_/g, " ")}</span>
                    <span className="text-sm text-gray-600">
                      Confidence: {(alert.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1">{alert.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {vigilAlerts.length === 0 && !vigilLoading && (
          <p className="text-gray-500 text-sm">
            No VIGIL analysis run yet. Click &quot;Run VIGIL Analysis&quot; to check for collusion patterns.
          </p>
        )}
      </div>
    </div>
  );
}
