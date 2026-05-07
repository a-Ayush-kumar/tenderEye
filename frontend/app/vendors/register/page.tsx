"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface KYCStep {
  title: string;
  description: string;
}

const steps: KYCStep[] = [
  { title: "Basic Info", description: "Name, email, phone" },
  { title: "PAN & GSTIN", description: "Tax registration" },
  { title: "Aadhaar KYC", description: "Identity verification" },
  { title: "Bank Account", description: "Payment details" },
  { title: "Documents", description: "Upload certificates" },
];

export default function VendorRegistration() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [vendorId, setVendorId] = useState<string | null>(null);
  const [error, setError] = useState("");

  // Form data
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone: "",
    pan: "",
    gstin: "",
    aadhaar: "",
    aadhaarOtp: "",
    accountNumber: "",
    ifscCode: "",
    accountHolderName: "",
  });

  const updateField = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setError("");
  };

  const createVendor = async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch("/api/v1/vendors/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formData.name,
          email: formData.email,
          phone: formData.phone,
          pan: formData.pan,
          gstin: formData.gstin,
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Failed to create vendor");
      }

      const vendor = await response.json();
      setVendorId(vendor.id);
      setCurrentStep(1);
    } catch (err:string | error) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const verifyGSTIN = async () => {
    if (!vendorId) return;
    setLoading(true);
    setError("");

    try {
      const formDataObj = new FormData();
      formDataObj.append("gstin", formData.gstin);

      const response = await fetch(`/api/v1/vendors/${vendorId}/kyc/gstin`, {
        method: "POST",
        body: formDataObj,
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "GSTIN verification failed");
      }

      setCurrentStep(2);
    } catch (err: string | error) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const initiateAadhaar = async () => {
    if (!vendorId) return;
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `/api/v1/vendors/${vendorId}/kyc/aadhaar`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ aadhaar_number: formData.aadhaar }),
        }
      );

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Aadhaar verification failed");
      }

      const data = await response.json();
      // For demo, auto-fill OTP
      updateField("aadhaarOtp", data.mock_otp || "");
    } catch (err: string | error) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const verifyAadhaarOtp = async () => {
    if (!vendorId) return;
    setLoading(true);
    setError("");

    try {
      const formDataObj = new FormData();
      formDataObj.append("session_id", "demo-session");
      formDataObj.append("otp", formData.aadhaarOtp);

      const response = await fetch(
        `/api/v1/vendors/${vendorId}/kyc/aadhaar/verify`,
        {
          method: "POST",
          body: formDataObj,
        }
      );

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "OTP verification failed");
      }

      setCurrentStep(3);
    } catch (err: string | error) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const verifyBank = async () => {
    if (!vendorId) return;
    setLoading(true);
    setError("");

    try {
      const formDataObj = new FormData();
      formDataObj.append("account_number", formData.accountNumber);
      formDataObj.append("ifsc_code", formData.ifscCode);
      formDataObj.append("account_holder_name", formData.accountHolderName);

      const response = await fetch(
        `/api/v1/vendors/${vendorId}/kyc/bank`,
        {
          method: "POST",
          body: formDataObj,
        }
      );

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Bank verification failed");
      }

      setCurrentStep(4);
    } catch (err: string | error) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const finishRegistration = () => {
    router.push(`/vendors/${vendorId}`);
  };

  const renderStep = () => {
    switch (currentStep) {
      case 0:
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Basic Information</h3>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Company Name *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => updateField("name", e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
                placeholder="M/S ABC Constructions"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => updateField("email", e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
                placeholder="contact@company.com"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Phone
              </label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => updateField("phone", e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
                placeholder="+91 98765 43210"
              />
            </div>
            <button
              onClick={createVendor}
              disabled={!formData.name || loading}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Creating..." : "Continue →"}
            </button>
          </div>
        );

      case 1:
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Tax Registration</h3>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                PAN Number *
              </label>
              <input
                type="text"
                value={formData.pan}
                onChange={(e) =>
                  updateField("pan", e.target.value.toUpperCase())
                }
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
                placeholder="AAAPA1234A"
                maxLength={10}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                GSTIN *
              </label>
              <input
                type="text"
                value={formData.gstin}
                onChange={(e) =>
                  updateField("gstin", e.target.value.toUpperCase())
                }
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
                placeholder="07AAAPA1234A1Z5"
                maxLength={15}
              />
              <p className="text-xs text-gray-500 mt-1">
                15-character GSTIN with checksum validation
              </p>
            </div>
            <button
              onClick={verifyGSTIN}
              disabled={formData.gstin.length !== 15 || loading}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Verifying..." : "Verify GSTIN →"}
            </button>
          </div>
        );

      case 2:
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Aadhaar eKYC</h3>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Aadhaar Number *
              </label>
              <input
                type="text"
                value={formData.aadhaar}
                onChange={(e) => updateField("aadhaar", e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
                placeholder="1234 5678 9012"
                maxLength={12}
              />
            </div>
            <button
              onClick={initiateAadhaar}
              disabled={formData.aadhaar.length !== 12 || loading}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Sending OTP..." : "Send OTP"}
            </button>

            {formData.aadhaarOtp && (
              <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
                <p className="text-sm text-yellow-800">
                  Demo OTP: <strong>{formData.aadhaarOtp}</strong>
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  In production, OTP is sent to Aadhaar-linked mobile
                </p>
                <button
                  onClick={verifyAadhaarOtp}
                  disabled={loading}
                  className="mt-3 w-full bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 disabled:opacity-50"
                >
                  {loading ? "Verifying..." : "Verify OTP →"}
                </button>
              </div>
            )}
          </div>
        );

      case 3:
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Bank Account Details</h3>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Account Number *
              </label>
              <input
                type="text"
                value={formData.accountNumber}
                onChange={(e) => updateField("accountNumber", e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
                placeholder="1234567890"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                IFSC Code *
              </label>
              <input
                type="text"
                value={formData.ifscCode}
                onChange={(e) =>
                  updateField("ifscCode", e.target.value.toUpperCase())
                }
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
                placeholder="SBIN0001234"
                maxLength={11}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Account Holder Name *
              </label>
              <input
                type="text"
                value={formData.accountHolderName}
                onChange={(e) =>
                  updateField("accountHolderName", e.target.value)
                }
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
                placeholder={formData.name}
              />
            </div>
            <button
              onClick={verifyBank}
              disabled={
                !formData.accountNumber ||
                formData.ifscCode.length !== 11 ||
                !formData.accountHolderName ||
                loading
              }
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Verifying..." : "Verify Bank →"}
            </button>
          </div>
        );

      case 4:
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Document Upload</h3>
            <p className="text-sm text-gray-600">
              Upload your company registration and KYC documents (optional for
              demo)
            </p>

            <div className="space-y-3">
              {["GSTIN Certificate", "PAN Card", "Bank Proof", "DSC"].map(
                (doc) => (
                  <div key={doc} className="flex items-center space-x-3">
                    <input
                      type="file"
                      id={doc}
                      className="hidden"
                      onChange={() => {}}
                    />
                    <label
                      htmlFor={doc}
                      className="flex-1 py-2 px-4 border border-gray-300 rounded-md hover:bg-gray-50 cursor-pointer text-center"
                    >
                      {doc}
                    </label>
                  </div>
                )
              )}
            </div>

            <button
              onClick={finishRegistration}
              className="w-full bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700"
            >
              Complete Registration →
            </button>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <h1 className="text-2xl font-bold mb-2">Vendor Registration</h1>
      <p className="text-gray-600 mb-8">
        Complete KYC to participate in government tenders
      </p>

      {/* Progress Steps */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          {steps.map((step, index) => (
            <div key={index} className="flex flex-col items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                  index < currentStep
                    ? "bg-green-600 text-white"
                    : index === currentStep
                    ? "bg-blue-600 text-white"
                    : "bg-gray-200 text-gray-600"
                }`}
              >
                {index < currentStep ? "✓" : index + 1}
              </div>
              <span className="text-xs mt-1 text-gray-600 hidden sm:block">
                {step.title}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-2 text-center">
          <p className="text-sm text-gray-600">
            Step {currentStep + 1}: {steps[currentStep]?.description}
          </p>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md">
          <p className="text-red-700">{error}</p>
        </div>
      )}

      {/* Step Content */}
      <div className="bg-white p-6 rounded-lg shadow-md">{renderStep()}</div>

      {/* KYC Info */}
      <div className="mt-6 p-4 bg-blue-50 rounded-md">
        <h4 className="font-medium text-blue-900 mb-2">
          Why do we need this?
        </h4>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>• PAN & GSTIN for tax compliance verification</li>
          <li>• Aadhaar for identity verification (masked, hash stored only)</li>
          <li>• Bank details for EMD refund and payment processing</li>
          <li>• All data encrypted and stored securely</li>
        </ul>
      </div>
    </div>
  );
}
