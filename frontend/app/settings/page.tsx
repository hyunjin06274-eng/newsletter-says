"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "../api-client";

const ALL_COUNTRIES = [
  { code: "KR", name: "Korea", flag: "\uD83C\uDDF0\uD83C\uDDF7" },
  { code: "RU", name: "Russia", flag: "\uD83C\uDDF7\uD83C\uDDFA" },
  { code: "VN", name: "Vietnam", flag: "\uD83C\uDDFB\uD83C\uDDF3" },
  { code: "TH", name: "Thailand", flag: "\uD83C\uDDF9\uD83C\uDDED" },
  { code: "PH", name: "Philippines", flag: "\uD83C\uDDF5\uD83C\uDDED" },
  { code: "PK", name: "Pakistan", flag: "\uD83C\uDDF5\uD83C\uDDF0" },
  { code: "GCC", name: "GCC", flag: "\uD83C\uDDF8\uD83C\uDDE6" },
  { code: "CN", name: "China", flag: "\uD83C\uDDE8\uD83C\uDDF3" },
  { code: "US", name: "USA", flag: "\uD83C\uDDFA\uD83C\uDDF8" },
  { code: "IN", name: "India", flag: "\uD83C\uDDEE\uD83C\uDDF3" },
  { code: "JP", name: "Japan", flag: "\uD83C\uDDEF\uD83C\uDDF5" },
];

const DAYS_OF_WEEK = [
  "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
];

interface CountryRecipients {
  country: string;
  to: string[];
  cc: string[];
}

interface Settings {
  schedule: {
    frequency: string;
    day_of_week: string;
    time: string;
    countries: string[];
    is_active: boolean;
    country_recipients: CountryRecipients[];
    min_total_score: number;
    min_country_score: number;
  };
  api_keys_configured: Record<string, boolean>;
  gmail_authenticated: boolean;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [frequency, setFrequency] = useState("weekly");
  const [dayOfWeek, setDayOfWeek] = useState("Tuesday");
  const [time, setTime] = useState("09:00");
  const [activeCountries, setActiveCountries] = useState<string[]>([]);
  const [isActive, setIsActive] = useState(true);
  const [days, setDays] = useState(30);

  // Recipients: global TO/CC + per-country TO/CC
  const [globalTo, setGlobalTo] = useState("");
  const [globalCc, setGlobalCc] = useState("");
  const [recipientsTo, setRecipientsTo] = useState<Record<string, string>>({});
  const [recipientsCc, setRecipientsCc] = useState<Record<string, string>>({});

  // Scoring thresholds
  const [minTotalScore, setMinTotalScore] = useState(10);
  const [minCountryScore, setMinCountryScore] = useState(3);

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");

  const STORAGE_KEY = "newsletter-saas-settings";

  function loadFromLocal(): Settings | null {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  }

