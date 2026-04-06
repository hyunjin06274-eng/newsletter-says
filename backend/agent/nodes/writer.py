"""Phase 3: HTML newsletter generation using LLM."""

import json
import logging
import os
from datetime import datetime

from backend.agent.state import NewsletterState

logger = logging.getLogger(__name__)

COUNTRY_NAMES = {
    "KR": "한국", "RU": "러시아", "VN": "베트남",
    "TH": "태국", "PH": "필리핀", "PK": "파키스탄",
}
COUNTRY_FLAGS = {
    "KR": "\U0001f1f0\U0001f1f7", "RU": "\U0001f1f7\U0001f1fa", "VN": "\U0001f1fb\U0001f1f3",
    "TH": "\U0001f1f9\U0001f1ed", "PH": "\U0001f1f5\U0001f1ed", "PK": "\U0001f1f5\U0001f1f0",
}

SECTOR_CONFIG = [
    ("윤활유동향", "해당 국가 윤활유 최신 동향"),
    ("경쟁사활동", "경쟁사 활동"),
    ("전방산업동향", "해당 국가 전방산업 동향"),
    ("윤활유규제", "해당 국가 윤활유 최신 규제"),
]

NEWSLETTER_PROMPT = """You are a newsletter writer for SK Enmove's Global MI newsletter.
Generate a professional HTML newsletter in Korean for the {country_name} market.

Articles (JSON):
{articles_json}

Newsletter structure (3 sections):
1. 핵심 인사이트 (3-5 bullet points summarizing key findings)
2. 섹터별 주요 뉴스 (grouped by sector: 윤활유동향, 경쟁사활동, 전방산업동향, 윤활유규제)
3. 마케팅 전략 제언 (3-5 actionable recommendations for sales team)

{audit_feedback}

Requirements:
- All text in Korean
- Email-safe HTML (table layout, inline CSS, no external fonts)
- Brand colors: Red #E5191E, Navy #1B3C6E
- Font: 'Malgun Gothic','Apple SD Gothic Neo',Arial,sans-serif
- Include article source links
- Collection period: last {days} days
- Professional tone targeting marketing/sales strategists

Output the complete HTML only, no markdown wrapper.
"""


async def write_newsletter(state: NewsletterState) -> dict:
    """Generate HTML newsletters for all countries."""
    import anthropic

    grouped = state.get("grouped_articles", {})
    days = state.get("days", 30)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    newsletters: dict[str, str] = {}

    # Check for audit feedback from previous iteration
    audit_feedback = state.get("audit_feedback", {})
    iteration = state.get("audit_iteration", 0)

    if api_key:
        client = anthropic.Anthropic(api_key=api_key)
    else:
        client = None

    for country, articles in grouped.items():
        if len(articles) < 3:
            logger.warning(f"[{country}] Only {len(articles)} articles, skipping newsletter")
            continue

        feedback_text = ""
        if country in audit_feedback and not audit_feedback[country].get("passed", True):
            fb = audit_feedback[country]
            feedback_text = f"\n\nPREVIOUS AUDIT FEEDBACK (iteration {iteration}):\n"
            feedback_text += f"Issues: {', '.join(fb.get('issues', []))}\n"
            feedback_text += f"Suggestions: {', '.join(fb.get('suggestions', []))}\n"
            feedback_text += "Please address these issues in the revised newsletter.\n"

        articles_json = json.dumps(
            [{"title": a.get("title"), "summary_kr": a.get("summary_kr", a.get("snippet", "")),
              "source": a.get("source"), "url": a.get("url"), "score": a.get("score"),
              "sector": a.get("sector", "윤활유동향"), "tags": a.get("tags", [])}
             for a in articles],
            ensure_ascii=False, indent=2,
        )

        if client:
            try:
                prompt = NEWSLETTER_PROMPT.format(
                    country_name=COUNTRY_NAMES.get(country, country),
                    articles_json=articles_json,
                    audit_feedback=feedback_text,
                    days=days,
                )
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=8000,
                    messages=[{"role": "user", "content": prompt}],
                )
                html = response.content[0].text.strip()
                # Strip markdown code fences if present
                if html.startswith("```"):
                    html = html.split("\n", 1)[1]
                if html.endswith("```"):
                    html = html.rsplit("```", 1)[0]
                newsletters[country] = html
            except Exception as e:
                logger.error(f"[{country}] Newsletter generation failed: {e}")
                newsletters[country] = _fallback_html(country, articles, days)
        else:
            newsletters[country] = _fallback_html(country, articles, days)

        logger.info(f"[{country}] Newsletter generated ({len(newsletters[country])} chars)")

    return {
        "newsletters": newsletters,
        "current_phase": "auditing",
        "phase_status": {**state.get("phase_status", {}), "writing": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "writing", "ts": datetime.now().isoformat(),
             "iteration": iteration}
        ],
    }


def _fallback_html(country: str, articles: list, days: int) -> str:
    """Generate a basic HTML newsletter without LLM."""
    name = COUNTRY_NAMES.get(country, country)
    flag = COUNTRY_FLAGS.get(country, "")
    today = datetime.now().strftime("%Y-%m-%d")

    rows = ""
    for a in articles[:15]:
        rows += f"""<tr>
  <td style="padding:12px;border-bottom:1px solid #eee">
    <a href="{a.get('url','#')}" style="color:#1B3C6E;font-weight:bold">{a.get('title','')}</a>
    <br><span style="color:#666;font-size:13px">{a.get('summary_kr', a.get('snippet',''))}</span>
    <br><span style="color:#999;font-size:11px">{a.get('source','')} | Score: {a.get('score',0)}</span>
  </td>
</tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:20px;font-family:'Malgun Gothic',Arial,sans-serif">
<table width="100%" style="max-width:700px;margin:auto;border-collapse:collapse">
<tr><td style="background:#1B3C6E;color:#fff;padding:20px;text-align:center">
<h1>{flag} SK엔무브 글로벌 MI 뉴스레터 — {name}</h1>
<p>{today} | 최근 {days}일 동향</p>
</td></tr>
{rows}
<tr><td style="background:#f5f5f5;padding:15px;text-align:center;color:#999;font-size:12px">
SK Enmove Global MI Newsletter | Auto-generated
</td></tr>
</table></body></html>"""
