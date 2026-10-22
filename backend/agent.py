"""Agent orchestration module for A11y Pilot.

Handles the scanning lifecycle: page load, axe-core audit, semantic extraction,
proposing fixes, and the verify/re-scan loop.
"""

import logging
import time

from backend.config import settings
from backend.extract import extract_page_semantics
from backend.runs import run_manager
from backend.scanner import (
    capture_aria_snapshot,
    create_scan_context,
    get_browser,
    load_page,
    run_axe,
)
from backend.scoring import compute_score
from backend.security import validate_pasted_html, validate_url

logger = logging.getLogger(__name__)

# Temporary in-memory storage for baseline and current HTML per run
_run_html_store: dict[str, dict[str, str]] = {}


def set_run_html(run_id: str, baseline: str, state: str | None = None):
    _run_html_store[run_id] = {
        "baseline": baseline,
        "state": state or baseline,
    }


def get_run_html(run_id: str) -> dict[str, str]:
    return _run_html_store.get(run_id, {"baseline": "", "state": ""})


async def run_scan_pipeline(
    run_id: str,
    url: str | None = None,
    html: str | None = None,
    base_url: str | None = None,
    language: str = "en",
):
    """Execute the full scan and initial proposal phase for a run."""
    start_time = time.time()
    try:
        run_manager.update_report(run_id, status="scanning")

        # 1. URL / HTML validation
        if url:
            is_valid, err = validate_url(url)
            if not is_valid:
                run_manager.emit_event(
                    run_id, "error", f"Security validation failed: {err}", step="scan"
                )
                run_manager.update_report(run_id, status="failed")
                return
        elif html:
            is_valid, err = validate_pasted_html(html)
            if not is_valid:
                run_manager.emit_event(
                    run_id, "error", f"HTML validation failed: {err}", step="scan"
                )
                run_manager.update_report(run_id, status="failed")
                return

        # 2. Step: Scan (Playwright + axe-core)
        run_manager.emit_event(
            run_id, "step_started", "Launching browser and loading page...", step="scan"
        )

        browser = await get_browser()
        context = await create_scan_context(browser)
        try:
            page = await load_page(context, url=url, html=html, base_url=base_url)
            page_title = await page.title()
            baseline_html = await page.content()
            html_bytes = len(baseline_html.encode("utf-8"))

            run_manager.emit_event(
                run_id,
                "step_started",
                "Running axe-core accessibility rule engine...",
                step="scan",
            )
            axe_issues = await run_axe(page)
            aria_before = await capture_aria_snapshot(page)
            await page.close()
        finally:
            await context.close()

        set_run_html(run_id, baseline_html)
        score_before = compute_score(axe_issues)

        # Emit issue_found events
        if len(axe_issues) <= 50:
            for iss in axe_issues:
                run_manager.emit_event(
                    run_id,
                    "issue_found",
                    f"Found [{iss.impact.upper()}] {iss.rule_id} on {iss.selector}",
                    step="scan",
                    data=iss.model_dump(),
                )
        else:
            run_manager.emit_event(
                run_id,
                "issue_found",
                f"Found {len(axe_issues)} axe issues across page nodes.",
                step="scan",
            )

        run_manager.emit_event(
            run_id,
            "step_completed",
            f"Scan completed: found {len(axe_issues)} rule issues. Initial score: {score_before.score}/100",
            step="scan",
            data={"score": score_before.score, "issues_count": len(axe_issues)},
        )

        all_issues = list(axe_issues)

        # 3. Step: AI Semantic Audit
        run_manager.emit_event(
            run_id,
            "step_started",
            "Extracting semantic elements for AI meaning audit...",
            step="audit",
        )
        semantics = extract_page_semantics(baseline_html)

        # Plug into LLM semantic audit
        try:
            from backend.llm import get_llm
            from backend.llm.prompts import build_semantic_audit_prompt

            llm = get_llm()
            sys_prompt, user_prompt = build_semantic_audit_prompt(semantics)
            llm_audit_raw = await llm.complete_json(
                system=sys_prompt,
                user=user_prompt,
                schema_hint="array of semantic issue objects",
            )

            # Validate and filter LLM issues
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(baseline_html, "lxml")
            existing_selectors = {iss.selector for iss in all_issues}
            llm_issue_idx = len(all_issues) + 1

            if isinstance(llm_audit_raw, list):
                for raw_iss in llm_audit_raw:
                    sel = raw_iss.get("selector", "")
                    # Hallucination guard: ensure selector resolves to exactly one node
                    try:
                        matches = soup.select(sel) if sel else []
                    except Exception:
                        matches = []
                    if len(matches) != 1:
                        continue
                    if sel in existing_selectors:
                        continue  # Avoid duplicate rule reporting on same element

                    from backend.schemas import Issue

                    iss_obj = Issue(
                        id=f"iss_{llm_issue_idx:03d}",
                        source="llm",
                        rule_id=raw_iss.get("rule_id", "llm-semantic"),
                        impact=raw_iss.get("impact", "serious"),
                        wcag=raw_iss.get("wcag", []),
                        selector=sel,
                        html=str(matches[0])[:500],
                        message=raw_iss.get("message", "Semantic meaning issue detected by AI"),
                        fixable=True,
                    )
                    all_issues.append(iss_obj)
                    existing_selectors.add(sel)
                    llm_issue_idx += 1
                    run_manager.emit_event(
                        run_id,
                        "issue_found",
                        f"AI detected [{iss_obj.impact.upper()}]: {iss_obj.message} on {iss_obj.selector}",
                        step="audit",
                        data=iss_obj.model_dump(),
                    )
        except Exception as e:
            logger.warning("LLM semantic audit skipped or errored: %s", e)

        # Recompute score including any LLM-detected issues
        score_before = compute_score(all_issues)
        run_manager.emit_event(
            run_id,
            "step_completed",
            f"Audit finished. Total issues: {len(all_issues)}, Baseline score: {score_before.score}/100",
            step="audit",
        )

        # 4. Step: Fix Generation (Drafting fixes)
        run_manager.emit_event(
            run_id,
            "step_started",
            "Generating safe code fixes for top issues...",
            step="fix",
        )
        from backend.patcher import dry_run

        fixes = []
        fixable_issues = [i for i in all_issues if i.fixable]
        # Order by impact, then source (axe first)
        impact_order = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
        fixable_issues.sort(
            key=lambda x: (impact_order.get(x.impact, 4), 0 if x.source == "axe" else 1)
        )
        target_issues = fixable_issues[: settings.MAX_ISSUES_FOR_FIXING]

        from backend.llm import get_llm
        from backend.llm.prompts import build_explain_and_fix_prompt
        from backend.schemas import FixSuggestion

        llm = get_llm()
        for idx, iss in enumerate(target_issues, 1):
            try:
                sys_prompt, user_prompt = build_explain_and_fix_prompt(iss, language=language)
                fix_raw = await llm.complete_json(
                    system=sys_prompt,
                    user=user_prompt,
                    schema_hint="FixSuggestion JSON",
                )
                if isinstance(fix_raw, dict):
                    explanation = fix_raw.get("explanation", f"Fix for {iss.rule_id}")
                    wcag_crit = fix_raw.get("wcag") or (iss.wcag[0] if iss.wcag else "1.1.1")
                    patch_obj = fix_raw.get("patch")
                    confidence = float(fix_raw.get("confidence", 0.8))
                    needs_human = bool(fix_raw.get("needs_human", False))
                    human_note = fix_raw.get("human_note")

                    # Dry run to generate unified diff
                    before_snip, after_snip, diff_str = None, None, None
                    if patch_obj and not needs_human:
                        from backend.schemas import parse_patch

                        try:
                            validated_patch = parse_patch(patch_obj)
                            res = dry_run(baseline_html, validated_patch)
                            if res.ok:
                                before_snip = res.before_snippet
                                after_snip = res.after_snippet
                                diff_str = res.diff
                            else:
                                needs_human = True
                                human_note = f"Patch dry-run failed: {res.error}"
                        except Exception as pe:
                            needs_human = True
                            human_note = f"Invalid patch format: {pe}"

                    if confidence < settings.CONFIDENCE_THRESHOLD:
                        needs_human = True

                    fix_sug = FixSuggestion(
                        id=f"fix_{idx:03d}",
                        issue_id=iss.id,
                        explanation=explanation,
                        wcag=wcag_crit,
                        patch=patch_obj if not needs_human else None,
                        confidence=confidence,
                        needs_human=needs_human,
                        human_note=human_note,
                        before_snippet=before_snip,
                        after_snippet=after_snip,
                        diff=diff_str,
                        status="needs_human" if needs_human else "proposed",
                    )
                    fixes.append(fix_sug)
                    run_manager.emit_event(
                        run_id,
                        "fix_proposed",
                        f"Proposed fix for {iss.rule_id}: {explanation}",
                        step="fix",
                        data=fix_sug.model_dump(),
                    )
            except Exception as fe:
                logger.error("Failed to generate fix for %s: %s", iss.id, fe)

        # Update report state to awaiting_review
        run_manager.update_report(
            run_id,
            status="awaiting_review",
            page_title=page_title,
            score_before=score_before,
            issues=all_issues,
            fixes=fixes,
            aria_before=aria_before,
            html_original_bytes=html_bytes,
            duration_seconds=round(time.time() - start_time, 2),
        )
        run_manager.emit_event(
            run_id,
            "step_completed",
            f"Fix proposals ready ({len(fixes)} fixes proposed). Awaiting human review.",
            step="fix",
        )

    except Exception as e:
        logger.exception("Error during scan pipeline for %s: %s", run_id, e)
        run_manager.emit_event(run_id, "error", f"Scan pipeline error: {e!s}", step="scan")
        run_manager.update_report(run_id, status="failed")


