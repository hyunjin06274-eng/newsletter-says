"""Phase 2: Article scoring, tagging, and filtering using Anthropic Claude."""

import json
import logging
import os
import re
from datetime import datetime

from backend.agent.state import NewsletterState, Article

logger = logging.getLogger(__name__)

SCORING_PROMPT = """You are an MI analyst for SK Enmove, a lubricant company.
Score this article on a scale of 0-30 for relevance to FINISHED lubricant product sales strategy.

The core question: "Does this news affect how SK Enmove sells lubricants?"

Scoring dimensions (each 0-10, total max 30):

A. Sales Relevance (0-10):
- 10: Direct competitor new product/promotion/channel in target country
- 8: Lubricant regulation change (API/ACEA/tariff) in target country
- 6: Vehicle/equipment sales data directly affecting lubricant demand
- 4: Base oil/crude price affecting manufacturing cost
- 2: Tangential industry news
- 0: Irrelevant

B. Country Specificity (0-10):
- 10: Exclusively about target country market, local companies, local data
- 7: Primarily about target country with some global context
- 4: Regional (Asia/Europe) news with some target country relevance
- 1: Pure global news with indirect country impact
- 0: About a different specific country

C. Actionability (0-10):
- 10: Requires immediate response (competitor launch, regulation deadline)
- 7: Should influence quarterly planning
- 4: Good-to-know market intelligence
- 2: Background context only
- 0: No actionable insight
- 0: Irrelevant — crypto, real estate, stock market, generic politics, entertainment, food, fashion

STRICT EXCLUSION rules:
- EV-only battery/charging articles with NO mention of lubricant/oil demand impact: score 0
- Pure stock market / financial instrument news: score 0
- Base oil-only upstream articles with no downstream sales implication: max 1 point
- Generic CSR/ESG/sustainability fluff: score 0
- Paid market research report previews (Mordor Intelligence, Allied Market Research, etc.): score 0

CRITICAL — COUNTRY vs GLOBAL classification:
Target country: {country}
Note: If target country is "GCC", treat ANY of these as "local": Saudi Arabia (SA), UAE (AE), Kuwait (KW), Qatar (QA), Bahrain (BH), Oman (OM), or GCC/Gulf States as a whole.

Classify scope strictly:
- "local" = article is specifically about {country} market, companies, events, or policy
- "global" = ONLY use for: OPEC production decisions, API/ACEA/ILSAC spec changes,
             Group II/III base oil price shifts, or supply disruptions affecting ALL markets equally.
             Do NOT use "global" for articles about US, Europe, India, China, or any other single market.
- "other_country" = article is about a DIFFERENT specific country or region, NOT {country}.
             Use this even if the article mentions lubricants or vehicles — if the market focus
             is another country (e.g., US motor oil shortage, India EV policy, Philippine car sales),
             classify as "other_country" → total score MUST be 0.

IMPORTANT: When in doubt between "global" and "other_country", choose "other_country".
A US market article about motor oil shortage is NOT global — it is "other_country" for {country}.

Article:
Title: {title}
Snippet: {snippet}
Source: {source}
Target country: {country}
Domain: {domain}

IMPORTANT — Factual accuracy in "reason" field:
- Write the reason based ONLY on what the article states. Do NOT reinterpret geopolitical events.
- If the article mentions a specific conflict (e.g., Iran war), do NOT replace it with another (e.g., Ukraine war).
- Use the original article's references verbatim.

Respond in JSON: {{"score_sales": 0-10, "score_country": 0-10, "score_action": 0-10, "scope": "local|global|other_country", "sector": "윤활유동향|경쟁사활동|전방산업동향|윤활유규제", "reason": "brief Korean reason", "tags": ["tag1"]}}
"""

