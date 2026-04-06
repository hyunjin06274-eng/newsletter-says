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
  const [time, setTime] = useState("08:00");
  const [activeCountries, setActiveCountries] = useState<string[]>([]);
  const [isActive, setIsActive] = useState(true);
  const [days, setDays] = useState(30);
  const [recipients, setRecipients] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, []);

  async function fetchSettings() {
    try {
      const res = await fetch("/api/settings");
      if (res.ok) {
        const data: Settings = await res.json();
        setSettings(data);
        setFrequency(data.schedule.frequency);
        setDayOfWeek(data.schedule.day_of_week);
        setTime(data.schedule.time);
        setActiveCountries(data.schedule.countries);
        setIsActive(data.schedule.is_active);

        const r: Record<string, string> = {};
        for (const cr of data.schedule.country_recipients || []) {
          r[cr.country] = cr.recipients.join(", ");
        }
        setRecipients(r);
      }
    } catch {
      // API not available
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

      await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          frequency,
          day_of_week: dayOfWeek,
          time,
          countries: activeCountries,
          is_active: isActive,
          country_recipients: countryRecipients,
        }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error("Save failed:", e);
    }
    setSaving(false);
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

      {/* Countries & Recipients */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h2 className="text-lg font-semibold mb-6">Countries & Recipients</h2>
        <div className="space-y-4">
          {ALL_COUNTRIES.map(({ code, name, flag }) => (
            <div key={code} className="flex items-start gap-4 p-4 bg-gray-800/50 rounded-lg">
              <button
                onClick={() => toggleCountry(code)}
                className={`mt-1 w-5 h-5 rounded border flex items-center justify-center text-xs transition-colors ${
                  activeCountries.includes(code)
                    ? "bg-red-600 border-red-600 text-white"
                    : "border-gray-600 text-transparent"
                }`}
              >
                {activeCountries.includes(code) ? "\u2713" : ""}
              </button>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xl">{flag}</span>
                  <span className="font-medium">{name}</span>
                  <span className="text-gray-500 text-sm">({code})</span>
                </div>
                <input
                  type="text"
                  placeholder="recipient1@email.com, recipient2@email.com"
                  value={recipients[code] || ""}
                  onChange={(e) =>
                    setRecipients((prev) => ({ ...prev, [code]: e.target.value }))
                  }
                  className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-300 placeholder-gray-600"
                />
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
