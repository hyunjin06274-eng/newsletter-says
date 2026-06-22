"""Phase 3: HTML newsletter generation — finalized design (Outlook-safe)."""

import json
import logging
import os
import html as html_module
from datetime import datetime

from backend.agent.state import NewsletterState

logger = logging.getLogger(__name__)

FONT = "'Malgun Gothic','맑은 고딕',Arial,sans-serif"

COUNTRY_NAMES = {
    "KR": "한국", "RU": "러시아", "VN": "베트남",
    "TH": "태국", "PH": "필리핀", "PK": "파키스탄",
    "GCC": "GCC(걸프협력회의)",
    "CN": "중국", "US": "미국", "IN": "인도", "JP": "일본",
}
COUNTRY_EMOJIS = {
    "KR": "🌏", "RU": "❄️", "VN": "🌴",
    "TH": "🌺", "PH": "🏝️", "PK": "🌙",
    "GCC": "🌙", "CN": "🐉", "US": "🗽", "IN": "🕌", "JP": "🗾",
}
MARKET_LABELS = {
    "KR": "KOREA MARKET", "RU": "RUSSIA MARKET", "VN": "VIETNAM MARKET",
    "TH": "THAILAND MARKET", "PH": "PHILIPPINES MARKET", "PK": "PAKISTAN MARKET",
    "GCC": "GCC MARKET", "CN": "CHINA MARKET", "US": "US MARKET",
    "IN": "INDIA MARKET", "JP": "JAPAN MARKET",
}
WEEKDAYS_KR = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

SECTOR_ORDER = ["경쟁사활동", "윤활유동향", "전방산업동향", "윤활유규제"]
SECTOR_CONFIGS = {
    "경쟁사활동":  {"icon": "⚔️",  "border": "#C8121A", "bg": "#FDFAFA"},
    "윤활유동향":  {"icon": "📊",  "border": "#2B7BB9", "bg": "#F7FAFD"},
    "전방산업동향": {"icon": "🏭", "border": "#3D8B37", "bg": "#F7FDF7"},
    "윤활유규제":  {"icon": "📋",  "border": "#7B5EA7", "bg": "#FAF7FD"},
}
PRIORITY_CONFIGS = [
    {"label": "🔴 최우선", "color": "#C8121A", "border": "#C8121A", "bg": "#FDF7F7"},
    {"label": "🟠 중요",   "color": "#D4700A", "border": "#D4700A", "bg": "#FDF9F4"},
    {"label": "🔵 주목",   "color": "#2B7BB9", "border": "#2B7BB9", "bg": "#F4F8FD"},
    {"label": "⚪ 참고",   "color": "#888888", "border": "#999999", "bg": "#F8F8F8"},
]
INSIGHT_NUMBERS = ["①", "②", "③", "④", "⑤"]


def _esc(text: str) -> str:
    return html_module.escape(str(text)) if text else ""


def _score_to_stars(score: int) -> str:
    """Convert 30-point score to 5-star HTML (gold filled + gray empty)."""
    if score >= 24:
        filled, empty = 5, 0
    elif score >= 18:
        filled, empty = 4, 1
    elif score >= 13:
        filled, empty = 3, 2
    elif score >= 10:
        filled, empty = 2, 3
    else:
        filled, empty = 1, 4
    gold = f'<span style="font-family:Arial,sans-serif;font-size:16px;color:#DAA520;">{"★" * filled}</span>'
    gray = f'<span style="font-family:Arial,sans-serif;font-size:16px;color:#DDD;">{"☆" * empty}</span>' if empty else ""
    return gold + gray


def _format_pub_date(raw: str) -> str:
    """Parse published_date string to YYYY.MM.DD. Returns '발행일 미확인' if unparseable."""
    if not raw:
        return "발행일 미확인"
    import re
    from email.utils import parsedate_to_datetime
    raw = raw.strip()
    # Try RFC 2822 (RSS standard: "Mon, 16 Jun 2026 10:00:00 +0000")
    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y.%m.%d")
    except Exception:
        pass
    # Try ISO-like: 2026-06-16, 2026/06/16, 20260616
    m = re.search(r"(\d{4})[-/.]?(\d{2})[-/.]?(\d{2})", raw)
    if m:
        return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
    return "발행일 미확인"


