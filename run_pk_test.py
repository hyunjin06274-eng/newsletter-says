#!/usr/bin/env python3
"""PK 단일 국가 뉴스레터 테스트 발송 → dpswpfguswls@naver.com"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

os.environ["DEFAULT_RECIPIENTS"] = "dpswpfguswls@naver.com"
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_KEY", None)


async def main():
    from backend.agent.graph import compile_graph, create_initial_state

    print("=" * 60, flush=True)
    print("🇵🇰 PK 뉴스레터 테스트 발송", flush=True)
    print("   수신자: dpswpfguswls@naver.com", flush=True)
    print("=" * 60, flush=True)

    app = compile_graph()
    state = create_initial_state(countries=["PK"], days=30)
    config = {"configurable": {"thread_id": "pk-test"}}

    final_state = await app.ainvoke(state, config=config)

    send_results = final_state.get("send_results", {})
    errors = final_state.get("errors", [])

    print("\n" + "=" * 60, flush=True)
    if send_results.get("PK"):
        print("✅ 발송 성공! dpswpfguswls@naver.com 을 확인해주세요.", flush=True)
    else:
        print("❌ 발송 실패", flush=True)
        for e in errors:
            print(f"  오류: {e}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