  function saveToLocal(data: Partial<Settings["schedule"]>) {
    try {
      const current = loadFromLocal();
      const merged: Settings = {
        schedule: { ...current?.schedule, ...data } as Settings["schedule"],
        api_keys_configured: current?.api_keys_configured || {},
        gmail_authenticated: current?.gmail_authenticated || false,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
    } catch {}
  }

  function applySettings(data: Settings) {
    setSettings(data);
    setFrequency(data.schedule.frequency);
    setDayOfWeek(data.schedule.day_of_week);
    setTime(data.schedule.time);
    setActiveCountries(data.schedule.countries);
    setIsActive(data.schedule.is_active);
    setMinTotalScore(data.schedule.min_total_score ?? 10);
    setMinCountryScore(data.schedule.min_country_score ?? 3);

    const to: Record<string, string> = {};
    const cc: Record<string, string> = {};
    for (const cr of data.schedule.country_recipients || []) {
      if (cr.country === "ALL") {
        setGlobalTo((cr.to || []).join(", "));
        setGlobalCc((cr.cc || []).join(", "));
      } else {
        to[cr.country] = (cr.to || []).join(", ");
        cc[cr.country] = (cr.cc || []).join(", ");
      }
    }
    setRecipientsTo(to);
    setRecipientsCc(cc);
  }

  useEffect(() => {
    fetchSettings();
  }, []);

  async function fetchSettings() {
    const local = loadFromLocal();
    if (local) applySettings(local);

    try {
      const res = await apiFetch("/api/settings");
      if (res.ok) {
        const data: Settings = await res.json();
        const apiHasRecipients = (data.schedule.country_recipients || []).length > 0;
        if (apiHasRecipients) {
          applySettings(data);
          saveToLocal(data.schedule);
        } else if (local) {
          const localRecipients = local.schedule?.country_recipients || [];
          if (localRecipients.length > 0) {
            apiFetch("/api/settings", {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(local.schedule),
            }).catch(() => {});
          }
        }
      }
    } catch {
      // API not available — localStorage data already loaded
    }
  }

  function parseEmails(str: string): string[] {
    return str.split(",").map((e) => e.trim()).filter(Boolean);
  }

  async function saveSettings() {
    setSaving(true);
    setSaveError("");
    try {
      const countryRecipients: CountryRecipients[] = [];

      if (globalTo.trim() || globalCc.trim()) {
        countryRecipients.push({
          country: "ALL",
          to: parseEmails(globalTo),
          cc: parseEmails(globalCc),
        });
      }

      for (const { code } of ALL_COUNTRIES) {
        const toStr = recipientsTo[code] || "";
        const ccStr = recipientsCc[code] || "";
        if (toStr.trim() || ccStr.trim()) {
          countryRecipients.push({
            country: code,
            to: parseEmails(toStr),
            cc: parseEmails(ccStr),
          });
        }
      }

      const settingsPayload = {
        frequency,
        day_of_week: dayOfWeek,
        time,
        countries: activeCountries,
        is_active: isActive,
        country_recipients: countryRecipients,
        min_total_score: minTotalScore,
        min_country_score: minCountryScore,
      };

      saveToLocal(settingsPayload);

      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        const res = await apiFetch("/api/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(settingsPayload),
          signal: controller.signal,
        });
        clearTimeout(timeout);
        if (res.ok) {
          setSaved(true);
          setSaving(false);
          setTimeout(() => setSaved(false), 3000);
          return;
        } else {
          const errText = await res.text().catch(() => "");
          setSaveError(`Server error ${res.status}: ${errText.slice(0, 100)}`);
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setSaveError(msg.includes("abort") ? "Request timed out — backend may be sleeping. Try again." : `Network error: ${msg}`);
      }

      setSaving(false);
    } catch (e) {
      console.error("Save failed:", e);
      setSaving(false);
    }
  }

