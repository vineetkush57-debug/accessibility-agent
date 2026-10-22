# Architectural & Design Decisions

## Decision 1: Contract-First Architecture
- **Context**: The master prompt mandates establishing `backend/schemas.py` before any other module is developed.
- **Decision**: All API responses, internal agent events, patch mutations, and review payloads are strictly typed via Pydantic v2 in `backend/schemas.py`.
- **Consequences**: Ensures clean separation of concerns, simplifies LLM structured output parsing, and prevents drift across frontend/backend.

## Decision 2: SSRF and Local Demo Allowlist
- **Context**: The tool accepts arbitrary URLs but must not be used as an internal intranet scanner or SSRF vector. At the same time, local demo sites (ports 8000 and 8001) must work offline.
- **Decision**: In `backend/security.py`, hostnames are resolved to IP addresses and checked against private/loopback/link-local ranges. An explicit `ALLOWED_LOCAL_HOSTS` configuration allows loopback access specifically for the local demo suite.

## Decision 3: Vendored axe-core
- **Context**: Relying on external CDN fetching for axe-core during audits causes network latency and breaks offline operation.
- **Decision**: `backend/vendor/axe.min.js` (axe-core 4.10.2) is stored locally and injected via Playwright's `page.add_script_tag(path=...)`.
