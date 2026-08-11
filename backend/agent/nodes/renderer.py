"""Render UnifiedIssue → HTML for email (A안) and web (tab UI).

Email (A안)
-----------
Layout: Global section + recipient's country section, inline Outlook-safe HTML.
Footer: link to web version with recipient's country pre-selected via ?country=XX.
No JavaScript — full Gmail/Outlook compatibility.

Web (tab UI)
------------
Full tab UI showing all countries. JavaScript toggles visibility per tab.
Progressive enhancement: all sections are visible in <noscript> / tab order.
?country=XX query param sets the initially active tab.
Accessibility: role="tablist", aria-selected, aria-controls on each tab.
"""

from __future__ import annotations

import html as html_module
import os
from datetime import datetime

from backend.agent.state import Article, CountrySection, GlobalSection, UnifiedIssue

# ── Shared constants (copied from writer.py to keep renderer self-contained) ──

FONT = "'Malgun Gothic','맑은 고딕',Arial,sans-serif"

COUNTRY_NAMES = {
    "KR": "한국", "RU": "러시아", "VN": "베트남",
    "TH": "태국", "PH": "필리핀", "PK": "파키스탄",
    "GCC": "GCC(걸프협력회의)",
    "CN": "중국", "US": "미국", "IN": "인도", "JP": "일본",
    "AE": "UAE", "SA": "사우디아라비아", "OM": "오만", "EG": "이집트",
    "MY": "말레이시아", "KH": "캄보디아", "LA": "라오스",
    "CL": "칠레", "AU": "호주", "IL": "이스라엘", "MN": "몽골",
}
COUNTRY_EMOJIS = {
    "KR": "🌏", "RU": "❄️", "VN": "🌴",
    "TH": "🌺", "PH": "🏝️", "PK": "🌙",
    "GCC": "🌙", "CN": "🐉", "US": "🗽", "IN": "🕌", "JP": "🗾",
    "AE": "🇦🇪", "SA": "🇸🇦", "OM": "🇴🇲", "EG": "🇪🇬",
    "MY": "🇲🇾", "KH": "🇰🇭", "LA": "🇱🇦",
    "CL": "🇨🇱", "AU": "🦘", "IL": "🇮🇱", "MN": "🇲🇳",
}
MARKET_LABELS = {
    "KR": "KOREA MARKET", "RU": "RUSSIA MARKET", "VN": "VIETNAM MARKET",
    "TH": "THAILAND MARKET", "PH": "PHILIPPINES MARKET", "PK": "PAKISTAN MARKET",
    "GCC": "GCC MARKET", "CN": "CHINA MARKET", "US": "US MARKET",
    "IN": "INDIA MARKET", "JP": "JAPAN MARKET",
    "AE": "UAE MARKET", "SA": "SAUDI ARABIA MARKET", "OM": "OMAN MARKET", "EG": "EGYPT MARKET",
    "MY": "MALAYSIA MARKET", "KH": "CAMBODIA MARKET", "LA": "LAOS MARKET",
    "CL": "CHILE MARKET", "AU": "AUSTRALIA MARKET", "IL": "ISRAEL MARKET", "MN": "MONGOLIA MARKET",
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


# ── Low-level helpers ─────────────────────────────────────────────────────────


def _esc(text: str) -> str:
    return html_module.escape(str(text)) if text else ""


def _format_pub_date(raw: str) -> str:
    if not raw:
        return "발행일 미확인"
    import re
    from email.utils import parsedate_to_datetime
    raw = raw.strip()
    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y.%m.%d")
    except Exception:
        pass
    m = re.search(r"(\d{4})[-/.]?(\d{2})[-/.]?(\d{2})", raw)
    if m:
        return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
    return "발행일 미확인"


def _score_to_stars(score: float) -> str:
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


def _truncate_at_boundary(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind("다."), cut.rfind("요."), cut.rfind("음."), cut.rfind("."))
    if end != -1 and end >= limit * 0.5:
        return cut[: end + 1]
    space = cut.rfind(" ")
    if space != -1 and space >= limit * 0.5:
        return cut[:space].rstrip() + "…"
    return cut.rstrip() + "…"


# ── Article / section HTML builders ──────────────────────────────────────────


def _article_card(article: Article, is_last: bool = False, show_global_badge: bool = True) -> str:
    title_text = _esc(article.get("title_kr", article.get("title", "")))
    summary = _esc(article.get("summary_kr", article.get("snippet", "")))
    score = article.get("score", 0)
    scope = article.get("scope", "local")
    sector = article.get("sector", "윤활유동향")
    cfg = SECTOR_CONFIGS.get(sector, SECTOR_CONFIGS["윤활유동향"])
    margin_bottom = "4px" if is_last else "10px"

    url = article.get("url", "")
    title_html = (
        f'<a href="{url}" target="_blank" style="color:#111;text-decoration:underline;">{title_text}</a>'
        if url else title_text
    )
    pub_date = _format_pub_date(article.get("published_date", ""))
    date_html = f'<span style="font-family:{FONT};font-size:12px;color:#999;">{pub_date}</span>'

    global_badge = ""
    title_padding = ""
    if show_global_badge and scope == "global":
        global_badge = f"""
                  <tr>
                    <td>
                      <span style="font-family:{FONT};font-size:12px;color:#666;font-weight:bold;background-color:#EBEBEB;padding:2px 7px;border-radius:3px;">🌐 GLOBAL</span>
                    </td>
                  </tr>"""
        title_padding = "padding-top:7px;"

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


def _sector_block(sector: str, articles: list[Article]) -> str:
    if not articles:
        return ""
    cfg = SECTOR_CONFIGS.get(sector, SECTOR_CONFIGS["윤활유동향"])
    cards = "".join(
        _article_card(a, is_last=(i == min(len(articles), 5) - 1))
        for i, a in enumerate(articles[:5])
    )
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


def _insights_html(insights: list[str]) -> str:
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


def _recommendations_html(recs: list[str]) -> str:
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


def _kpi_dashboard(kpi: dict | None) -> str:
    if not kpi:
        return ""
    ex = kpi.get("exchange_rate", {})
    ir = kpi.get("interest_rate", {})
    cpi = kpi.get("cpi", {})
    vreg = kpi.get("vehicle_reg", {})

    ex_val = ex.get("formatted", "N/A")
    ex_label = ex.get("label", "환율")
    vreg_val = vreg.get("formatted", "N/A")
    vreg_period = vreg.get("period", "")
    mom = vreg.get("mom_pct", 0)
    if mom > 0:
        mom_html = f'<span style="color:#2E7D32;font-size:12px;">▲ {mom:+.1f}%</span>'
    elif mom < 0:
        mom_html = f'<span style="color:#C62828;font-size:12px;">▼ {mom:.1f}%</span>'
    else:
        mom_html = '<span style="color:#888;font-size:12px;">→ 0.0%</span>'
    ir_val = ir.get("formatted", "N/A")
    ir_label = ir.get("label", "기준금리")
    ir_updated = ir.get("updated", "")
    cpi_val = cpi.get("formatted", "N/A")
    cpi_year = cpi.get("year", "")

    cell = f"padding:14px 10px;text-align:center;border-right:1px solid #EBEBEB;vertical-align:top;"
    last = f"padding:14px 10px;text-align:center;vertical-align:top;"
    title_s = f"font-family:{FONT};font-size:10px;color:#999;letter-spacing:1px;text-transform:uppercase;"
    val_s = f"font-family:{FONT};font-size:18px;font-weight:bold;color:#1A1A1A;line-height:1.2;margin-top:4px;"
    sub_s = f"font-family:{FONT};font-size:11px;color:#888;margin-top:3px;"

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
              <td width="25%" style="{cell}">
                <div style="{title_s}">환율</div>
                <div style="{val_s}">{ex_val}</div>
                <div style="{sub_s}">{ex_label}</div>
              </td>
              <td width="25%" style="{cell}">
                <div style="{title_s}">차량 등록 (월간)</div>
                <div style="{val_s}">{vreg_val}</div>
                <div style="{sub_s}">{mom_html}&nbsp; {vreg_period} 기준</div>
              </td>
              <td width="25%" style="{cell}">
                <div style="{title_s}">기준금리</div>
                <div style="{val_s}">{ir_val}</div>
                <div style="{sub_s}">{ir_label}<br>{ir_updated}</div>
              </td>
              <td width="25%" style="{last}">
                <div style="{title_s}">소비자 물가 (CPI)</div>
                <div style="{val_s}">{cpi_val}</div>
                <div style="{sub_s}">전년 대비 YoY&nbsp; {cpi_year}</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
"""


def _articles_by_sector(articles: list[Article]) -> str:
    sectors: dict[str, list[Article]] = {}
    for a in articles:
        sectors.setdefault(a.get("sector", "윤활유동향"), []).append(a)
    for s in sectors:
        sectors[s].sort(key=lambda x: x.get("score", 0), reverse=True)
    return "".join(_sector_block(s, sectors[s]) for s in SECTOR_ORDER if s in sectors)


def _fallback_insights(articles: list[Article]) -> list[str]:
    top = sorted(articles, key=lambda x: x.get("score", 0), reverse=True)[:5]
    return [
        _truncate_at_boundary(a.get("summary_kr", a.get("snippet", a.get("title", ""))), 120)
        for a in top
        if a.get("summary_kr") or a.get("snippet")
    ]


_FALLBACK_RECS = [
    "경쟁사 동향 분석 기반 대응 전략 수립 검토 필요.",
    "시장 규제 변화 선제 대응을 통한 인증 선점 기회 모색.",
    "전방산업 수요 변화 반영 제품 포트폴리오 최적화.",
    "프리미엄 제품군 재고 전략 조기 재검토 필요.",
]


# ── Email header / footer helpers ──────────────────────────────────────────────


def _email_header(recipient_country: str, date_str: str, days: int,
                  raw_count: int, source_count: int) -> str:
    name = COUNTRY_NAMES.get(recipient_country, recipient_country)
    emoji = COUNTRY_EMOJIS.get(recipient_country, "🌐")
    market_label = MARKET_LABELS.get(recipient_country, f"{recipient_country} MARKET")
    now = datetime.now()
    today = now.strftime("%Y.%m.%d")
    weekday = WEEKDAYS_KR[now.weekday()]
    return f"""  <!-- ═══ HEADER ═══ -->
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
      <tr>
        <td bgcolor="#e3000f" style="background-color:#e3000f;padding:20px 28px 0 28px;">
          <div style="font-family:{FONT};font-size:12px;color:#FFFFFF;letter-spacing:1px;margin-bottom:1px;">{emoji} &nbsp;{market_label}</div>
          <div style="font-family:{FONT};font-size:26px;font-weight:bold;color:#FFFFFF;line-height:1.2;letter-spacing:-0.5px;">{name} 윤활유 시장 Weekly Brief</div>
        </td>
      </tr>
      <tr>
        <td bgcolor="#e3000f" style="background-color:#e3000f;height:24px;font-size:1px;line-height:1px;">&nbsp;</td>
      </tr>
      <tr>
        <td bgcolor="#e3000f" style="background-color:#e3000f;padding:0 28px 11px 28px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td style="padding:3px 0px;"><span style="font-family:{FONT};font-size:13px;color:#FFFFFF;">📅 &nbsp;수집기간: 최근 {days}일</span></td>
              <td style="width:8px;"></td>
              <td style="padding:3px 0px;"><span style="font-family:{FONT};font-size:13px;color:#FFFFFF;">📰 &nbsp;수집 기사: {raw_count}건</span></td>
              <td style="width:8px;"></td>
              <td style="padding:3px 0px;"><span style="font-family:{FONT};font-size:13px;color:#FFFFFF;">🔍 &nbsp;출처 소스: {source_count}개</span></td>
            </tr>
          </table>
        </td>
      </tr>"""


def _email_footer(run_id: str, recipient_country: str, web_base_url: str) -> str:
    sender_email = os.environ.get("GMAIL_SENDER", "skenbizst@gmail.com")
    now = datetime.now()
    today = now.strftime("%Y.%m.%d")
    web_url = f"{web_base_url}/newsletters/{run_id}?country={recipient_country}"
    return f"""      <!-- ═══ WEB LINK ═══ -->
      <tr>
        <td style="background-color:#FFFFFF;padding:24px 28px 0 28px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid #E0E0E0;border-radius:6px;background-color:#F8F8F8;">
            <tr>
              <td style="padding:16px 20px;">
                <span style="font-family:{FONT};font-size:14px;font-weight:bold;color:#1A1A1A;">🌐 다른 국가 뉴스 보기</span><br>
                <span style="font-family:{FONT};font-size:13px;color:#666;line-height:1.7;">이 뉴스레터에는 전체 국가 소식이 수록되어 있습니다.<br>웹 버전에서 국가 탭을 선택해 다른 시장 동향을 확인하세요.</span><br>
                <a href="{web_url}" style="font-family:{FONT};font-size:13px;color:#e3000f;font-weight:bold;">→ 웹에서 전체 국가 뉴스 보기</a>
              </td>
            </tr>
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
      </tr>"""


# ── Section renderers ─────────────────────────────────────────────────────────


def _render_global_section_email(global_section: GlobalSection, days: int) -> str:
    articles = global_section.get("articles", [])
    if not articles:
        return ""

    sector_html = _articles_by_sector(articles)
    all_insights = _fallback_insights(articles)
    insights_html = _insights_html(all_insights)

    return f"""      <!-- ═══ GLOBAL SECTION ═══ -->
      <tr>
        <td style="background-color:#FFFFFF;padding:28px 28px 0 28px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td style="border-bottom:2px solid #333;padding-bottom:6px;">
                <span style="font-family:{FONT};font-size:18px;font-weight:bold;color:#1A1A1A;">🌐 글로벌 공통 소식</span>
              </td>
            </tr>
          </table>
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:14px;">
{insights_html}
          </table>
{sector_html}
        </td>
      </tr>"""


def _render_country_section_email(cs: CountrySection) -> str:
    country = cs.get("country", "")
    articles = cs.get("articles", [])
    name = COUNTRY_NAMES.get(country, country)
    emoji = COUNTRY_EMOJIS.get(country, "🌐")
    kpi = cs.get("kpi_data")
    insights = cs.get("insights") or _fallback_insights(articles)
    recs = cs.get("recommendations") or _FALLBACK_RECS

    kpi_html = _kpi_dashboard(kpi)
    insights_html = _insights_html(insights)
    recs_html = _recommendations_html(recs)

    if not articles:
        empty_msg = f'<tr><td style="padding:20px 0;font-family:{FONT};font-size:14px;color:#999;">이번 호에는 {name} 관련 소식이 없습니다.</td></tr>'
        sector_html = f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">{empty_msg}</table>'
    else:
        sector_html = _articles_by_sector(articles)

    return f"""      <!-- ═══ COUNTRY SECTION: {country} ═══ -->
      <tr>
        <td style="background-color:#FFFFFF;padding:28px 28px 0 28px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td style="border-bottom:2px solid #C8121A;padding-bottom:6px;">
                <span style="font-family:{FONT};font-size:18px;font-weight:bold;color:#1A1A1A;">{emoji} {name} 시장 동향</span>
              </td>
            </tr>
          </table>
        </td>
      </tr>
{kpi_html}
      <tr>
        <td style="background-color:#FFFFFF;padding:14px 28px 0 28px;">
          <!-- 핵심 인사이트 -->
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td style="border-bottom:2px solid #C8121A;padding-bottom:6px;">
                <span style="font-family:{FONT};font-size:16px;font-weight:bold;color:#1A1A1A;">💡 핵심 인사이트</span>
              </td>
            </tr>
          </table>
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:12px;">
{insights_html}
          </table>
{sector_html}
          <!-- 마케팅 전략 제언 -->
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:22px;">
            <tr>
              <td style="border-bottom:2px solid #C8121A;padding-bottom:6px;">
                <span style="font-family:{FONT};font-size:16px;font-weight:bold;color:#1A1A1A;">🎯 마케팅 전략 제언</span>
              </td>
            </tr>
          </table>
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:16px;">
{recs_html}
          </table>
        </td>
      </tr>"""


# ── Public API ────────────────────────────────────────────────────────────────


def render_email_html(
    issue: UnifiedIssue,
    recipient_country: str,
    run_id: str,
    days: int = 30,
    raw_count: int = 0,
    source_count: int = 0,
    web_base_url: str = "",
) -> str:
    """Render A안 email HTML: Global section + recipient country section.

    Compatible with Gmail and Outlook (table-based layout, no JS).
    Footer includes a link to the web version with ?country=<recipient_country>.
    """
    if not web_base_url:
        web_base_url = os.environ.get("WEB_BASE_URL", "https://newsletter-says.onrender.com")

    global_section = issue.get("global_section", GlobalSection(articles=[]))
    country_sections = issue.get("country_sections", {})
    cs = country_sections.get(recipient_country, CountrySection(
        country=recipient_country, articles=[], insights=[], recommendations=[], kpi_data={},
    ))

    header = _email_header(recipient_country, issue.get("date_str", ""), days, raw_count, source_count)
    global_html = _render_global_section_email(global_section, days)
    country_html = _render_country_section_email(cs)
    footer = _email_footer(run_id, recipient_country, web_base_url)

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
<!--[if mso]><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#F0F0F0"><tr><td><![endif]-->
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#F0F0F0;">
  <tr>
    <td align="center" style="padding:20px 8px;">
    <table role="presentation" width="620" cellspacing="0" cellpadding="0" border="0" style="width:620px;max-width:620px;">
{header}
{global_html}
{country_html}
{footer}
    </table>
    </td>
  </tr>
</table>
<!--[if mso]></td></tr></table><![endif]-->
</body>
</html>"""


def render_web_html(
    issue: UnifiedIssue,
    default_country: str = "KR",
) -> str:
    """Render web tab UI HTML: all countries in tabs, JS-driven tab switching.

    Progressive enhancement:
    - With JS: tabs switch on click, ?country=XX sets initial active tab
    - Without JS (<noscript>): all sections are displayed sequentially

    Accessibility:
    - role="tablist" / role="tab" / role="tabpanel"
    - aria-selected, aria-controls, tabindex on tabs
    """
    countries = issue.get("countries", [])
    global_section = issue.get("global_section", GlobalSection(articles=[]))
    country_sections = issue.get("country_sections", {})
    date_str = issue.get("date_str", "")
    run_id = issue.get("run_id", "")

    now = datetime.now()
    today = now.strftime("%Y.%m.%d")
    weekday = WEEKDAYS_KR[now.weekday()]

    # ── Tab bar ───────────────────────────────────────────────────────────────
    tab_items = ""
    for cc in countries:
        name = COUNTRY_NAMES.get(cc, cc)
        emoji = COUNTRY_EMOJIS.get(cc, "🌐")
        tab_items += f"""    <button role="tab" id="tab-{cc}" aria-controls="panel-{cc}" aria-selected="false"
      class="sk-tab" data-country="{cc}"
      style="display:inline-flex;align-items:center;gap:6px;padding:10px 18px;border:none;border-bottom:3px solid transparent;background:transparent;cursor:pointer;font-family:{FONT};font-size:14px;font-weight:600;color:#555;white-space:nowrap;"
      onclick="switchTab('{cc}')">{emoji} {name}</button>\n"""

    # ── Global section panel ──────────────────────────────────────────────────
    global_articles = global_section.get("articles", [])
    if global_articles:
        g_sector_html = _articles_by_sector(global_articles)
        global_panel_content = f"""
      <h2 style="font-size:20px;font-weight:bold;color:#1A1A1A;border-bottom:2px solid #333;padding-bottom:8px;margin:0 0 20px 0;">🌐 글로벌 공통 소식</h2>
      {g_sector_html}"""
    else:
        global_panel_content = '<p style="color:#999;padding:20px 0;">이번 호 글로벌 공통 소식이 없습니다.</p>'

    # ── Country section panels ────────────────────────────────────────────────
    country_panels = ""
    for cc in countries:
        cs = country_sections.get(cc, CountrySection(
            country=cc, articles=[], insights=[], recommendations=[], kpi_data={},
        ))
        articles = cs.get("articles", [])
        name = COUNTRY_NAMES.get(cc, cc)
        emoji = COUNTRY_EMOJIS.get(cc, "🌐")
        insights = cs.get("insights") or _fallback_insights(articles)
        recs = cs.get("recommendations") or _FALLBACK_RECS
        kpi = cs.get("kpi_data")

        if articles:
            sector_body = _articles_by_sector(articles)
        else:
            sector_body = f'<p style="color:#999;padding:20px 0;font-family:{FONT};">이번 호에는 {name} 관련 소식이 없습니다.</p>'

        kpi_block = _kpi_dashboard(kpi)

        insights_rows = _insights_html(insights)
        recs_rows = _recommendations_html(recs)

        country_panels += f"""
    <div role="tabpanel" id="panel-{cc}" aria-labelledby="tab-{cc}" class="sk-panel" style="display:none;">
      <h2 style="font-size:20px;font-weight:bold;color:#1A1A1A;border-bottom:2px solid #C8121A;padding-bottom:8px;margin:0 0 20px 0;">{emoji} {name} 시장 동향</h2>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
        {kpi_block}
      </table>
      <h3 style="font-size:16px;font-weight:bold;color:#1A1A1A;margin:24px 0 12px 0;">💡 핵심 인사이트</h3>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
        {insights_rows}
      </table>
      <h3 style="font-size:16px;font-weight:bold;color:#1A1A1A;margin:24px 0 12px 0;">📌 섹터별 주요 뉴스</h3>
      {sector_body}
      <h3 style="font-size:16px;font-weight:bold;color:#1A1A1A;margin:24px 0 12px 0;">🎯 마케팅 전략 제언</h3>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
        {recs_rows}
      </table>
    </div>
"""

    sender_email = os.environ.get("GMAIL_SENDER", "skenbizst@gmail.com")

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SK엔무브 윤활유 시장 인텔리전스 뉴스레터 — {today}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #F0F0F0; font-family: {FONT}; color: #1A1A1A; }}
    .sk-wrapper {{ max-width: 860px; margin: 0 auto; padding: 24px 12px; }}
    .sk-header {{ background: #e3000f; color: #fff; border-radius: 8px 8px 0 0; padding: 24px 32px; }}
    .sk-label {{ font-size: 10px; letter-spacing: 2px; color: rgba(255,255,255,0.8); margin-bottom: 4px; }}
    .sk-title {{ font-size: 24px; font-weight: bold; line-height: 1.3; }}
    .sk-tab-bar {{ background: #fff; border-bottom: 1px solid #E0E0E0; overflow-x: auto; white-space: nowrap; display: flex; }}
    .sk-tab[aria-selected="true"] {{ color: #e3000f !important; border-bottom-color: #e3000f !important; }}
    .sk-tab:hover {{ color: #e3000f; }}
    .sk-global-panel {{ background: #fff; padding: 28px 32px; border-bottom: 3px solid #E0E0E0; }}
    .sk-panels {{ background: #fff; padding: 28px 32px; border-radius: 0 0 8px 8px; }}
    .sk-panel {{ display: none; }}
    .sk-panel.active {{ display: block; }}
    .sk-footer {{ background: #1C1C1C; color: #888; text-align: center; padding: 24px 32px; border-radius: 0 0 8px 8px; font-size: 12px; line-height: 1.8; }}
    .sk-footer strong {{ color: #fff; font-size: 16px; letter-spacing: 2px; }}
    /* noscript: show all panels */
  </style>
</head>
<body>
<div class="sk-wrapper">

  <!-- Header -->
  <div class="sk-header">
    <div class="sk-label">SK ENMOVE · LUBRICANT MARKET INTELLIGENCE</div>
    <div class="sk-title">글로벌 윤활유 시장 Weekly Brief</div>
    <div style="font-size:13px;color:rgba(255,255,255,0.8);margin-top:6px;">📅 {today} {weekday}</div>
  </div>

  <!-- Global section (always shown, above tabs) -->
  <div class="sk-global-panel">
    {global_panel_content}
  </div>

  <!-- Tab bar -->
  <div class="sk-tab-bar" role="tablist" aria-label="국가별 시장 동향">
{tab_items}  </div>

  <!-- Country panels -->
  <div class="sk-panels">
{country_panels}

    <!-- noscript fallback: show all panels sequentially -->
    <noscript>
      <style>.sk-panel {{ display: block !important; border-bottom: 2px solid #E0E0E0; padding-bottom: 32px; margin-bottom: 32px; }}</style>
    </noscript>
  </div>

  <!-- Footer -->
  <div class="sk-footer">
    <div><strong>SK ENMOVE</strong> &nbsp;·&nbsp; Lubricant Market Intelligence</div>
    <div>본 뉴스레터는 AI 기반 시장 인텔리전스 시스템에 의해 자동 생성되었습니다.</div>
    <div>© {now.year} SK Enmove &nbsp;|&nbsp; 발송일: {today} &nbsp;|&nbsp; 문의: {sender_email}</div>
  </div>

</div>

<script>
(function () {{
  // Read initial country from ?country=XX query param, fallback to default
  var defaultCountry = "{default_country}";
  var params = new URLSearchParams(window.location.search);
  var initialCountry = params.get("country") || defaultCountry;

  function switchTab(country) {{
    // Deactivate all tabs and panels
    document.querySelectorAll(".sk-tab").forEach(function (t) {{
      t.setAttribute("aria-selected", "false");
      t.style.color = "#555";
      t.style.borderBottomColor = "transparent";
    }});
    document.querySelectorAll(".sk-panel").forEach(function (p) {{
      p.style.display = "none";
    }});

    // Activate selected tab and panel
    var tab = document.getElementById("tab-" + country);
    var panel = document.getElementById("panel-" + country);
    if (tab) {{
      tab.setAttribute("aria-selected", "true");
      tab.style.color = "#e3000f";
      tab.style.borderBottomColor = "#e3000f";
    }}
    if (panel) {{
      panel.style.display = "block";
    }}

    // Update URL without reload
    var url = new URL(window.location);
    url.searchParams.set("country", country);
    history.replaceState(null, "", url);
  }}

  // Keyboard navigation on tab bar
  document.querySelectorAll(".sk-tab").forEach(function (tab) {{
    tab.setAttribute("tabindex", "0");
    tab.addEventListener("keydown", function (e) {{
      if (e.key === "Enter" || e.key === " ") {{
        e.preventDefault();
        switchTab(tab.dataset.country);
      }}
    }});
  }});

  // Initial tab
  switchTab(initialCountry);

  // Expose for onclick attributes
  window.switchTab = switchTab;
}})();
</script>
</body>
</html>"""
