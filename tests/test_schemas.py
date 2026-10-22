"""Tests for data contracts in backend/schemas.py."""

import pytest
from pydantic import ValidationError

from backend.schemas import (
    AddCss,
    AgentEvent,
    ChangeTag,
    FixSuggestion,
    Issue,
    RemoveAttr,
    ScanReport,
    ScoreBreakdown,
    SetAttr,
    SetText,
    WrapLabel,
)


def test_issue_valid_and_defaults():
    iss = Issue(
        id="iss_001",
        source="axe",
        rule_id="image-alt",
        impact="critical",
        wcag=["1.1.1"],
        selector="img.hero",
        html='<img class="hero" src="hero.jpg">',
        message="Images must have alternate text.",
    )
    assert iss.id == "iss_001"
    assert iss.fixable is True
    assert iss.help_url is None
    assert iss.wcag == ["1.1.1"]


def test_patch_discriminator_valid_types():
    # Test all 6 valid patch types
    p1 = SetAttr(selector="img", name="alt", value="Hero banner")
    assert p1.op == "set_attr"

    p2 = RemoveAttr(selector="div", name="aria-hidden")
    assert p2.op == "remove_attr"

    p3 = SetText(selector="a.btn", value="Read admissions guide")
    assert p3.op == "set_text"

    p4 = WrapLabel(selector="#email", label_text="Email address")
    assert p4.op == "wrap_label"

    p5 = AddCss(selector="p.note", property="color", value="#333333")
    assert p5.op == "add_css"

    p6 = ChangeTag(selector="h4.title", new_tag="h2")
    assert p6.op == "change_tag"


def test_patch_invalid_op_or_missing_fields():
    # Missing required selector
    with pytest.raises(ValidationError):
        SetAttr(name="alt", value="test")  # type: ignore

    # Missing label_text
    with pytest.raises(ValidationError):
        WrapLabel(selector="#name")  # type: ignore


def test_fix_suggestion_confidence_bounds():
    # Valid bounds
    FixSuggestion(
        id="fix_001",
        issue_id="iss_001",
        explanation="Add descriptive alt text.",
        wcag="1.1.1",
        confidence=0.0,
    )
    FixSuggestion(
        id="fix_002",
        issue_id="iss_001",
        explanation="Add descriptive alt text.",
        wcag="1.1.1",
        confidence=1.0,
    )

    # Below 0
    with pytest.raises(ValidationError):
        FixSuggestion(
            id="fix_bad",
            issue_id="iss_001",
            explanation="Test",
            wcag="1.1.1",
            confidence=-0.1,
        )

    # Above 1
    with pytest.raises(ValidationError):
        FixSuggestion(
            id="fix_bad",
            issue_id="iss_001",
            explanation="Test",
            wcag="1.1.1",
            confidence=1.05,
        )


def test_scan_report_round_trip_json():
    rep = ScanReport(
        run_id="run_123",
        status="completed",
        score_before=ScoreBreakdown(
            score=45,
            penalty=55,
            by_impact={"critical": 2, "serious": 3, "moderate": 0, "minor": 0},
            rules_violated=3,
        ),
        score_after=ScoreBreakdown(
            score=95,
            penalty=5,
            by_impact={"critical": 0, "serious": 0, "moderate": 0, "minor": 1},
            rules_violated=1,
        ),
        issues=[
            Issue(
                id="iss_001",
                source="axe",
                rule_id="image-alt",
                impact="critical",
                selector="img",
                html="<img>",
                message="Missing alt",
            )
        ],
        fixes=[
            FixSuggestion(
                id="fix_001",
                issue_id="iss_001",
                explanation="Fix alt",
                wcag="1.1.1",
                patch=SetAttr(selector="img", name="alt", value="Banner"),
                confidence=0.95,
                status="applied",
            )
        ],
    )
    json_data = rep.model_dump_json()
    loaded = ScanReport.model_validate_json(json_data)
    assert loaded.run_id == "run_123"
    assert loaded.score_before is not None
    assert loaded.score_before.score == 45
    assert loaded.fixes[0].patch is not None
    assert loaded.fixes[0].patch.op == "set_attr"


def test_agent_event():
    ev = AgentEvent(
        seq=1,
        ts=1700000000.0,
        type="step_started",
        step="scan",
        message="Starting accessibility scan",
        data={"url": "http://127.0.0.1:8000/demo/page1.html"},
    )
    assert ev.seq == 1
    assert ev.type == "step_started"
