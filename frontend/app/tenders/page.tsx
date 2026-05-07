"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface Tender {
  id: string;
  title: string;
  department: string;
  status: string;
  criteria_locked: string | null;
}

export default function TendersList() {
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTenders();
  }, []);

  async function fetchTenders() {
    try {
      const res = await fetch("/api/v1/tenders");
      if (res.ok) {
        const data = await res.json();
        setTenders(data);
      }
    } catch (err) {
      console.error("Failed to fetch tenders", err);
    } finally {
      setLoading(false);
    }
  }
  return (
    <div>
      <h1 className="mb-6">All Tenders</h1>

      {loading ? (
        <div className="text-center py-8 text-gray-500">Loading...</div>
      ) : tenders.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No tenders found. Create one from the{" "}
          <Link href="/" className="text-primary-600 hover:underline">
            Dashboard
          </Link>
          .
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow divide-y">
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
                  View Details
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
