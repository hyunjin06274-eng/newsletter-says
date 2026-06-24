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
  { code: "AE", name: "UAE", flag: "\uD83C\uDDE6\uD83C\uDDEA" },
  { code: "SA", name: "Saudi Arabia", flag: "\uD83C\uDDF8\uD83C\uDDE6" },
  { code: "OM", name: "Oman", flag: "\uD83C\uDDF4\uD83C\uDDF2" },
  { code: "EG", name: "Egypt", flag: "\uD83C\uDDEA\uD83C\uDDEC" },
  { code: "MY", name: "Malaysia", flag: "\uD83C\uDDF2\uD83C\uDDFE" },
  { code: "KH", name: "Cambodia", flag: "\uD83C\uDDF0\uD83C\uDDED" },
  { code: "LA", name: "Laos", flag: "\uD83C\uDDF1\uD83C\uDDE6" },
  { code: "CL", name: "Chile", flag: "\uD83C\uDDE8\uD83C\uDDF1" },
  { code: "AU", name: "Australia", flag: "\uD83C\uDDE6\uD83C\uDDFA" },
  { code: "IL", name: "Israel", flag: "\uD83C\uDDEE\uD83C\uDDF1" },
  { code: "MN", name: "Mongolia", flag: "\uD83C\uDDF2\uD83C\uDDF3" },
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
  const [cronInfo, setCronInfo] = useState("");

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
        setGlobalTo((cr.to || []).join("\n"));
        setGlobalCc((cr.cc || []).join("\n"));
      } else {
        to[cr.country] = (cr.to || []).join("\n");
        cc[cr.country] = (cr.cc || []).join("\n");
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
      // Load settings (from Render) and recipients table (from Vercel → Supabase directly) in parallel
      const [settingsRes, recipientsRes] = await Promise.allSettled([
        apiFetch("/api/settings"),
        fetch("/api/recipients"),  // Next.js API route — Vercel calls Supabase directly, no Render needed
      ]);

      let settingsData: Settings | null = null;
      if (settingsRes.status === "fulfilled" && settingsRes.value.ok) {
        settingsData = await settingsRes.value.json();
      }

      // Parse recipients table rows (these are always TO)
      let recipientRows: CountryRecipients[] = [];
      if (recipientsRes.status === "fulfilled" && recipientsRes.value.ok) {
        const rData = await recipientsRes.value.json();
        recipientRows = rData.recipients || [];
      }

      if (settingsData) {
        // Merge: settings is primary, recipients table adds to TO if not already set
        const merged = { ...settingsData };
        const existingCountries = new Set((merged.schedule.country_recipients || []).map((cr) => cr.country));
        const hasAnySavedRecipients = existingCountries.size > 0;

        for (const row of recipientRows) {
          if (existingCountries.has(row.country)) {
            // Settings already has data for this country → settings is authoritative, skip
            continue;
          }
          if (hasAnySavedRecipients && row.country === "ALL") {
            // User has saved settings with some countries — don't re-inject legacy ALL recipients
            continue;
          }
          // No saved data for this country yet → pre-fill from recipients table (first-time only)
          merged.schedule.country_recipients = [
            ...(merged.schedule.country_recipients || []),
            { country: row.country, to: row.to, cc: [] },
          ];
        }

        applySettings(merged);
        saveToLocal(merged.schedule);
      } else if (recipientRows.length > 0) {
        // No settings data but have recipients table — build a minimal settings from it
        const fakeSchedule = local?.schedule || {
          frequency: "weekly", day_of_week: "Wednesday", time: "07:00",
          countries: ["KR","RU","VN","TH","PH","PK","GCC","CN","US","IN","JP"],
          is_active: true, country_recipients: [], min_total_score: 10, min_country_score: 3,
        };
        fakeSchedule.country_recipients = recipientRows;
        const fakeSettings: Settings = {
          schedule: fakeSchedule,
          api_keys_configured: {},
          gmail_authenticated: false,
        };
        applySettings(fakeSettings);
      }
    } catch {
      // API not available — localStorage data already loaded
    }
  }

  function parseEmails(str: string): string[] {
    return str.split(/[\n,]+/).map((e) => e.trim()).filter(Boolean);
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
          const resData = await res.json().catch(() => ({}));
          setSaved(true);
          setSaving(false);
          if (resData.cron) {
            setCronInfo(resData.cron_updated
              ? `GitHub Actions 크론 업데이트됨: ${resData.cron} (UTC)`
              : `설정 저장됨 (크론 업데이트 실패 — GH_DISPATCH_TOKEN 확인 필요)`
            );
          }
          setTimeout(() => { setSaved(false); setCronInfo(""); }, 5000);
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
          {cronInfo && (
            <p className="text-xs text-green-400 max-w-xs text-right">{cronInfo}</p>
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
          TO: 주 수신자 &nbsp;·&nbsp; CC: 참조 수신자 &nbsp;·&nbsp;
          <span className="text-gray-600">이메일 주소를 한 줄에 하나씩 입력 (쉼표도 가능)</span>
        </p>

        {/* Global recipients */}
        <div className="p-4 bg-gray-800/80 rounded-lg border border-gray-700 mb-6">
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm font-medium text-white">All Countries (공통 수신자)</label>
            <span className="text-xs text-gray-500">
              TO {globalTo ? parseEmails(globalTo).length : 0}명
              {globalCc ? ` · CC ${parseEmails(globalCc).length}명` : ""}
            </span>
          </div>
          <p className="text-gray-500 text-xs mb-3">모든 국가 뉴스레터에 공통으로 발송됩니다. 이메일 주소를 한 줄에 하나씩 입력하세요.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">TO</label>
              <textarea
                rows={Math.max(3, parseEmails(globalTo).length + 1)}
                placeholder={"team@company.com\nmanager@company.com"}
                value={globalTo}
                onChange={(e) => setGlobalTo(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none resize-none font-mono leading-relaxed"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">CC</label>
              <textarea
                rows={Math.max(3, parseEmails(globalCc).length + 1)}
                placeholder={"cc@company.com"}
                value={globalCc}
                onChange={(e) => setGlobalCc(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none resize-none font-mono leading-relaxed"
              />
            </div>
          </div>
        </div>

        {/* Per-country recipients */}
        <div className="flex items-center justify-between mb-3">
          <p className="text-gray-500 text-xs">
            국가별 추가 수신자 (해당 국가 뉴스레터에만 발송, 공통 수신자에 더해집니다):
          </p>
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-full bg-green-500/70" /> 발송
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-full bg-gray-600" /> 제외
            </span>
            <button
              onClick={() => setActiveCountries(ALL_COUNTRIES.map((c) => c.code))}
              className="text-blue-400 hover:text-blue-300 underline"
            >전체 선택</button>
            <button
              onClick={() => setActiveCountries([])}
              className="text-gray-500 hover:text-gray-400 underline"
            >전체 해제</button>
          </div>
        </div>
        <div className="space-y-1">
          {ALL_COUNTRIES.map(({ code, name, flag }) => {
            const isActive = activeCountries.includes(code);
            const toEmails = parseEmails(recipientsTo[code] || "");
            const ccEmails = parseEmails(recipientsCc[code] || "");
            const totalCount = toEmails.length + ccEmails.length;
            return (
              <div
                key={code}
                className={`rounded-lg border overflow-hidden transition-all ${
                  isActive
                    ? "border-gray-700 bg-gray-800/20"
                    : "border-gray-800/50 bg-gray-900/20 opacity-50"
                }`}
              >
                {/* Country header row */}
                <div className={`flex items-center justify-between px-4 py-2.5 ${isActive ? "bg-gray-800/40" : "bg-gray-800/20"}`}>
                  <div className="flex items-center gap-3">
                    {/* Send toggle */}
                    <button
                      onClick={() => toggleCountry(code)}
                      title={isActive ? "클릭하여 발송 제외" : "클릭하여 발송 포함"}
                      className={`relative flex-shrink-0 w-9 h-5 rounded-full transition-colors ${
                        isActive ? "bg-green-600" : "bg-gray-700"
                      }`}
                    >
                      <span
                        className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                          isActive ? "translate-x-4" : "translate-x-0.5"
                        }`}
                      />
                    </button>
                    <span className="text-base">{flag}</span>
                    <span className={`text-sm font-medium ${isActive ? "text-gray-300" : "text-gray-600"}`}>{name}</span>
                    <span className="text-xs text-gray-700">({code})</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {!isActive && (
                      <span className="text-xs text-gray-600 bg-gray-800 px-2 py-0.5 rounded-full">발송 제외</span>
                    )}
                    {isActive && totalCount > 0 && (
                      <span className="text-xs text-gray-500 bg-gray-700/50 px-2 py-0.5 rounded-full">
                        TO {toEmails.length}{ccEmails.length > 0 ? ` · CC ${ccEmails.length}` : ""}
                      </span>
                    )}
                  </div>
                </div>
                {/* TO / CC fields — only show when active */}
                {isActive && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-gray-800">
                    <div className="bg-gray-900/60 px-4 py-2">
                      <label className="block text-xs text-gray-500 mb-1">TO</label>
                      <textarea
                        rows={Math.max(2, toEmails.length + 1)}
                        placeholder={"to@company.com"}
                        value={recipientsTo[code] || ""}
                        onChange={(e) => setRecipientsTo((prev) => ({ ...prev, [code]: e.target.value }))}
                        className="w-full bg-transparent border border-gray-700/50 rounded px-2 py-1.5 text-xs text-gray-300 placeholder-gray-700 focus:border-blue-500 focus:outline-none resize-none font-mono leading-relaxed"
                      />
                    </div>
                    <div className="bg-gray-900/40 px-4 py-2">
                      <label className="block text-xs text-gray-500 mb-1">CC</label>
                      <textarea
                        rows={Math.max(2, ccEmails.length + 1)}
                        placeholder={"cc@company.com"}
                        value={recipientsCc[code] || ""}
                        onChange={(e) => setRecipientsCc((prev) => ({ ...prev, [code]: e.target.value }))}
                        className="w-full bg-transparent border border-gray-700/50 rounded px-2 py-1.5 text-xs text-gray-300 placeholder-gray-700 focus:border-blue-500 focus:outline-none resize-none font-mono leading-relaxed"
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
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
