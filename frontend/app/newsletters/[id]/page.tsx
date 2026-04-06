"use client";

import { useState, useEffect, use } from "react";

const COUNTRY_NAMES: Record<string, string> = {
  KR: "Korea", RU: "Russia", VN: "Vietnam",
  TH: "Thailand", PH: "Philippines", PK: "Pakistan",
};

export default function NewsletterPreviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [html, setHtml] = useState("");
  const [country, setCountry] = useState("KR");

  useEffect(() => {
    fetchNewsletter();
  }, [id, country]);

  async function fetchNewsletter() {
    try {
      const res = await fetch(`/api/newsletters/${id}?country=${country}`);
      if (res.ok) {
        const data = await res.json();
        setHtml(data.html || "");
      }
    } catch {
      setHtml("<p>Newsletter not available</p>");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <a href={`/runs/${id}`} className="text-gray-400 hover:text-white">&larr; Back</a>
        <h1 className="text-2xl font-bold">Newsletter Preview</h1>
        <select
          value={country}
          onChange={(e) => setCountry(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1 text-sm"
        >
          {Object.entries(COUNTRY_NAMES).map(([code, name]) => (
            <option key={code} value={code}>{name}</option>
          ))}
        </select>
      </div>
      <div className="bg-white rounded-xl overflow-hidden">
        <iframe
          srcDoc={html}
          className="w-full h-[80vh]"
          title="Newsletter"
        />
      </div>
    </div>
  );
}
