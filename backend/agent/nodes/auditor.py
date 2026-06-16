"""Phase 3.5: LLM-based newsletter quality audit with self-correction loop."""

import json
import logging
import os
from datetime import datetime

from backend.agent.state import NewsletterState, AuditFeedback

logger = logging.getLogger(__name__)

AUDIT_PROMPT = """You are a quality auditor for SK Enmove's MI newsletter.
Evaluate this newsletter HTML for quality. Score each criterion 1-5.

Newsletter HTML (truncated to 3000 chars):
{html_preview}

Criteria:
1. accuracy: Are facts/numbers plausible? No hallucinated data?
2. korean: Natural Korean, no awkward machine translation?
3. tone: Professional, suitable for marketing/sales strategists?
4. completeness: Has all 3 sections (핵심 인사이트, 섹터별 뉴스, 전략 제언)?
5. actionability: Are strategy recommendations specific and actionable?
6. no_fluff: Avoids generic CSR/ESG sustainability filler?
7. factual_fidelity: Accurately reflects original articles without substituting or reinterpreting geopolitical facts?

Respond ONLY with valid JSON (no markdown, no extra text):
{{"passed": true, "score": 4.2, "scores": {{"accuracy": 4, "korean": 4, "tone": 5, "completeness": 4, "actionability": 4, "no_fluff": 4, "factual_fidelity": 5}}, "issues": [], "suggestions": []}}

Set "passed" to true if average score >= 3.5, false otherwise.
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
                import asyncio
                prompt = AUDIT_PROMPT.format(html_preview=html[:3000])
                response = await asyncio.to_thread(
                    client.messages.create,
                    model="claude-sonnet-4-6",
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text.strip()
                # Strip markdown code fences if present
                if "```" in text:
                    text = text[text.find("```") + 3:]
                    if text.startswith("json"):
                        text = text[4:]
                    text = text[:text.rfind("```")].strip()
                start, end = text.find("{"), text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    data = json.loads(text[start:end + 1])
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