NEGATIVE_KEYWORDS = [
    # ── 금융·주가 (순수 주식시장 뉴스) ──────────────────────────────────────
    "bitcoin", "cryptocurrency", "crypto", "dogecoin", "shiba inu",
    "stock market", "dow jones", "s&p 500", "nasdaq", "wall street", "forex",
    "seoul stocks", "korean stocks", "shares open lower", "shares open higher",
    "bourse", "wall street closes", "wall street opens",
    "stocks fall", "stocks rise", "stock index",
    "주식", "코인", "가상화폐",
    "외국인 보유 종목", "krx 외국인",
    # ── 부동산 ───────────────────────────────────────────────────────────
    "real estate", "property price", "부동산", "집값", "아파트 분양",
    # ── 유료 페이드 마켓 리서치 ────────────────────────────────────────────
    "smartkarma", "grand view research", "mordor intelligence",
    "allied market research", "technavio", "imarc group", "indexbox",
    "buy now", "request a sample", "download report",
    "market analysis, forecast, size, trends and insights",
    # ── 장기 시장 전망 리포트 (CAGR 패턴) ────────────────────────────────
    "cagr ", "cagr,", "cagr of",
    "market size forecast", "market forecast report",
    "lubricant market forecast", "lubricants market forecast",
    "lubricant market size", "lubricants market size",
    "market research report", "market analysis report",
    "market is projected to reach", "market is expected to reach",
    "market will reach",
    "million by 203", "billion by 203", "million by 202", "billion by 202",
    "향후 시장 전망", "시장 규모 예측", "시장 전망 보고서", "글로벌 시장 분석 리포트",
    # ── 순수 엔터테인먼트 ─────────────────────────────────────────────────
    "celebrity", "k-pop", "drama",
    # ── 의료·보험 ─────────────────────────────────────────────────────────
    "한의과", "한방병원", "한방 치료", "진료비", "의료비",
    "8주 룰", "경상환자", "자동차보험 진료",
    # ── 스포츠·구단 (기업명 포함돼도 윤활유와 무관) ─────────────────────────
    "배구단", "배구 구단", "배구 선수", "배구 경기", "배구 리그",
    "준플레이오프", "플레이오프 진출",
    "v리그", "v-리그", "봄 배구", "챔프전", "챔피언 결정전",
    "농구단", "야구단", "축구단", "스포츠단",
    "후원 업무협약", "공식 후원사", "스포츠 스폰서",
    "volleyball", "basketball team", "baseball team", "football club",
    "playoff results", "sports sponsorship",
    "경기 결과", "경기 승리", "우승", "준우승",
    # ── CSR·문화예술·사회공헌 ──────────────────────────────────────────────
    "문화예술 나눔", "나눔공연", "사회공헌 활동", "봉사 활동",
    "문화 공연", "나눔 콘서트", "csr 활동",
    "환경보호 캠페인", "탄소중립 캠페인", "지속가능성 수상",
    "기업시민", "사회적 가치", "esg 캠페인",
    # ── IT아웃소싱·전산 ─────────────────────────────────────────────────
    "it아웃소싱", "it 아웃소싱", "통합 it아웃소싱",
    "it 시스템 구축", "erp 구축", "sap 구축",
    "it 인프라", "데이터센터 구축",
    # ── 지식재산권·특허 분쟁 ──────────────────────────────────────────────
    "지재권", "지식재산권", "특허 침해", "특허분쟁", "상표 침해",
    "intellectual property infringement", "patent infringement",
    "trademark infringement",
    # ── 증권사 주식 분석 리포트 ───────────────────────────────────────────
    "가장 빠른 리포트", "클릭 e종목", "today's pick", "종목 분석", "투자 의견",
    # ── 주유소·연료비·주유 할인 (윤활유 완제품 판매와 무관) ──────────────────
    "주유소", "주유 할인", "주유할인", "주유 제휴", "주유제휴",
    "연료비 절감", "제유카드", "주유카드", "주유 앱",
    "주유 멤버십", "주유 포인트", "주유 쿠폰", "주유비",
    "휘발유 가격", "경유 가격", "기름값",
    "gas station", "petrol station", "filling station",
    "gas station discount", "fuel discount", "fuel rewards",
    "fuel card discount", "fuel card", "fuel voucher", "fuel coupon",
    "fuel subsidy", "gasoline price", "diesel price",
    # ── 연비 팁 ──────────────────────────────────────────────────────────
    "연비 향상 팁", "경제운전 팁", "연비 절약", "연료 절약 방법",
    "fuel saving tips", "fuel economy tips",
    # ── 브랜드 수상·순위 PR ────────────────────────────────────────────────
    "k-bpi", "kbpi", "한국산업의 브랜드파워", "한국의 브랜드파워",
    "브랜드파워 1위", "고객만족지수 1위", "소비자만족도 1위",
    # ── 군사·교전·공격 (연료 저장소 피격 등) ─────────────────────────────
    "attacked occupiers", "fuel and lubricant depots",
    "electronic warfare station", "occupiers' fuel",
    "drone strike on depot", "air strike on fuel",
    # ── 레이싱 갤러리 ───────────────────────────────────────────────────
    "drag racing gallery", "capturing drag racing", "race gallery", "motorsport gallery",
    # ── 순수 농업 식품 기사 (농기계 제외) ────────────────────────────────
    "food security", "crop production", "rice harvest", "wheat harvest",
    "food", "restaurant",
    # ── 완전 다른 산업 ──────────────────────────────────────────────────
    "gold mine", "kumtor",
    # ── 금융·정치 인사 뉴스 ───────────────────────────────────────────────
    "한은총재", "총재 후보", "중앙은행 총재",
    "노벨상 후보", "노벨 경제학",
    "금리 결정", "기준금리", "통화정책",
]

