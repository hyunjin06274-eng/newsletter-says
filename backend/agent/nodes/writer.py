"""Phase 3: Professional HTML newsletter generation (Outlook-compatible)."""

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
    "윤활유동향": ("윤활유동향", "#D97706"),
    "경쟁사활동": ("경쟁사활동", "#DC2626"),
    "전방산업동향": ("전방산업동향", "#2563EB"),
    "윤활유규제": ("윤활유규제", "#7C3AED"),
}

FONT_STACK = "'Malgun Gothic','맑은 고딕',Arial,sans-serif"
BRAND_RED = "#E5191E"
NAVY = "#1B3C6E"


def score_to_stars(score_30: int) -> str:
    """Convert 30-point score to 5-star unicode string (0.5 step)."""
    stars_raw = round((score_30 / 30) * 5 * 2) / 2
    full = int(stars_raw)
    half = 1 if (stars_raw - full) >= 0.5 else 0
    empty = 5 - full - half
    return "\u2605" * full + ("\u00BD" if half else "") + "\u2606" * empty


def _esc(text: str) -> str:
    """HTML-escape text."""
    return html_module.escape(str(text)) if text else ""


def _format_date(date_str: str) -> str:
    """Convert RSS date to clean Korean format."""
    if not date_str:
        return ""
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%Y.%m.%d")
    except Exception:
        if "." in date_str and len(date_str) <= 12:
            return date_str
        return date_str[:10] if len(date_str) > 10 else date_str


def _build_article_card(article: dict, idx: int) -> str:
    """Build a single article card HTML — Outlook safe, no background highlights."""
    score = article.get("score", 0)
    stars = score_to_stars(score)
    title = _esc(article.get("title_kr", article.get("title", "Untitled")))
    summary = _esc(article.get("summary_kr", article.get("snippet", "")))
    source = _esc(article.get("source", ""))
    url = article.get("url", "#")
    url_valid = article.get("url_valid", True)
    date = _format_date(article.get("published_date", ""))

    if url_valid and url and url != "#":
        title_html = f'<a href="{url}" style="color:{NAVY};font-size:15px;font-weight:bold;text-decoration:none;font-family:{FONT_STACK}" target="_blank">{title}</a>'
        source_link = f' · <a href="{url}" style="color:#3B82F6;text-decoration:none;font-size:11px;font-weight:bold;font-family:{FONT_STACK}" target="_blank">원문보기</a>'
    else:
        title_html = f'<span style="color:{NAVY};font-size:15px;font-weight:bold;font-family:{FONT_STACK}">{title}</span>'
        source_link = ""

    scope = article.get("scope", "local")
    global_tag = '<span style="display:inline;color:#6366F1;font-size:10px;font-weight:bold;font-family:Arial,sans-serif;margin-left:6px">[GLOBAL]</span>' if scope == "global" else ""

    return f"""<tr>
<td style="padding:16px 20px;border-bottom:1px solid #E5E7EB;font-family:{FONT_STACK}">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td style="font-family:{FONT_STACK}">
    <span style="color:#B45309;font-size:13px;font-weight:bold;font-family:{FONT_STACK}">{stars}</span>{global_tag}
  </td></tr>
  <tr><td style="padding-top:6px;font-family:{FONT_STACK}">
    {title_html}
  </td></tr>
  <tr><td style="padding-top:6px;font-family:{FONT_STACK}">
    <span style="font-size:13px;color:#4B5563;line-height:1.7;font-family:{FONT_STACK}">{summary}</span>
  </td></tr>
  <tr><td style="padding-top:8px;font-family:{FONT_STACK}">
    <span style="font-size:11px;color:#9CA3AF;font-family:{FONT_STACK}">{source}{" · " + date if date else ""}{source_link}</span>
    {_build_related_sources(article)}
  </td></tr>
  </table>
</td>
</tr>"""


