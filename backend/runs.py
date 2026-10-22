"""Run state, event stream, and disk persistence for A11y Pilot."""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path

from backend.config import settings
from backend.schemas import (
    AgentEvent,
    FixSuggestion,
    Issue,
    RunStatus,
    ScanReport,
    ScoreBreakdown,
)

logger = logging.getLogger(__name__)


class RunManager:
    """Manages active run states, event broadcasting, and disk persistence."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or (settings.project_root / "data" / "runs")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._reports: dict[str, ScanReport] = {}
        self._events: dict[str, list[AgentEvent]] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
        self._active_runs: set[str] = set()

    def can_start_run(self) -> bool:
        """Limit concurrent active runs to 2."""
        return len(self._active_runs) < 2

    def create_run(
        self,
        source_url: str | None = None,
        llm_provider: str | None = None,
    ) -> ScanReport:
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        report = ScanReport(
            run_id=run_id,
            source_url=source_url,
            status="created",
            llm_provider=llm_provider or settings.LLM_PROVIDER,
        )
        self._reports[run_id] = report
        self._events[run_id] = []
        self._subscribers[run_id] = []
        self._active_runs.add(run_id)
        self.save_report(report)
        return report

    def get_report(self, run_id: str) -> ScanReport | None:
        if run_id in self._reports:
            return self._reports[run_id]

        # Check disk cache
        file_path = self.data_dir / f"{run_id}.json"
        if file_path.exists():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                report = ScanReport.model_validate(data)
                self._reports[run_id] = report
                return report
            except Exception as e:
                logger.error("Failed to load run %s from disk: %s", run_id, e)
        return None

    def update_report(
        self,
        run_id: str,
        status: RunStatus | None = None,
        page_title: str | None = None,
        score_before: ScoreBreakdown | None = None,
        score_after: ScoreBreakdown | None = None,
        issues: list[Issue] | None = None,
        fixes: list[FixSuggestion] | None = None,
        aria_before: str | None = None,
        aria_after: str | None = None,
        html_original_bytes: int | None = None,
        limitations: list[str] | None = None,
        needs_manual_checks: list[str] | None = None,
        duration_seconds: float | None = None,
    ) -> ScanReport:
        report = self.get_report(run_id)
        if not report:
            raise KeyError(f"Run {run_id} not found")

        if status is not None:
            report.status = status
            if status in ("completed", "failed"):
                self._active_runs.discard(run_id)
        if page_title is not None:
            report.page_title = page_title
        if score_before is not None:
            report.score_before = score_before
        if score_after is not None:
            report.score_after = score_after
        if issues is not None:
            report.issues = issues
        if fixes is not None:
            report.fixes = fixes
        if aria_before is not None:
            report.aria_before = aria_before
        if aria_after is not None:
            report.aria_after = aria_after
        if html_original_bytes is not None:
            report.html_original_bytes = html_original_bytes
        if limitations is not None:
            report.limitations = limitations
        if needs_manual_checks is not None:
            report.needs_manual_checks = needs_manual_checks
        if duration_seconds is not None:
            report.duration_seconds = duration_seconds

        self.save_report(report)
        return report

    def emit_event(
        self,
        run_id: str,
        event_type: str,
        message: str,
        step: str | None = None,
        data: dict | None = None,
    ) -> AgentEvent:
        events = self._events.setdefault(run_id, [])
        seq = len(events) + 1
        ev = AgentEvent(
            seq=seq,
            ts=time.time(),
            type=event_type,  # type: ignore
            step=step,
            message=message,
            data=data,
        )
        events.append(ev)

        # Notify active SSE subscribers
        subscribers = self._subscribers.get(run_id, [])
        for queue in list(subscribers):
            try:
                queue.put_nowait(ev)
            except Exception:
                pass

        return ev

    def get_events(self, run_id: str, after: int = 0) -> list[AgentEvent]:
        events = self._events.get(run_id, [])
        return [e for e in events if e.seq > after]

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        # Preload past events into queue
        for e in self.get_events(run_id):
            queue.put_nowait(e)
        self._subscribers.setdefault(run_id, []).append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue):
        if run_id in self._subscribers and queue in self._subscribers[run_id]:
            self._subscribers[run_id].remove(queue)

    def save_report(self, report: ScanReport):
        try:
            file_path = self.data_dir / f"{report.run_id}.json"
            file_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to write report to disk: %s", e)


run_manager = RunManager()
