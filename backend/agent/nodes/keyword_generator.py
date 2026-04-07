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
        "competitors": ["PSO", "Shell Pakistan", "Attock Petroleum", "Caltex Pakistan", "Total Parco"],
        "forward_industries": ["Pakistan vehicle market Suzuki Toyota", "Pakistan truck fleet", "Pakistan oil energy import", "Pakistan agricultural machinery"],
    },
}

BASE_KEYWORDS = [
    "lubricant market", "engine oil", "OEM lubricant approval",
]

KEYWORD_PROMPT = """Generate 12 search keywords for {country_name} lubricant market intelligence.

Priority order (generate in this order):
1. Local competitors + lubricant (4 keywords): {competitors}
2. Forward industry + demand (4 keywords): {forward_industries}
3. Lubricant regulation/specification (2 keywords)
4. Market trends in {country_lang} language (2 keywords)

Rules:
- Each keyword should be a Google News search query (2-5 words)
- Mix English and {country_lang} keywords
- Focus on what affects lubricant SALES in {country_name}

Output JSON array of 12 strings only. No explanation."""


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
                )

                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=400,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.text.strip() if hasattr(response, 'text') else response.content[0].text.strip()

                if "[" in text and "]" in text:
                    try:
                        country_keywords = json.loads(text[text.index("["):text.rindex("]") + 1])
                        print(f"[{country}] Haiku generated {len(country_keywords)} keywords", flush=True)
                    except json.JSONDecodeError:
                        country_keywords = []
            except Exception as e:
                print(f"[{country}] Keyword generation failed: {e}", flush=True)
                country_keywords = []

        # Fallback: use hardcoded competitor + industry keywords
        if not country_keywords:
            country_keywords = [c + " lubricant" for c in ctx.get("competitors", [])[:4]]
            country_keywords += ctx.get("forward_industries", [])[:4]
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
