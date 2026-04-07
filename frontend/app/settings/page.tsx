"use client";

import { useState, useEffect } from "react";

const ALL_COUNTRIES = [
  { code: "KR", name: "Korea", flag: "\uD83C\uDDF0\uD83C\uDDF7" },
  { code: "RU", name: "Russia", flag: "\uD83C\uDDF7\uD83C\uDDFA" },
  { code: "VN", name: "Vietnam", flag: "\uD83C\uDDFB\uD83C\uDDF3" },
  { code: "TH", name: "Thailand", flag: "\uD83C\uDDF9\uD83C\uDDED" },
  { code: "PH", name: "Philippines", flag: "\uD83C\uDDF5\uD83C\uDDED" },
  { code: "PK", name: "Pakistan", flag: "\uD83C\uDDF5\uD83C\uDDF0" },
];

const DAYS_OF_WEEK = [
  "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
];

interface CountryRecipients {
  country: string;
  recipients: string[];
}

interface Settings {
  schedule: {
    frequency: string;
    day_of_week: string;
    time: string;
    countries: string[];
    is_active: boolean;
    country_recipients: CountryRecipients[];
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
  const [globalRecipients, setGlobalRecipients] = useState("");
  const [recipients, setRecipients] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

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

    const r: Record<string, string> = {};
    for (const cr of data.schedule.country_recipients || []) {
      if (cr.country === "ALL") {
        setGlobalRecipients(cr.recipients.join(", "));
      } else {
        r[cr.country] = cr.recipients.join(", ");
      }
    }
    setRecipients(r);
  }

  useEffect(() => {
    fetchSettings();
  }, []);

  async function fetchSettings() {
    // 1. Always load localStorage first (instant, reliable)
    const local = loadFromLocal();
    if (local) {
      applySettings(local);
    }

    // 2. Then try API — only overwrite if API has recipients data
    try {
      const res = await fetch("/api/settings");
      if (res.ok) {
        const data: Settings = await res.json();
        const apiHasRecipients = (data.schedule.country_recipients || []).length > 0;

        if (apiHasRecipients) {
          // API has real data — use it and sync to localStorage
          applySettings(data);
          saveToLocal(data.schedule);
        } else if (local) {
          // API has no recipients but localStorage does — push local to API
          const localRecipients = local.schedule?.country_recipients || [];
          if (localRecipients.length > 0) {
            fetch("/api/settings", {
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

  async function saveSettings() {
    setSaving(true);
    try {
      const countryRecipients = Object.entries(recipients)
        .filter(([_, v]) => v.trim())
        .map(([country, emailStr]) => ({
          country,
          recipients: emailStr.split(",").map((e) => e.trim()).filter(Boolean),
        }));

      if (globalRecipients.trim()) {
        countryRecipients.unshift({
          country: "ALL",
          recipients: globalRecipients.split(",").map((e) => e.trim()).filter(Boolean),
        });
      }

      const settingsPayload = {
        frequency,
        day_of_week: dayOfWeek,
        time,
        countries: activeCountries,
        is_active: isActive,
        country_recipients: countryRecipients,
      };

      // 1. Save to localStorage (instant, never fails)
      saveToLocal(settingsPayload);

      // 2. Save to API (Supabase) — await with timeout
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        const res = await fetch("/api/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(settingsPayload),
          signal: controller.signal,
        });
        clearTimeout(timeout);
        if (res.ok) {
          setSaved(true);
          setSaving(false);
          setTimeout(() => setSaved(false), 2000);
          return;
        }
      } catch {
        // API failed — but localStorage saved
      }

      // Show saved (localStorage at minimum)
      setSaved(true);
      setSaving(false);
      setTimeout(() => setSaved(false), 2000);
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
          <p className="text-gray-400 mt-1">Configure schedule, countries, and recipients</p>
        </div>
        <button
          onClick={saveSettings}
          disabled={saving}
          className="px-6 py-3 bg-red-600 hover:bg-red-700 disabled:bg-gray-700 text-white rounded-lg font-medium transition-colors"
        >
          {saving ? "Saving..." : saved ? "Saved!" : "Save Settings"}
        </button>
      </div>

      {/* Schedule */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold">Schedule</h2>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-sm text-gray-400">Active</span>
            <button
              onClick={() => setIsActive(!isActive)}
              className={`w-11 h-6 rounded-full transition-colors ${
                isActive ? "bg-green-600" : "bg-gray-700"
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full bg-white transition-transform ${
                  isActive ? "translate-x-5" : "translate-x-0.5"
                }`}
              />
            </button>
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Frequency</label>
            <select
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">Day of Week</label>
            <select
              value={dayOfWeek}
              onChange={(e) => setDayOfWeek(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
            >
              {DAYS_OF_WEEK.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">Time (KST)</label>
            <input
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">Collection Period</label>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
            >
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
              <option value={60}>Last 60 days</option>
              <option value={90}>Last 90 days</option>
            </select>
          </div>
        </div>
      </div>

      {/* Recipients */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h2 className="text-lg font-semibold mb-6">Recipients</h2>

        {/* Global recipients - all countries */}
        <div className="p-4 bg-gray-800/80 rounded-lg border border-gray-700 mb-6">
          <label className="block text-sm font-medium text-white mb-1">All Countries (common)</label>
          <p className="text-gray-500 text-xs mb-3">Every newsletter will be sent to these addresses.</p>
          <input
            type="text"
            placeholder="team@company.com, manager@company.com"
            value={globalRecipients}
            onChange={(e) => setGlobalRecipients(e.target.value)}
            className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Per-country additional recipients */}
        <p className="text-gray-500 text-xs mb-3">Country-specific (additional recipients for that country only):</p>
        <div className="space-y-2">
          {ALL_COUNTRIES.map(({ code, name, flag }) => (
            <div key={code} className="flex items-center gap-3 px-4 py-3 bg-gray-800/30 rounded-lg">
              <div className="flex items-center gap-2 w-32 shrink-0">
                <span className="text-lg">{flag}</span>
                <span className="text-sm text-gray-300">{name}</span>
              </div>
              <input
                type="text"
                placeholder="additional@company.com"
                value={recipients[code] || ""}
                onChange={(e) =>
                  setRecipients((prev) => ({ ...prev, [code]: e.target.value }))
                }
                className="flex-1 bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-400 placeholder-gray-700 focus:border-blue-500 focus:outline-none"
              />
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
            <div
              key={key}
              className={`p-4 rounded-lg border ${
                settings?.api_keys_configured[key]
                  ? "border-green-800 bg-green-900/20"
                  : "border-yellow-800 bg-yellow-900/20"
              }`}
            >
              <div className="flex items-center gap-2">
                <div
                  className={`w-2 h-2 rounded-full ${
                    settings?.api_keys_configured[key] ? "bg-green-500" : "bg-yellow-500"
                  }`}
                />
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
