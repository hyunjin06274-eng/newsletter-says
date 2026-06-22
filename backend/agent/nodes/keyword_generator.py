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
            "日本 自動車販売台数 乗用車",
            "日本 ハイブリッド EV 潤滑油 需要",
            "日本 二輪車 バイク 潤滑油",
            "JASO規格 エンジンオイル 日本",
            "コマツ 日立建機 建設機械 潤滑油",
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
    "AE": {
        "name": "UAE", "lang": "Arabic/English",
        "competitors": ["ADNOC Lubricants UAE", "Shell UAE engine oil", "Castrol UAE", "Total Energies UAE", "Gulf Oil UAE", "Mobil UAE"],
        "forward_industries": ["UAE automobile sales Dubai", "UAE construction fleet equipment", "UAE EV adoption Tesla BMW", "UAE fleet management lubricant", "UAE maritime port Jebel Ali lubricant", "UAE aviation lubricant"],
        "local_media": ["Gulf News UAE automotive", "Khaleej Times oil lubricant UAE", "ADNOC downstream UAE", "Emirates automotive industry"],
    },
    "SA": {
        "name": "사우디아라비아", "lang": "Arabic/English",
        "competitors": ["Petromin lubricant Saudi Arabia", "ADNOC Saudi", "Shell Saudi Arabia", "Castrol KSA", "Total Energies Saudi", "Mobil Saudi Arabia"],
        "forward_industries": ["Saudi Vision 2030 automotive", "Saudi car sales Toyota Hyundai", "Saudi EV electric vehicle policy", "Saudi construction fleet lubricant", "Saudi oil refinery base oil Aramco", "Saudi mining machinery lubricant"],
        "local_media": ["Saudi Gazette automotive lubricant", "Arab News oil industry Saudi", "Aramco downstream lubricant", "Saudi automotive sector"],
    },
    "OM": {
        "name": "오만", "lang": "Arabic/English",
        "competitors": ["OmanOil lubricant", "Shell Oman", "Castrol Oman", "Total Energies Oman", "Gulf Oil Oman"],
        "forward_industries": ["Oman car sales automobile", "Oman mining machinery lubricant", "Oman oil refinery Sohar", "Oman port logistics fleet", "Oman construction equipment"],
        "local_media": ["Times of Oman automotive", "Oman Observer oil lubricant", "OmanOil downstream"],
    },
    "EG": {
        "name": "이집트", "lang": "Arabic/English",
        "competitors": ["Oilco Egypt lubricant", "Shell Egypt", "Castrol Egypt", "Total Egypt", "Mobil Egypt", "Egyptian lubricant market"],
        "forward_industries": ["Egypt car sales automobile market", "Egypt motorcycle market", "Egypt construction infrastructure lubricant", "Egypt truck fleet commercial vehicle", "Egypt oil refinery base oil EGPC", "Egypt EV policy electric vehicle"],
        "local_media": ["Al-Ahram economic Egypt automotive", "Egypt Today oil lubricant", "EGPC petroleum Egypt", "Cairo automotive market"],
    },
    "MY": {
        "name": "말레이시아", "lang": "Malay/English",
        "competitors": ["Petronas Syntium lubricant Malaysia", "Shell Malaysia engine oil", "Castrol Malaysia", "Total Malaysia lubricant", "Idemitsu Malaysia", "Mobil Malaysia"],
        "forward_industries": ["Malaysia car sales Perodua Proton", "Malaysia motorcycle market lubricant", "Malaysia EV policy Proton EV", "Malaysia palm oil biofuel lubricant", "Malaysia construction equipment fleet", "Malaysia truck commercial vehicle lubricant"],
        "local_media": ["The Star Malaysia automotive", "Malay Mail car sales lubricant", "Petronas downstream Malaysia", "Malaysia automotive institute"],
    },
    "KH": {
        "name": "캄보디아", "lang": "Khmer/English",
        "competitors": ["Total Cambodia lubricant", "Shell Cambodia engine oil", "Castrol Cambodia", "Caltex Cambodia", "Mobil Cambodia"],
        "forward_industries": ["Cambodia motorcycle market lubricant", "Cambodia construction equipment boom", "Cambodia automotive sales import", "Cambodia truck fleet logistics", "Cambodia garment textile machinery"],
        "local_media": ["Phnom Penh Post automotive Cambodia", "Khmer Times oil lubricant", "Cambodia construction industry"],
    },
    "LA": {
        "name": "라오스", "lang": "Lao/English",
        "competitors": ["Total Laos lubricant", "Shell Laos engine oil", "Castrol Laos", "Caltex Laos", "PTT Laos lubricant"],
        "forward_industries": ["Laos motorcycle sales lubricant", "Laos construction hydropower equipment", "Laos truck fleet logistics", "Laos mining equipment lubricant", "Laos automotive import market"],
        "local_media": ["Vientiane Times automotive Laos", "Laos construction industry lubricant", "Mekong region automotive"],
    },
    "CL": {
        "name": "칠레", "lang": "Spanish",
        "competitors": ["Copec lubricant Chile", "Shell Chile engine oil", "Castrol Chile", "Total Energies Chile", "Mobil Chile", "YPF Chile"],
        "forward_industries": ["Chile car sales automobile market", "Chile mining copper lubricant equipment", "Chile truck fleet commercial vehicle", "Chile EV electric vehicle policy", "Chile construction equipment machinery", "Chile agriculture tractor lubricant"],
        "local_media": ["La Tercera Chile automotive", "El Mercurio lubricant Chile", "ANAC Chile car sales", "Minería Chilena mining lubricant"],
    },
    "AU": {
        "name": "호주", "lang": "English",
        "competitors": ["Castrol Australia engine oil", "Mobil Synergy Australia", "Shell Helix Australia", "Total Energies Australia", "Penrite lubricant Australia", "Nulon Australia", "Valvoline Australia"],
        "forward_industries": ["Australia car sales VFACTS", "Australia EV adoption Tesla policy", "Australia mining lubricant BHP Rio Tinto", "Australia truck fleet diesel lubricant", "Australia agriculture farm machinery lubricant", "Australia construction equipment lubricant"],
        "local_media": ["FCAI Australia vehicle sales", "CarAdvice Australia lubricant", "Australian Mining lubricant", "Drive.com.au engine oil Australia"],
    },
    "IL": {
        "name": "이스라엘", "lang": "Hebrew/English",
        "competitors": ["Paz lubricant Israel", "Delek Israel engine oil", "Castrol Israel", "Total Israel lubricant", "Shell Israel", "Mobil Israel"],
        "forward_industries": ["Israel car sales automobile import", "Israel EV electric vehicle adoption Tesla", "Israel defense military lubricant", "Israel construction equipment machinery", "Israel truck fleet logistics lubricant", "Israel agriculture machinery kibbutz"],
        "local_media": ["Haaretz Israel automotive", "Ynet Israel car lubricant", "Israel Oil industry", "Israeli automotive market report"],
    },
    "MN": {
        "name": "몽골", "lang": "Mongolian/English",
        "competitors": ["Petro Mongolia lubricant", "Shell Mongolia engine oil", "Castrol Mongolia", "Total Mongolia", "Mobil Mongolia"],
        "forward_industries": ["Mongolia mining lubricant Oyu Tolgoi", "Mongolia truck fleet diesel", "Mongolia automobile sales import", "Mongolia construction equipment", "Mongolia agriculture tractor lubricant", "Mongolia winter lubricant low temperature"],
        "local_media": ["Mongolian Mining Journal lubricant", "UB Post Mongolia automotive", "Mongolia petroleum industry news"],
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
