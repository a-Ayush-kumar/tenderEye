"use client";

import { useEffect, useState } from "react";
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
  created_at: string;
}

export default function VendorsList() {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"ALL" | "VERIFIED" | "PENDING">("ALL");

  useEffect(() => {
    fetchVendors();
  }, [filter]);

  async function fetchVendors() {
    try {
      setLoading(true);
      const url =
        filter === "ALL"
          ? "/api/v1/vendors/"
          : `/api/v1/vendors/?kyc_status=${filter}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setVendors(data);
      }
    } catch (err) {
      console.error("Failed to fetch vendors", err);
    } finally {
      setLoading(false);
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "VERIFIED":
        return "bg-green-100 text-green-800";
      case "PENDING":
        return "bg-yellow-100 text-yellow-800";
      case "REJECTED":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const verifiedCount = vendors.filter((v) => v.kyc_status === "VERIFIED").length;

  return (
    <div className="max-w-6xl mx-auto py-8 px-4">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">Registered Vendors</h1>
          <p className="text-gray-600">
            {verifiedCount} verified vendors available for bidding
          </p>
        </div>
        <Link
          href="/vendors/register"
          className="bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700"
        >
          + Register New Vendor
        </Link>
      </div>

      {/* Filters */}
      <div className="flex space-x-2 mb-6">
        {["ALL", "VERIFIED", "PENDING"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f as any)}
            className={`px-4 py-2 rounded-md text-sm font-medium ${
              filter === f
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {f === "ALL" ? "All Vendors" : f === "VERIFIED" ? "Verified" : "Pending KYC"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading vendors...</p>
        </div>
      ) : vendors.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <p className="text-gray-500 mb-4">No vendors found</p>
          <Link
            href="/vendors/register"
            className="text-blue-600 hover:underline"
          >
            Register the first vendor →
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Company
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Tax IDs
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  KYC Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Registered
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {vendors.map((vendor) => (
                <tr key={vendor.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="font-medium text-gray-900">{vendor.name}</div>
                    <div className="text-sm text-gray-500">
                      {vendor.email || "No email"}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <div className="font-mono">{vendor.pan || "-"}</div>
                    <div className="text-gray-500">{vendor.gstin || "-"}</div>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(
                        vendor.kyc_status
                      )}`}
                    >
                      {vendor.kyc_status}
                    </span>
                    {vendor.kyc_verified_at && (
                      <div className="text-xs text-gray-500 mt-1">
                        Verified {new Date(vendor.kyc_verified_at).toLocaleDateString()}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {new Date(vendor.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-right text-sm font-medium">
                    <Link
                      href={`/vendors/${vendor.id}`}
                      className="text-blue-600 hover:text-blue-900"
                    >
                      View →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Market Depth Widget */}
      <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-blue-50 p-4 rounded-lg">
          <h3 className="font-semibold text-blue-900">Verified Vendors</h3>
          <p className="text-2xl font-bold text-blue-700">{verifiedCount}</p>
          <p className="text-sm text-blue-600">Ready to bid</p>
        </div>
        <div className="bg-yellow-50 p-4 rounded-lg">
          <h3 className="font-semibold text-yellow-900">Pending KYC</h3>
          <p className="text-2xl font-bold text-yellow-700">
            {vendors.filter((v) => v.kyc_status === "PENDING").length}
          </p>
          <p className="text-sm text-yellow-600">In progress</p>
        </div>
        <div className="bg-green-50 p-4 rounded-lg">
          <h3 className="font-semibold text-green-900">Active Tenders</h3>
          <p className="text-2xl font-bold text-green-700">-</p>
          <p className="text-sm text-green-600">From TenderEye</p>
        </div>
      </div>
    </div>
  );
}