def _build_article_card(article: dict, is_last: bool = False) -> str:
    title_text = _esc(article.get("title_kr", article.get("title", "")))
    summary = _esc(article.get("summary_kr", article.get("snippet", "")))
    score = article.get("score", 0)
    scope = article.get("scope", "local")
    sector = article.get("sector", "윤활유동향")
    cfg = SECTOR_CONFIGS.get(sector, SECTOR_CONFIGS["윤활유동향"])
    margin_bottom = "4px" if is_last else "10px"

    # Rule 2: 제목에 원문 URL 하이퍼링크
    url = article.get("url", "")
    if url:
        title_html = f'<a href="{url}" target="_blank" style="color:#111;text-decoration:underline;">{title_text}</a>'
    else:
        title_html = title_text

    # Rule 1: 원문 발행일 표시
    pub_date = _format_pub_date(article.get("published_date", ""))
    date_html = f'<span style="font-family:{FONT};font-size:12px;color:#999;">{pub_date}</span>'

    global_badge = ""
    if scope == "global":
        global_badge = f"""
                  <tr>
                    <td>
                      <span style="font-family:{FONT};font-size:12px;color:#666;font-weight:bold;background-color:#EBEBEB;padding:2px 7px;border-radius:3px;">🌐 GLOBAL</span>
                    </td>
                  </tr>"""
        title_padding = "padding-top:7px;"
    else:
        title_padding = ""

    return f"""          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom:{margin_bottom};border-left:4px solid {cfg['border']};">
            <tr>
              <td style="background-color:{cfg['bg']};padding:13px 16px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">{global_badge}
                  <tr><td style="{title_padding}font-family:{FONT};font-size:15px;font-weight:bold;color:#111;line-height:1.5;">{title_html}</td></tr>
                  <tr><td style="padding-top:3px;">{date_html}</td></tr>
                  <tr><td style="padding-top:4px;">{_score_to_stars(score)}</td></tr>
                  <tr><td style="padding-top:5px;font-family:{FONT};font-size:14px;color:#444;line-height:1.7;">{summary}</td></tr>
                </table>
              </td>
            </tr>
          </table>
"""


def _build_sector_block(sector: str, articles: list) -> str:
    if not articles:
        return ""
    cfg = SECTOR_CONFIGS.get(sector, SECTOR_CONFIGS["윤활유동향"])
    cards = ""
    for i, a in enumerate(articles[:5]):
        cards += _build_article_card(a, is_last=(i == min(len(articles), 5) - 1))
    return f"""
          <!-- ── {sector} ── -->
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:22px;">
            <tr>
              <td style="padding-bottom:10px;">
                <span style="font-family:{FONT};font-size:16px;font-weight:bold;color:#555;">{cfg['icon']} &nbsp;{sector}</span>
              </td>
            </tr>
          </table>
{cards}"""


