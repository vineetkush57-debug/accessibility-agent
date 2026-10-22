# A11y Pilot 🧭
> **Agentic Web Accessibility Auditor and Auto-Fixer**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MPL-2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](https://www.mozilla.org/en-US/MPL/2.0/)
[![Tests Passing](https://img.shields.io/badge/tests-41%20passed-success.svg)]()
[![WCAG Score](https://img.shields.io/badge/Self--Audit-100%2F100-teal.svg)]()

> *"Finding accessibility issues is easy; understanding and fixing them is hard. A11y Pilot scans, explains, fixes, and verifies."*

---

## 1. Overview & Key Differentiators

A11y Pilot takes a web page (URL or pasted HTML), audits it for accessibility defects against WCAG guidelines, explains each problem in plain language, proposes a **safe, whitelisted code patch** for each issue, empowers a **human to approve or reject** each fix, and then executes a **closed-loop verification loop**:
$$\text{Scan} \longrightarrow \text{Audit} \longrightarrow \text{Fix} \longrightarrow \text{Review} \longrightarrow \text{Apply} \longrightarrow \text{Re-scan} \longrightarrow \text{Retry / Revert} \longrightarrow \text{Report}$$

### Why It's Truly Agentic
- **Closed-Loop Verification**: Re-scans candidate DOM mutations in headless Chromium. If an issue is not resolved, it automatically retries with failure feedback up to 2 times.
- **Regression Rollback**: Reverts any patch that creates new violations or drops the overall accessibility score.
- **Multi-Engine Detection**: Combines **axe-core** rules with **LLM semantic auditing** to discover issues rules engines miss (e.g., generic alt text like `image1.jpg`, unhelpful link text like `"Click here"`, and broken heading hierarchies).
- **Safe by Design**: The LLM can only output operations from a strict 6-operation whitelist (`set_attr`, `remove_attr`, `set_text`, `wrap_label`, `add_css`, `change_tag`). Raw HTML string injections, inline event handlers, and script executions are strictly forbidden.
- **Screen Reader Before/After Comparison**: Generates side-by-side ARIA tree snapshots to demonstrate what assistive technologies actually announce.

---

## 2. Quick Start in 3 Commands

A11y Pilot works completely **offline with zero API keys** required out of the box using deterministic mock fixtures.

### Windows / macOS / Linux

```bash
# 1. Setup environment (installs dependencies, Chromium, and vendors axe-core)
python scripts/dev.py setup

# 2. Start demo application with mock LLM and open browser
python scripts/dev.py demo

# 3. Run complete evaluation benchmark suite
python scripts/dev.py eval
```

On Unix/macOS systems with `make`:
```bash
make setup
make demo
make eval
```

The application will be accessible at [http://127.0.0.1:8000](http://127.0.0.1:8000) and the demo test suite at [http://127.0.0.1:8000/demo/](http://127.0.0.1:8000/demo/).

---

## 3. Configuration & Environment Variables

Copy `.env.example` to `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `mock` | Active provider: `mock`, `gemini`, or `openai_compat` |
| `GEMINI_API_KEY` | `""` | Google Gemini API Key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `OPENAI_COMPAT_BASE_URL` | `""` | Base URL for OpenAI-compatible endpoints |
| `OPENAI_COMPAT_API_KEY` | `""` | API key for OpenAI-compatible provider |
| `OPENAI_COMPAT_MODEL` | `gpt-4o-mini` | Model name for OpenAI-compatible endpoint |
| `LLM_CACHE_DIR` | `data/cache/llm` | Disk cache directory for prompt responses |
| `ALLOWED_LOCAL_HOSTS` | `127.0.0.1:8000,localhost:8000,127.0.0.1:8001,localhost:8001` | SSRF whitelist for local demo pages |
| `MOCK_SCENARIO` | `normal` | Mock scenario behavior: `normal`, `retry`, or `revert` |

### Using a Live LLM Provider
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

### Warming the LLM Cache for Offline Demos
When using a live LLM provider, all prompt responses are automatically cached to disk under `data/cache/llm` using a SHA-256 hash. Run the demo once online before an event to warm the cache; subsequent runs can execute offline seamlessly.

---

## 4. Testing & Verification

```bash
# Run unit tests (fast, no browser dependencies)
python scripts/dev.py test

# Run all tests (including Playwright headless browser tests)
python scripts/dev.py test-all

# Run code style & formatting checks
python scripts/dev.py lint

# Run UI self-audit dogfooding test
pytest tests/test_self_audit.py
```

---

## 5. Security & SSRF Protection

- **SSRF Defense (`backend/security.py`)**: Hostnames are resolved to IP addresses and checked against private/RFC1918, loopback, and link-local ranges before fetching. Only explicitly allowlisted hosts in `ALLOWED_LOCAL_HOSTS` can be fetched locally.
- **Prompt Injection Defense**: All untrusted page contents are enclosed inside `<page_data>...</page_data>` with strict instructions to treat content solely as data.
- **Strict AST Whitelist (`backend/patcher.py`)**: Modifies elements only through parsed AST structures using BeautifulSoup4 + lxml.

---

## 6. Licenses & Vendored Files

- **A11y Pilot**: Licensed under the MIT License.
- **axe-core**: Vendored at `backend/vendor/axe.min.js`. Licensed under the [Mozilla Public License 2.0 (MPL-2.0)](https://github.com/dequelabs/axe-core/blob/develop/LICENSE).
