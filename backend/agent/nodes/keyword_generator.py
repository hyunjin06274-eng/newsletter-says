"""Phase 0.5: Dynamic keyword generation using Claude Haiku."""

import json
import logging
import os
from datetime import datetime

from backend.agent.state import NewsletterState

logger = logging.getLogger(__name__)

COUNTRY_CONTEXT = {
    "KR": {
        "name": "한국", "lang": "Korean",
        "competitors": ["GS칼텍스 Kixx", "S-OIL", "현대오일뱅크", "Shell Korea", "Castrol Korea", "Valvoline Korea", "Motul Korea"],
        "forward_industries": ["현대차 기아 자동차 판매", "하이브리드 전기차 전환", "건설기계 수출 두산밥캣", "조선해양 선박엔진", "농기계 트랙터"],
    },
    "RU": {
        "name": "러시아", "lang": "Russian",
        "competitors": ["Lukoil", "Gazpromneft G-Energy", "Rosneft", "Shell Russia", "Castrol Russia", "Tatneft"],
        "forward_industries": ["Russia car sales Lada", "Russia truck fleet KAMAZ", "Russia oil refinery base oil", "Russia sanctions oil export"],
    },
    "VN": {
        "name": "베트남", "lang": "Vietnamese",
        "competitors": ["Petrolimex PLC", "Castrol Vietnam", "Shell Vietnam", "Total Vietnam", "Idemitsu Vietnam"],
        "forward_industries": ["Vietnam motorcycle sales Honda Yamaha", "Vietnam car market VinFast", "Vietnam construction boom", "Vietnam EV policy"],
    },
    "TH": {
        "name": "태국", "lang": "Thai",
        "competitors": ["PTT Lubricants", "Shell Thailand", "Castrol Thailand", "Caltex Thailand", "Valvoline Thailand"],
        "forward_industries": ["Thailand car production export", "Thailand EV policy BYD", "Thailand motorcycle market", "Thailand petrochemical"],
    },
    "PH": {
        "name": "필리핀", "lang": "Filipino/English",
        "competitors": ["Petron", "Shell Philippines", "Caltex Philippines", "Total Philippines", "Castrol Philippines"],
        "forward_industries": ["Philippines car motorcycle sales", "Philippines jeepney modernization", "Philippines oil import", "Philippines maritime shipping"],
    },
    "PK": {
        "name": "파키스탄", "lang": "Urdu/English",
        "competitors": [
            "PSO lubricant Pakistan", "Shell Pakistan engine oil", "Attock Petroleum lubricant",
            "Total Parco Pakistan", "Caltex Pakistan lubricant", "LOPAL lubricant Pakistan",
            "Havoline Pakistan", "Castrol Pakistan", "Mobil Pakistan",
        ],
        "forward_industries": [
            "Pakistan automobile sales Suzuki Toyota", "Pakistan motorcycle market Honda Atlas",
            "Pakistan truck bus fleet CNG", "Pakistan tractor agricultural Millat",
            "Pakistan construction machinery equipment", "Pakistan oil refinery PARCO",
            "Pakistan petroleum import lubricant", "Pakistan EV electric vehicle policy",
            "Pakistan industrial sector lubricant demand", "Pakistan auto parts aftermarket",
        ],
        "local_media": [
            "Dawn Pakistan lubricant", "The News International oil Pakistan",
            "Pakistan automotive sector oil", "OGRA Pakistan petroleum",
            "Pakistan Engineering Council lubricant",
        ],
    },
    "GCC": {
        "name": "GCC(걸프협력회의)", "lang": "Arabic/English",
        "competitors": ["ADNOC Lubricants", "Bapco Lubricants", "Shell Middle East", "Castrol Middle East", "Total Energies ME", "Petromin", "Gulf Oil Middle East"],
        "forward_industries": ["Saudi Arabia Vision 2030 automotive", "UAE construction fleet", "GCC petrochemical refinery", "Qatar LNG marine shipping", "Kuwait oil field equipment", "Oman mining machinery"],
        "local_media": ["Saudi Gazette lubricant", "Arab News oil industry", "ADNOC downstream", "Gulf Business automotive"],
    },
    "CN": {
        "name": "중국", "lang": "Chinese",
        "competitors": [
            # 현지어 브랜드명 우선 — Google CN 피드에서 검색 효율↑
            "中国石化润滑油 嘉实多",
            "昆仑润滑油 中国石油",
            "长城润滑油 Great Wall",
            "壳牌机油 Shell China",
            "美孚润滑油 Mobil China",
            "嘉实多 Castrol China 润滑油",
            "福斯润滑油 Fuchs China",
            "道达尔润滑油 TotalEnergies China",
        ],
        "forward_industries": [
            "中国汽车销量 乘用车 润滑油",         # 중국 승용차 판매
            "比亚迪 新能源车 润滑油需求",           # BYD NEV 윤활유 수요
            "中国重卡 商用车 润滑油",               # 중국 트럭 윤활유
            "中国工程机械 挖掘机 润滑油",           # 건설기계
            "中国摩托车市场 润滑油",                # 오토바이
            "China NEV EV lubricant demand 2024",
            "China construction machinery lubricant XCMG Sany",
            "China base oil refinery output Sinopec",
        ],
        "local_media": [
            "润滑油行业 中国 市场",
            "中国汽车工业协会 CAAM 销量",
            "China lubricant market news 中国",
            "中国石化 润滑油 新品",
        ],
    },
    "US": {
        "name": "미국", "lang": "English",
        "competitors": [
            "Valvoline earnings revenue lubricant",
            "Pennzoil Platinum Shell US engine oil",
            "Castrol GTX US market launch",
            "Mobil 1 ExxonMobil engine oil US",
            "Quaker State Quick Lube US",
            "Lucas Oil United States lubricant",
            "Royal Purple synthetic oil US",
            "Jiffy Lube quick lube service US",
        ],
        "forward_industries": [
            "US auto sales SAAR light vehicle 2024",
            "US pickup truck SUV lubricant demand",
            "US heavy duty diesel HDDO lubricant fleet",
            "US EV adoption ICE lubricant impact America",
            "US automotive aftermarket oil change revenue",
            "US construction equipment lubricant demand",
            "America motor oil price trend retail",
            "US oil change interval synthetic lubricant",
        ],
        "local_media": [
            "ILSAC GF-7 specification API approval US",
            "Lubes N Greases magazine United States",
            "API engine oil category dexos US",
            "STLE lubricant technical conference US",
        ],
    },
    "IN": {
        "name": "인도", "lang": "Hindi/English",
        "competitors": [
            "Castrol India engine oil sales revenue",
            "Gulf Oil India lubricant market share",
            "Servo IOCL engine oil India",
            "MAK Lubricants BPCL India market",
            "HP Lubricants HPCL India",
            "Shell India Helix lubricant launch",
            "Veedol India lubricant",
            "Motul India two-wheeler lubricant",
        ],
        "forward_industries": [
            "India passenger vehicle sales Maruti Suzuki Hyundai",
            "India two-wheeler motorcycle Hero Honda Bajaj lubricant",
            "India commercial vehicle truck lubricant demand",
            "India tractor agricultural lubricant Mahindra",
            "India EV two-wheeler policy lubricant impact",
            "India infrastructure construction lubricant demand",
            "India base oil refinery BPCL HPCL output",
            "India BIS lubricant standard specification",
        ],
        "local_media": [
            "SIAM India automobile sales monthly data",
            "Economic Times India lubricant market",
            "Autocar India engine oil lubricant",
            "India lubricant industry ACMA aftermarket",
        ],
    },
    "JP": {
        "name": "일본", "lang": "Japanese",
        "competitors": [
            # 현지어 검색어 — Google JP 피드에서 검출율↑
            "ENEOSエンジンオイル 潤滑油",
            "出光興産 潤滑油 エンジンオイル",
            "カストロール 日本 エンジンオイル",
            "モービル1 日本 潤滑油",
            "シェルヒリックス 日本",
            "トヨタ純正オイル 販売",
            "Eneos lubricant Japan market",
            "Idemitsu lubricant Japan engine oil",
        ],
        "forward_industries": [
            "日本 自動車販売台数 乗用車",           # 일본 자동車 판매
            "日本 ハイブリッド EV 潤滑油 需要",     # 하이브리드/EV 윤활유
            "日本 二輪車 バイク 潤滑油",            # 오토바이
            "JASO規格 エンジンオイル 日本",         # JASO 규격
            "コマツ 日立建機 建設機械 潤滑油",      # 건설기계
            "Japan car sales Toyota Honda monthly",
            "Japan hybrid vehicle lubricant demand",
            "Japan lubricant export Asia Pacific",
        ],
        "local_media": [
            "JAMA 日本自動車工業会 販売台数",
            "石油学会 潤滑油 日本",
            "日本潤滑油学会 tribology",
            "Japan lubricant market industry report",
        ],
    },
}

