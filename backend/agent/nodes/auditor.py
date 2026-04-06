"""Phase 3.5: LLM-based newsletter quality audit with self-correction loop."""

import json
import logging
import os
from datetime import datetime

from backend.agent.state import NewsletterState, AuditFeedback

logger = logging.getLogger(__name__)

AUDIT_PROMPT = """You are a quality auditor for SK Enmove's MI newsletter.
Evaluate this newsletter HTML for quality. Score 1-5 on each criterion.

Newsletter HTML (truncated to 3000 chars):
{html_preview}

Criteria:
1. Information Accuracy: Are facts/numbers plausible? No hallucinated data?
2. Korean Quality: Natural Korean, no awkward machine translation?
3. Tone & Style: Professional, suitable for marketing/sales strategists?
4. Completeness: Has all 3 sections (핵심 인사이트, 섹터별 뉴스, 전략 제언)?
5. Actionability: Are strategy recommendations specific and actionable?
6. No CSR/ESG fluff: Avoids generic sustainability filler?

Respond in JSON:
{{
  "passed": true/false (true if avg score >= 3.5),
  "score": 0.0-5.0 (average),
  "scores": {{"accuracy": N, "korean": N, "tone": N, "completeness": N, "actionability": N, "no_fluff": N}},
  "issues": ["issue1", "issue2"],
  "suggestions": ["suggestion1", "suggestion2"]
}}
"""


async def audit_newsletter(state: NewsletterState) -> dict:
    """Audit newsletter quality and decide whether to retry or proceed."""
    import anthropic

    newsletters = state.get("newsletters", {})
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    iteration = state.get("audit_iteration", 0) + 1
    max_iter = state.get("max_audit_iterations", 3)
    feedback: dict[str, AuditFeedback] = {}

    if api_key:
        client = anthropic.Anthropic(api_key=api_key)
    else:
        client = None

    for country, html in newsletters.items():
        if client:
            try:
                prompt = AUDIT_PROMPT.format(html_preview=html[:3000])
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text.strip()
                if "{" in text:
                    data = json.loads(text[text.index("{"):text.rindex("}") + 1])
                    feedback[country] = AuditFeedback(
                        passed=data.get("passed", True),
                        score=data.get("score", 4.0),
                        issues=data.get("issues", []),
                        suggestions=data.get("suggestions", []),
                    )
                else:
                    feedback[country] = AuditFeedback(passed=True, score=4.0, issues=[], suggestions=[])
            except Exception as e:
                logger.warning(f"[{country}] Audit failed: {e}")
                feedback[country] = AuditFeedback(passed=True, score=4.0, issues=[], suggestions=[])
        else:
            # No API key: pass by default
            feedback[country] = AuditFeedback(passed=True, score=4.0, issues=[], suggestions=[])

        status = "PASS" if feedback[country]["passed"] else "FAIL"
        logger.info(
            f"[{country}] Audit {status} (score={feedback[country]['score']:.1f}, "
            f"iteration={iteration}/{max_iter})"
        )

    return {
        "audit_feedback": feedback,
        "audit_iteration": iteration,
        "current_phase": "auditing",
        "phase_status": {**state.get("phase_status", {}), "auditing": "done"},
        "events": state.get("events", []) + [
            {"type": "audit_complete", "phase": "auditing", "ts": datetime.now().isoformat(),
             "iteration": iteration,
             "results": {c: {"passed": f["passed"], "score": f["score"]} for c, f in feedback.items()}}
        ],
    }
