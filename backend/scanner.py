"""Scanner module: Playwright headless browser, axe-core runner, and ARIA snapshots."""

import asyncio
import logging
import re
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from backend.config import settings
from backend.schemas import Issue, ScoreBreakdown
from backend.scoring import compute_score

logger = logging.getLogger(__name__)

# Global shared browser instance and loop tracker
_playwright = None
_browser: Browser | None = None
_browser_loop = None


async def get_browser() -> Browser:
    """Get or initialize the shared Playwright Chromium browser on the current event loop."""
    global _playwright, _browser, _browser_loop
    curr_loop = asyncio.get_running_loop()

    needs_restart = _browser is None or _playwright is None or _browser_loop != curr_loop

    if not needs_restart:
        try:
            if not _browser.is_connected():
                needs_restart = True
        except Exception:
            needs_restart = True

    if needs_restart:
        if _browser:
            try:
                await _browser.close()
            except Exception:
                pass
            _browser = None
        if _playwright:
            try:
                await _playwright.stop()
            except Exception:
                pass
            _playwright = None

        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        _browser_loop = curr_loop
        logger.info("Playwright Chromium browser launched on active event loop.")

    return _browser


async def close_browser():
    """Shut down the shared Playwright Chromium browser."""
    global _playwright, _browser, _browser_loop
    if _browser:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None
    if _playwright:
        try:
            await _playwright.stop()
        except Exception:
            pass
        _playwright = None
    _browser_loop = None
    logger.info("Playwright Chromium browser closed.")


def get_axe_script_path() -> Path:
    """Return path to vendored axe.min.js."""
    p = settings.project_root / "backend" / "vendor" / "axe.min.js"
    if not p.exists() or p.stat().st_size == 0:
        raise FileNotFoundError(f"axe.min.js not found at {p}. Run scripts/dev.py setup.")
    return p


def parse_wcag_tags(tags: list[str]) -> list[str]:
    """Extract standard WCAG criteria numbers from axe tags (e.g., 'wcag111' -> '1.1.1')."""
    criteria = []
    for tag in tags:
        m = re.match(r"^wcag(\d)(\d)(\d+)$", tag)
        if m:
            criteria.append(f"{m.group(1)}.{m.group(2)}.{m.group(3)}")
        elif tag in ("wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"):
            continue
    return criteria


async def create_scan_context(browser: Browser) -> BrowserContext:
    """Create a clean browser context with standard viewport and locale."""
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="en-US",
        service_workers="block",
    )
    return context


async def load_page(
    context: BrowserContext,
    url: str | None = None,
    html: str | None = None,
    base_url: str | None = None,
) -> Page:
    """Load a URL or pasted HTML into a new browser page."""
    page = await context.new_page()

    if url:
        try:
            await page.goto(
                url,
                wait_until="networkidle",
                timeout=settings.PAGE_LOAD_TIMEOUT_MS,
            )
        except Exception as e:
            logger.warning("networkidle navigation timed out, trying domcontentloaded: %s", e)
            try:
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=settings.PAGE_LOAD_TIMEOUT_MS,
                )
                await asyncio.sleep(1.5)
            except Exception as e2:
                await page.close()
                raise RuntimeError(f"Failed to load URL '{url}': {e2!s}") from e2
    elif html:
        content_to_load = html
        if base_url:
            base_tag = f'<base href="{base_url}">'
            if "<head>" in content_to_load:
                content_to_load = content_to_load.replace("<head>", f"<head>{base_tag}", 1)
            else:
                content_to_load = f"{base_tag}{content_to_load}"
        await page.set_content(content_to_load, wait_until="domcontentloaded")
        await asyncio.sleep(0.5)
    else:
        await page.close()
        raise ValueError("Either 'url' or 'html' must be provided.")

    return page


async def run_axe(page: Page) -> list[Issue]:
    """Inject axe.min.js and run rules audit, producing normalized Issue objects."""
    axe_path = get_axe_script_path()
    await page.add_script_tag(path=str(axe_path))

    axe_options = {
        "resultTypes": ["violations"],
        "runOnly": {
            "type": "tag",
            "values": [
                "wcag2a",
                "wcag2aa",
                "wcag21a",
                "wcag21aa",
                "wcag22aa",
                "best-practice",
            ],
        },
    }

    raw_results = await page.evaluate(
        """(options) => {
            return new Promise((resolve, reject) => {
                axe.run(document, options, (err, results) => {
                    if (err) reject(err);
                    else resolve(results);
                });
            });
        }""",
        axe_options,
    )

    violations = raw_results.get("violations", [])
    issues: list[Issue] = []
    seen_keys = set()
    issue_seq = 1

    for violation in violations:
        rule_id = violation.get("id", "unknown-rule")
        impact = violation.get("impact") or "minor"
        if impact not in ("critical", "serious", "moderate", "minor"):
            impact = "minor"
        wcag_list = parse_wcag_tags(violation.get("tags", []))
        help_url = violation.get("helpUrl")
        general_help = violation.get("help", "")

        for node in violation.get("nodes", []):
            targets = node.get("target", [])
            if isinstance(targets, list) and len(targets) == 1 and isinstance(targets[0], str):
                selector = targets[0]
                fixable = True
            else:
                selector = " > ".join(str(t) for t in targets)
                fixable = False  # Complex selector / iframe / shadow DOM

            key = (rule_id, selector)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            html_snippet = (node.get("html") or "")[:500]
            failure_summary = node.get("failureSummary") or general_help
            msg_clean = " ".join(failure_summary.split())[:300]

            issues.append(
                Issue(
                    id=f"iss_{issue_seq:03d}",
                    source="axe",
                    rule_id=rule_id,
                    impact=impact,  # type: ignore
                    wcag=wcag_list,
                    selector=selector,
                    html=html_snippet,
                    message=msg_clean,
                    help_url=help_url,
                    fixable=fixable,
                )
            )
            issue_seq += 1

    return issues


async def capture_aria_snapshot(page: Page) -> str:
    """Capture accessibility tree snapshot (Playwright locator aria_snapshot or fallback)."""
    try:
        body = page.locator("body")
        snapshot = await body.aria_snapshot()
        if snapshot:
            return snapshot[:6000]
    except Exception as e:
        logger.debug("body.aria_snapshot() failed, trying fallback: %s", e)

    # Fallback to page.accessibility.snapshot() or DOM text
    try:
        snapshot_dict = await page.accessibility.snapshot()
        if snapshot_dict:
            lines = []

            def _walk(node, indent=0):
                role = node.get("role", "")
                name = node.get("name", "")
                val = f"{'  ' * indent}- {role}: {name}" if name else f"{'  ' * indent}- {role}"
                lines.append(val)
                for child in node.get("children", []):
                    _walk(child, indent + 1)

            _walk(snapshot_dict)
            return "\n".join(lines)[:6000]
    except Exception as e2:
        logger.warning("accessibility.snapshot() fallback also failed: %s", e2)

    return "ARIA snapshot unavailable"


async def rescan_html(
    html: str,
    base_url: str | None = None,
) -> tuple[list[Issue], ScoreBreakdown, str]:
    """Rescan an HTML string in a fresh isolated page and compute issues, score, and ARIA tree."""
    browser = await get_browser()
    context = await create_scan_context(browser)
    try:
        page = await load_page(context, html=html, base_url=base_url)
        issues = await run_axe(page)
        aria = await capture_aria_snapshot(page)
        score = compute_score(issues)
        await page.close()
        return issues, score, aria
    finally:
        await context.close()
