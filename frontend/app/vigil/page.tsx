"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface Alert {
  id: string;
  tender_id: string;
  alert_type: string;
  confidence: number;
  risk_score: number;
  description: string;
  status: string;
  created_at: string;
}

interface TenderStatus {
  tender_id: string;
  title: string;
  risk_score: number;
  risk_level: string;
  alert_count: number;
}

interface DashboardData {
  summary: {
    total_alerts: number;
    status_breakdown: Record<string, number>;
    risk_distribution: Record<string, number>;
  };
  critical_alerts: Alert[];
  tender_status: TenderStatus[];
}

export default function VigilDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchDashboard();
  }, []);

  async function fetchDashboard() {
    try {
      const res = await fetch("/api/v1/vigil/dashboard");
      if (!res.ok) throw new Error("Failed to fetch");
      const data = await res.json();
      setData(data);
    } catch (err) {
      setError("Failed to load VIGIL dashboard");
    } finally {
      setLoading(false);
    }
  }

  function getRiskBadgeClass(level: string) {
    switch (level) {
      case "CRITICAL":
        return "bg-red-100 text-red-800";
      case "HIGH":
        return "bg-orange-100 text-orange-800";
      case "MEDIUM":
        return "bg-yellow-100 text-yellow-800";
      default:
        return "bg-green-100 text-green-800";
    }
  }

  function getAlertTypeIcon(type: string) {
    const icons: Record<string, string> = {
      COVER_PRICING: "💰",
      IDENTICAL_BIDS: "🎯",
      BID_ROTATION: "🔄",
      NETWORK_COMMUNITY: "🕸️",
      TEMPORAL_ANOMALY: "⏰",
      HONEYPOT_HIT: "🍯",
    };
    return icons[type] || "⚠️";
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg text-gray-500">Loading VIGIL Dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
        {error}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">VIGIL Dashboard</h1>
        <p className="text-gray-600">
          Verifiable Integrity Guardian & Intelligence Layer — Collusion Detection
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">Total Alerts</div>
          <div className="text-3xl font-bold text-indigo-600">
            {data.summary.total_alerts}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">Critical Risk</div>
          <div className="text-3xl font-bold text-red-600">
            {data.summary.risk_distribution.CRITICAL || 0}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">High Risk</div>
          <div className="text-3xl font-bold text-orange-600">
            {data.summary.risk_distribution.HIGH || 0}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">Pending Action</div>
          <div className="text-3xl font-bold text-yellow-600">
            {data.summary.status_breakdown.NEW || 0}
          </div>
        </div>
      </div>

      {/* Risk Distribution */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <h2 className="text-lg font-semibold mb-4">Risk Distribution</h2>
        <div className="flex items-center gap-2">
          {Object.entries(data.summary.risk_distribution).map(([level, count]) => (
            <div
              key={level}
              className={`px-3 py-2 rounded-lg ${getRiskBadgeClass(level)}`}
            >
              <span className="font-semibold">{level}:</span> {count}
            </div>
          ))}
        </div>
      </div>

      {/* Critical Alerts */}
      {data.critical_alerts.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <h2 className="text-lg font-semibold text-red-800 mb-4">
            🚨 Critical Alerts Requiring Immediate Attention
          </h2>
          <div className="space-y-3">
            {data.critical_alerts.map((alert) => (
              <div
                key={alert.id}
                className="bg-white rounded-lg p-3 shadow-sm border-l-4 border-red-500"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">{getAlertTypeIcon(alert.alert_type)}</span>
                    <span className="font-semibold">{alert.alert_type.replace(/_/g, " ")}</span>
                    <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs">
                      Score: {alert.risk_score.toFixed(0)}
                    </span>
                  </div>
                  <Link
                    href={`/tenders/${alert.tender_id}`}
                    className="text-sm text-blue-600 hover:underline"
                  >
                    View Tender →
                  </Link>
                </div>
                <p className="text-sm text-gray-600 mt-1">{alert.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tender Risk Status */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-4 py-3 border-b">
          <h2 className="text-lg font-semibold">Tender Risk Status</h2>
        </div>
        {data.tender_status.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No tenders with VIGIL alerts yet. Run analysis on a tender to generate alerts.
          </div>
        ) : (
          <div className="divide-y">
            {data.tender_status.map((tender) => (
              <div key={tender.tender_id} className="px-4 py-3 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div>
                    <Link
                      href={`/tenders/${tender.tender_id}`}
                      className="font-medium text-blue-600 hover:underline"
                    >
                      {tender.title}
                    </Link>
                    <div className="text-sm text-gray-500 mt-1">
                      {tender.alert_count} alert{tender.alert_count !== 1 ? "s" : ""}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span
                      className={`px-3 py-1 rounded-full text-sm font-medium ${getRiskBadgeClass(
                        tender.risk_level
                      )}`}
                    >
                      {tender.risk_level}
                    </span>
                    <span className="text-sm text-gray-600">
                      Score: {tender.risk_score.toFixed(0)}/100
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="mt-6 flex gap-4">
        <Link
          href="/vigil/alerts"
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
        >
          View All Alerts
        </Link>
        <Link
          href="/"
          className="px-4 py-2 border rounded-lg hover:bg-gray-100 transition"
        >
          Back to Dashboard
        </Link>
      </div>
    </div>
  );
}
