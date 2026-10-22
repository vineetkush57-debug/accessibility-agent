"""Self-audit dogfooding test for A11y Pilot's own user interface."""

import pytest

from backend.config import settings
from backend.scanner import (
    capture_aria_snapshot,
    create_scan_context,
    get_browser,
    load_page,
    run_axe,
)
from backend.scoring import compute_score


@pytest.mark.browser
@pytest.mark.asyncio
async def test_ui_self_audit():
    """Verify that A11y Pilot's own frontend achieves score >= 90 with zero critical or serious axe violations."""
    frontend_index = settings.project_root / "frontend" / "index.html"
    assert frontend_index.exists(), f"Frontend index not found at {frontend_index}"

    html_content = frontend_index.read_text(encoding="utf-8")

    browser = await get_browser()
    context = await create_scan_context(browser)
    try:
        page = await load_page(
            context,
            html=html_content,
            base_url="http://127.0.0.1:8000/",
        )

        issues = await run_axe(page)
        await capture_aria_snapshot(page)
        score_breakdown = compute_score(issues)

        # Assert zero critical or serious axe violations
        critical_issues = [i for i in issues if i.impact == "critical"]
        serious_issues = [i for i in issues if i.impact == "serious"]

        critical_messages = [f"{i.rule_id} on {i.selector}: {i.message}" for i in critical_issues]
        serious_messages = [f"{i.rule_id} on {i.selector}: {i.message}" for i in serious_issues]

        assert len(critical_issues) == 0, (
            f"Found critical axe violations in UI: {critical_messages}"
        )
        assert len(serious_issues) == 0, f"Found serious axe violations in UI: {serious_messages}"

        # Assert score >= 90
        assert score_breakdown.score >= 90, (
            f"UI self-audit score was {score_breakdown.score}/100, expected >= 90"
        )

        # Capture screenshot for evidence
        screenshot_path = settings.project_root / "docs" / "self_audit_screenshot.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(screenshot_path))
        assert screenshot_path.exists() and screenshot_path.stat().st_size > 0

    finally:
        await context.close()
