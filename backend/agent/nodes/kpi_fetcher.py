"""KPI data fetcher — exchange rates (live API) + static reference data."""

import asyncio
import json
import logging
import urllib.request
from datetime import datetime

from backend.agent.state import NewsletterState

logger = logging.getLogger(__name__)

# ── 국가 → ISO 코드 매핑 ────────────────────────────────────────────────────
CURRENCY_CODE: dict[str, str] = {
    "KR": "KRW", "CN": "CNY", "US": "USD", "IN": "INR",
    "JP": "JPY", "RU": "RUB", "VN": "VND", "TH": "THB",
    "PH": "PHP", "PK": "PKR", "GCC": "SAR",
}

CURRENCY_LABEL: dict[str, str] = {
    "KR": "원/달러", "CN": "위안/달러", "US": "달러 (기준)",
    "IN": "루피/달러", "JP": "엔/달러", "RU": "루블/달러",
    "VN": "동/달러", "TH": "바트/달러", "PH": "페소/달러",
    "PK": "루피/달러", "GCC": "리얄/달러",
}

WB_ISO3: dict[str, str] = {
    "KR": "KOR", "CN": "CHN", "US": "USA", "IN": "IND",
    "JP": "JPN", "RU": "RUS", "VN": "VNM", "TH": "THA",
    "PH": "PHL", "PK": "PAK", "GCC": "SAU",
}

# ── 기준금리 (정적 — 각국 중앙은행 기준, 분기마다 확인 권장) ────────────────
# 출처: 각국 중앙은행 공시 기준 (2025년 기준 최신치)
INTEREST_RATES: dict[str, dict] = {
    "KR":  {"rate": 2.75,  "label": "한국은행 기준금리",        "updated": "2025.02"},
    "CN":  {"rate": 3.10,  "label": "PBOC 1년 LPR",            "updated": "2025.01"},
    "US":  {"rate": 4.33,  "label": "Fed 연방기금금리 (상단)",  "updated": "2025.05"},
    "IN":  {"rate": 6.25,  "label": "RBI 레포금리",             "updated": "2025.02"},
    "JP":  {"rate": 0.50,  "label": "BOJ 정책금리",             "updated": "2025.01"},
    "RU":  {"rate": 21.0,  "label": "러시아 중앙은행 기준금리", "updated": "2025.03"},
    "VN":  {"rate": 4.50,  "label": "SBV 기준금리",             "updated": "2024.06"},
    "TH":  {"rate": 2.50,  "label": "BOT 정책금리",             "updated": "2024.10"},
    "PH":  {"rate": 5.75,  "label": "BSP 역레포금리",           "updated": "2025.04"},
    "PK":  {"rate": 11.0,  "label": "SBP 정책금리",             "updated": "2025.05"},
    "GCC": {"rate": 5.50,  "label": "SAMA 레포금리(사우디)",     "updated": "2025.05"},
}

# ── 월간 차량 등록 대수 (정적 — 최신 집계 기준, OICA / 각국 자동차 협회) ──
# mom_pct: 전월 대비 증감률(%), period: 집계 기간
VEHICLE_REG: dict[str, dict] = {
    "KR":  {"monthly": 134000, "mom_pct": -2.3,  "unit": "대",  "period": "2025.04"},
    "CN":  {"monthly": 2850000,"mom_pct": +5.1,  "unit": "대",  "period": "2025.04"},
    "US":  {"monthly": 1380000,"mom_pct": +1.8,  "unit": "대",  "period": "2025.04"},
    "IN":  {"monthly": 370000, "mom_pct": +3.2,  "unit": "대",  "period": "2025.04"},
    "JP":  {"monthly": 360000, "mom_pct": -1.5,  "unit": "대",  "period": "2025.04"},
    "RU":  {"monthly": 138000, "mom_pct": +6.4,  "unit": "대",  "period": "2025.04"},
    "VN":  {"monthly": 35000,  "mom_pct": +4.7,  "unit": "대",  "period": "2025.04"},
    "TH":  {"monthly": 68000,  "mom_pct": -3.1,  "unit": "대",  "period": "2025.04"},
    "PH":  {"monthly": 46000,  "mom_pct": +2.0,  "unit": "대",  "period": "2025.04"},
    "PK":  {"monthly": 32000,  "mom_pct": +8.5,  "unit": "대",  "period": "2025.04"},
    "GCC": {"monthly": 74000,  "mom_pct": +1.3,  "unit": "대",  "period": "2025.04"},
}


# frankfurter.app (ECB) 지원 통화만 API 조회, 나머지는 정적 참고값 사용
_FRANKFURTER_SUPPORTED = {"KRW", "CNY", "JPY", "INR", "PHP", "THB"}

# 정적 참고 환율 (대비 USD, 약 2025년 기준 — 실제 운영 시 주기적 확인 권장)
_STATIC_RATES: dict[str, float] = {
    "USD": 1.0,
    "RUB": 90.0,    # 러시아 루블 (제재로 ECB 미지원)
    "VND": 25400.0, # 베트남 동
    "PKR": 278.0,   # 파키스탄 루피
    "SAR": 3.75,    # 사우디 리얄 (USD 고정 환율)
}