def _build_kpi_dashboard(kpi: dict | None) -> str:
    """Build KPI dashboard row: 환율 / 차량 등록 / 기준금리 / 소비자물가."""
    if not kpi:
        return ""

    ex = kpi.get("exchange_rate", {})
    ir = kpi.get("interest_rate", {})
    cpi = kpi.get("cpi", {})
    vreg = kpi.get("vehicle_reg", {})

    # 환율
    ex_val = ex.get("formatted", "N/A")
    ex_label = ex.get("label", "환율")

    # 차량 등록 대수
    vreg_val = vreg.get("formatted", "N/A")
    vreg_period = vreg.get("period", "")
    mom = vreg.get("mom_pct", 0)
    if mom > 0:
        mom_html = f'<span style="color:#2E7D32;font-size:12px;">▲ {mom:+.1f}%</span>'
    elif mom < 0:
        mom_html = f'<span style="color:#C62828;font-size:12px;">▼ {mom:.1f}%</span>'
    else:
        mom_html = '<span style="color:#888;font-size:12px;">→ 0.0%</span>'

    # 기준금리
    ir_val = ir.get("formatted", "N/A")
    ir_label = ir.get("label", "기준금리")
    ir_updated = ir.get("updated", "")

    # CPI
    cpi_val = cpi.get("formatted", "N/A")
    cpi_year = cpi.get("year", "")

    cell_style = f"padding:14px 10px;text-align:center;border-right:1px solid #EBEBEB;vertical-align:top;"
    last_cell_style = f"padding:14px 10px;text-align:center;vertical-align:top;"
    title_style = f"font-family:{FONT};font-size:10px;color:#999;letter-spacing:1px;text-transform:uppercase;"
    value_style = f"font-family:{FONT};font-size:18px;font-weight:bold;color:#1A1A1A;line-height:1.2;margin-top:4px;"
    sub_style = f"font-family:{FONT};font-size:11px;color:#888;margin-top:3px;"

    return f"""
      <!-- ═══ KPI DASHBOARD ═══ -->
      <tr>
        <td style="background-color:#F8F8F8;border-top:3px solid #e3000f;border-bottom:1px solid #EBEBEB;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td colspan="4" style="padding:8px 16px 4px 16px;">
                <span style="font-family:{FONT};font-size:10px;color:#999;letter-spacing:1.5px;">📊 &nbsp;시장 핵심 지표</span>
              </td>
            </tr>
            <tr>
              <td width="25%" style="{cell_style}">
                <div style="{title_style}">환율</div>
                <div style="{value_style}">{ex_val}</div>
                <div style="{sub_style}">{ex_label}</div>
              </td>
              <td width="25%" style="{cell_style}">
                <div style="{title_style}">차량 등록 (월간)</div>
                <div style="{value_style}">{vreg_val}</div>
                <div style="{sub_style}">{mom_html}&nbsp; {vreg_period} 기준</div>
              </td>
              <td width="25%" style="{cell_style}">
                <div style="{title_style}">기준금리</div>
                <div style="{value_style}">{ir_val}</div>
                <div style="{sub_style}">{ir_label}<br>{ir_updated}</div>
              </td>
              <td width="25%" style="{last_cell_style}">
                <div style="{title_style}">소비자 물가 (CPI)</div>
                <div style="{value_style}">{cpi_val}</div>
                <div style="{sub_style}">전년 대비 YoY&nbsp; {cpi_year}</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
"""


def _build_insights_html(insights: list) -> str:
    rows = ""
    for i, text in enumerate(insights[:5]):
        num = INSIGHT_NUMBERS[i]
        rows += f"""
            <tr><td style="padding:6px 0;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td width="28" valign="top" style="font-family:{FONT};font-size:16px;color:#C8121A;font-weight:bold;line-height:1.6;">{num}</td>
                  <td style="font-family:{FONT};font-size:15px;color:#333333;line-height:1.75;">{_esc(text)}</td>
                </tr>
              </table>
            </td></tr>"""
    return rows


def _build_recommendations_html(recs: list) -> str:
    rows = ""
    for i, text in enumerate(recs[:4]):
        cfg = PRIORITY_CONFIGS[i]
        padding = "padding-bottom:10px;" if i < len(recs) - 1 else ""
        rows += f"""
            <tr><td style="{padding}">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-left:4px solid {cfg['border']};background-color:{cfg['bg']};">
                <tr><td style="padding:13px 16px;">
                  <div style="margin-bottom:7px;">
                    <span style="font-family:{FONT};font-size:14px;font-weight:bold;color:{cfg['color']};">{cfg['label']}</span>
                  </div>
                  <div style="font-family:{FONT};font-size:15px;color:#333;line-height:1.75;">{_esc(text)}</div>
                </td></tr>
              </table>
            </td></tr>"""
    return rows