# ── 제목 차단 패턴 (정규식) — LLM 호출 전 코드 기반 차단 ──────────────────────
TITLE_BLOCKLIST_PATTERNS = [
    # 경쟁사·정유사 분기 실적·영업이익·배당
    r"(?:에쓰오일|[Ss]-?[Oo]il).{0,30}(?:실적|영업이익|순이익|매출액|배당|[Qq][1-4]\s*실적)",
    r"(?:GS칼텍스|HD현대오일뱅크|현대오일뱅크|SK에너지).{0,30}(?:실적|영업이익|순이익|배당)",
    r"(?:Shell|Castrol|ExxonMobil|TotalEnergies|Valvoline|Lukoil|BP)"
    r".{0,30}(?:earnings|revenue|profit|dividend|quarterly results|[Qq][1-4] results)",
    # 글로벌 EV 합작 (국가 언급 없는 것)
    r"소니.{0,25}혼다.{0,35}(?:합작|EV|전기차|협력|파트너)",
    r"혼다.{0,25}소니.{0,35}(?:합작|EV|전기차|협력|파트너)",
    # 장기 시장 전망 리포트 제목
    r"\d{4}\s*[~\-]\s*\d{4}.{0,20}(?:전망|시장 규모|시장 분석|분석 보고서)",
    r"(?:[Gg]lobal|[Ww]orldwide)\s+[Ll]ubricant.{0,30}(?:[Mm]arket|[Ff]orecast|[Oo]utlook).{0,30}\d{4}",
    # 경쟁사 순수 주가·상장
    r"(?:에쓰오일|현대오일뱅크|GS칼텍스).{0,20}(?:주가|주식|[Ii][Pp][Oo]|상장)",
    # 데이터센터 냉각유 (자동차 윤활유와 무관)
    r"(?:데이터센터|서버|[Dd]ata.?[Cc]enter|[Ss]erver).{0,25}(?:냉각유|냉각|[Cc]ooling.?[Ff]luid|[Tt]hermal.?[Ff]luid)",
    # 거시경제·국제기구 순수 정책
    r"WTO\s*(?:회의|각료|총회|협상|결정|규정)",
    r"G20\s*(?:정상|회의|서밋|합의|성명)",
    r"IMF\s*(?:전망|보고서|경고|권고|전망치)",
    r"GDP\s*(?:성장|하락|전망|감소|증가|추이)",
    # 목공·금속가공·섬유 산업
    r"목공|목재\s*가공|절삭유|공작기계|섬유\s*(?:산업|직물|원단)|직물",
    r"woodworking|metalworking|textile\s*(?:industry|mill|fabric)|cutting\s*fluid",
    r"деревообработ|древесин|металлообработ|текстильн",
    # 소비자 사용후기·랭킹
    r"(?:교체|사용)\s*후기|추천\s*템|베스트\s*\d+\s*(?:제품|오일|추천)",
    r"많이\s*팔린|인기\s*상품|판매\s*랭킹|구매\s*후기",
    # CSR·사회공헌
    r"CSR|사회\s*공헌|봉사\s*활동|기부\s*(?:행사|캠페인)|charity|volunteer",
    # 스포츠·엔터테인먼트
    r"(?:축구|야구|농구|배구|골프|테니스)\s*(?:경기|선수|팀|리그|우승|감독)",
    r"올림픽|월드컵|EPL|프리미어\s*리그|챔피언스\s*리그|스포츠\s*후원",
    r"[Kk][Ii][Xx][Xx].{0,30}(?:승리|패배|우승|꺾고|결승|PO|플레이오프|챔프전|배구)",
    r"(?:서울\s*KIXX|현대건설.{0,15}꺾고|꺾고.{0,15}PO)",
    # 순수 재무·주가 (윤활유 내용 없는 것)
    r"(?:실적|영업이익|순이익)\s*(?:반등|악화|개선|하락|전망|발표|서프라이즈)",
    r"주가.{0,25}(?:하락|상승|급락|급등|반등|전망|목표가)",
    r"(?:에쓰오일|[Ss]-?[Oo]il|GS칼텍스|현대오일뱅크).{0,40}(?:목표주가|목표가|정제마진|원유\s*조달)",
    r"정제마진.{0,30}(?:강세|상승|구조적|[Ss]-?[Oo]il|에쓰오일|GS칼텍스)",
    # CSR 보훈·사회복지 지원
    r"(?:쌀|연탄|성금|물품|급식|장학금|기부금).{0,20}(?:지원|기부|전달|나눔|봉사)",
    r"(?:보훈|사회복지|불우이웃|취약계층).{0,20}(?:지원|후원|전달|봉사)",
    # 경쟁사 브랜드 수상·CSR
    r"(?:GS칼텍스|에쓰오일|현대오일뱅크|HD현대오일뱅크|쉘|카스트롤|루코일)"
    r".{0,40}(?:디자인\s*어워드|대상\s*수상|우수\s*기업\s*선정|브랜드\s*파워\s*1위"
    r"|소비자\s*대상|지속가능경영\s*대상|기업\s*시민\s*대상)",
    # OEM 차량 서비스 프로모션 (윤활유 아닌 차량 서비스)
    r"(?:르노\s*코리아|르노코리아|BYD|볼보\s*코리아|GM\s*코리아|쌍용\s*자동차)"
    r".{0,40}(?:무상\s*점검|점검\s*이벤트|무상\s*수리|서비스\s*캠페인|구매\s*할인)",
]

