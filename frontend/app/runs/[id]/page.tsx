"use client";

import { useState, useEffect, use } from "react";

const COUNTRY_FLAGS: Record<string, string> = {
  KR: "\uD83C\uDDF0\uD83C\uDDF7", RU: "\uD83C\uDDF7\uD83C\uDDFA", VN: "\uD83C\uDDFB\uD83C\uDDF3",
  TH: "\uD83C\uDDF9\uD83C\uDDED", PH: "\uD83C\uDDF5\uD83C\uDDED", PK: "\uD83C\uDDF5\uD83C\uDDF0",
};
const COUNTRY_NAMES: Record<string, string> = {
  KR: "Korea", RU: "Russia", VN: "Vietnam",
  TH: "Thailand", PH: "Philippines", PK: "Pakistan",
};

const PHASES = [
  "keywords", "collection", "merge", "scoring",
  "enrichment", "grouping", "writing", "auditing", "sending",
];
const PHASE_LABELS: Record<string, string> = {
  keywords: "Keywords", collection: "Collection", merge: "Merge & Dedupe",
  scoring: "Scoring", enrichment: "Enrichment", grouping: "Grouping",
  writing: "Newsletter Writing", auditing: "Quality Audit", sending: "Email Sending",
};

interface RunDetail {
  id: string;
  countries: string[];
  date_str: string;
  status: string;
  current_phase: string;
  phase_status: Record<string, string>;
  errors: string[];
  audit_iterations: number;
  total_collected: number;
  total_filtered: number;
  total_sent: number;
  created_at: string;
  completed_at: string | null;
}

interface SSEEvent {
  type: string;
  phase?: string;
  ts: string;
  [key: string]: unknown;
}

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [previewCountry, setPreviewCountry] = useState<string>("");
  const [previewHtml, setPreviewHtml] = useState<string>("");

  useEffect(() => {
    fetchRun();
    const interval = setInterval(fetchRun, 3000);
    return () => clearInterval(interval);
  }, [id]);

  useEffect(() => {
    if (!run || run.status !== "running") return;

    const evtSource = new EventSource(`/api/runs/${id}/events`);
    evtSource.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => [...prev, data]);
    };
    evtSource.onerror = () => evtSource.close();
    return () => evtSource.close();
  }, [id, run?.status]);

  async function fetchRun() {
    try {
      const res = await fetch(`/api/runs/${id}`);
      if (res.ok) {
        const data = await res.json();
        setRun(data);
        if (!previewCountry && data.countries?.length > 0) {
          setPreviewCountry(data.countries[0]);
        }
      }
    } catch {
      // API not available
    }
  }

  async function loadPreview(country: string) {
    setPreviewCountry(country);
    try {
      const res = await fetch(`/api/newsletters/${id}?country=${country}`);
      if (res.ok) {
        const data = await res.json();
        setPreviewHtml(data.html || "");
      }
    } catch {
      setPreviewHtml("");
    }
  }

  if (!run) {
    return <div className="text-center py-20 text-gray-500">Loading...</div>;
  }

  const currentPhaseIdx = PHASES.indexOf(run.current_phase);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <a href="/runs" className="text-gray-400 hover:text-white">&larr;</a>
            <h1 className="text-3xl font-bold">Run {run.date_str}</h1>
          </div>
          <p className="text-gray-400 mt-1 text-sm">ID: {run.id}</p>
        </div>
        <span
          className={`px-4 py-2 rounded-lg text-sm font-medium ${
            run.status === "completed"
              ? "bg-green-900/50 text-green-300"
              : run.status === "running"
              ? "bg-blue-900/50 text-blue-300 animate-pulse"
              : run.status === "failed"
              ? "bg-red-900/50 text-red-300"
              : "bg-gray-700 text-gray-300"
          }`}
        >
          {run.status.toUpperCase()}
        </span>
      </div>

      {/* Phase Timeline */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h2 className="text-lg font-semibold mb-4">Pipeline Progress</h2>
        <div className="space-y-2">
          {PHASES.map((phase, idx) => {
            const status = run.phase_status[phase] || "pending";
            const isActive = phase === run.current_phase && run.status === "running";
            return (
              <div key={phase} className="flex items-center gap-3">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                    status === "done"
                      ? "bg-green-600 text-white"
                      : isActive
                      ? "bg-blue-600 text-white animate-pulse"
                      : status === "failed"
                      ? "bg-red-600 text-white"
                      : "bg-gray-800 text-gray-500"
                  }`}
                >
                  {status === "done" ? "\u2713" : idx + 1}
                </div>
                <span className={isActive ? "text-white font-medium" : "text-gray-400"}>
                  {PHASE_LABELS[phase]}
                </span>
                {phase === "auditing" && run.audit_iterations > 0 && (
                  <span className="text-xs text-yellow-400 ml-2">
                    (iteration {run.audit_iterations})
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 text-center">
          <div className="text-3xl font-bold text-blue-400">{run.total_collected}</div>
          <div className="text-sm text-gray-400 mt-1">Collected</div>
        </div>
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 text-center">
          <div className="text-3xl font-bold text-yellow-400">{run.total_filtered}</div>
          <div className="text-sm text-gray-400 mt-1">Filtered</div>
        </div>
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 text-center">
          <div className="text-3xl font-bold text-green-400">{run.total_sent}</div>
          <div className="text-sm text-gray-400 mt-1">Sent</div>
        </div>
      </div>

      {/* Newsletter Preview */}
      {run.status === "completed" && (
        <div className="bg-gray-900 rounded-xl border border-gray-800">
          <div className="p-4 border-b border-gray-800 flex items-center gap-3">
            <h2 className="text-lg font-semibold">Newsletter Preview</h2>
            <div className="flex gap-2">
              {run.countries.map((c) => (
                <button
                  key={c}
                  onClick={() => loadPreview(c)}
                  className={`px-3 py-1 rounded text-sm ${
                    previewCountry === c
                      ? "bg-red-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:text-white"
                  }`}
                >
                  {COUNTRY_FLAGS[c]} {COUNTRY_NAMES[c]}
                </button>
              ))}
            </div>
          </div>
          {previewHtml ? (
            <iframe
              srcDoc={previewHtml}
              className="w-full h-[600px] bg-white rounded-b-xl"
              title="Newsletter Preview"
            />
          ) : (
            <div className="p-12 text-center text-gray-500">
              Select a country to preview the newsletter
            </div>
          )}
        </div>
      )}

      {/* Event Log */}
      {events.length > 0 && (
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
          <h2 className="text-lg font-semibold mb-4">Event Log</h2>
          <div className="space-y-2 max-h-64 overflow-y-auto font-mono text-sm">
            {events.map((evt, i) => (
              <div key={i} className="flex gap-3 text-gray-400">
                <span className="text-gray-600 shrink-0">
                  {new Date(evt.ts).toLocaleTimeString("ko-KR")}
                </span>
                <span className="text-blue-400">[{evt.type}]</span>
                <span>{evt.phase || ""}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Errors */}
      {run.errors.length > 0 && (
        <div className="bg-red-900/20 rounded-xl p-6 border border-red-800">
          <h2 className="text-lg font-semibold text-red-400 mb-3">Errors</h2>
          <ul className="space-y-2">
            {run.errors.map((err, i) => (
              <li key={i} className="text-sm text-red-300">{err}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
