"""Scoring formula for A11y Pilot.

NOTE: This is a demonstration heuristic for relative before/after progress,
NOT an official WCAG accessibility compliance metric.
"""

from collections import defaultdict

from backend.schemas import Issue, ScoreBreakdown

WEIGHTS = {
    "critical": 10,
    "serious": 5,
    "moderate": 2,
    "minor": 1,
}


def compute_score(issues: list[Issue]) -> ScoreBreakdown:
    """Compute score breakdown according to the heuristic formula:

    WEIGHTS = {"critical": 10, "serious": 5, "moderate": 2, "minor": 1}
    penalty = sum over violated RULES of: WEIGHTS[impact] * min(affected_nodes, 5)
    score   = max(0, 100 - penalty)
    """
    by_impact_counts = {
        "critical": 0,
        "serious": 0,
        "moderate": 0,
        "minor": 0,
    }

    # Group by (rule_id, impact)
    rule_nodes = defaultdict(int)
    for issue in issues:
        impact = issue.impact
        if impact not in WEIGHTS:
            impact = "minor"
        by_impact_counts[impact] += 1
        rule_nodes[(issue.rule_id, impact)] += 1

    total_penalty = 0
    unique_rules = set()

    for (rule_id, impact), count in rule_nodes.items():
        unique_rules.add(rule_id)
        weight = WEIGHTS.get(impact, 1)
        capped_nodes = min(count, 5)
        total_penalty += weight * capped_nodes

    score = max(0, 100 - total_penalty)

    return ScoreBreakdown(
        score=score,
        penalty=total_penalty,
        by_impact=by_impact_counts,
        rules_violated=len(unique_rules),
    )
