"use client";

import { useEffect, useState } from "react";

interface MarketDepthData {
  tender_id: string;
  tender_title: string;
  market_depth: {
    total_kyc_verified: number;
    dsc_ready: number;
    eligible_to_bid: number;
    already_submitted_bids: number;
    unique_vendors_bidded: number;
    competition_ratio: number;
  };
  state_distribution: Record<string, number>;
  health_indicators: {
    sufficient_competition: boolean;
    single_vendor_dominance: boolean;
  };
}

export default function MarketDepthWidget({ tenderId }: { tenderId?: string }) {
  const [data, setData] = useState<MarketDepthData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (tenderId) fetchDepth(tenderId);
  }, [tenderId]);

  async function fetchDepth(id: string) {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/vendors/market-depth/${id}`);
      if (res.ok) setData(await res.json());
    } catch (e) {
      console.error("Market depth fetch failed:", e);
    } finally {
      setLoading(false);
    }
  }

  if (!tenderId) {
    return (
      <div className="bg-white rounded-lg shadow p-4 text-center text-gray-500">
        Select a tender to view market depth
      </div>
    );
  }

  if (loading) return <div className="p-4 text-sm text-gray-500">Loading market depth...</div>;
  if (!data) return null;

  const md = data.market_depth;
  const health = data.health_indicators;

  return (
    <div className="bg-white rounded-lg shadow p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900">📊 Market Depth</h3>
        <span className={`text-xs px-2 py-1 rounded font-medium ${
          health.sufficient_competition && !health.single_vendor_dominance
            ? "bg-green-100 text-green-700"
            : "bg-yellow-100 text-yellow-700"
        }`}>
          {health.sufficient_competition && !health.single_vendor_dominance ? "Healthy" : "Caution"}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-blue-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-blue-700">{md.total_kyc_verified}</div>
          <div className="text-xs text-blue-600">KYC Verified</div>
        </div>
        <div className="bg-green-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-green-700">{md.dsc_ready}</div>
          <div className="text-xs text-green-600">DSC Ready</div>
        </div>
        <div className="bg-purple-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-purple-700">{md.already_submitted_bids}</div>
          <div className="text-xs text-purple-600">Bids Submitted</div>
        </div>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-600">Competition Ratio</span>
          <span className="font-mono">{md.competition_ratio.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Unique Bidders</span>
          <span className="font-mono">{md.unique_vendors_bidded}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Eligible Vendors</span>
          <span className="font-mono">{md.eligible_to_bid}</span>
        </div>
      </div>

      {Object.keys(data.state_distribution).length > 0 && (
        <div className="mt-4 pt-3 border-t">
          <div className="text-xs font-medium text-gray-500 mb-2">State Distribution</div>
          <div className="flex flex-wrap gap-1">
            {Object.entries(data.state_distribution).map(([state, count]) => (
              <span key={state} className="text-xs px-2 py-0.5 bg-gray-100 rounded">
                {state}: {count}
              </span>
            ))}
          </div>
        </div>
      )}

      {health.single_vendor_dominance && (
        <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
          ⚠️ Single vendor dominance detected — one state/entity controls &gt;50% of verified vendors
        </div>
      )}

      {!health.sufficient_competition && md.already_submitted_bids < 3 && (
        <div className="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-700">
          ⚠️ Low competition — fewer than 3 bids received. Consider extending deadline.
        </div>
      )}
    </div>
  );
}
