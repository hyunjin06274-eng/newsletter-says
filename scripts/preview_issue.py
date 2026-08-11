#!/usr/bin/env python3
"""로컬 드라이런 미리보기 스크립트.

발송 없이 파이프라인을 돌려 이메일 HTML(A안)과 웹 탭 UI HTML을 로컬 파일로 출력합니다.

사용법:
    cd newsletter-saas
    python scripts/preview_issue.py [국가코드...] [--days N]

예시:
    python scripts/preview_issue.py KR RU          # KR + RU 두 국가
    python scripts/preview_issue.py KR --days 7    # 7일치 기사
    python scripts/preview_issue.py                # 기본값: KR 단독

출력 파일 (output/preview/ 디렉터리):
    email_{COUNTRY}.html  — 각 수신 국가용 이메일 HTML (A안)
    web.html              — 전국가 탭 UI 웹 버전 HTML

환경 변수:
    ANTHROPIC_API_KEY  필수 — LLM 호출
    GMAIL_TOKEN_JSON   선택 — 발송은 하지 않으므로 불필요
    SUPABASE_URL/KEY   선택 — 없어도 미리보기 가능
"""

import asyncio
import os
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv()

# 발송 비활성화: sender.py에서 Gmail API를 건드리지 않도록 환경변수 제거
os.environ.pop("GMAIL_TOKEN_JSON", None)
os.environ.pop("GMAIL_CREDENTIALS_JSON", None)
# Supabase 없어도 동작하도록 (수신인 로딩 실패 → fallback 수신인 없음)
# DEFAULT_RECIPIENTS를 빈 값으로 두면 발송 시도 자체가 skip됨
os.environ.setdefault("DEFAULT_RECIPIENTS", "")

# 통합 뉴스레터 모드 활성화 (이 스크립트의 목적)
os.environ["USE_UNIFIED_NEWSLETTER"] = "true"


async def main(countries: list[str], days: int) -> None:
    from backend.agent.graph import compile_graph, create_initial_state
    from backend.agent.nodes.renderer import render_email_html, render_web_html

    print("=" * 64, flush=True)
    print(f"🔍 드라이런 미리보기: {countries} ({days}일치)", flush=True)
    print("   발송 없음 — 로컬 파일로만 출력", flush=True)
    print("=" * 64, flush=True)

    app = compile_graph()
    state = create_initial_state(countries=countries, days=days)
    config = {"configurable": {"thread_id": "preview-dryrun"}}

    final: dict = {}
    async for event in app.astream(state, config=config):
        for node_name, output in event.items():
            phase = output.get("current_phase", "")
            final.update(output)
            print(f"  [{node_name}] → {phase}", flush=True)

    unified_issue = final.get("unified_issue")
    newsletters = final.get("newsletters", {})

    out_dir = ROOT / "output" / "preview"
    out_dir.mkdir(parents=True, exist_ok=True)

    if unified_issue:
        # ── 웹 탭 UI HTML ────────────────────────────────────────────────────
        default_country = countries[0] if countries else "KR"
        web_html = render_web_html(unified_issue, default_country=default_country)
        web_path = out_dir / "web.html"
        web_path.write_text(web_html, encoding="utf-8")
        print(f"\n✅ 웹 탭 UI: {web_path}  ({len(web_html):,} chars)", flush=True)

        # ── 이메일 HTML (각 국가별 A안) ──────────────────────────────────────
        raw_articles = final.get("raw_articles", {})
        merged_articles = final.get("merged_articles", {})

        for cc in countries:
            raw_count = len(raw_articles.get(cc, []))
            merged = merged_articles.get(cc, [])
            source_count = len({a.get("source", "") for a in merged if a.get("source")})

            email_html = render_email_html(
                issue=unified_issue,
                recipient_country=cc,
                run_id=unified_issue.get("run_id", "preview"),
                days=days,
                raw_count=raw_count,
                source_count=source_count,
                web_base_url="http://localhost:3000",
            )
            email_path = out_dir / f"email_{cc}.html"
            email_path.write_text(email_html, encoding="utf-8")
            print(f"✅ 이메일 [{cc}]: {email_path}  ({len(email_html):,} chars)", flush=True)

    else:
        # unified_issue가 없으면 (USE_UNIFIED_NEWSLETTER=false 시 발생 불가하지만 안전망)
        print("\n⚠️  unified_issue 없음 — 레거시 per-country HTML로 저장", flush=True)
        for cc, html in newsletters.items():
            path = out_dir / f"legacy_{cc}.html"
            path.write_text(html, encoding="utf-8")
            print(f"  legacy [{cc}]: {path}", flush=True)

    errors = final.get("errors", [])
    if errors:
        print(f"\n⚠️  파이프라인 오류 {len(errors)}건:", flush=True)
        for e in errors:
            print(f"   - {e}", flush=True)

    print("\n" + "=" * 64, flush=True)
    print("미리보기 완료. 브라우저로 output/preview/ 파일을 열어 확인하세요.", flush=True)
    print("=" * 64, flush=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="뉴스레터 드라이런 미리보기")
    parser.add_argument("countries", nargs="*", default=["KR"], help="국가 코드 (기본: KR)")
    parser.add_argument("--days", type=int, default=30, help="기사 수집 기간 (기본: 30일)")
    args = parser.parse_args()

    asyncio.run(main(countries=args.countries, days=args.days))
