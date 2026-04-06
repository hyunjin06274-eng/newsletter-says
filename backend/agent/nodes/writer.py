"""Phase 3: Professional HTML newsletter generation."""

import json
import logging
import os
import html as html_module
from datetime import datetime

from backend.agent.state import NewsletterState

logger = logging.getLogger(__name__)

COUNTRY_NAMES = {
    "KR": "한국", "RU": "러시아", "VN": "베트남",
    "TH": "태국", "PH": "필리핀", "PK": "파키스탄",
}
COUNTRY_FLAGS = {
    "KR": "🇰🇷", "RU": "🇷🇺", "VN": "🇻🇳",
    "TH": "🇹🇭", "PH": "🇵🇭", "PK": "🇵🇰",
}

SECTOR_ICONS = {
    "윤활유동향": ("🛢️", "#D97706", "Lubricant Trends"),
    "경쟁사활동": ("🏆", "#DC2626", "Competitor Activity"),
    "전방산업동향": ("🚗", "#2563EB", "Forward Industry"),
    "윤활유규제": ("⚖️", "#7C3AED", "Regulation"),
}

SCORE_BADGES = {
    5: ("★★★★★", "#B45309", "#FEF3C7"),
    4: ("★★★★☆", "#1E40AF", "#DBEAFE"),
    3: ("★★★☆☆", "#065F46", "#D1FAE5"),
    2: ("★★☆☆☆", "#6B7280", "#F3F4F6"),
}

FONT_STACK = "'Malgun Gothic','Apple SD Gothic Neo','Noto Sans KR',Arial,Helvetica,sans-serif"
BRAND_RED = "#E5191E"
NAVY = "#1B3C6E"
DARK_BG = "#0F172A"
CARD_BG = "#1E293B"

NEWSLETTER_PROMPT = """You are a premium newsletter designer for SK Enmove's Global MI (Market Intelligence) team.
Create a STUNNING, professional HTML newsletter in Korean for the {country_name} lubricant market.

Articles data:
{articles_json}

{audit_feedback}

=== STRICT DESIGN REQUIREMENTS ===

1. STRUCTURE (3 sections, clearly separated):
   A. 📋 핵심 인사이트 (Executive Summary)
      - 4-5 bullet points with red accent markers
      - Each insight must reference specific data from the articles
      - Business-critical tone, no fluff

   B. 📰 섹터별 주요 뉴스 (Sector News)
      - Group articles by sector: 윤활유동향, 경쟁사활동, 전방산업동향, 윤활유규제
      - Each sector has a colored header bar
      - Each article card shows: score badge, title (linked), Korean summary, source+date
      - Score badge: 5=gold, 4=blue, 3=green (star ratings)

   C. 💡 마케팅 전략 제언 (Strategic Recommendations)
      - 3-5 numbered, specific, actionable recommendations
      - Each must tie back to a specific news item or trend
      - Format: Bold title + 1-2 sentence explanation

2. VISUAL DESIGN (Email-safe, must look PREMIUM):
   - Background: #f4f4f4
   - Container: white, max-width 680px, centered, subtle shadow
   - Header: Dark navy gradient (#1B3C6E → #0D2240), SK enmove red badge
   - Section headers: Clean, bold, with colored left border accent
   - Article cards: Light background, 1px border, 8px border-radius
   - Score badges: Colored pills (gold/blue/green based on score)
   - Typography: 'Malgun Gothic' stack, line-height 1.6
   - Footer: Light gray, subtle, with disclaimer
   - All CSS must be INLINE (no <style> blocks, no external CSS)
   - Use TABLE layout for email compatibility (not div/flexbox)
   - NO external images, fonts, or resources

3. CONTENT RULES:
   - ALL text in Korean (titles, summaries, insights, recommendations)
   - Every article must link to its source URL
   - Show collection period: "최근 {days}일" in the header
   - Date format: YYYY.MM.DD
   - No hallucinated data — only reference what's in the articles

Output the COMPLETE HTML document. No markdown code fences. Start with <!DOCTYPE html>.
"""


def _esc(text: str) -> str:
    """HTML-escape text."""
    return html_module.escape(str(text)) if text else ""


