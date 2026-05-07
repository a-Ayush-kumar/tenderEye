"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

interface Criterion {
  id: string;
  type: string;
  description: string;
  threshold: number | null;
  currency: string | null;
  time_window_years: number | null;
}

export default function NewTenderPage() {
  const router = useRouter();

  // Step 1: Basic info
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("");

  // Step 2: PDF upload & extraction
  const [tenderId, setTenderId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [pdfName, setPdfName] = useState("");

  // Step 3: Edit & lock
  const [locking, setLocking] = useState(false);
  const [locked, setLocked] = useState(false);

  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ─────────────────────────────────────────────
  // Step 1: Create the tender record
  // ─────────────────────────────────────────────
  async function createTender(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch("/api/v1/tenders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, department }),
      });
      if (!res.ok) throw new Error("Failed to create tender");
      const data = await res.json();
      setTenderId(data.id);
    } catch (err) {
      setError("Failed to create tender. Is the backend running?");
    }
  }

  // ─────────────────────────────────────────────
  // Step 2: Upload PDF → extract text → LLM criteria
  // ─────────────────────────────────────────────
  async function uploadPdf(file: File) {
    if (!tenderId) return;
    setUploading(true);
    setUploadProgress("Uploading PDF...");
    setError("");
    setPdfName(file.name);

    try {
      const formData = new FormData();
      formData.append("file", file);

      setUploadProgress("Extracting text & running AI criteria detection...");

      const res = await fetch(`/api/v1/tenders/${tenderId}/documents`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload failed");
      }

      const data = await res.json();
      setUploadProgress("");

      if (data.criteria && data.criteria.length > 0) {
        setCriteria(data.criteria);
      } else {
        setError(
          "No criteria could be extracted from this document. You can add them manually below."
        );
        setCriteria([]);
      }
    } catch (err: string | Error) {
      setError(err.message || "Upload failed");
      setUploadProgress("");
    } finally {
      setUploading(false);
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) uploadPdf(file);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && file.type === "application/pdf") {
      uploadPdf(file);
    } else {
      setError("Please drop a PDF file");
    }
  }

  // ─────────────────────────────────────────────
  // Step 3: Edit criteria inline
  // ─────────────────────────────────────────────
  function updateCriterion(index: number, field: string, value: string | number | null) {
    setCriteria((prev) =>
      prev.map((c, i) => (i === index ? { ...c, [field]: value } : c))
    );
  }

  function removeCriterion(index: number) {
    setCriteria((prev) => prev.filter((_, i) => i !== index));
  }

  function addCriterion() {
    const nextId = `C-${String(criteria.length + 1).padStart(2, "0")}`;
    setCriteria((prev) => [
      ...prev,
      {
        id: nextId,
        type: "FINANCIAL",
        description: "",
        threshold: null,
        currency: "INR",
        time_window_years: null,
      },
    ]);
  }

  // ─────────────────────────────────────────────
  // Step 4: Save criteria & lock
  // ─────────────────────────────────────────────
  async function saveCriteria() {
    if (!tenderId) return;
    setError("");
    try {
      const res = await fetch(`/api/v1/tenders/${tenderId}/criteria`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(criteria),
      });
      if (!res.ok) throw new Error("Failed to save criteria");
    } catch (err) {
      setError("Failed to save criteria");
    }
  }

  async function lockAndFinish() {
    if (!tenderId) return;
    setLocking(true);
    setError("");
    try {
      // Save first
      await saveCriteria();

      // Then lock
      const res = await fetch(`/api/v1/tenders/${tenderId}/lock`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Lock failed");
      }
      setLocked(true);
      // Redirect to tender detail after short delay
      setTimeout(() => router.push(`/tenders/${tenderId}`), 1500);
    } catch (err: identifier) {
      setError(err.message || "Failed to lock criteria");
    } finally {
      setLocking(false);
    }
  }

  // ─────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────
  const currentStep = locked ? 4 : criteria.length > 0 ? 3 : tenderId ? 2 : 1;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <Link
          href="/"
          className="text-sm text-gray-500 hover:text-primary-600"
        >
          ← Back to Dashboard
        </Link>
        <h1 className="mt-2">Create New Tender</h1>
        <p className="text-gray-500 text-sm mt-1">
          Upload a tender PDF to automatically extract eligibility criteria
        </p>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center gap-0 mb-8">
        {[
          "Basic Info",
          "Upload PDF",
          "Review Criteria",
          "Locked",
        ].map((label, i) => {
          const step = i + 1;
          const active = currentStep === step;
          const done = currentStep > step;
          return (
            <div key={label} className="flex items-center flex-1">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all ${
                  done
                    ? "bg-green-500 text-white"
                    : active
                    ? "bg-primary-600 text-white ring-4 ring-primary-100"
                    : "bg-gray-200 text-gray-500"
                }`}
              >
                {done ? "✓" : step}
              </div>
              <span
                className={`ml-2 text-sm ${
                  active ? "text-gray-900 font-medium" : "text-gray-400"
                }`}
              >
                {label}
              </span>
              {i < 3 && (
                <div
                  className={`flex-1 h-0.5 mx-3 ${
                    done ? "bg-green-400" : "bg-gray-200"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
          <button
            onClick={() => setError("")}
            className="ml-2 underline text-xs"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Step 1: Basic Info */}
      {!tenderId && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="mb-4">Step 1: Tender Information</h2>
          <form onSubmit={createTender} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Tender Title
              </label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                placeholder="e.g., CRPF Construction Tender 2026/0847"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Department
              </label>
              <input
                type="text"
                required
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                placeholder="e.g., CRPF, PWD, CPWD"
              />
            </div>
            <button
              type="submit"
              className="px-6 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition font-medium"
            >
              Continue →
            </button>
          </form>
        </div>
      )}

      {/* Step 2: Upload PDF */}
      {tenderId && criteria.length === 0 && !locked && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="mb-4">Step 2: Upload Tender Document</h2>
          <p className="text-sm text-gray-500 mb-4">
            Drop or select the tender PDF. The system will extract text and use
            AI to identify eligibility criteria automatically.
          </p>

          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => !uploading && fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all ${
              uploading
                ? "border-primary-400 bg-primary-50"
                : "border-gray-300 hover:border-primary-400 hover:bg-gray-50"
            }`}
          >
            {uploading ? (
              <div className="space-y-3">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600 mx-auto" />
                <p className="text-primary-700 font-medium">{uploadProgress}</p>
                <p className="text-xs text-gray-400">
                  This may take a moment if Ollama is processing...
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <svg
                  className="w-12 h-12 text-gray-400 mx-auto"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
                <p className="text-gray-600 font-medium">
                  Drop your tender PDF here
                </p>
                <p className="text-xs text-gray-400">or click to browse</p>
              </div>
            )}
          </div>

          <input
          title="Upload Tender PDF"
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={handleFileSelect}
          />

          {pdfName && !uploading && (
            <p className="text-sm text-gray-500 mt-3">
              Uploaded: <span className="font-medium">{pdfName}</span>
            </p>
          )}
        </div>
      )}

      {/* Step 3: Review & Edit Criteria */}
      {criteria.length > 0 && !locked && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2>Step 3: Review Extracted Criteria</h2>
              <p className="text-sm text-gray-500 mt-1">
                AI extracted {criteria.length} criteria from your document. Edit
                as needed, then lock.
              </p>
            </div>
            <button
              onClick={addCriterion}
              className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 transition"
            >
              + Add Criterion
            </button>
          </div>

          <div className="space-y-4">
            {criteria.map((c, i) => (
              <div
                key={i}
                className="border rounded-lg p-4 bg-gray-50 relative group"
              >
                <button
                  onClick={() => removeCriterion(i)}
                  className="absolute top-2 right-2 text-red-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition text-sm"
                  title="Remove"
                >
                  ✕
                </button>

                <div className="grid grid-cols-12 gap-3">
                  {/* ID */}
                  <div className="col-span-2">
                    <label className="block text-xs text-gray-500 mb-1">
                      ID
                    </label>
                    <input
                        type="text"
                        title="Criterion ID"
                      value={c.id}
                      onChange={(e) => updateCriterion(i, "id", e.target.value)}
                      className="w-full px-2 py-1.5 border rounded text-sm font-mono"
                    />
                  </div>

                  {/* Type */}
                  <div className="col-span-3">
                    <label className="block text-xs text-gray-500 mb-1">
                      Type
                    </label>
                    <select
                    title="Criterion Type"
                      value={c.type}
                      onChange={(e) =>
                        updateCriterion(i, "type", e.target.value)
                      }
                      className="w-full px-2 py-1.5 border rounded text-sm bg-white"
                    >
                      <option value="FINANCIAL">FINANCIAL</option>
                      <option value="TECHNICAL">TECHNICAL</option>
                      <option value="COMPLIANCE">COMPLIANCE</option>
                      <option value="DOCUMENTARY">DOCUMENTARY</option>
                    </select>
                  </div>

                  {/* Threshold */}
                  <div className="col-span-3">
                    <label className="block text-xs text-gray-500 mb-1">
                      Threshold (INR)
                    </label>
                    <input
                      type="number"
                      value={c.threshold ?? ""}
                      onChange={(e) =>
                        updateCriterion(
                          i,
                          "threshold",
                          e.target.value ? Number(e.target.value) : null
                        )
                      }
                      className="w-full px-2 py-1.5 border rounded text-sm"
                      placeholder="e.g., 50000000"
                    />
                  </div>

                  {/* Time window */}
                  <div className="col-span-4">
                    <label className="block text-xs text-gray-500 mb-1">
                      Time Window (years)
                    </label>
                    <input
                      type="number"
                      value={c.time_window_years ?? ""}
                      onChange={(e) =>
                        updateCriterion(
                          i,
                          "time_window_years",
                          e.target.value ? Number(e.target.value) : null
                        )
                      }
                      className="w-full px-2 py-1.5 border rounded text-sm"
                      placeholder="e.g., 3"
                    />
                  </div>

                  {/* Description (full width) */}
                  <div className="col-span-12">
                    <label className="block text-xs text-gray-500 mb-1">
                      Description
                    </label>
                    <input
                      value={c.description}
                      onChange={(e) =>
                        updateCriterion(i, "description", e.target.value)
                      }
                      className="w-full px-2 py-1.5 border rounded text-sm"
                      placeholder="Describe the eligibility criterion..."
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="flex gap-3 mt-6">
            <button
              onClick={saveCriteria}
              className="px-5 py-2.5 border rounded-lg hover:bg-gray-50 transition text-sm font-medium"
            >
              Save Draft
            </button>
            <button
              onClick={lockAndFinish}
              disabled={locking || criteria.length === 0}
              className="px-5 py-2.5 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {locking ? "Locking..." : "🔒 Lock Criteria & Publish"}
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Done */}
      {locked && (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl">✓</span>
          </div>
          <h2 className="mb-2">Tender Published Successfully!</h2>
          <p className="text-gray-500 text-sm mb-4">
            Criteria have been locked. Redirecting to tender details...
          </p>
          <Link
            href={`/tenders/${tenderId}`}
            className="text-primary-600 hover:underline text-sm"
          >
            Go to Tender →
          </Link>
        </div>
      )}
    </div>
  );
}
