"""Acceptance test suite for public URLs and localhost demo pages."""

import json
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def api_post(endpoint: str, data: dict):
    req = urllib.request.Request(
        f"{BASE_URL}{endpoint}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_get(endpoint: str):
    with urllib.request.urlopen(f"{BASE_URL}{endpoint}") as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_get_text(endpoint: str) -> str:
    with urllib.request.urlopen(f"{BASE_URL}{endpoint}") as resp:
        return resp.read().decode("utf-8")


def poll_run(run_id: str, target_statuses: tuple, timeout: float = 120.0) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        report = api_get(f"/api/runs/{run_id}")
        status = report.get("status")
        if status in target_statuses:
            return report
        if status == "failed":
            raise RuntimeError(f"Run {run_id} failed: {report}")
        time.sleep(1.5)
    raise TimeoutError(f"Run {run_id} timed out waiting for {target_statuses}")


def run_all_acceptance_tests():
    print("=" * 70)
    print("STARTING ACCEPTANCE TESTS")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. https://example.com
    # -------------------------------------------------------------
    print("\n--- [TEST 1] https://example.com ---")
    res1 = api_post("/api/scan", {"url": "https://example.com"})
    run_id1 = res1["run_id"]
    print(f"Started run {run_id1} for https://example.com")
    report1 = poll_run(run_id1, ("awaiting_review", "completed"))
    score1 = report1.get("score_before", {}).get("score")
    issues1_count = len(report1.get("issues", []))
    print(f"Status: {report1['status']}")
    print(f"Issues found: {issues1_count}")
    print(f"Score before: {score1}/100")
    assert score1 is not None, "Score must be computed for example.com"
    print(">>> TEST 1 PASSED: Scan returned, score computed, no crash.")

    # -------------------------------------------------------------
    # 2. https://www.w3.org/WAI/demos/bad/before/home.html
    # -------------------------------------------------------------
    print("\n--- [TEST 2] https://www.w3.org/WAI/demos/bad/before/home.html ---")
    res2 = api_post("/api/scan", {"url": "https://www.w3.org/WAI/demos/bad/before/home.html"})
    run_id2 = res2["run_id"]
    print(f"Started run {run_id2} for W3C bad demo")
    report2 = poll_run(run_id2, ("awaiting_review",))
    issues2 = report2.get("issues", [])
    fixes2 = report2.get("fixes", [])
    score2_before = report2.get("score_before", {}).get("score")
    print(f"Status: {report2['status']}")
    print(f"Issues found: {len(issues2)}")
    print(f"Fixes proposed: {len(fixes2)}")
    print(f"Score before: {score2_before}/100")
    assert len(issues2) > 0, "Expected issues to be found on W3C bad demo"

    # Apply approved fixes
    approved2 = [f["id"] for f in fixes2 if not f.get("needs_human") and f.get("patch")]
    print(f"Applying {len(approved2)} approved fixes: {approved2}")
    api_post(f"/api/runs/{run_id2}/apply", {"approved_fix_ids": approved2})
    final2 = poll_run(run_id2, ("completed",))
    score2_after = final2.get("score_after", {}).get("score")
    applied2 = [f for f in final2.get("fixes", []) if f.get("status") == "applied"]
    print(f"Final status: {final2['status']}")
    print(f"Score after: {score2_after}/100")
    print(f"Fixes successfully applied: {len(applied2)}")
    assert len(applied2) > 0, "Expected at least some fixes to be applied and verified"
    print(">>> TEST 2 PASSED: Issues found, fixes applied and verified.")

    # -------------------------------------------------------------
    # 3. https://en.wikipedia.org/wiki/Rohit_Sharma
    # -------------------------------------------------------------
    print("\n--- [TEST 3] https://en.wikipedia.org/wiki/Rohit_Sharma ---")
    res3 = api_post("/api/scan", {"url": "https://en.wikipedia.org/wiki/Rohit_Sharma"})
    run_id3 = res3["run_id"]
    print(f"Started run {run_id3} for Wikipedia Rohit Sharma")
    report3 = poll_run(run_id3, ("awaiting_review",))
    issues3 = report3.get("issues", [])
    fixes3 = report3.get("fixes", [])
    score3_before = report3.get("score_before", {}).get("score")
    print(f"Status: {report3['status']}")
    print(f"Total issues found on page: {len(issues3)}")
    print(f"Fixes proposed by LLM (capped <= 10): {len(fixes3)}")
    assert len(fixes3) <= 10, f"Expected <= 10 issues sent to LLM, got {len(fixes3)}"

    # Apply fixes
    approved3 = [f["id"] for f in fixes3 if not f.get("needs_human") and f.get("patch")][:8]
    print(f"Approving {len(approved3)} fixes: {approved3}")
    api_post(f"/api/runs/{run_id3}/apply", {"approved_fix_ids": approved3})
    final3 = poll_run(run_id3, ("completed",))
    score3_after = final3.get("score_after", {}).get("score")
    applied3 = [f["id"] for f in final3.get("fixes", []) if f.get("status") == "applied"]
    failed3 = [f["id"] for f in final3.get("fixes", []) if f.get("status") in ("failed", "reverted")]
    print(f"Final status: {final3['status']}")
    print(f"Score before: {score3_before} -> Score after: {score3_after}")
    print(f"Patcher applied list: {applied3}")
    print(f"Patcher failed/reverted list: {failed3}")
    assert score3_after is not None, "After-score must be returned"

    # Preview check: fetch preview HTML for iframe.srcdoc
    preview_html = api_get_text(f"/api/runs/{run_id3}/preview")
    assert 'href="https://en.wikipedia.org/wiki/Rohit_Sharma"' in preview_html and "<base" in preview_html, (
        "Preview HTML must have base href set"
    )
    assert "<script" not in preview_html.lower(), "Preview HTML must have scripts stripped"
    print(f"Preview HTML verified for srcdoc (length: {len(preview_html)} chars, <base> injected, scripts stripped)")
    print(">>> TEST 3 PASSED: Wikipedia scan completed, <= 10 sent to LLM, patcher reported applied/failed, after-score returned, preview rendered via srcdoc.")

    # -------------------------------------------------------------
    # 4. Localhost Demo Pages
    # -------------------------------------------------------------
    print("\n--- [TEST 4] Localhost Demo Page 1 (http://127.0.0.1:8000/demo/page1.html) ---")
    res4 = api_post("/api/scan", {"url": "http://127.0.0.1:8000/demo/page1.html"})
    run_id4 = res4["run_id"]
    print(f"Started run {run_id4} for demo page1.html")
    report4 = poll_run(run_id4, ("awaiting_review",))
    score4_before = report4.get("score_before", {}).get("score")
    fixes4 = report4.get("fixes", [])
    print(f"Demo baseline score: {score4_before}/100")
    assert score4_before <= 60, f"Expected baseline <= 60, got {score4_before}"

    # Check fake-btn is flagged needs_human
    fake_btn_fix = next(
        (
            f
            for f in fixes4
            if "fake-btn" in f.get("explanation", "").lower()
            or (f.get("human_note") and "button" in f.get("human_note", "").lower())
        ),
        None,
    )
    assert fake_btn_fix is not None, "Expected fake-btn fix proposal"
    assert fake_btn_fix.get("needs_human") is True, "fake-btn must be needs_human"
    print(f"fake-btn fix correctly flagged needs_human: {fake_btn_fix['explanation']}")

    approved4 = [f["id"] for f in fixes4 if not f.get("needs_human") and f.get("patch")]
    print(f"Approving {len(approved4)} fixes: {approved4}")
    api_post(f"/api/runs/{run_id4}/apply", {"approved_fix_ids": approved4})
    final4 = poll_run(run_id4, ("completed",))
    score4_after = final4.get("score_after", {}).get("score")
    applied4 = [f["id"] for f in final4.get("fixes", []) if f.get("status") == "applied"]
    print(f"Demo page 1 final score: {score4_after}/100 (improved by {score4_after - score4_before} points)")
    print(f"Fixes applied: {applied4}")
    assert score4_after > score4_before, "Score must improve"
    print(">>> TEST 4 PASSED: Localhost demo page1 works exactly as expected.")

    print("\n" + "=" * 70)
    print("ALL 4 ACCEPTANCE TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_acceptance_tests()