def _build_article_card(article: dict, idx: int) -> str:
    """Build a single article card HTML."""
    score = article.get("score", 0)
    badge_text, badge_color, badge_bg = SCORE_BADGES.get(
        min(max(score, 2), 5), ("★★☆☆☆", "#6B7280", "#F3F4F6")
    )
    # Prefer Korean title, fallback to original
    title = _esc(article.get("title_kr", article.get("title", "Untitled")))
    summary = _esc(article.get("summary_kr", article.get("snippet", "")))
    source = _esc(article.get("source", ""))
    url = article.get("url", "#")
    url_valid = article.get("url_valid", True)
    date = _esc(article.get("published_date", ""))

    # Title: linked if URL is valid, plain text otherwise
    if url_valid and url and url != "#":
        title_html = f'<a href="{url}" style="color:{NAVY};font-size:15px;font-weight:700;text-decoration:none;line-height:1.5" target="_blank">{title}</a>'
        source_link = f' · <a href="{url}" style="color:#6B7280;text-decoration:underline;font-size:11px" target="_blank">원문보기</a>'
    else:
        title_html = f'<span style="color:{NAVY};font-size:15px;font-weight:700;line-height:1.5">{title}</span>'
        source_link = ""

    return f"""<tr>
<td style="padding:18px 20px;border-bottom:1px solid #f0f0f0">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td>
    <span style="display:inline-block;background-color:{badge_bg};color:{badge_color};font-size:11px;padding:3px 10px;border-radius:12px;font-weight:600;letter-spacing:0.5px">{badge_text} {score}</span>
  </td></tr>
  <tr><td style="padding-top:8px">
    {title_html}
  </td></tr>
  <tr><td style="padding-top:8px">
    <span style="font-size:13px;color:#4B5563;line-height:1.7">{summary}</span>
  </td></tr>
  <tr><td style="padding-top:8px">
    <span style="font-size:11px;color:#9CA3AF">{source}{' | ' + date if date else ''}{source_link}</span>
  </td></tr>
  </table>
</td>
</tr>"""


def _build_sector_block(sector: str, articles: list) -> str:
    """Build a sector section with all its articles."""
    if not articles:
        return ""

    icon, color, eng_name = SECTOR_ICONS.get(sector, ("📰", "#6B7280", "Other"))

    article_rows = ""
    for i, a in enumerate(articles[:5]):
        article_rows += _build_article_card(a, i)

    return f"""<tr>
<td style="padding:0 32px 24px 32px">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E5E7EB;border-radius:8px;overflow:hidden">
  <tr>
    <td style="background-color:{NAVY};padding:12px 20px">
      <span style="color:#ffffff;font-size:14px;font-weight:700;letter-spacing:0.3px">{icon} {sector}</span>
      <span style="color:#8BA4C4;font-size:11px;float:right;padding-top:2px">{len(articles)} 건</span>
    </td>
  </tr>
  {article_rows}
  </table>
</td>
</tr>"""


def build_newsletter_html(country: str, articles: list, days: int, insights: list[str] = None, recommendations: list[str] = None) -> str:
    """Build a complete professional newsletter HTML."""
    name = COUNTRY_NAMES.get(country, country)
    flag = COUNTRY_FLAGS.get(country, "")
    today = datetime.now().strftime("%Y.%m.%d")

    # Group articles by sector
    sectors: dict[str, list] = {}
    for a in articles:
        sector = a.get("sector", "윤활유동향")
        sectors.setdefault(sector, []).append(a)

    # Sort each sector by score
    for s in sectors:
        sectors[s].sort(key=lambda x: x.get("score", 0), reverse=True)

    # Build sector blocks
    sector_html = ""
    for sector_name in ["경쟁사활동", "윤활유동향", "전방산업동향", "윤활유규제"]:
        if sector_name in sectors:
            sector_html += _build_sector_block(sector_name, sectors[sector_name])

    # Build insights section
    if not insights:
        insights = []
        top_articles = sorted(articles, key=lambda x: x.get("score", 0), reverse=True)[:5]
        for a in top_articles:
            summary = a.get("summary_kr", a.get("snippet", a.get("title", "")))
            if summary:
                insights.append(summary[:120])

    insights_html = ""
    for ins in insights[:5]:
        insights_html += f"""<tr><td style="padding:6px 0;font-size:14px;color:#374151;line-height:1.6">
  <span style="color:{BRAND_RED};font-weight:700;margin-right:6px">▶</span>{_esc(ins)}
</td></tr>"""

    # Build recommendations
    if not recommendations:
        recommendations = [
            f"경쟁사 동향 분석을 바탕으로 대응 전략 수립 검토 필요",
            f"시장 규제 변화에 선제적으로 대응하여 인증 선점 기회 모색",
            f"전방산업 수요 변화를 반영한 제품 포트폴리오 최적화",
        ]

    recs_html = ""
    for i, rec in enumerate(recommendations[:5], 1):
        recs_html += f"""<tr><td style="padding:10px 0;font-size:14px;color:#374151;line-height:1.6">
  <span style="display:inline-block;background:{NAVY};color:#fff;width:24px;height:24px;border-radius:50%;text-align:center;line-height:24px;font-size:12px;font-weight:700;margin-right:10px">{i}</span>
  {_esc(rec)}
</td></tr>"""

    total_articles = len(articles)
    total_sources = len(set(a.get("source", "") for a in articles if a.get("source")))

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SK엔무브 글로벌 MI 뉴스레터 — {name}</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f4;font-family:{FONT_STACK};line-height:1.6;color:#333333;-webkit-text-size-adjust:100%">

<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f4f4">
<tr><td align="center" style="padding:24px 12px">

<table width="680" cellpadding="0" cellspacing="0" border="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">

