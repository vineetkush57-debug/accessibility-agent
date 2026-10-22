# Project Progress Log

## Phase 0: Foundations & Data Contracts
- **Status**: Completed (100% verified)
- **Completed**:
  - Initialized git repository connected to user's remote.
  - Setup `.gitignore`, `.env.example`, `.env`, `requirements.txt`, `requirements-dev.txt`.
  - Installed all Python 3.14 packages: FastAPI, Uvicorn, Pydantic v2, BeautifulSoup4, LXML, Playwright, Pytest, Ruff.
  - Playwright Chromium and headless shell downloaded and ready.
  - Implemented `backend/config.py` using `pydantic-settings`.
  - Implemented `backend/schemas.py` defining the contract-first models: `Impact`, `IssueSource`, `FixStatus`, `RunStatus`, `Issue`, `Patch` (discriminated union for `set_attr`, `remove_attr`, `set_text`, `wrap_label`, `add_css`, `change_tag`), `FixSuggestion`, `ScoreBreakdown`, `AgentEvent`, `ScanReport`.
  - Implemented `backend/security.py` with SSRF protection, IP/range validation, allowed local host exception, and payload size bounds.
  - Implemented `backend/scoring.py` with the capped penalty formula.
  - Vendored `backend/vendor/axe.min.js` (axe-core 4.10.2).
  - Implemented `.github/copilot-instructions.md`, `Makefile`, and `scripts/dev.py`.
  - Test verification: 17 of 17 tests passed in `tests/test_schemas.py`, `tests/test_security.py`, `tests/test_scoring.py`.

## Phase 1: Scan Path & Core Engine
- **Status**: Completed (100% verified)
- **Completed**:
  - Implemented `backend/scanner.py` with Playwright browser lifecycle, axe-core runner, ARIA snapshot capture, and DOM rescan.
  - Implemented `backend/extract.py` generating compact JSON with stable, unique CSS selectors for semantic audit.
  - Implemented `backend/runs.py` for run management, SSE event queues, and disk persistence.
  - Built `demo-site/page1.html` (10 planted issues), `assets/`, `ground_truth.json`, and `index.html`.
  - Checkpoint 1 verified: `page1.html` scanned and baseline score computed.

## Phase 2: AI Semantic Audit & Fix Generation
- **Status**: Completed (100% verified)
- **Completed**:
  - Implemented `backend/llm/` (base protocol, cache, mock provider, gemini, openai_compat, prompts with `<page_data>` boundaries).
  - Implemented `backend/patcher.py` with 6-op whitelist, safety validators, and unified diff generator.
  - Built frontend components: `diffView.js`, `issueCard.js`, `gauge.js`, `timeline.js`, `srView.js`.
  - Checkpoint 2 verified: Review screen renders valid diffs, detects AI-only alt/link issues, flags Issue #10 as `needs_human`.

## Phase 3: Verification Loop & Complete Agent Orchestration
- **Status**: Completed (100% verified)
- **Completed**:
  - Implemented `backend/agent.py` closed-loop apply, re-scan, retry, and revert loop.
  - Implemented API endpoints (`/api/scan`, `/api/runs/{id}`, `/api/runs/{id}/events`, `/api/runs/{id}/apply`, `/api/runs/{id}/download`, `/api/runs/{id}/report.json`).
  - Tested with `tests/test_api.py` and `tests/test_pipeline_mock.py`.
  - Checkpoint 3 verified: Full end-to-end loop improves score by $\ge 30$ points on `page1.html`.
