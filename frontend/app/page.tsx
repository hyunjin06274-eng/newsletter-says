"use client";

import { useState, useEffect } from "react";

const COUNTRY_FLAGS: Record<string, string> = {
  KR: "\uD83C\uDDF0\uD83C\uDDF7",
  RU: "\uD83C\uDDF7\uD83C\uDDFA",
  VN: "\uD83C\uDDFB\uD83C\uDDF3",
  TH: "\uD83C\uDDF9\uD83C\uDDED",
  PH: "\uD83C\uDDF5\uD83C\uDDED",
  PK: "\uD83C\uDDF5\uD83C\uDDF0",
};

const COUNTRY_NAMES: Record<string, string> = {
  KR: "Korea", RU: "Russia", VN: "Vietnam",
  TH: "Thailand", PH: "Philippines", PK: "Pakistan",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-700 text-gray-300",
  running: "bg-blue-900/50 text-blue-300 animate-pulse",
  completed: "bg-green-900/50 text-green-300",
  failed: "bg-red-900/50 text-red-300",
};

const PHASE_LABELS: Record<string, string> = {
  keywords: "Keyword Gen",
  collection: "Collecting",
  merge: "Merging",
  scoring: "Scoring",
  enrichment: "Enriching",
  grouping: "Grouping",
  writing: "Writing",
  auditing: "Auditing",
  sending: "Sending",
  complete: "Complete",
};

interface Run {
  id: string;
  date_str: string;
  status: string;
  countries: string[];
  current_phase: string;
  total_sent: number;
  created_at: string;
}

export default function Dashboard() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(false);
  const [startingRun, setStartingRun] = useState(false);
  const [selectedCountries, setSelectedCountries] = useState<string[]>(
    Object.keys(COUNTRY_FLAGS)
  );

  useEffect(() => {
    fetchRuns();
    const interval = setInterval(fetchRuns, 5000);
    return () => clearInterval(interval);
  }, []);

  async function fetchRuns() {
    try {
      const res = await fetch("/api/runs");
      if (res.ok) {
        const data = await res.json();
        setRuns(data.runs || []);
      }
    } catch {
      // API not available yet
    }
  }

  async function startNewRun() {
    setStartingRun(true);
    try {
      const res = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ countries: selectedCountries, days: 30 }),
      });
      if (res.ok) {
        fetchRuns();
      }
    } catch (e) {
      console.error("Failed to start run:", e);
    }
    setStartingRun(false);
  }

  function toggleCountry(code: string) {
    setSelectedCountries((prev) =>
      prev.includes(code)
        ? prev.filter((c) => c !== code)
        : [...prev, code]
    );
  }

  const activeRun = runs.find((r) => r.status === "running");

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-gray-400 mt-1">SK Enmove Global MI Newsletter Pipeline</p>
        </div>
        <button
          onClick={startNewRun}
          disabled={startingRun || !!activeRun}
          className="px-6 py-3 bg-red-600 hover:bg-red-700 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg font-medium transition-colors"
        >
          {startingRun ? "Starting..." : activeRun ? "Run in Progress" : "Start New Run"}
        </button>
      </div>

      {/* Country Selection */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h2 className="text-lg font-semibold mb-4">Target Countries</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
          {Object.entries(COUNTRY_FLAGS).map(([code, flag]) => (
            <button
              key={code}
              onClick={() => toggleCountry(code)}
              className={`p-3 rounded-lg border transition-all text-center ${
                selectedCountries.includes(code)
                  ? "border-red-500 bg-red-900/20 text-white"
                  : "border-gray-700 bg-gray-800/50 text-gray-500"
              }`}
            >
              <span className="text-2xl block">{flag}</span>
              <span className="text-xs mt-1 block">{COUNTRY_NAMES[code]}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Active Run Status */}
      {activeRun && (
        <div className="bg-gray-900 rounded-xl p-6 border border-blue-800/50">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse" />
            <h2 className="text-lg font-semibold">Active Run</h2>
            <span className="text-sm text-gray-400">{activeRun.id.slice(0, 8)}...</span>
          </div>

          {/* Phase Progress */}
          <div className="flex gap-1 mt-4">
            {Object.entries(PHASE_LABELS).map(([phase, label]) => {
              const isActive = activeRun.current_phase === phase;
              const isPast =
                Object.keys(PHASE_LABELS).indexOf(phase) <
                Object.keys(PHASE_LABELS).indexOf(activeRun.current_phase);
              return (
                <div
                  key={phase}
                  className={`flex-1 py-2 px-1 rounded text-center text-xs transition-all ${
                    isActive
                      ? "bg-blue-600 text-white font-medium"
                      : isPast
                      ? "bg-green-900/50 text-green-400"
                      : "bg-gray-800 text-gray-600"
                  }`}
                >
                  {label}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recent Runs */}
      <div className="bg-gray-900 rounded-xl border border-gray-800">
        <div className="p-6 border-b border-gray-800">
          <h2 className="text-lg font-semibold">Recent Runs</h2>
        </div>
        <div className="divide-y divide-gray-800">
          {runs.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              No runs yet. Click &quot;Start New Run&quot; to begin.
            </div>
          ) : (
            runs.map((run) => (
              <a
                key={run.id}
                href={`/runs/${run.id}`}
                className="flex items-center justify-between p-4 hover:bg-gray-800/50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${STATUS_COLORS[run.status]}`}>
                    {run.status}
                  </span>
                  <div>
                    <span className="font-medium">{run.date_str}</span>
                    <span className="text-gray-500 text-sm ml-3">
                      {run.countries.map((c) => COUNTRY_FLAGS[c] || c).join(" ")}
                    </span>
                  </div>
                </div>
                <div className="text-sm text-gray-400">
                  {run.total_sent > 0 && <span>{run.total_sent} sent</span>}
                  <span className="ml-4">
                    {new Date(run.created_at).toLocaleString("ko-KR")}
                  </span>
                </div>
              </a>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
