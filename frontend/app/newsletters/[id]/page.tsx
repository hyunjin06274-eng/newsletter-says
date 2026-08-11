"use client";

import { useState, useEffect, use } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { apiFetch } from "../../api-client";

const COUNTRY_NAMES: Record<string, string> = {
  KR: "한국", RU: "러시아", VN: "베트남",
  TH: "태국", PH: "필리핀", PK: "파키스탄",
  GCC: "GCC", CN: "중국", US: "미국",
  IN: "인도", JP: "일본",
  AE: "UAE", SA: "사우디", OM: "오만", EG: "이집트",
  MY: "말레이시아", KH: "캄보디아", LA: "라오스",
  CL: "칠레", AU: "호주", IL: "이스라엘", MN: "몽골",
};

export default function NewsletterPreviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const searchParams = useSearchParams();
  const router = useRouter();

  // Initial country from ?country= query param, default KR
  const initialCountry = searchParams.get("country") || "KR";
  const [country, setCountry] = useState(initialCountry);
  const [webHtml, setWebHtml] = useState("");
  const [mode, setMode] = useState<"unified" | "legacy" | "loading">("loading");

  // Fetch the web version (unified tab UI or legacy fallback)
  useEffect(() => {
    fetchWebNewsletter();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Sync ?country= query param when country tab changes (legacy mode only)
  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("country", country);
    router.replace(url.pathname + url.search, { scroll: false });
  }, [country, router]);

  async function fetchWebNewsletter() {
    setMode("loading");
    try {
      // Try unified web endpoint first (/newsletters/{id}/web?country=XX)
      const res = await apiFetch(`/api/newsletters/${id}/web?country=${country}`);
      if (res.ok) {
        const data = await res.json();
        setWebHtml(data.html || "");
        setMode(data.mode === "unified" ? "unified" : "legacy");
        return;
      }
    } catch {
      // fall through to legacy
    }

    // Fallback: legacy per-country endpoint
    try {
      const res = await apiFetch(`/api/newsletters/${id}?country=${country}`);
      if (res.ok) {
        const data = await res.json();
        setWebHtml(data.html || "");
        setMode("legacy");
        return;
      }
    } catch {
      setWebHtml("<p style='padding:24px;color:#999;'>뉴스레터를 불러올 수 없습니다.</p>");
      setMode("legacy");
    }
  }

  const isUnified = mode === "unified";

  return (
    <div className="space-y-4">
      {/* Header bar */}
      <div className="flex items-center gap-4 flex-wrap">
        <a href={`/runs/${id}`} className="text-gray-400 hover:text-white text-sm">
          &larr; Back
        </a>
        <h1 className="text-2xl font-bold">Newsletter Preview</h1>

        {/* Mode badge */}
        {mode !== "loading" && (
          <span
            className={`text-xs px-2 py-1 rounded font-mono ${
              isUnified
                ? "bg-green-900 text-green-300"
                : "bg-gray-700 text-gray-300"
            }`}
          >
            {isUnified ? "통합 (탭 UI)" : "레거시 (국가별)"}
          </span>
        )}

        {/* Country selector — only shown in legacy mode */}
        {!isUnified && mode !== "loading" && (
          <select
            value={country}
            onChange={(e) => {
              setCountry(e.target.value);
              // In legacy mode, re-fetch when country changes
              apiFetch(`/api/newsletters/${id}?country=${e.target.value}`)
                .then((r) => r.json())
                .then((d) => setWebHtml(d.html || ""))
                .catch(() => {});
            }}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1 text-sm"
          >
            {Object.entries(COUNTRY_NAMES).map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
        )}

        {/* In unified mode, show a note that tab switching is inside the iframe */}
        {isUnified && (
          <span className="text-xs text-gray-400">
            아래 탭을 클릭해 국가를 전환하세요 (?country= 쿼리 파라미터로 초기 탭 지정)
          </span>
        )}
      </div>

      {/* Preview frame */}
      <div className="bg-white rounded-xl overflow-hidden">
        {mode === "loading" ? (
          <div className="flex items-center justify-center h-64 text-gray-400">
            Loading…
          </div>
        ) : (
          <iframe
            srcDoc={webHtml}
            className="w-full"
            style={{ height: "80vh" }}
            title="Newsletter Preview"
            sandbox="allow-scripts allow-same-origin"
          />
        )}
      </div>
    </div>
  );
}
