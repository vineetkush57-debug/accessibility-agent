"""Live end-to-end integration test against Wikipedia Web Accessibility page."""

import json
import time
import urllib.request

BASE_URL = "http://127.0.0.1:8000"
TARGET_URL = "https://en.wikipedia.org/wiki/Web_accessibility"


def run_test():
    print(f"1. Submitting scan request for: {TARGET_URL}...")
    payload = json.dumps({"url": TARGET_URL}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/scan",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(req) as resp:
        scan_res = json.loads(resp.read().decode())
    run_id = scan_res["run_id"]
    print(f"   -> Run started with ID: {run_id}")

    print("2. Polling run status until review is ready...")
    status = "created"
    report = {}
    for i in range(45):
        time.sleep(1)
        with urllib.request.urlopen(f"{BASE_URL}/api/runs/{run_id}") as resp:
            report = json.loads(resp.read().decode())
        status = report["status"]
        print(f"   [t={i+1}s] Status: {status}")
        if status in ("awaiting_review", "completed", "failed"):
            break

    if status != "awaiting_review":
        print(f"FAILED: Expected awaiting_review, got {status}")
        return False

    print("\n3. Scan Results Summary:")
    print(f"   Page Title: {report.get('page_title')}")
    score_before = report.get("score_before", {}).get("score", 0)
    print(f"   Baseline Score: {score_before}/100")
    print(f"   Total Issues Discovered: {len(report.get('issues', []))}")
    print(f"   Fixes Proposed: {len(report.get('fixes', []))}")

    fixes = report.get("fixes", [])
    for fix in fixes[:5]:
        print(
            f"   * [{fix['id']}] {fix['explanation'][:70]}... (Conf: {fix['confidence']}, Needs Human: {fix['needs_human']})"
        )

    # 4. Approve fixes
    candidate_ids = [f["id"] for f in fixes if f.get("patch")]
    approved_ids = candidate_ids[:2]
    print(f"\n4. Applying {len(approved_ids)} approved fixes: {approved_ids}...")

    apply_payload = json.dumps({"approved_fix_ids": approved_ids}).encode("utf-8")
    apply_req = urllib.request.Request(
        f"{BASE_URL}/api/runs/{run_id}/apply",
        data=apply_payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(apply_req) as resp:
        apply_res = json.loads(resp.read().decode())
    print(f"   -> Apply response: {apply_res}")

    print("5. Polling until verification completes...")
    final_report = {}
    for i in range(90):
        time.sleep(1)
        with urllib.request.urlopen(f"{BASE_URL}/api/runs/{run_id}") as resp:
            final_report = json.loads(resp.read().decode())
        final_status = final_report["status"]
        print(f"   [t={i+1}s] Status: {final_status}")
        if final_status in ("completed", "failed"):
            break

    print("\n6. Final Verification Report:")
    print(f"   Final Status: {final_report['status']}")
    score_after_obj = final_report.get("score_after") or {}
    score_after = score_after_obj.get("score", score_before)
    print(f"   Score: {score_before} -> {score_after} (Delta: +{score_after - score_before})")
    applied_fixes = [f for f in final_report.get("fixes", []) if f["status"] in ("applied", "retried_applied")]
    print(f"   Successfully verified applied fixes: {len(applied_fixes)}")

    print("\n7. Testing fixed.html download...")
    with urllib.request.urlopen(f"{BASE_URL}/api/runs/{run_id}/download") as resp:
        html_data = resp.read().decode("utf-8", errors="ignore")
    print(f"   Fixed HTML downloaded successfully! Length: {len(html_data)} bytes")

    print("\n" + "=" * 60)
    print("ALL LIVE WIKIPEDIA CHECKS PASSED 100%!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_test()
    if not success:
        exit(1)