def build_newsletter_html(
    country: str,
    articles: list,
    days: int,
    raw_count: int = 0,
    source_count: int = 0,
    insights: list = None,
    recommendations: list = None,
    kpi: dict = None,
) -> str:
    name = COUNTRY_NAMES.get(country, country)
    emoji = COUNTRY_EMOJIS.get(country, "🌐")
    market_label = MARKET_LABELS.get(country, f"{country} MARKET")
    now = datetime.now()
    today = now.strftime("%Y.%m.%d")
    weekday = WEEKDAYS_KR[now.weekday()]
    sender_email = os.environ.get("GMAIL_SENDER", "skenbizst@gmail.com")

    # Group by sector and sort by score
    sectors: dict[str, list] = {}
    for a in articles:
        sector = a.get("sector", "윤활유동향")
        sectors.setdefault(sector, []).append(a)
    for s in sectors:
        sectors[s].sort(key=lambda x: x.get("score", 0), reverse=True)

    # Sector blocks
    sector_html = ""
    for sector in SECTOR_ORDER:
        if sector in sectors:
            sector_html += _build_sector_block(sector, sectors[sector])

    # Fallback insights
    if not insights:
        top = sorted(articles, key=lambda x: x.get("score", 0), reverse=True)[:5]
        insights = [a.get("summary_kr", a.get("snippet", a.get("title", "")))[:120] for a in top if a.get("summary_kr") or a.get("snippet")]

    # Fallback recommendations
    if not recommendations:
        recommendations = [
            "경쟁사 동향 분석 기반 대응 전략 수립 검토 필요.",
            "시장 규제 변화 선제 대응을 통한 인증 선점 기회 모색.",
            "전방산업 수요 변화 반영 제품 포트폴리오 최적화.",
            "프리미엄 제품군 재고 전략 조기 재검토 필요.",
        ]

    insights_html = _build_insights_html(insights)
    recs_html = _build_recommendations_html(recommendations)
    kpi_html = _build_kpi_dashboard(kpi)

    collected_count = raw_count if raw_count > 0 else len(articles)
    sources = source_count if source_count > 0 else len(set(a.get("source", "") for a in articles if a.get("source")))

    return f"""<!DOCTYPE html>
<html lang="ko" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="x-apple-disable-message-reformatting">
  <title>SK엔무브 윤활유 시장 인텔리전스 뉴스레터</title>
  <!--[if mso]>
  <noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript>
  <![endif]-->
  <style>
    body {{ margin:0; padding:0; background-color:#F0F0F0; }}
    table {{ border-collapse:collapse; mso-table-lspace:0pt; mso-table-rspace:0pt; }}
    img {{ border:0; display:block; }}
  </style>
</head>
<body style="margin:0;padding:0;background-color:#F0F0F0;font-family:{FONT};">

<!--[if mso]>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#F0F0F0"><tr><td>
<![endif]-->

<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#F0F0F0;">
  <tr>
    <td align="center" style="padding:20px 8px;">
    <table role="presentation" width="620" cellspacing="0" cellpadding="0" border="0" style="width:620px;max-width:620px;">

      <!-- ═══ HEADER ═══ -->
      <!-- 라벨바: 주황 -->
      <tr>
        <td bgcolor="#f04c23" style="background-color:#f04c23;border-radius:8px 8px 0 0;padding:9px 28px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td style="font-family:{FONT};font-size:10px;color:#FFFFFF;letter-spacing:2px;">SK ENMOVE &nbsp;&nbsp;·&nbsp;&nbsp; LUBRICANT MARKET INTELLIGENCE</td>
              <td align="right" style="font-family:{FONT};font-size:10px;color:#FFFFFF;">{today} {weekday}</td>
            </tr>
          </table>
        </td>
      </tr>
      <!-- 타이틀: 빨강 -->
      <tr>
        <td bgcolor="#e3000f" style="background-color:#e3000f;padding:20px 28px 0 28px;">
          <div style="font-family:{FONT};font-size:12px;color:#FFFFFF;letter-spacing:1px;margin-bottom:1px;">{emoji} &nbsp;{market_label}</div>
          <div style="font-family:{FONT};font-size:26px;font-weight:bold;color:#FFFFFF;line-height:1.2;letter-spacing:-0.5px;">{name} 윤활유 시장 Weekly Brief</div>
        </td>
      </tr>
      <!-- 스페이서 -->
      <tr>
        <td bgcolor="#e3000f" style="background-color:#e3000f;height:24px;font-size:1px;line-height:1px;">&nbsp;</td>
      </tr>
      <!-- Pills -->
      <tr>
        <td bgcolor="#e3000f" style="background-color:#e3000f;padding:0 28px 11px 28px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td style="padding:3px 0px;">
                <span style="font-family:{FONT};font-size:13px;color:#FFFFFF;">📅 &nbsp;수집기간: 최근 {days}일</span>
              </td>
              <td style="width:8px;"></td>
              <td style="padding:3px 0px;">
                <span style="font-family:{FONT};font-size:13px;color:#FFFFFF;">📰 &nbsp;수집 기사: {collected_count}건</span>
              </td>
              <td style="width:8px;"></td>
              <td style="padding:3px 0px;">
                <span style="font-family:{FONT};font-size:13px;color:#FFFFFF;">🔍 &nbsp;출처 소스: {sources}개</span>
              </td>
            </tr>
          </table>
        </td>
      </tr>

{kpi_html}

      <!-- ═══ BODY ═══ -->
      <tr>
        <td style="background-color:#FFFFFF;padding:28px 28px 0 28px;">

          <!-- 핵심 인사이트 -->
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td style="border-bottom:2px solid #C8121A;padding-bottom:6px;">
                <span style="font-family:{FONT};font-size:18px;font-weight:bold;color:#1A1A1A;">💡 핵심 인사이트</span>
              </td>
            </tr>
          </table>
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:14px;">
{insights_html}
          </table>

        </td>
      </tr>

      <!-- 섹터별 주요 뉴스 -->
      <tr>
        <td style="background-color:#FFFFFF;padding:28px 28px 0 28px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td style="border-bottom:2px solid #C8121A;padding-bottom:6px;">
                <span style="font-family:{FONT};font-size:18px;font-weight:bold;color:#1A1A1A;">📌 섹터별 주요 뉴스</span>
              </td>
            </tr>
          </table>
{sector_html}
        </td>
      </tr>

      <!-- 마케팅 전략 제언 -->
      <tr>
        <td style="background-color:#FFFFFF;padding:28px 28px 0 28px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td style="border-bottom:2px solid #C8121A;padding-bottom:6px;">
                <span style="font-family:{FONT};font-size:18px;font-weight:bold;color:#1A1A1A;">🎯 마케팅 전략 제언</span>
              </td>
            </tr>
          </table>
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:16px;">
{recs_html}
          </table>
        </td>
      </tr>

      <!-- ═══ FOOTER ═══ -->
      <tr>
        <td style="background-color:#FFFFFF;padding:28px 28px 0 28px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
            <tr><td style="border-top:1px solid #EEEEEE;"></td></tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="background-color:#1C1C1C;border-radius:0 0 8px 8px;padding:24px 28px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td align="center" style="padding-bottom:10px;">
                <span style="font-family:{FONT};font-size:16px;font-weight:bold;color:#FFFFFF;letter-spacing:2px;">SK ENMOVE</span>
                <span style="font-family:{FONT};font-size:14px;color:#888;">&nbsp; · &nbsp;Lubricant Market Intelligence</span>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding-bottom:10px;">
                <span style="font-family:{FONT};font-size:13px;color:#666;line-height:1.8;">본 뉴스레터는 AI 기반 시장 인텔리전스 시스템에 의해 자동 생성되었습니다.<br>수록된 정보는 공개 소스 기반으로 수집·분석된 것이며, 단독 투자·사업 판단의 근거로 사용을 권장하지 않습니다.</span>
              </td>
            </tr>
            <tr>
              <td align="center" style="border-top:1px solid #333;padding-top:10px;">
                <span style="font-family:{FONT};font-size:12px;color:#555;">© {now.year} SK Enmove &nbsp;|&nbsp; 발송일: {today} &nbsp;|&nbsp; 문의: {sender_email}</span>
              </td>
            </tr>
          </table>
        </td>
      </tr>

    </table>
    </td>
  </tr>
</table>

<!--[if mso]>
</td></tr></table>
<![endif]-->

</body>
</html>"""


