"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "../api-client";

const COUNTRY_FLAGS: Record<string, string> = {
  KR: "\uD83C\uDDF0\uD83C\uDDF7", RU: "\uD83C\uDDF7\uD83C\uDDFA", VN: "\uD83C\uDDFB\uD83C\uDDF3",
  TH: "\uD83C\uDDF9\uD83C\uDDED", PH: "\uD83C\uDDF5\uD83C\uDDED", PK: "\uD83C\uDDF5\uD83C\uDDF0",
};

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-gray-700 text-gray-300",
  running: "bg-blue-900/50 text-blue-300",
  completed: "bg-green-900/50 text-green-300",
  failed: "bg-red-900/50 text-red-300",
};

interface RunItem {
  id: string;
  date_str: string;
  status: string;
  countries: string[];
  total_sent: number;
  created_at: string;
}

export default function RunsPage() {
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    fetchRuns();
  }, [page]);

  async function fetchRuns() {
    try {
      const res = await apiFetch(`/api/runs?page=${page}&page_size=20`);
      if (res.ok) {
        const data = await res.json();
        setRuns(data.runs || []);
        setTotal(data.total || 0);
      }
    } catch {
      // API not available
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Run History</h1>

      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800 text-gray-400 text-sm">
              <th className="text-left p-4">Date</th>
              <th className="text-left p-4">Status</th>
              <th className="text-left p-4">Countries</th>
              <th className="text-left p-4">Sent</th>
              <th className="text-left p-4">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {runs.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-12 text-center text-gray-500">
                  No runs yet
                </td>
              </tr>
            ) : (
              runs.map((run) => (
                <tr key={run.id} className="hover:bg-gray-800/50 transition-colors">
                  <td className="p-4">
                    <a href={`/runs/${run.id}`} className="text-blue-400 hover:text-blue-300 font-medium">
                      {run.date_str}
                    </a>
                  </td>
                  <td className="p-4">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${STATUS_STYLES[run.status]}`}>
                      {run.status}
                    </span>
                  </td>
                  <td className="p-4 text-lg">
                    {run.countries.map((c) => COUNTRY_FLAGS[c] || c).join(" ")}
                  </td>
                  <td className="p-4 text-gray-400">{run.total_sent}</td>
                  <td className="p-4 text-gray-400 text-sm">
                    {new Date(run.created_at).toLocaleString("ko-KR")}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {total > 20 && (
          <div className="flex items-center justify-between p-4 border-t border-gray-800">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-4 py-2 bg-gray-800 rounded text-sm disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-sm text-gray-400">
              Page {page} of {Math.ceil(total / 20)}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page * 20 >= total}
              className="px-4 py-2 bg-gray-800 rounded text-sm disabled:opacity-50"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
