"""Compliance-adjacent operational pressure intelligence."""
from __future__ import annotations

from services.acquisition.acquisition_probability import score_acquisition_probability
from services.acquisition.connectors.reddit.autonomy import decide_engagement
from services.acquisition.connectors.reddit.classifier import classify_post
from services.acquisition.connectors.reddit.qualification import qualify_post
from services.acquisition.intelligence.operational_pressure import (
    SIGNAL_CATEGORIES,
    score_operational_pressure,
)


def _pipeline(title: str, body: str):
    post = {"title": title, "selftext": body, "post_id": "t1", "subreddit": "smallbusiness"}
    cls = classify_post(title, body)
    qual = qualify_post(post, cls)
    plan = decide_engagement(
        {"title": title, "selftext": body, "post_id": "t1", "subreddit": "smallbusiness", "num_comments": 1},
        cls,
        qual,
    )
    return cls, qual, plan


def test_signal_categories_defined():
    assert "customer_security_pressure" in SIGNAL_CATEGORIES
    assert "ai_governance_pressure" in SIGNAL_CATEGORIES
    assert len(SIGNAL_CATEGORIES) >= 14


def test_customer_questionnaire_post():
    op = score_operational_pressure(
        "Customer questionnaire",
        "Customer sent security questionnaire. What policies do we need?",
    )
    assert op["operational_pressure_score"] >= 28
    assert "Customer pressure" in op["ui_badges"] or "Questionnaire burden" in op["ui_badges"]
    _, qual, plan = _pipeline(
        "Customer questionnaire",
        "Customer sent security questionnaire. What policies do we need?",
    )
    assert qual.get("prey_score", 0) >= 42
    assert plan.get("show_operator_queue") is True


def test_vendor_onboarding_post():
    op = score_operational_pressure(
        "Vendor onboarding",
        "Vendor onboarding security review — supplier questionnaire and MFA required.",
    )
    assert op["primary_pressure"] in ("vendor_onboarding_pressure", "security_questionnaire_pressure", "mfa_requirement_pressure")
    _, qual, _ = _pipeline(
        "Vendor onboarding",
        "Vendor onboarding security review — supplier questionnaire required.",
    )
    assert qual.get("prey_score", 0) >= 40


def test_insurance_requirement_post():
    op = score_operational_pressure(
        "Cyber insurance",
        "Cyber insurance questionnaire — need evidence for controls.",
    )
    assert op["signal_categories"].get("insurance_compliance_pressure", 0) > 0
    _, qual, _ = _pipeline("Cyber insurance", "Cyber insurance questionnaire — need evidence.")
    assert qual.get("prey_score", 0) >= 38


def test_ai_governance_pressure_post():
    op = score_operational_pressure(
        "AI Act",
        "Customer added AI Act compliance section — need AI governance documentation and model card.",
    )
    assert op["signal_categories"].get("ai_governance_pressure", 0) > 0
    assert "AI governance" in op["ui_badges"]


def test_evidence_request_post():
    op = score_operational_pressure("Contract evidence", "Need evidence for contract — partial spreadsheets only.")
    assert op["signal_categories"].get("evidence_request_pressure", 0) > 0


def test_operational_burden_without_compliance_keywords():
    title = "Supplier security review"
    body = "Prime contractor asking for MFA. What documentation do we need? We store technical drawings."
    op = score_operational_pressure(title, body)
    assert not op["explicit_compliance_language"] or op["has_pre_compliance_entanglement"]
    assert op["operational_pressure_score"] >= 30
    out = score_acquisition_probability(title, body, classification=classify_post(title, body))
    assert out["prey_score"] >= 40
    assert out.get("operational_pressure_score", 0) >= 28


def test_predator_still_blocked():
    title = "CMMC consultant AMA"
    body = "As a consultant I advise clients. Book a call — pro tip webinar."
    cls = classify_post(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["queue_eligible"] is False
    assert out["prey_tier"] == 5


def test_topic_chatter_blocked_or_low():
    title = "Thoughts on cybersecurity"
    body = "What do you think about the new rule change announced? Discussion thread."
    cls = classify_post(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["prey_tier"] >= 4 or not out["queue_eligible"]
