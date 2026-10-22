"""Tests for FastAPI endpoints in backend/main.py."""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.runs import run_manager


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "llm_provider" in data


@pytest.mark.asyncio
async def test_scan_invalid_url_returns_400():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # file:// scheme blocked
        resp = await client.post("/api/scan", json={"url": "file:///etc/passwd"})
        assert resp.status_code == 400
        assert "Invalid URL" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_scan_pasted_html_accepted():
    html = "<html><body><h1>Test</h1></body></html>"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/scan", json={"html": html})
        assert resp.status_code == 202
        data = resp.json()
        assert "run_id" in data


@pytest.mark.asyncio
async def test_download_before_completion_returns_409():
    report = run_manager.create_run()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/runs/{report.run_id}/download")
        assert resp.status_code == 409
        assert "not completed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_apply_unknown_fix_id_returns_400():
    report = run_manager.create_run()
    run_manager.update_report(report.run_id, status="awaiting_review")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/runs/{report.run_id}/apply",
            json={"approved_fix_ids": ["fix_nonexistent_999"]},
        )
        assert resp.status_code == 400
        assert "Unknown fix IDs" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_events_polling_after_query():
    report = run_manager.create_run()
    run_manager.emit_event(report.run_id, "step_started", "Test event 1", step="scan")
    run_manager.emit_event(report.run_id, "step_completed", "Test event 2", step="scan")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/runs/{report.run_id}/events?after=1")
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) == 1
        assert events[0]["seq"] == 2
        assert events[0]["message"] == "Test event 2"
