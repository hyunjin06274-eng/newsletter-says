"""Phase 0.5: LLM-based dynamic keyword generation using Gemini."""

import json
import logging
import os
from datetime import datetime

from backend.agent.state import NewsletterState

logger = logging.getLogger(__name__)

COUNTRY_CONTEXT = {
    "KR": {"name": "한국", "lang": "Korean", "competitors": ["SK ZIC", "GS Kixx", "S-OIL", "현대오일뱅크"]},
    "RU": {"name": "러시아", "lang": "Russian", "competitors": ["Lukoil", "Gazpromneft", "Rosneft", "Shell Russia"]},
    "VN": {"name": "베트남", "lang": "Vietnamese", "competitors": ["Petrolimex PLC", "Castrol Vietnam", "Shell Vietnam"]},
    "TH": {"name": "태국", "lang": "Thai", "competitors": ["PTT Lubricants", "Shell Thailand", "Castrol Thailand"]},
    "PH": {"name": "필리핀", "lang": "Filipino/English", "competitors": ["Petron", "Shell Philippines", "Caltex PH"]},
    "PK": {"name": "파키스탄", "lang": "Urdu/English", "competitors": ["PSO", "Shell Pakistan", "Attock Petroleum"]},
}

BASE_KEYWORDS = [
    "Shell lubricants", "Castrol engine oil", "Valvoline lubricant",
    "Mobil 1 lubricant", "TotalEnergies lubricants", "Fuchs lubricant",
    "lubricant market", "engine oil distribution", "OEM lubricant approval",
]

KEYWORD_PROMPT = """You are a market intelligence keyword generator for the lubricant industry.
Generate 10 search keywords for {country_name} ({country_lang}) market.
Focus on: lubricant sales strategy, competitor activity, regulatory changes, vehicle market trends.
Local competitors: {competitors}

Output JSON array of strings only. Include mix of English and {country_lang} keywords.
"""


async def generate_keywords(state: NewsletterState) -> dict:
    """Generate search keywords for each country using Gemini LLM."""
    countries = state["countries"]
    date_str = state["date_str"]
    keywords = {}

    google_api_key = os.environ.get("GOOGLE_API_KEY", "")

    for country in countries:
        ctx = COUNTRY_CONTEXT.get(country, {"name": country, "lang": "English", "competitors": []})

        if google_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_api_key)
                model = genai.GenerativeModel("gemini-2.0-flash")

                prompt = KEYWORD_PROMPT.format(
                    country_name=ctx["name"],
                    country_lang=ctx["lang"],
                    competitors=", ".join(ctx["competitors"]),
                )
                import asyncio
                response = await asyncio.to_thread(model.generate_content, prompt)
                text = response.text.strip()
                # Extract JSON array from response
                if "[" in text:
                    json_str = text[text.index("["):text.rindex("]") + 1]
                    country_keywords = json.loads(json_str)
                else:
                    country_keywords = []
            except Exception as e:
                logger.warning(f"Gemini keyword generation failed for {country}: {e}")
                country_keywords = []
        else:
            country_keywords = []

        # Always include base keywords
        keywords[country] = BASE_KEYWORDS + country_keywords
        logger.info(f"[{country}] Generated {len(keywords[country])} keywords")

    return {
        "keywords": keywords,
        "current_phase": "collection",
        "phase_status": {**state.get("phase_status", {}), "keywords": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "keywords", "ts": datetime.now().isoformat()}
        ],
    }