def _build_related_sources(article: dict) -> str:
    """Show related sources if article was grouped from multiple."""
    related = article.get("related_sources", [])
    if not related:
        return ""
    links = []
    for r in related[:3]:
        src = _esc(r.get("source", ""))
        if src:
            links.append(src)
    if links:
        return f'<br><span style="font-size:10px;color:#B0B8C4;font-family:{FONT_STACK}">관련: {", ".join(links)}</span>'
    return ""


def _build_sector_block(sector: str, articles: list) -> str:
    """Build a sector section with all its articles — Outlook safe."""
    if not articles:
        return ""

    label, color = SECTOR_ICONS.get(sector, ("기타", "#6B7280"))

    article_rows = ""
    for i, a in enumerate(articles[:5]):
        article_rows += _build_article_card(a, i)

    return f"""<tr>
<td style="padding:0 32px 24px 32px;font-family:{FONT_STACK}">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #D1D5DB">
  <tr>
    <td style="background-color:{NAVY};padding:12px 20px;border-bottom:1px solid #D1D5DB;font-family:{FONT_STACK}">
      <span style="color:#ffffff;font-size:14px;font-weight:bold;font-family:{FONT_STACK}">[{label}]</span>
      <span style="color:rgba(255,255,255,0.6);font-size:11px;float:right;padding-top:2px;font-family:{FONT_STACK}">{len(articles)}건</span>
    </td>
  </tr>
  {article_rows}
  </table>
</td>
</tr>"""


def build_newsletter_html(country: str, articles: list, days: int, insights: list[str] = None, recommendations: list[str] = None) -> str:
    """Build a complete professional newsletter HTML — Outlook compatible."""
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
    for i, ins in enumerate(insights[:5], 1):
        insights_html += f"""<tr><td style="padding:6px 0;font-family:{FONT_STACK}">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td width="24" valign="top" style="font-size:13px;color:{NAVY};font-weight:bold;font-family:{FONT_STACK}">{i}.</td>
    <td style="padding-left:4px;font-size:13px;color:#374151;line-height:1.65;font-family:{FONT_STACK}">{_esc(ins)}</td>
  </tr>
  </table>
</td></tr>"""

    # Build recommendations
    if not recommendations:
        recommendations = [
            "경쟁사 동향 분석을 바탕으로 대응 전략 수립 검토 필요",
            "시장 규제 변화에 선제적으로 대응하여 인증 선점 기회 모색",
            "전방산업 수요 변화를 반영한 제품 포트폴리오 최적화",
        ]

    priority_labels = ["최우선", "중요", "주목", "참고", "모니터링"]

    recs_html = ""
    for i, rec in enumerate(recommendations[:5]):
        prio = priority_labels[i] if i < len(priority_labels) else ""
        recs_html += f"""<tr><td style="padding:10px 0;font-size:13px;color:#374151;line-height:1.6;border-bottom:1px solid #E5E7EB;font-family:{FONT_STACK}">
  <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
    <td width="24" valign="top" style="font-size:13px;font-weight:bold;color:{NAVY};font-family:{FONT_STACK}">{i+1}.</td>
    <td style="padding-left:4px;font-family:{FONT_STACK}"><span style="font-size:11px;color:#6B7280;font-family:{FONT_STACK}">[{prio}]</span> <span style="font-weight:bold;font-family:{FONT_STACK}">{_esc(rec)}</span></td>
  </tr></table>
</td></tr>"""

    total_articles = len(articles)
    total_sources = len(set(a.get("source", "") for a in articles if a.get("source")))

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SK엔무브 글로벌 MI 뉴스레터 — {name}</title>
<!--[if mso]>
<style type="text/css">
table {{border-collapse:collapse;}}
td {{font-family:'Malgun Gothic','맑은 고딕',Arial,sans-serif;}}
</style>
<![endif]-->
</head>
<body style="margin:0;padding:0;font-family:{FONT_STACK};line-height:1.6;color:#333333;-webkit-text-size-adjust:100%">

<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr><td align="center" style="padding:24px 12px">

<table width="680" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #D1D5DB">

