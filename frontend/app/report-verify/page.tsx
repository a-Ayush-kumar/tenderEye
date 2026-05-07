"use client";

import { useState } from "react";

export default function ReportVerifyPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<string>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function verifyReport() {
    if (!file) {
      setError("Please select a PDF report file");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/v1/audit/verify-report", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      if (res.ok) {
        setResult(data);
      } else {
        setError(data.detail || "Verification failed");
      }
    } catch {
      setError("Network error. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">🔏 Report Verification</h1>
      <p className="text-gray-500 mb-6">
        Upload a VIGIL evaluation report PDF to verify its hash chain integrity.
      </p>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Upload Report PDF
        </label>
        <input
          label="Upload Report PDF"
          title="Upload Report PDF"
          type="file"
          accept=".pdf"
          onChange={(e) => {
            setFile(e.target.files?.[0] || null);
            setResult(null);
            setError("");
          }}
          className="w-full mb-4 text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
        />

        <button
          onClick={verifyReport}
          disabled={loading || !file}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:opacity-50 font-medium"
        >
          {loading ? "Verifying..." : "Verify Integrity"}
        </button>

        {error && (
          <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm border border-red-200">
            {error}
          </div>
        )}
      </div>

      {result && (
        <div
          className={`rounded-lg shadow p-6 border-l-4 ${result.integrity_valid ? "bg-green-50 border-green-500" : "bg-yellow-50 border-yellow-500"}`}
        >
          <div className="flex items-center gap-2 mb-3">
            <span className="text-2xl">
              {result.integrity_valid ? "✅" : "⚠️"}
            </span>
            <h2
              className={`text-lg font-bold ${result.integrity_valid ? "text-green-800" : "text-yellow-800"}`}
            >
              {result.integrity_valid
                ? "Integrity Verified"
                : "Verification Issue"}
            </h2>
          </div>

          {result.integrity_valid && result.report_hash && (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between border-b pb-2">
                <span className="text-gray-600">Report Hash (SHA-256)</span>
                <span className="font-mono text-xs max-w-[200px] truncate">
                  {result.report_hash}
                </span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span className="text-gray-600">Tender ID</span>
                <span className="font-mono">{result.tender_id || "N/A"}</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span className="text-gray-600">Evaluated At</span>
                <span>{result.evaluated_at || "N/A"}</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span className="text-gray-600">Chain Valid</span>
                <span
                  className={
                    result.chain_valid
                      ? "text-green-700 font-bold"
                      : "text-red-700 font-bold"
                  }
                >
                  {result.chain_valid ? "Yes" : "No"}
                </span>
              </div>
              <div className="pt-2">
                <span className="text-gray-600">
                  This report is cryptographically sealed and tamper-evident.
                </span>
              </div>
            </div>
          )}

          {!result.integrity_valid && (
            <p className="text-sm text-yellow-700">
              The report could not be verified. It may have been modified or is
              not a genuine VIGIL report.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
