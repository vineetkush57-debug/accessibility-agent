"""FastAPI application for A11y Pilot.

Serves REST endpoints, Server-Sent Events (SSE), fixed HTML downloads,
and mounts the accessible frontend and demo site.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.agent import get_run_html, run_apply_pipeline, run_scan_pipeline
from backend.config import settings
from backend.runs import run_manager
from backend.scanner import close_browser, get_browser
from backend.schemas import ApplyRequest, ScanReport, ScanRequest
from backend.security import validate_pasted_html, validate_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("a11y_pilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure browser initialized
    logger.info("A11y Pilot starting up...")
    try:
        await get_browser()
    except Exception as e:
        logger.warning("Browser startup delayed or failed: %s", e)
    yield
    # Shutdown: clean up browser
    logger.info("A11y Pilot shutting down...")
    await close_browser()


app = FastAPI(
    title="A11y Pilot API",
    description="Agentic web accessibility auditor and auto-fixer",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: same-origin and local test ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Service health and configured LLM provider."""
    return {
        "status": "ok",
        "llm_provider": settings.LLM_PROVIDER,
        "version": "1.0.0",
    }


@app.post("/api/scan", status_code=202)
async def start_scan(req: ScanRequest, bg_tasks: BackgroundTasks):
    """Initiate an accessibility audit on a URL or pasted HTML."""
    if not req.url and not req.html:
        raise HTTPException(status_code=400, detail="Must provide either 'url' or 'html'.")

    # Concurrent active run guard
    if not run_manager.can_start_run():
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent runs in progress. Maximum 2 allowed simultaneously.",
        )

    # Pre-validation for security
    if req.url:
        is_valid, err = validate_url(req.url)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid URL: {err}")
    elif req.html:
        is_valid, err = validate_pasted_html(req.html)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid HTML: {err}")

    # Create run report
    report = run_manager.create_run(source_url=req.url)
    run_id = report.run_id

    # Launch scan in background task
    bg_tasks.add_task(
        run_scan_pipeline,
        run_id=run_id,
        url=req.url,
        html=req.html,
        base_url=req.base_url,
        language=req.language or "en",
    )

    return {"run_id": run_id}


@app.get("/api/runs/{run_id}", response_model=ScanReport)
async def get_run(run_id: str):
    """Retrieve full scan report and current run status."""
    report = run_manager.get_report(run_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return report


@app.get("/api/runs/{run_id}/events")
async def stream_events(run_id: str, request: Request, after: int | None = None):
    """Stream agent events via SSE with fallback for polling query ?after=<seq>."""
    report = run_manager.get_report(run_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    # 1. Polling fallback when ?after= is explicitly passed in query
    if after is not None:
        events = run_manager.get_events(run_id, after=after)
        return JSONResponse(content=[e.model_dump() for e in events])

    # 2. Server-Sent Events (SSE) stream
    # Check Last-Event-ID header for stream reconnection
    last_id_hdr = request.headers.get("Last-Event-ID")
    start_seq = int(last_id_hdr) if (last_id_hdr and last_id_hdr.isdigit()) else 0

    async def event_generator():
        # Yield existing past events first
        for past_ev in run_manager.get_events(run_id, after=start_seq):
            data_str = json.dumps(past_ev.model_dump())
            yield f"id: {past_ev.seq}\nevent: agent_event\ndata: {data_str}\n\n"

        queue = run_manager.subscribe(run_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15.0)
                    if ev.seq > start_seq:
                        data_str = json.dumps(ev.model_dump())
                        yield f"id: {ev.seq}\nevent: agent_event\ndata: {data_str}\n\n"
                    if ev.type in ("run_completed", "error"):
                        break
                except TimeoutError:
                    # Keep-alive comment
                    yield ": keep-alive\n\n"
        finally:
            run_manager.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/runs/{run_id}/apply", status_code=202)
async def apply_fixes(run_id: str, req: ApplyRequest, bg_tasks: BackgroundTasks):
    """Apply approved fixes and trigger the re-scan / verification loop."""
    report = run_manager.get_report(run_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    if report.status != "awaiting_review":
        raise HTTPException(
            status_code=400,
            detail=f"Run must be in 'awaiting_review' status to apply fixes (current: {report.status}).",
        )

    # Validate that all requested fix IDs exist in the report
    valid_fix_ids = {f.id for f in report.fixes}
    unknown_ids = set(req.approved_fix_ids) - valid_fix_ids
    if unknown_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown fix IDs: {list(unknown_ids)}",
        )

    # Launch apply verification in background
    bg_tasks.add_task(
        run_apply_pipeline,
        run_id=run_id,
        approved_fix_ids=req.approved_fix_ids,
    )

    return {"status": "applying"}


@app.get("/api/runs/{run_id}/download")
async def download_fixed_html(run_id: str):
    """Download the sanitized and remediated HTML file."""
    report = run_manager.get_report(run_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    if report.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Run is not completed yet (current: {report.status}). Fixed HTML unavailable.",
        )

    html_store = get_run_html(run_id)
    state_html = html_store.get("state") or html_store.get("baseline", "")

    return Response(
        content=state_html,
        media_type="text/html",
        headers={
            "Content-Disposition": 'attachment; filename="fixed.html"',
        },
    )


@app.get("/api/runs/{run_id}/report.json")
async def download_report_json(run_id: str):
    """Download the final ScanReport as a JSON attachment."""
    report = run_manager.get_report(run_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    return Response(
        content=report.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="report_{run_id}.json"',
        },
    )


# Mount Demo Site at /demo/
demo_dir = settings.project_root / "demo-site"
if demo_dir.exists():
    app.mount("/demo", StaticFiles(directory=str(demo_dir), html=True), name="demo-site")

# Mount Frontend at /
frontend_dir = settings.project_root / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