  function toggleCountry(code: string) {
    setActiveCountries((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  }

  return (
    <div className="space-y-8 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Settings</h1>
          <p className="text-gray-400 mt-1">Configure schedule, countries, recipients, and scoring</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <button
            onClick={saveSettings}
            disabled={saving}
            className={`px-6 py-3 rounded-lg font-medium transition-colors text-white ${
              saved ? "bg-green-600" : saving ? "bg-gray-700" : "bg-red-600 hover:bg-red-700"
            }`}
          >
            {saving ? "Saving..." : saved ? "✓ Saved to server" : "Save Settings"}
          </button>
          {saveError && (
            <p className="text-xs text-red-400 max-w-xs text-right">{saveError}</p>
          )}
        </div>
      </div>

      {/* Schedule */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold">Schedule</h2>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-sm text-gray-400">Active</span>
            <button
              onClick={() => setIsActive(!isActive)}
              className={`w-11 h-6 rounded-full transition-colors ${isActive ? "bg-green-600" : "bg-gray-700"}`}
            >
              <div className={`w-5 h-5 rounded-full bg-white transition-transform ${isActive ? "translate-x-5" : "translate-x-0.5"}`} />
            </button>
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Frequency</label>
            <select value={frequency} onChange={(e) => setFrequency(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white">
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">Day of Week</label>
            <select value={dayOfWeek} onChange={(e) => setDayOfWeek(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white">
              {DAYS_OF_WEEK.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">Time (KST)</label>
            <input type="time" value={time} onChange={(e) => setTime(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white" />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">Collection Period</label>
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white">
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
              <option value={60}>Last 60 days</option>
              <option value={90}>Last 90 days</option>
            </select>
          </div>
        </div>
      </div>

      {/* Article Filtering / Scoring Thresholds */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h2 className="text-lg font-semibold mb-2">Article Filtering</h2>
        <p className="text-gray-500 text-xs mb-6">
          LLM scores each article on three dimensions (0–10 each, total 0–30). Adjust thresholds to allow more or fewer articles per country.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Min Total Score */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-sm font-medium text-gray-300">
                Min Total Score
                <span className="text-gray-500 text-xs font-normal ml-2">(Sales + Country + Actionability, out of 30)</span>
              </label>
              <span className="text-white font-bold text-lg w-8 text-right">{minTotalScore}</span>
            </div>
            <input
              type="range" min={3} max={25} step={1}
              value={minTotalScore}
              onChange={(e) => setMinTotalScore(Number(e.target.value))}
              className="w-full accent-red-500"
            />
            <div className="flex justify-between text-xs text-gray-600 mt-1">
              <span>3 (관대)</span>
              <span className="text-yellow-600">10 (기본값)</span>
              <span>25 (엄격)</span>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              낮추면 더 많은 기사가 통과됩니다. KR/VN 기사 부족 시 8–10 권장.
            </p>
          </div>

          {/* Min Country Score */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-sm font-medium text-gray-300">
                Min Country Specificity Score
                <span className="text-gray-500 text-xs font-normal ml-2">(Country dimension, out of 10)</span>
              </label>
              <span className="text-white font-bold text-lg w-8 text-right">{minCountryScore}</span>
            </div>
            <input
              type="range" min={1} max={10} step={1}
              value={minCountryScore}
              onChange={(e) => setMinCountryScore(Number(e.target.value))}
              className="w-full accent-red-500"
            />
            <div className="flex justify-between text-xs text-gray-600 mt-1">
              <span>1 (관대)</span>
              <span className="text-yellow-600">3 (기본값)</span>
              <span>10 (엄격)</span>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              낮추면 해당 국가 언급이 적은 기사도 허용됩니다. 1–2로 낮추면 지역 기사 포함.
            </p>
          </div>
        </div>

        <div className="mt-4 p-3 bg-gray-800/50 rounded-lg border border-gray-700">
          <p className="text-xs text-gray-400">
            현재 설정: 총점 <span className="text-white font-medium">{minTotalScore}</span> 이상 &amp;&amp;
            국가 점수 <span className="text-white font-medium">{minCountryScore}</span> 이상인 기사만 뉴스레터에 포함
            <span className="text-gray-600 ml-2">(global 분류 기사는 항상 제외)</span>
          </p>
        </div>
      </div>

      {/* Recipients */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h2 className="text-lg font-semibold mb-2">Recipients</h2>
        <p className="text-gray-500 text-xs mb-6">
          TO: 주 수신자 (이름 표시됨) &nbsp;·&nbsp; CC: 참조 수신자 (이름 표시됨)
        </p>

        {/* Global recipients */}
        <div className="p-4 bg-gray-800/80 rounded-lg border border-gray-700 mb-6">
          <label className="block text-sm font-medium text-white mb-1">All Countries (공통 수신자)</label>
          <p className="text-gray-500 text-xs mb-3">모든 국가 뉴스레터에 공통으로 발송됩니다.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">TO</label>
              <input
                type="text"
                placeholder="team@company.com, manager@company.com"
                value={globalTo}
                onChange={(e) => setGlobalTo(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">CC</label>
              <input
                type="text"
                placeholder="cc@company.com"
                value={globalCc}
                onChange={(e) => setGlobalCc(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Per-country recipients */}
        <p className="text-gray-500 text-xs mb-3">국가별 추가 수신자 (해당 국가 뉴스레터에만 발송):</p>
        <div className="space-y-2">
          {ALL_COUNTRIES.map(({ code, name, flag }) => (
            <div key={code} className="px-4 py-3 bg-gray-800/30 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-lg">{flag}</span>
                <span className="text-sm font-medium text-gray-300">{name}</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pl-7">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">TO</label>
                  <input
                    type="text"
                    placeholder="to@company.com"
                    value={recipientsTo[code] || ""}
                    onChange={(e) => setRecipientsTo((prev) => ({ ...prev, [code]: e.target.value }))}
                    className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-400 placeholder-gray-700 focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">CC</label>
                  <input
                    type="text"
                    placeholder="cc@company.com"
                    value={recipientsCc[code] || ""}
                    onChange={(e) => setRecipientsCc((prev) => ({ ...prev, [code]: e.target.value }))}
                    className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-400 placeholder-gray-700 focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* API Status */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h2 className="text-lg font-semibold mb-4">API Keys Status</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { key: "anthropic", label: "Anthropic Claude", desc: "Scoring & Newsletter" },
            { key: "google", label: "Google Gemini", desc: "Keywords & Gmail" },
            { key: "tavily", label: "Tavily", desc: "SNS Collection" },
          ].map(({ key, label, desc }) => (
            <div key={key} className={`p-4 rounded-lg border ${
              settings?.api_keys_configured[key]
                ? "border-green-800 bg-green-900/20"
                : "border-yellow-800 bg-yellow-900/20"
            }`}>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${settings?.api_keys_configured[key] ? "bg-green-500" : "bg-yellow-500"}`} />
                <span className="font-medium text-sm">{label}</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