# ── 윤활유 safeguard 키워드 — blocklist 매칭 시 교차 확인용 ─────────────────────
# blocklist 패턴이 매칭돼도 이 키워드가 제목/스니펫에 있으면 차단하지 않음
LUBRICANT_SAFEGUARD_KEYWORDS = [
    # 영어
    "lubricant", "lubricants", "engine oil", "motor oil", "gear oil",
    "transmission oil", "transmission fluid", "grease", "hydraulic oil",
    "pcmo", "hddo", "mco", "motorcycle oil", "industrial oil",
    "base oil", "lube oil", "synthetic oil", "oil change",
    # 한국어
    "윤활유", "엔진오일", "기어유", "미션유", "그리스", "유압유",
    "기유", "합성유", "엔진 오일", "윤활", "오일 교환",
    # 러시아어
    "смазочн", "моторное масло", "трансмиссионн", "консистентн",
    "гидравлическое масло",
    # 베트남어
    "dầu nhớt", "dầu hộp số", "mỡ bôi trơn", "dầu thủy lực",
    # 태국어
    "น้ำมันหล่อลื่น", "น้ำมันเกียร์", "น้ำมันเครื่อง",
]

# ── 국가별 로컬 식별 키워드 ─────────────────────────────────────────────────────
# Rule: 기사에 target_country 마커가 있으면 → 유지
#       다른 국가 마커가 2개 이상 있고 글로벌 우회 키워드가 없으면 → 제거
COUNTRY_IDENTIFIERS: dict[str, list[str]] = {
    "KR": [
        "south korea", "korea", "korean", "한국", "서울", "seoul",
        "부산", "busan", "인천", "대구", "수원", "국내", "현대차", "기아차",
    ],
    "RU": [
        "russia", "russian", "moscow", "россия", "москва", "русск",
        "russian federation", "siberia", "ural",
    ],
    "VN": [
        "vietnam", "vietnamese", "việt nam", "viet nam", "hanoi", "hà nội",
        "ho chi minh", "tp hcm", "hcmc", "danang", "đà nẵng",
    ],
    "TH": [
        "thailand", "thai", "bangkok", "ไทย", "กรุงเทพ", "phuket", "chiang mai",
    ],
    "PH": [
        "philippines", "philippine", "filipino", "pilipinas", "manila",
        "cebu", "davao", "mindanao", "luzon",
    ],
    "PK": [
        "pakistan", "pakistani", "karachi", "lahore", "islamabad",
        "پاکستان", "rawalpindi", "faisalabad", "peshawar",
        "lopal", "pso lubricant", "attock petroleum", "total parco",
        "parco", "ogra", "dawn.com", "thenews.com", "geo.tv",
    ],
    "GCC": [
        "saudi arabia", "saudi", "uae", "united arab emirates", "emirates",
        "kuwait", "qatar", "bahrain", "oman", "gcc", "gulf states", "gulf region",
        "riyadh", "dubai", "abu dhabi", "doha", "muscat", "jeddah",
        "الخليج", "السعودية", "الإمارات", "الكويت", "قطر", "البحرين", "عُمان",
    ],
    "CN": [
        "china", "chinese", "beijing", "shanghai", "shenzhen", "guangzhou",
        "中国", "中國", "北京", "上海", "深圳", "guangdong", "sinopec", "cnpc",
        "petrochina", "great wall motor", "byd china", "geely", "saic",
    ],
    "US": [
        "united states", "u.s.", "us market", "american", "usa",
        "new york", "los angeles", "houston", "detroit", "exxonmobil",
        "valvoline us", "pennzoil", "castrol usa", "napa auto",
    ],
    "IN": [
        "india", "indian", "delhi", "mumbai", "chennai", "bangalore",
        "भारत", "maruti suzuki", "tata motors india", "hero motocorp",
        "bajaj auto", "iocl", "bpcl", "hpcl", "castrol india",
    ],
    "JP": [
        "japan", "japanese", "tokyo", "osaka", "nagoya",
        "日本", "東京", "大阪", "toyota japan", "honda japan", "nissan",
        "jxtg", "eneos", "idemitsu kosan", "出光", "japanese automaker",
    ],
}