async def write_newsletter(state: NewsletterState) -> dict:
    """Generate HTML newsletters for all countries."""
    import anthropic
    import asyncio

    grouped = state.get("grouped_articles", {})
    raw_articles = state.get("raw_articles", {})
    merged_articles = state.get("merged_articles", {})
    kpi_data = state.get("kpi_data", {})
    days = state.get("days", 30)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    newsletters: dict[str, str] = {}
    audit_feedback = state.get("audit_feedback", {})
    iteration = state.get("audit_iteration", 0)
    client = anthropic.Anthropic(api_key=api_key) if api_key else None

    for country, articles in grouped.items():
        # Raw collected count (before filtering)
        raw_count = len(raw_articles.get(country, []))
        # Unique sources from merged articles (more accurate)
        merged = merged_articles.get(country, articles)
        source_count = len(set(a.get("source", "") for a in merged if a.get("source")))

        insights: list[str] = []
        recommendations: list[str] = []

        if client and len(articles) >= 2:
            try:
                articles_summary = json.dumps(
                    [{"title": a.get("title_kr", a.get("title", "")),
                      "summary_kr": a.get("summary_kr", a.get("snippet", "")),
                      "sector": a.get("sector", "윤활유동향"),
                      "score": a.get("score", 0)}
                     for a in articles[:15]],
                    ensure_ascii=False,
                )
                feedback_text = ""
                if country in audit_feedback and not audit_feedback[country].get("passed", True):
                    fb = audit_feedback[country]
                    feedback_text = f"\n이전 감사 지적 사항: {', '.join(fb.get('issues', []))}"

                prompt = f"""당신은 SK엔무브 글로벌 MI팀의 {COUNTRY_NAMES.get(country, country)} 시장 분석 전문가입니다.
아래 기사 데이터를 바탕으로 다음을 작성하세요.{feedback_text}

규칙:
- 반드시 명사형 종결어미 사용 (예: "~확인.", "~필요.", "~예상.", "~추진.")
- 경영층 보고 톤, 데이터 기반, 구체적 수치/사실 인용
- 핵심 인사이트: 5개, 각 1-2문장, 윤활유 판매/시장에 미치는 영향 중심
- 전략 제언: 4개, SK엔무브 영업/마케팅팀 실행 가능한 구체적 액션
- [중요] 기사 원문에 명시된 사실만 서술. 추측·평가·전망 등 주관적 해석 금지.
- [중요] 전문가 발언·인용 포함 시 반드시 출처 명시 (예: "XX사 CEO에 따르면").
- [중요] agent 자신의 의견이나 추천을 추가하지 말 것.

기사 데이터:
{articles_summary}

JSON만 출력: {{"insights": ["...", "...", "...", "...", "..."], "recommendations": ["...", "...", "...", "..."]}}"""

                response = await asyncio.to_thread(
                    client.messages.create,
                    model="claude-sonnet-4-6",
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text.strip()
                if "{" in text:
                    data = json.loads(text[text.find("{"):text.rfind("}") + 1])
                    insights = data.get("insights", [])
                    recommendations = data.get("recommendations", [])
            except Exception as e:
                logger.warning(f"[{country}] LLM generation failed: {e}")

        newsletters[country] = build_newsletter_html(
            country=country,
            articles=articles,
            days=days,
            raw_count=raw_count,
            source_count=source_count,
            insights=insights,
            recommendations=recommendations,
            kpi=kpi_data.get(country),
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
