"use client";

import { useState, useEffect, useRef } from "react";
import { apiFetch } from "./api-client";

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

type RunState = "idle" | "starting" | "running" | "error";

export default function Dashboard() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [runState, setRunState] = useState<RunState>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [apiConnected, setApiConnected] = useState(false);
  const [waking, setWaking] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    wakeAndFetch();
    pollRef.current = setInterval(fetchRuns, 5000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  useEffect(() => {
    const active = runs.find((r) => r.status === "running");
    if (active && runState !== "starting") {
      setRunState("running");
    } else if (!active && runState === "running") {
      setRunState("idle");
    }
  }, [runs]);

  async function wakeAndFetch() {
    setWaking(true);
    // Try up to 4 times (covers ~60s cold start)
    for (let i = 0; i < 4; i++) {
      try {
        const res = await apiFetch("/api/runs", { signal: AbortSignal.timeout(20000) });
        if (res.ok) {
          const data = await res.json();
          setRuns(data.runs || []);
          setApiConnected(true);
          setWaking(false);
          return;
        }
      } catch {}
      // Wait before retry
      if (i < 3) await new Promise((r) => setTimeout(r, 5000));
    }
    setApiConnected(false);
    setWaking(false);
  }

  async function fetchRuns() {
    try {
      const res = await apiFetch("/api/runs", { signal: AbortSignal.timeout(10000) });
      if (res.ok) {
        const data = await res.json();
        setRuns(data.runs || []);
        if (!apiConnected) setApiConnected(true);
      }
    } catch {
      if (apiConnected) setApiConnected(false);
    }
  }

  async function handleStartRun() {
    setRunState("starting");
    setErrorMsg("");

    try {
      const res = await apiFetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ countries: Object.keys(COUNTRY_FLAGS), days: 30 }),
      });

      if (res.ok) {
        setRunState("running");
        // Refresh runs list
        await fetchRuns();
      } else {
        setRunState("error");
        setErrorMsg("API returned error. Check backend server.");
      }
    } catch {
      setRunState("error");
      setErrorMsg("Backend not reachable. Start the server: uvicorn backend.main:app --port 8000");
    }
  }

  const isRunning = runState === "starting" || runState === "running";

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-gray-400 mt-1">SK Enmove Global MI Newsletter Pipeline</p>
          <div className="flex items-center gap-3 mt-2">
            <span className="text-gray-600 text-xs">Schedule: Every Wednesday 07:00 KST</span>
            <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
              apiConnected ? "bg-green-900/40 text-green-400"
                : waking ? "bg-yellow-900/40 text-yellow-400"
                : "bg-red-900/40 text-red-400"
            }`}>
              {waking ? (
                <>
                  <svg className="animate-spin w-3 h-3" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Waking up server...
                </>
              ) : (
                <>
                  <span className={`w-1.5 h-1.5 rounded-full ${apiConnected ? "bg-green-400" : "bg-red-400"}`} />
                  {apiConnected ? "API Connected" : "API Offline — click to retry"}
                </>
              )}
            </span>
            {!apiConnected && !waking && (
              <button onClick={wakeAndFetch} className="text-xs text-blue-400 underline ml-1">Retry</button>
            )}
          </div>
        </div>

        <div className="flex gap-3">
        {/* Start / Active toggle */}
        <button
          onClick={() => {
            if (isRunning) {
              setRunState("idle");
            } else {
              handleStartRun();
            }
          }}
          className={`px-5 py-3 rounded-lg font-medium transition-all flex items-center gap-2 text-sm ${
            isRunning
              ? "bg-blue-600 text-white ring-2 ring-blue-400/50"
              : "bg-red-600 hover:bg-red-700 hover:scale-105 text-white"
          }`}
        >
          {isRunning ? (
            <>
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-white" />
              </span>
              Active
            </>
          ) : (
            <>
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Start New Run
            </>
          )}
        </button>

        {/* One-time Send */}
        <button
          onClick={() => {
            if (confirm("6개국 뉴스레터를 즉시 생성하고 이메일 발송하시겠습니까?")) {
              handleStartRun();
            }
          }}
          disabled={isRunning}
          className={`px-5 py-3 rounded-lg font-medium transition-all flex items-center gap-2 text-sm ${
            isRunning
              ? "bg-gray-800 text-gray-600 cursor-not-allowed"
              : "bg-emerald-600 hover:bg-emerald-700 text-white hover:scale-105"
          }`}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          One-time Send
        </button>
        </div>
      </div>

      {/* Error Banner */}
      {runState === "error" && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 flex items-start gap-3">
          <span className="text-red-400 text-lg">!</span>
          <div>
            <p className="text-red-300 font-medium text-sm">Run failed to start</p>
            <p className="text-red-400/70 text-xs mt-1">{errorMsg}</p>
            <button
              onClick={() => { setRunState("idle"); setErrorMsg(""); }}
              className="text-xs text-red-400 underline mt-2"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Active Run Status */}
      {runs.find((r) => r.status === "running") && (
        <div className="bg-gray-900 rounded-xl p-6 border border-blue-800/50">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse" />
            <h2 className="text-lg font-semibold">Active Run</h2>
            <span className="text-sm text-gray-400">
              {runs.find((r) => r.status === "running")!.id.slice(0, 8)}...
            </span>
          </div>
          <div className="flex gap-1 mt-4">
            {Object.entries(PHASE_LABELS).map(([phase, label]) => {
              const activeRun = runs.find((r) => r.status === "running")!;
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

      {/* Target Countries (read-only, from Settings) */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Target Countries</h2>
          <a href="/settings" className="text-xs text-blue-400 hover:text-blue-300">
            Edit in Settings &rarr;
          </a>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
          {Object.entries(COUNTRY_FLAGS).map(([code, flag]) => (
            <div
              key={code}
              className="p-3 rounded-lg border border-gray-700 bg-gray-800/50 text-center"
            >
              <span className="text-2xl block">{flag}</span>
              <span className="text-xs mt-1 block text-gray-400">{COUNTRY_NAMES[code]}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Runs */}
      <div className="bg-gray-900 rounded-xl border border-gray-800">
        <div className="p-6 border-b border-gray-800">
          <h2 className="text-lg font-semibold">Recent Runs</h2>
        </div>
        <div className="divide-y divide-gray-800">
          {runs.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              {apiConnected
                ? 'No runs yet. Click "Start New Run" to begin.'
                : "Connect backend server to see run history."}
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