<!-- ═══ HEADER ═══ -->
<tr>
<td style="background:linear-gradient(135deg, {NAVY} 0%, #0D2240 100%);padding:36px 40px;text-align:center">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td align="center">
    <table cellpadding="0" cellspacing="0" border="0">
    <tr>
      <td style="background-color:{BRAND_RED};color:#ffffff;font-weight:800;font-size:14px;padding:6px 16px;border-radius:6px;letter-spacing:1.5px">SK enmove</td>
    </tr>
    </table>
  </td></tr>
  <tr><td align="center" style="padding-top:20px">
    <span style="color:#ffffff;font-size:26px;font-weight:800;letter-spacing:-0.5px;line-height:1.3">{flag} {name} 윤활유 시장 인텔리전스</span>
  </td></tr>
  <tr><td align="center" style="padding-top:10px">
    <span style="color:#8BA4C4;font-size:13px">{today} | 최근 {days}일 동향 분석 | {total_articles}건 분석 · {total_sources}개 소스</span>
  </td></tr>
  </table>
</td>
</tr>

<!-- ═══ EXECUTIVE SUMMARY ═══ -->
<tr>
<td style="padding:32px 32px 24px 32px">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#FFFBF0;border-left:4px solid {BRAND_RED};border-radius:0 8px 8px 0">
  <tr><td style="padding:20px 24px">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr><td style="padding-bottom:14px">
      <span style="font-size:18px;font-weight:800;color:{NAVY}">📋 핵심 인사이트</span>
    </td></tr>
    {insights_html}
    </table>
  </td></tr>
  </table>
</td>
</tr>

<!-- ═══ SECTION DIVIDER ═══ -->
<tr>
<td style="padding:8px 32px 20px 32px">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="border-bottom:2px solid {NAVY};padding-bottom:8px">
      <span style="font-size:18px;font-weight:800;color:{NAVY}">📰 섹터별 주요 뉴스</span>
    </td>
  </tr>
  </table>
</td>
</tr>

<!-- ═══ SECTOR BLOCKS ═══ -->
{sector_html}

<!-- ═══ STRATEGIC RECOMMENDATIONS ═══ -->
<tr>
<td style="padding:8px 32px 32px 32px">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#F0F4FF;border-left:4px solid {NAVY};border-radius:0 8px 8px 0">
  <tr><td style="padding:20px 24px">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr><td style="padding-bottom:14px">
      <span style="font-size:18px;font-weight:800;color:{NAVY}">💡 마케팅 전략 제언</span>
    </td></tr>
    {recs_html}
    </table>
  </td></tr>
  </table>
</td>
</tr>

<!-- ═══ FOOTER ═══ -->
<tr>
<td style="background-color:#F8FAFC;padding:24px 40px;text-align:center;border-top:1px solid #E5E7EB">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td align="center">
    <span style="color:#6B7280;font-size:12px;line-height:2">
      SK Enmove Global MI Newsletter<br>
      본 뉴스레터는 공개 소스 기반 자동 수집·분석 결과이며, 투자 조언이 아닙니다.<br>
      <span style="color:#9CA3AF">Powered by LangGraph + Claude AI | Newsletter SaaS v1.0</span>
    </span>
  </td></tr>
  </table>
</td>
</tr>

</table>
</td></tr>
</table>

</body>
</html>"""


async def write_newsletter(state: NewsletterState) -> dict:
    """Generate HTML newsletters for all countries."""
    import anthropic

    grouped = state.get("grouped_articles", {})
    days = state.get("days", 30)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    newsletters: dict[str, str] = {}

    audit_feedback = state.get("audit_feedback", {})
    iteration = state.get("audit_iteration", 0)

    if api_key:
        client = anthropic.Anthropic(api_key=api_key)
    else:
        client = None

    for country, articles in grouped.items():
        if len(articles) < 2:
            logger.warning(f"[{country}] Only {len(articles)} articles, using minimal template")

        # Always use the structured template for consistent quality
        # LLM generates insights and recommendations, template handles layout
        insights = []
        recommendations = []

        if client and len(articles) >= 2:
            try:
                articles_summary = json.dumps(
                    [{"title": a.get("title"), "summary_kr": a.get("summary_kr", a.get("snippet", "")),
                      "sector": a.get("sector", "윤활유동향"), "score": a.get("score")}
                     for a in articles[:15]],
                    ensure_ascii=False,
                )

                feedback_text = ""
                if country in audit_feedback and not audit_feedback[country].get("passed", True):
                    fb = audit_feedback[country]
                    feedback_text = f"\nPrevious issues: {', '.join(fb.get('issues', []))}"

                prompt = f"""Based on these {COUNTRY_NAMES.get(country, country)} lubricant market articles, generate:
1. Exactly 5 Korean executive insights (핵심 인사이트) — each 1-2 sentences, data-driven, about lubricant sales impact
2. Exactly 4 Korean strategic recommendations (전략 제언) — each specific and actionable for SK Enmove sales team
{feedback_text}

Articles: {articles_summary}

Output JSON only: {{"insights": ["...", "..."], "recommendations": ["...", "..."]}}"""

                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1500,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text.strip()
                if "{" in text:
                    data = json.loads(text[text.index("{"):text.rindex("}") + 1])
                    insights = data.get("insights", [])
                    recommendations = data.get("recommendations", [])
            except Exception as e:
                logger.warning(f"[{country}] LLM insight generation failed: {e}")

        newsletters[country] = build_newsletter_html(
            country, articles, days, insights, recommendations
        )
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