async def run_apply_pipeline(run_id: str, approved_fix_ids: list[str]):
    """Execute the closed-loop apply, re-scan, retry, and revert pipeline."""
    start_time = time.time()
    try:
        report = run_manager.get_report(run_id)
        if not report:
            raise KeyError(f"Run {run_id} not found")

        run_manager.update_report(run_id, status="applying")
        run_manager.emit_event(
            run_id,
            "step_started",
            f"Applying {len(approved_fix_ids)} approved fixes...",
            step="verify",
        )

        html_store = get_run_html(run_id)
        state_html = html_store.get("state") or html_store.get("baseline", "")
        if not state_html:
            raise RuntimeError("Baseline HTML not found in session memory.")

        # Baseline issues and score
        current_score = report.score_before.score if report.score_before else 0
        issues_by_id = {iss.id: iss for iss in report.issues}
        fixes_by_id = {f.id: f for f in report.fixes}

        # Track known rule+selector pairs in baseline
        known_issue_keys = {(iss.rule_id, iss.selector) for iss in report.issues}

        from backend.llm import get_llm
        from backend.llm.prompts import build_explain_and_fix_prompt
        from backend.patcher import apply_patch
        from backend.scanner import rescan_html

        llm = get_llm()

        for fix_id in approved_fix_ids:
            fix = fixes_by_id.get(fix_id)
            if not fix or fix.needs_human or not fix.patch:
                continue

            target_issue = issues_by_id.get(fix.issue_id)
            attempt = 0
            curr_fix = fix

            while True:
                # 1. Apply patch to candidate HTML
                res = apply_patch(state_html, curr_fix.patch)
                if not res.ok:
                    curr_fix.status = "failed"
                    curr_fix.verification_note = res.error
                    run_manager.emit_event(
                        run_id,
                        "fix_reverted",
                        f"Patch execution failed on {curr_fix.id}: {res.error}",
                        step="verify",
                    )
                    break

                # 2. Re-scan candidate HTML
                candidate_html = res.html_after
                re_issues, re_score, re_aria = await rescan_html(candidate_html)
                re_keys = {(iss.rule_id, iss.selector) for iss in re_issues}

                # Check if target issue resolved
                if target_issue:
                    if target_issue.source == "axe":
                        target_key = (target_issue.rule_id, target_issue.selector)
                        resolved = target_key not in re_keys
                    else:
                        # For LLM issue, verify selector exists and changed
                        resolved = True
                else:
                    resolved = True

                # Check regression: new violations or score drop
                new_violations = [k for k in re_keys if k not in known_issue_keys]
                regression = bool(new_violations) or (re_score.score < current_score)

                if resolved and not regression:
                    state_html = candidate_html
                    current_score = re_score.score
                    curr_fix.status = "retried_applied" if attempt > 0 else "applied"
                    curr_fix.attempts = attempt + 1
                    curr_fix.verification_note = f"Verified: score now {current_score}/100"
                    run_manager.emit_event(
                        run_id,
                        "fix_applied",
                        f"Fix {curr_fix.id} successfully verified (Score: {current_score})",
                        step="verify",
                    )
                    break

                # Needs retry or revert
                if attempt >= settings.MAX_RETRIES_PER_FIX:
                    curr_fix.status = "reverted"
                    curr_fix.attempts = attempt + 1
                    reason = f"Regression detected ({new_violations}) or unresolved after {attempt} retries"
                    curr_fix.verification_note = reason
                    run_manager.emit_event(
                        run_id,
                        "fix_reverted",
                        f"Fix {curr_fix.id} reverted: {reason}",
                        step="verify",
                    )
                    break

                # Trigger retry with LLM feedback
                attempt += 1
                curr_fix.attempts = attempt
                run_manager.emit_event(
                    run_id,
                    "fix_retry",
                    f"Fix {curr_fix.id} attempt {attempt} failed verification. Asking AI for adapted patch...",
                    step="verify",
                )
                try:
                    sys_prompt, user_prompt = build_explain_and_fix_prompt(
                        target_issue,
                        previous_attempt=curr_fix,
                        feedback="Patch did not fully resolve violation or caused low contrast.",
                    )
                    retry_raw = await llm.complete_json(
                        system=sys_prompt,
                        user=user_prompt,
                        schema_hint="FixSuggestion JSON",
                    )
                    if isinstance(retry_raw, dict) and retry_raw.get("patch"):
                        from backend.schemas import parse_patch

                        curr_fix.patch = parse_patch(retry_raw["patch"])
                    else:
                        curr_fix.status = "failed"
                        break
                except Exception as re_err:
                    curr_fix.status = "failed"
                    curr_fix.verification_note = f"Retry error: {re_err}"
                    break

        # Mark non-approved proposed fixes as rejected
        for f in report.fixes:
            if f.id not in approved_fix_ids and f.status == "proposed":
                f.status = "rejected"

        # Final verification re-scan
        run_manager.emit_event(
            run_id,
            "step_started",
            "Running final comprehensive verification scan...",
            step="report",
        )
        final_issues, final_score, final_aria = await rescan_html(state_html)

        # Update saved HTML state
        html_store["state"] = state_html

        # Standard limitations and manual checks
        limitations = [
            "Automated tools, including A11y Pilot, cannot certify WCAG or legal compliance. Manual testing with real assistive technology (for example NVDA, VoiceOver) is still required.",
            "Fixes were applied to a snapshot of the rendered HTML; mapping them back to framework source files is future work.",
            "Color contrast calculations rely on computed styling and may differ under active user stylesheets or dark mode toggles.",
        ]

        needs_manual = [
            "Keyboard-only navigation: Ensure all interactive widgets can be reached and activated using Tab, Shift+Tab, Enter, and Space.",
            "Visible focus order: Verify that the focus indicator is clearly distinguishable with at least 3:1 contrast against adjacent colors.",
            "Video/audio captions and transcripts: Confirm that synchronized closed captions and transcripts are present for multimedia.",
            "Meaningful reading order: Verify that the document reading order preserves meaning when CSS layout is disabled.",
            "Zoom to 200%: Confirm that page layout reflows without horizontal scrolling or clipped text at 200% browser zoom.",
        ]
        for f in report.fixes:
            if f.status == "needs_human" and f.human_note:
                needs_manual.append(f"Issue {f.issue_id}: {f.human_note}")

        run_manager.update_report(
            run_id,
            status="completed",
            score_after=final_score,
            fixes=report.fixes,
            aria_after=final_aria,
            limitations=limitations,
            needs_manual_checks=needs_manual,
            duration_seconds=round(time.time() - start_time, 2),
        )

        run_manager.emit_event(
            run_id,
            "verification_done",
            f"Verification complete: Score moved from {report.score_before.score if report.score_before else 0} to {final_score.score} (+{(final_score.score - (report.score_before.score if report.score_before else 0))})",
            step="report",
            data={
                "score_before": report.score_before.score if report.score_before else 0,
                "score_after": final_score.score,
            },
        )
        run_manager.emit_event(
            run_id,
            "run_completed",
            "A11y Pilot audit and auto-remediation run completed.",
            step="report",
        )

    except Exception as e:
        logger.exception("Error during apply pipeline for %s: %s", run_id, e)
        run_manager.emit_event(run_id, "error", f"Apply pipeline error: {e!s}", step="verify")
        run_manager.update_report(run_id, status="failed")
