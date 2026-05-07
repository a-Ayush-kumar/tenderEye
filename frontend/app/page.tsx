"use-client";
import { useState, useEffect } from "react";
import Link from "next/link";
import MarketDepthWidget from "./components/MarketDepthWidget";

interface Tender {
  id: string;
  title: string;
  department: string;
  status: string;
  cafetaria_locked: string | null;
  bidders_count: string;
}

interface VendorStats {
  total: number;
  verified: number;
  pending: number;
}

export default function Dashboard() {
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [vendors, setVendors] = useState<VendorStats>({
    total: 0,
    verified: 0,
    pending: 0,
  });
  const [selectedTender, setSelectedTender] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchTenders();
    fetchVendorStats();
  }, []);

  async function fetchTenders() {
    try {
      const res = await fetch("/api/v1/tenders");
      if (!res.ok) throw new Error("Failed to fetch");
      const data = await res.json();
      setTenders(data);
    } catch (err) {
      setError("API not connected. Make sure backend is running.");
    } finally {
      setLoading(false);
    }
  }

  async function fetchVendorStats() {
    try {
      const res = await fetch("/api/v1/vendors/");
      if (res.ok) {
        const data = await res.json();
        setVendors({
          total: data.length,
          verified: data.filter((v: user) => v.kyc_status === "VERIFIED").length,
          pending: data.filter((v: user) => v.kyc_status === "PENDING").length,
        });
      }
    } catch (err) {
      console.error("Failed to fetch vendor stats", err);
    }
  }

  async function createTender(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const title = (form.elements.namedItem("title") as HTMLInputElement).value;
    const department = (
      form.elements.namedItem("department") as HTMLInputElement
    ).value;

    try {
      const res = await fetch("/api/v1/tenders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, department, criteria: [] }),
      });
      if (res.ok) {
        form.reset();
        fetchTenders();
      }
    } catch (err) {
      setError("Failed to create tender");
    }
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="mb-2">Dashboard</h1>
        <p className="text-gray-600">
          Government e-Procurement Integrity Platform — Prototype
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-500 mb-1">Active Tenders</div>
          <div className="text-3xl font-bold text-primary-700">
            {loading ? "..." : tenders.length}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-500 mb-1">Verified Vendors</div>
          <div className="text-3xl font-bold text-green-600">
            {vendors.verified}
          </div>
          <Link href="/vendors" className="text-xs text-blue-600 hover:underline">
            {vendors.pending} pending KYC →
          </Link>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-500 mb-1">System Status</div>
          <div className="text-3xl font-bold text-green-600">
            {error ? "Offline" : "Online"}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-500 mb-1">Version</div>
          <div className="text-3xl font-bold text-gray-800">0.1.0</div>
          <span className="text-xs text-gray-500">+ BidShield Phase 1</span>
        </div>
      </div>
{vendors.verified > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2">
            <div className="bg-linear-to-r from-blue-50 to-indigo-50 rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold text-indigo-900 mb-2">Market Depth</h2>
              <div className="flex items-center gap-6 mb-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-indigo-700">{vendors.verified}</div>
                  <div className="text-sm text-indigo-600">Verified Vendors</div>
                </div>
                <div className="h-12 w-px bg-indigo-200"></div>
                <div>
                  <p className="text-sm text-indigo-800">
                    {vendors.verified >= 5
                      ? "✓ Strong competition expected"
                      : vendors.verified >= 3
                        ? "⚠ Moderate vendor interest"
                        : "⚠ Limited vendor pool"}
                  </p>
                  <p className="text-xs text-indigo-600 mt-1">
                    Based on KYC-verified vendors ready to bid
                  </p>
                </div>
                <div className="ml-auto">
                  <Link
                    href="/vendors/register"
                    className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 transition"
                  >
                    + Onboard Vendor
                  </Link>
                </div>
              </div>
      {tenders.length > 0 && (
                <div className="mt-4 pt-4 border-t border-indigo-100">
                  <label className="block text-sm text-indigo-700 mb-2">Select tender for detailed market depth:</label>
                  <select
                    id="tender"
                    title="tender"
                    value={selectedTender}
                    onChange={(e) => setSelectedTender(e.target.value)}
                    className="w-full px-3 py-2 border border-indigo-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="">-- Select a tender --</option>
                    {tenders.map((t) => (
                      <option key={t.id} value={t.id}>{t.title}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>

          <div className="lg:col-span-1">
            <MarketDepthWidget tenderId={selectedTender} />
          </div>
        </div>
      )}
      <div className="bg-white rounded-lg shadow p-6 mb-8">
        <h2 className="mb-4">Create New Tender</h2>
        <form onSubmit={createTender} className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Title
            </label>
            <input
              name="title"
              type="text"
              required
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
              placeholder="e.g., CRPF Construction Tender 2026/0847"
            />
          </div>
          <div className="w-48">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Department
            </label>
            <input
              name="department"
              type="text"
              required
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
              placeholder="e.g., CRPF"
            />
          </div>
          <button
            type="submit"
            className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition"
          >
            Create
          </button>
        </form>
      </div>
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b">
          <h2 className="mb-0">Recent Tenders</h2>
        </div>
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
        ) : error ? (
          <div className="p-8 text-center text-red-500">{error}</div>
        ) : tenders.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No tenders yet. Create one above or run <code className="bg-gray-100 px-2 py-1 rounded">make seed</code>.
          </div>
        ) : (
          <div className="divide-y">
            {tenders.map((tender) => (
              <div
                key={tender.id}
                className="px-6 py-4 hover:bg-gray-50 transition"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <Link
                      href={`/tenders/${tender.id}`}
                      className="font-medium text-primary-700 hover:underline"
                    >
                      {tender.title}
                    </Link>
                    <div className="text-sm text-gray-500 mt-1">
                      {tender.department} | {tender.status}
                      {tender.criteria_locked && (
                        <span className="ml-2 px-2 py-0.5 bg-yellow-100 text-yellow-800 rounded text-xs">
                          Locked
                        </span>
                      )}
                    </div>
                  </div>
                  <Link
                    href={`/tenders/${tender.id}`}
                    className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-100 transition"
                  >
                    View
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