BASE_KEYWORDS = [
    "lubricant market", "engine oil", "OEM lubricant approval",
]

KEYWORD_PROMPT = """Generate 15 search keywords for {country_name} lubricant market intelligence.

Priority order (generate in this order):
1. Local competitors + lubricant (5 keywords): {competitors}
2. Forward industry + demand (5 keywords): {forward_industries}
3. Local media / industry sources (2 keywords): {local_media}
4. Lubricant regulation/specification in {country_name} (2 keywords)
5. Market trends in {country_lang} language (1 keyword)

Rules:
- Each keyword should be a Google News search query (2-6 words)
- All keywords MUST be specific to {country_name} — include country name or local brand names
- Mix English and {country_lang} keywords
- Focus on what affects lubricant SALES in {country_name}
- Avoid generic global terms without country context

Output JSON array of 15 strings only. No explanation."""


async def generate_keywords(state: NewsletterState) -> dict:
    """Generate search keywords using Claude Haiku (fast + cheap)."""
    countries = state["countries"]
    keywords = {}
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    for country in countries:
        ctx = COUNTRY_CONTEXT.get(country, {
            "name": country, "lang": "English",
            "competitors": [], "forward_industries": [],
        })

        country_keywords = []

        if api_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)

                prompt = KEYWORD_PROMPT.format(
                    country_name=ctx["name"],
                    country_lang=ctx["lang"],
                    competitors=", ".join(ctx["competitors"]),
                    forward_industries=", ".join(ctx["forward_industries"]),
                    local_media=", ".join(ctx.get("local_media", [])) or "local industry news",
                )

                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=400,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.text.strip() if hasattr(response, 'text') else response.content[0].text.strip()

                if "[" in text and "]" in text:
                    try:
                        s, e = text.find("["), text.rfind("]")
                        country_keywords = json.loads(text[s:e + 1]) if s != -1 and e != -1 and e > s else []
                        print(f"[{country}] Haiku generated {len(country_keywords)} keywords", flush=True)
                    except json.JSONDecodeError:
                        country_keywords = []
            except Exception as e:
                print(f"[{country}] Keyword generation failed: {e}", flush=True)
                country_keywords = []

        # Fallback: use hardcoded competitor + industry + local_media keywords
        if not country_keywords:
            country_keywords = ctx.get("competitors", [])[:5]
            country_keywords += ctx.get("forward_industries", [])[:5]
            country_keywords += ctx.get("local_media", [])[:2]
            print(f"[{country}] Using fallback keywords ({len(country_keywords)})", flush=True)

        keywords[country] = BASE_KEYWORDS + country_keywords
        print(f"[{country}] Total {len(keywords[country])} keywords ready", flush=True)

    return {
        "keywords": keywords,
        "current_phase": "collection",
        "phase_status": {**state.get("phase_status", {}), "keywords": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "keywords", "ts": datetime.now().isoformat()}
        ],
    }