# ── 글로벌 우회 키워드: 이 키워드가 있으면 국가 필터 통과 (진짜 글로벌 산업 토픽만)
# 주의: "global", "worldwide" 같은 단어는 너무 광범위 — 미국/유럽 기사도 통과시킴
# 실제 모든 시장에 동시 영향을 미치는 토픽만 포함
GLOBAL_BYPASS_KEYWORDS = [
    "opec", "crude oil", "brent crude", "wti crude",
    "base oil group ii", "base oil group iii", "group ii base", "group iii base",
    "api specification", "acea specification", "ilsac specification",
    "jaso specification",
]


def is_blocklisted(title: str, snippet: str = "") -> bool:
    """Regex blocklist check — rejects articles matching known irrelevant patterns.

    Lubricant safeguard: if the article contains lubricant-related keywords,
    it is NOT rejected even if a blocklist pattern matches.
    """
    if not title:
        return False
    combined = f"{title} {snippet}".lower()
    has_lubricant = any(kw in combined for kw in LUBRICANT_SAFEGUARD_KEYWORDS)
    for pattern in TITLE_BLOCKLIST_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            if has_lubricant:
                return False  # Safeguard: keep lubricant-context articles
            return True  # Blocklisted
    return False


def country_relevance_filter(article: Article, country: str) -> bool:
    """Pre-filter articles that are clearly about a different specific country.

    Returns True (keep), False (reject).
    Conservative: only rejects when 2+ markers of another country are detected
    AND no target-country markers AND no global topic keywords are present.
    """
    text = f"{article.get('title', '')} {article.get('snippet', '')}".lower()

    # Rule 1: Contains target country markers → keep
    target_markers = COUNTRY_IDENTIFIERS.get(country, [])
    if any(marker in text for marker in target_markers):
        return True

    # Rule 2: Global/industry-wide topic → keep
    if any(bypass in text for bypass in GLOBAL_BYPASS_KEYWORDS):
        return True

    # Rule 3: Clearly about a different specific country → reject
    for other_country, markers in COUNTRY_IDENTIFIERS.items():
        if other_country == country:
            continue
        hit_count = sum(1 for m in markers if m in text)
        if hit_count >= 2:
            logger.debug(
                f"[{country}] Country filter rejected: '{article.get('title', '')[:50]}' "
                f"(detected {other_country} markers: {hit_count})"
            )
            return False

    # Rule 4: No clear signal → keep (let LLM decide)
    return True


