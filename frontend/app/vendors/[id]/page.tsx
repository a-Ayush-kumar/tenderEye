"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

interface Vendor {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  pan: string | null;
  gstin: string | null;
  kyc_status: string;
  kyc_verified_at: string | null;
  dsc_bound: string | null;
  bank_account: string | null;
  bank_ifsc: string | null;
  created_at: string;
}

interface KYCStatus {
  vendor_id: string;
  kyc_status: string;
  aadhaar_verified: boolean;
  pan_verified: boolean;
  gstin_verified: boolean;
  bank_verified: boolean;
  dsc_bound: boolean;
  progress_percent: number;
}

interface Tender {
  id: string;
  title: string;
  department: string;
  status: string;
  closing_date: string | null;
}

export default function VendorDetail() {
  const params = useParams();
  const router = useRouter();
  const vendorId = params.id as string;

  const [vendor, setVendor] = useState<Vendor | null>(null);
  const [kycStatus, setKycStatus] = useState<KYCStatus | null>(null);
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [selectedTender, setSelectedTender] = useState<string>("");
  const [bidAmount, setBidAmount] = useState<string>("");
  const [bidFile, setBidFile] = useState<File | null>(null);
  const [fileHash, setFileHash] = useState<string>("");
  const [submitResult, setSubmitResult] = useState<any>(null);

  useEffect(() => {
    if (vendorId) {
      fetchVendorData();
      fetchTenders();
    }
  }, [vendorId]);

  async function fetchVendorData() {
    try {
      // Fetch vendor details
      const vendorRes = await fetch(`/api/v1/vendors/${vendorId}`);
      if (vendorRes.ok) {
        setVendor(await vendorRes.json());
      }

      // Fetch KYC status
      const kycRes = await fetch(`/api/v1/vendors/${vendorId}/kyc-status`);
      if (kycRes.ok) {
        setKycStatus(await kycRes.json());
      }
    } catch (err) {
      console.error("Failed to fetch vendor data", err);
    } finally {
      setLoading(false);
    }
  }

  async function fetchTenders() {
    try {
      const res = await fetch("/api/v1/tenders/");
      if (res.ok) {
        const allTenders = await res.json();
        // Only show published/open tenders
        setTenders(
          allTenders.filter(
            (t: Tender) => t.status === "PUBLISHED" || t.status === "OPEN"
          )
        );
      }
    } catch (err) {
      console.error("Failed to fetch tenders", err);
    }
  }

  // Compute SHA-256 hash of file
  async function computeFileHash(file: File): Promise<string> {
    const buffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setBidFile(file);
      const hash = await computeFileHash(file);
      setFileHash(hash);
    }
  };

  const submitBid = async () => {
    if (!selectedTender || !bidFile || !fileHash) {
      alert("Please select tender, file, and ensure hash is computed");
      return;
    }

    setSubmitting(true);
    setSubmitResult(null);

    try {
      const formData = new FormData();
      formData.append("tender_id", selectedTender);
      formData.append("vendor_id", vendorId);
      formData.append("file_hash", fileHash);
      formData.append("bid_amount", bidAmount);
      formData.append("bid_file", bidFile);

      const res = await fetch("/api/v1/bids/submit", {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        const result = await res.json();
        setSubmitResult({ success: true, data: result });
      } else {
        const err = await res.json();
        setSubmitResult({ success: false, error: err.detail });
      }
    } catch (err: string | error) {
      setSubmitResult({ success: false, error: err.message });
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusColor = (verified: boolean) =>
    verified ? "text-green-600" : "text-gray-400";

  const getStatusIcon = (verified: boolean) => (verified ? "✓" : "○");

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto py-12 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">Loading vendor profile...</p>
      </div>
    );
  }

  if (!vendor) {
    return (
      <div className="max-w-4xl mx-auto py-12 text-center">
        <p className="text-red-600">Vendor not found</p>
        <Link href="/vendors" className="text-blue-600 hover:underline mt-4 block">
          ← Back to vendors
        </Link>
      </div>
    );
  }

  const kycComplete = vendor.kyc_status === "VERIFIED";

  return (
    <div className="max-w-4xl mx-auto py-8 px-4">
      {/* Header */}
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-2xl font-bold">{vendor.name}</h1>
          <p className="text-gray-600">Vendor ID: {vendor.id}</p>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-sm font-medium ${
            kycComplete
              ? "bg-green-100 text-green-800"
              : "bg-yellow-100 text-yellow-800"
          }`}
        >
          {vendor.kyc_status}
        </span>
      </div>

      {/* KYC Progress */}
      {kycStatus && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">KYC Verification Progress</h2>
          <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all"
              style={{ width: `${kycStatus.progress_percent}%` }}
            ></div>
          </div>
          <p className="text-sm text-gray-600 mb-4">
            {kycStatus.progress_percent}% complete
          </p>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className={`flex items-center space-x-2 ${getStatusColor(kycStatus.aadhaar_verified)}`}>
              <span className="text-lg">{getStatusIcon(kycStatus.aadhaar_verified)}</span>
              <span className="text-sm">Aadhaar</span>
            </div>
            <div className={`flex items-center space-x-2 ${getStatusColor(kycStatus.pan_verified)}`}>
              <span className="text-lg">{getStatusIcon(kycStatus.pan_verified)}</span>
              <span className="text-sm">PAN</span>
            </div>
            <div className={`flex items-center space-x-2 ${getStatusColor(kycStatus.gstin_verified)}`}>
              <span className="text-lg">{getStatusIcon(kycStatus.gstin_verified)}</span>
              <span className="text-sm">GSTIN</span>
            </div>
            <div className={`flex items-center space-x-2 ${getStatusColor(kycStatus.bank_verified)}`}>
              <span className="text-lg">{getStatusIcon(kycStatus.bank_verified)}</span>
              <span className="text-sm">Bank</span>
            </div>
            <div className={`flex items-center space-x-2 ${getStatusColor(kycStatus.dsc_bound)}`}>
              <span className="text-lg">{getStatusIcon(kycStatus.dsc_bound)}</span>
              <span className="text-sm">DSC</span>
            </div>
          </div>
        </div>
      )}

      {/* Company Details */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Company Details</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-gray-500">PAN</label>
            <p className="font-mono">{vendor.pan || "Not provided"}</p>
          </div>
          <div>
            <label className="text-sm text-gray-500">GSTIN</label>
            <p className="font-mono">{vendor.gstin || "Not provided"}</p>
          </div>
          <div>
            <label className="text-sm text-gray-500">Email</label>
            <p>{vendor.email || "Not provided"}</p>
          </div>
          <div>
            <label className="text-sm text-gray-500">Phone</label>
            <p>{vendor.phone || "Not provided"}</p>
          </div>
          <div>
            <label className="text-sm text-gray-500">Bank Account</label>
            <p className="font-mono">
              {vendor.bank_account ? `XXXX${vendor.bank_account.slice(-4)}` : "Not linked"}
            </p>
          </div>
          <div>
            <label className="text-sm text-gray-500">IFSC</label>
            <p className="font-mono">{vendor.bank_ifsc || "-"}</p>
          </div>
        </div>
      </div>

      {/* Bid Submission Section */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Submit Bid</h2>

        {!kycComplete ? (
          <div className="bg-yellow-50 border border-yellow-200 p-4 rounded-md">
            <p className="text-yellow-800">
              Complete KYC verification to submit bids. Current status: {vendor.kyc_status}
            </p>
            <Link
              href={`/vendors/register`}
              className="text-blue-600 hover:underline mt-2 inline-block"
            >
              Continue KYC →
            </Link>
          </div>
        ) : tenders.length === 0 ? (
          <p className="text-gray-500">No open tenders available for bidding.</p>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Select Tender *
              </label>
              <select
              title="tender"
               value={selectedTender}
                onChange={(e) => setSelectedTender(e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
              >
                <option value="">Choose a tender...</option>
                {tenders.map((tender) => (
                  <option key={tender.id} value={tender.id}>
                    {tender.title} ({tender.department})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Bid Amount (₹)
              </label>
              <input
                type="number"
                value={bidAmount}
                onChange={(e) => setBidAmount(e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
                placeholder="5000000"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Bid Document (PDF) *
              </label>
              <input
              title="bid_file"
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                className="mt-1 block w-full"
              />
              <p className="text-xs text-gray-500 mt-1">
                Client-side hash will be computed automatically
              </p>
            </div>

            {fileHash && (
              <div className="p-3 bg-gray-100 rounded-md">
                <p className="text-xs text-gray-600">Computed SHA-256 Hash:</p>
                <p className="font-mono text-xs break-all">{fileHash}</p>
              </div>
            )}

            <button
              onClick={submitBid}
              disabled={!selectedTender || !bidFile || submitting}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? "Submitting..." : "Submit Bid with Blockchain Anchor"}
            </button>

            {submitResult && (
              <div
                className={`p-4 rounded-md ${
                  submitResult.success
                    ? "bg-green-50 border border-green-200"
                    : "bg-red-50 border border-red-200"
                }`}
              >
                {submitResult.success ? (
                  <div>
                    <p className="text-green-800 font-medium">✓ Bid Submitted Successfully!</p>
                    <p className="text-sm text-green-700 mt-1">
                      Bid ID: {submitResult.data.id}
                    </p>
                    <p className="text-sm text-green-700">
                      Blockchain Status: {submitResult.data.blockchain_anchor_status}
                    </p>
                    <Link
                      href={`/bids/${submitResult.data.id}`}
                      className="text-blue-600 hover:underline text-sm mt-2 inline-block"
                    >
                      View blockchain receipt →
                    </Link>
                  </div>
                ) : (
                  <p className="text-red-700">Error: {submitResult.error}</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex justify-between">
        <Link href="/vendors" className="text-blue-600 hover:underline">
          ← Back to vendors
        </Link>
        <Link href="/tenders" className="text-blue-600 hover:underline">
          View all tenders →
        </Link>
      </div>
    </div>
  );
}
