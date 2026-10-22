"""End-to-end browser pipeline test using mock LLM and demo page1.html."""

import pytest

from backend.agent import run_apply_pipeline, run_scan_pipeline
from backend.config import settings
from backend.runs import run_manager


@pytest.mark.browser
@pytest.mark.asyncio
async def test_page1_mock_pipeline_end_to_end():
    # 1. Read demo page1.html
    page1_path = settings.project_root / "demo-site" / "page1.html"
    assert page1_path.exists(), f"Missing {page1_path}"
    html_content = page1_path.read_text(encoding="utf-8")

    # 2. Start scan run
    report = run_manager.create_run(source_url="http://127.0.0.1:8000/demo/page1.html")
    run_id = report.run_id

    await run_scan_pipeline(
        run_id=run_id,
        html=html_content,
        base_url="http://127.0.0.1:8000/demo/",
    )

    scanned_report = run_manager.get_report(run_id)
    assert scanned_report is not None
    assert scanned_report.status == "awaiting_review"
    assert scanned_report.score_before is not None

    initial_score = scanned_report.score_before.score
    assert initial_score <= 60, f"Expected initial score <= 60, got {initial_score}"

    # Assert AI-only catches
    ai_issues = [i for i in scanned_report.issues if i.source == "llm"]
    assert len(ai_issues) >= 2, f"Expected at least 2 AI-only catches, got {len(ai_issues)}"

    # Assert Issue #10 (fake-btn) is marked needs_human
    fake_btn_fix = next(
        (
            f
            for f in scanned_report.fixes
            if "fake-btn" in f.explanation.lower()
            or (f.human_note and "button" in f.human_note.lower())
        ),
        None,
    )
    assert fake_btn_fix is not None, "Expected fix proposal for fake-btn"
    assert fake_btn_fix.needs_human is True, "fake-btn must be marked needs_human"
    assert fake_btn_fix.status == "needs_human"

    # 3. Approve all safe fixes
    approved_fix_ids = [
        f.id for f in scanned_report.fixes if not f.needs_human and f.patch is not None
    ]
    assert len(approved_fix_ids) >= 5, (
        f"Expected at least 5 approvable fixes, got {len(approved_fix_ids)}"
    )

    # 4. Run Apply & Verification pipeline
    await run_apply_pipeline(run_id=run_id, approved_fix_ids=approved_fix_ids)

    final_report = run_manager.get_report(run_id)
    assert final_report is not None
    assert final_report.status == "completed"
    assert final_report.score_after is not None

    final_score = final_report.score_after.score
    delta = final_score - initial_score

    # Score improves by at least 30 points
    assert delta >= 30, (
        f"Expected score improvement >= 30, got {delta} (from {initial_score} to {final_score})"
    )
    assert final_score >= initial_score, "Score must not regress"

    # Per-fix status check
    applied_count = sum(1 for f in final_report.fixes if f.status in ("applied", "retried_applied"))
    assert applied_count >= len(approved_fix_ids) - 1, (
        f"Expected most approved fixes applied, got {applied_count}"
    )