def quick_filter(article: Article, country: str = "") -> bool:
    """Fast pre-filter before LLM scoring.

    Applies three sequential checks:
    1. Country relevance: reject articles clearly about a different country
    2. Negative keywords: reject articles with irrelevant topic keywords
    3. Regex blocklist: reject articles matching known irrelevant patterns
    """
    title = article.get("title", "")
    snippet = article.get("snippet", "")
    text = f"{title} {snippet}".lower()

    # Determine country from argument or article field
    target_country = country or article.get("country", "")

    # 1. Country relevance pre-filter
    if target_country and not country_relevance_filter(article, target_country):
        return False

    # 2. Negative keyword filter
    if any(neg in text for neg in NEGATIVE_KEYWORDS):
        return False

    # 3. Regex blocklist check (with lubricant safeguard)
    if is_blocklisted(title, snippet):
        return False

    return True


async def score_single_article(article: Article, client) -> Article:
    """Score a single article using Claude."""
    import asyncio
    try:
        prompt = SCORING_PROMPT.format(
            title=article.get("title", ""),
            snippet=article.get("snippet", ""),
            source=article.get("source", ""),
            country=article.get("country", ""),
            domain=article.get("collection_domain", ""),
        )

        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-sonnet-4-6",
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        # Find outermost { } — handle truncation gracefully
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(text[start:end + 1])
            scope = data.get("scope", "local")
            if scope == "other_country":
                article["score"] = 0
                article["score_reason"] = "Other country - rejected"
            else:
                s1 = min(data.get("score_sales", 0), 10)
                s2 = min(data.get("score_country", 0), 10)
                s3 = min(data.get("score_action", 0), 10)
                article["score"] = s1 + s2 + s3  # 0-30 total
                article["score_sales"] = s1
                article["score_country"] = s2
                article["score_action"] = s3
                article["score_reason"] = data.get("reason", "")
            article["tags"] = data.get("tags", [])
            article["sector"] = data.get("sector", "윤활유동향")
            article["scope"] = scope
            if scope == "global":
                article["tags"] = list(set(article["tags"] + ["글로벌"]))
        else:
            article["score"] = 0
    except Exception as e:
        logger.warning(f"Scoring failed for article: {e}")
        article["score"] = 0

    return article


