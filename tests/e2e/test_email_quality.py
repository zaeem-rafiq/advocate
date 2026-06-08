"""LLM-judge gate for subjective quality the binary gate can't see.

Two kinds of test here:
1. A LIVE draft from the deployed service must clear the quality judge.
2. Calibration tests that prove the judge DISCRIMINATES — it rejects a blatantly
   salesy/job-asking email and accepts a genuinely warm one. Without these, a judge
   that returned `pass` for everything would look like it's working. They also need
   no deployed call, so they're cheap and fast.
"""
from __future__ import annotations

import pytest

from adk_client import require_tool_response
from llm_judge import EMAIL_QUALITY

pytestmark = pytest.mark.e2e

# A deliberately bad outreach: asks for a job + a referral + a resume review, salesy,
# generic. The rubric's fail_if conditions should reject it.
_SALESY_JOB_EMAIL = (
    "Hi, I'm extremely passionate about your world-class company and would be a "
    "perfect fit. Could you refer me for the open Senior Product Manager position? "
    "I've attached my resume — please pass it to your hiring manager and let me know "
    "how to apply. Looking forward to joining the team!"
)

# A warm, connection-first email that asks only for a short conversation.
_GOOD_EMAIL = (
    "Hi Maya, as a fellow Columbia alum I was struck by your move from consulting "
    "into climate product at Helio Grid — it's exactly the path I'm weighing after "
    "eight years in consulting. Would you have 20 minutes in the next couple of weeks "
    "to share how you navigated that shift? Either way, thank you for the work you're "
    "doing."
)

_CONTEXT = "Networking email to Maya Okonkwo at Helio Grid; shared connection: fellow Columbia alum."


def test_judge_rejects_salesy_job_email(judge):
    """The judge must FAIL an email that asks for a job/referral/resume review."""
    verdict = judge(EMAIL_QUALITY, _CONTEXT, _SALESY_JOB_EMAIL)
    assert verdict.passed is False, f"judge wrongly passed a job-asking email: {verdict.reasons}"


def test_judge_accepts_warm_connection_first_email(judge):
    """The judge must PASS a genuinely warm, connection-first, advice-only email."""
    verdict = judge(EMAIL_QUALITY, _CONTEXT, _GOOD_EMAIL)
    assert verdict.passed is True, f"judge wrongly failed a good email: {verdict.reasons}"


def test_live_draft_passes_quality_judge(adk, e2e_user, judge):
    """A draft the deployed service actually produced must clear the quality bar."""
    sid = adk.new_session(e2e_user, prefix="quality")
    events = adk.run_until_tool(
        e2e_user, sid,
        "Draft a connection-first outreach email to Diego Salcedo at Verdant Mobility. "
        "My background: a transit planner exploring product roles. Lead with our shared "
        "Columbia alumni connection.",
        "draft_outreach_email", retries=2,
    )
    draft = require_tool_response(events, "draft_outreach_email")
    assert draft["passed"] is True, f"draft did not pass the binary gate: {draft}"

    verdict = judge(
        EMAIL_QUALITY,
        "Networking email to Diego Salcedo at Verdant Mobility; shared connection: fellow Columbia alum.",
        draft["email"],
    )
    assert verdict.passed, f"live draft failed the quality judge: {verdict.reasons}"
