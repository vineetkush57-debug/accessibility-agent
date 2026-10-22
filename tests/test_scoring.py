"""Tests for scoring formula in backend/scoring.py."""

from backend.schemas import Issue
from backend.scoring import compute_score


def _make_issue(rule_id: str, impact: str, idx: int = 1) -> Issue:
    return Issue(
        id=f"iss_{idx}",
        source="axe",
        rule_id=rule_id,
        impact=impact,  # type: ignore
        selector=f"element-{idx}",
        html="<div></div>",
        message="Test issue",
    )


def test_empty_issues_gives_100():
    res = compute_score([])
    assert res.score == 100
    assert res.penalty == 0
    assert res.rules_violated == 0
    assert res.by_impact == {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}


def test_single_critical_node():
    issues = [_make_issue("image-alt", "critical", 1)]
    res = compute_score(issues)
    assert res.penalty == 10
    assert res.score == 90
    assert res.rules_violated == 1
    assert res.by_impact["critical"] == 1


def test_twenty_nodes_same_critical_rule_capped_at_five():
    issues = [_make_issue("image-alt", "critical", i) for i in range(20)]
    res = compute_score(issues)
    # penalty = WEIGHT["critical"] (10) * min(20, 5) = 50
    assert res.penalty == 50
    assert res.score == 50
    assert res.rules_violated == 1
    assert res.by_impact["critical"] == 20  # uncapped count


def test_mixed_rules_and_impacts():
    issues = [
        _make_issue("image-alt", "critical", 1),  # 1 * 10 = 10
        _make_issue("color-contrast", "serious", 2),  # 1 * 5 = 5
        _make_issue("heading-order", "moderate", 3),  # 1 * 2 = 2
        _make_issue("region", "minor", 4),  # 1 * 1 = 1
    ]
    res = compute_score(issues)
    # penalty = 10 + 5 + 2 + 1 = 18
    assert res.penalty == 18
    assert res.score == 82
    assert res.rules_violated == 4


def test_score_floor_at_zero():
    # 3 distinct critical rules with 5+ nodes each: 3 * 50 = 150 penalty
    issues = []
    for r in ["rule1", "rule2", "rule3"]:
        for i in range(6):
            issues.append(_make_issue(r, "critical", len(issues) + 1))
    res = compute_score(issues)
    assert res.penalty == 150
    assert res.score == 0