async def score_articles(state: NewsletterState) -> dict:
    """Score and filter articles for all countries."""
    import anthropic

    merged = state.get("merged_articles", {})
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    scored: dict[str, list[Article]] = {}

    if api_key:
        client = anthropic.Anthropic(api_key=api_key)
    else:
        client = None
        logger.warning("ANTHROPIC_API_KEY not set, using keyword-based scoring fallback")

    # Load scoring thresholds from Supabase settings (with hardcoded fallback)
    min_total_score = 10
    min_country_score = 3
    try:
        import requests as _req
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_KEY", "")
        if supabase_url and supabase_key:
            resp = _req.get(
                f"{supabase_url}/rest/v1/settings?order=id.desc&limit=1&select=min_total_score,min_country_score",
                headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
                timeout=5,
            )
            if resp.ok and resp.json():
                row = resp.json()[0]
                if row.get("min_total_score") is not None:
                    min_total_score = int(row["min_total_score"])
                if row.get("min_country_score") is not None:
                    min_country_score = int(row["min_country_score"])
    except Exception:
        pass
    print(f"📊 Scoring thresholds: total≥{min_total_score}, country≥{min_country_score}", flush=True)

    for country, articles in merged.items():
        # Quick filter first (country passed explicitly for country relevance check)
        filtered = [a for a in articles if quick_filter(a, country)]
        # Limit to 30 articles max for LLM scoring (saves time + cost)
        to_score = filtered[:30]
        print(f"📊 [{country}] Quick filter: {len(articles)} -> {len(filtered)}, scoring top {len(to_score)}", flush=True)

        if client:
            scored_articles = []
            for i, article in enumerate(to_score, 1):
                title_short = article.get("title", "")[:40]
                print(f"  📊 [{country}] Scoring {i}/{len(to_score)}: {title_short}...", flush=True)
                scored_article = await score_single_article(article, client)
                s = scored_article.get("score", 0)
                sc = scored_article.get("score_country", 0)
                scope = scored_article.get("scope", "local")
                # 총점 ≥ min_total_score AND 국가 연관성 ≥ min_country_score AND scope≠global
                if s >= min_total_score and sc >= min_country_score and scope != "global":
                    scored_articles.append(scored_article)
                    print(f"  📊 [{country}] -> score={s} (country={sc}) ✓", flush=True)
                else:
                    if scope == "global":
                        reason = "global — 전면 차단"
                    elif s < min_total_score:
                        reason = f"score={s}<{min_total_score}"
                    else:
                        reason = f"country={sc}<{min_country_score}"
                    print(f"  📊 [{country}] -> score={s} (country={sc}) ✗ ({reason})", flush=True)
        else:
            for a in to_score:
                a["score"] = 3
            scored_articles = to_score

        scored_articles.sort(key=lambda a: a.get("score", 0), reverse=True)
        scored[country] = scored_articles[:15]
        print(f"📊 [{country}] ✅ Scoring done: {len(scored[country])} articles kept", flush=True)

    return {
        "scored_articles": scored,
        "current_phase": "enrichment",
        "phase_status": {**state.get("phase_status", {}), "scoring": "done"},
        "events": state.get("events", []) + [
            {"type": "phase_complete", "phase": "scoring", "ts": datetime.now().isoformat(),
             "stats": {c: len(a) for c, a in scored.items()}}
        ],
    }