<!-- HEADER -->
<tr>
<td style="padding:32px 40px;text-align:center;border-bottom:2px solid {BRAND_RED};font-family:{FONT_STACK}">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td align="center" style="font-family:{FONT_STACK}">
    <span style="color:{BRAND_RED};font-weight:bold;font-size:14px;letter-spacing:1.5px;font-family:{FONT_STACK}">SK enmove</span>
  </td></tr>
  <tr><td align="center" style="padding-top:16px;font-family:{FONT_STACK}">
    <span style="color:{NAVY};font-size:24px;font-weight:bold;font-family:{FONT_STACK}">{flag} {name} 윤활유 시장 인텔리전스</span>
  </td></tr>
  <tr><td align="center" style="padding-top:8px;font-family:{FONT_STACK}">
    <span style="color:#6B7280;font-size:12px;font-family:{FONT_STACK}">{today} | 최근 {days}일 동향 분석 | {total_articles}건 분석 · {total_sources}개 소스</span>
  </td></tr>
  </table>
</td>
</tr>

<!-- EXECUTIVE SUMMARY -->
<tr>
<td style="padding:28px 32px 20px 32px;font-family:{FONT_STACK}">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-left:4px solid {BRAND_RED}">
  <tr><td style="padding:16px 20px;font-family:{FONT_STACK}">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr><td style="padding-bottom:12px;font-family:{FONT_STACK}">
      <span style="font-size:17px;font-weight:bold;color:{NAVY};font-family:{FONT_STACK}">핵심 인사이트</span>
    </td></tr>
    {insights_html}
    </table>
  </td></tr>
  </table>
</td>
</tr>

<!-- SECTION DIVIDER -->
<tr>
<td style="padding:8px 32px 20px 32px;font-family:{FONT_STACK}">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="border-bottom:2px solid {NAVY};padding-bottom:8px;font-family:{FONT_STACK}">
      <span style="font-size:17px;font-weight:bold;color:{NAVY};font-family:{FONT_STACK}">섹터별 주요 뉴스</span>
    </td>
  </tr>
  </table>
</td>
</tr>

<!-- SECTOR BLOCKS -->
{sector_html}

<!-- STRATEGIC RECOMMENDATIONS -->
<tr>
<td style="padding:8px 32px 28px 32px;font-family:{FONT_STACK}">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-left:4px solid {NAVY}">
  <tr><td style="padding:16px 20px;font-family:{FONT_STACK}">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr><td style="padding-bottom:12px;font-family:{FONT_STACK}">
      <span style="font-size:17px;font-weight:bold;color:{NAVY};font-family:{FONT_STACK}">마케팅 전략 제언</span>
    </td></tr>
    {recs_html}
    </table>
  </td></tr>
  </table>
</td>
</tr>

<!-- FOOTER -->
<tr>
<td style="padding:20px 40px;text-align:center;border-top:1px solid #D1D5DB;font-family:{FONT_STACK}">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td align="center" style="font-family:{FONT_STACK}">
    <span style="color:#6B7280;font-size:11px;line-height:2;font-family:{FONT_STACK}">
      SK Enmove Global MI Newsletter<br>
      본 뉴스레터는 공개 소스 기반 자동 수집·분석 결과이며, 투자 조언이 아닙니다.<br>
      <span style="color:#9CA3AF;font-family:{FONT_STACK}">Powered by LangGraph + Claude AI</span>
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
1. Exactly 5 Korean executive insights — each MUST be 1 sentence only (max 80 characters). Data-driven, about lubricant sales impact. No filler.
2. Exactly 4 Korean strategic recommendations — each 1 sentence, specific and actionable for SK Enmove sales team.
{feedback_text}

Articles: {articles_summary}

Output JSON only: {{"insights": ["...", "..."], "recommendations": ["...", "..."]}}"""

                import asyncio
                response = await asyncio.to_thread(
                    client.messages.create,
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
        print(f"[{country}] Newsletter generated ({len(newsletters[country])} chars)", flush=True)

    return {
        "newsletters": newsletters,
        "current_phase": "auditing",
        "phase_status": {**state.get("phase_status", {}), "writing": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "writing", "ts": datetime.now().isoformat(),
             "iteration": iteration}
        ],
    }