def _fetch_exchange_rates_sync(currencies: list[str]) -> dict[str, float]:
    """Fetch USD-based rates. Uses frankfurter.app for ECB currencies, static for others."""
    result: dict[str, float] = {"USD": 1.0}

    # Apply static values first
    for c in currencies:
        if c in _STATIC_RATES:
            result[c] = _STATIC_RATES[c]

    # Fetch live rates for supported currencies
    api_targets = [c for c in currencies if c in _FRANKFURTER_SUPPORTED]
    if api_targets:
        to_param = ",".join(api_targets)
        url = f"https://api.frankfurter.app/latest?from=USD&to={to_param}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SK-Newsletter/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())
                live = data.get("rates", {})
                result.update(live)
        except Exception as e:
            logger.warning(f"frankfurter.app fetch failed: {e}")

    return result


def _fetch_wb_cpi_sync(iso3: str) -> dict | None:
    """Fetch latest CPI inflation (YoY %) from World Bank API."""
    url = (
        f"https://api.worldbank.org/v2/country/{iso3}/indicator/"
        f"FP.CPI.TOTL.ZG?format=json&mrv=2&per_page=2"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SK-Newsletter/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            if len(data) >= 2 and data[1]:
                for record in data[1]:
                    val = record.get("value")
                    if val is not None:
                        return {"value": round(float(val), 1), "year": record.get("date", "")}
    except Exception as e:
        logger.debug(f"World Bank CPI fetch failed for {iso3}: {e}")
    return None


async def fetch_kpi_data(state: NewsletterState) -> dict:
    """Fetch KPI metrics for all countries in the run."""
    countries = state.get("countries", [])
    kpi: dict[str, dict] = {}

    # 1. Exchange rates — one batch call
    needed_currencies = list({CURRENCY_CODE.get(c) for c in countries if CURRENCY_CODE.get(c)})
    rates = await asyncio.to_thread(_fetch_exchange_rates_sync, needed_currencies)
    if rates:
        print(f"[KPI] Exchange rates fetched: {list(rates.keys())}", flush=True)
    else:
        print("[KPI] Exchange rate fetch failed, using fallback", flush=True)

    # 2. CPI — parallel World Bank calls
    async def _get_cpi(country: str) -> tuple[str, dict | None]:
        iso3 = WB_ISO3.get(country)
        if not iso3:
            return country, None
        result = await asyncio.to_thread(_fetch_wb_cpi_sync, iso3)
        return country, result

    cpi_results = await asyncio.gather(*[_get_cpi(c) for c in countries])
    cpi_map = {c: r for c, r in cpi_results}

    # 3. Assemble per-country KPI
    for country in countries:
        currency = CURRENCY_CODE.get(country, "USD")
        rate = rates.get(currency)
        ir = INTEREST_RATES.get(country)
        vreg = VEHICLE_REG.get(country)
        cpi = cpi_map.get(country)

        # Format vehicle reg display
        m = vreg["monthly"] if vreg else 0
        if m >= 1_000_000:
            vreg_display = f"{m / 1_000_000:.1f}백만"
        elif m >= 10_000:
            vreg_display = f"{m // 10000}만 {(m % 10000) // 1000}천"
        else:
            vreg_display = f"{m:,}"

        kpi[country] = {
            "exchange_rate": {
                "value": rate,
                "currency": currency,
                "label": CURRENCY_LABEL.get(country, f"{currency}/USD"),
                "formatted": f"{rate:,.1f}" if rate else "N/A",
            },
            "interest_rate": {
                "value": ir["rate"] if ir else None,
                "label": ir["label"] if ir else "기준금리",
                "updated": ir["updated"] if ir else "",
                "formatted": f"{ir['rate']:.2f}%" if ir else "N/A",
            },
            "cpi": {
                "value": cpi["value"] if cpi else None,
                "year": cpi["year"] if cpi else "",
                "formatted": f"{cpi['value']:+.1f}%" if cpi else "N/A",
            },
            "vehicle_reg": {
                "monthly": vreg["monthly"] if vreg else 0,
                "mom_pct": vreg["mom_pct"] if vreg else 0.0,
                "period": vreg["period"] if vreg else "",
                "display": vreg_display,
                "formatted": f"{vreg_display}대",
            },
        }
        print(f"[KPI][{country}] rate={kpi[country]['exchange_rate']['formatted']} "
              f"ir={kpi[country]['interest_rate']['formatted']} "
              f"cpi={kpi[country]['cpi']['formatted']} "
              f"vreg={kpi[country]['vehicle_reg']['formatted']}", flush=True)

    return {
        "kpi_data": kpi,
        "phase_status": {**state.get("phase_status", {}), "kpi": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "kpi", "ts": datetime.now().isoformat()}
        ],
    }
