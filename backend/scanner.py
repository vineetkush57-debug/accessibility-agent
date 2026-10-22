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
    """Create a clean browser context with standard viewport 1280x900 and desktop Chrome UA."""
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        locale="en-US",
        service_workers="block",
        bypass_csp=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    )
    return context


async def tag_elements_with_a11y_id(page: Page) -> None:
    """Assign data-a11y-id='a0', 'a1', ... to every element, preserving existing tags."""
    await page.evaluate(
        """() => {
            let maxId = 0;
            const all = document.querySelectorAll('*');
            for (const el of all) {
                const existing = el.getAttribute('data-a11y-id');
                if (existing && existing.startsWith('a')) {
                    const num = parseInt(existing.slice(1), 10);
                    if (!isNaN(num) && num >= maxId) {
                        maxId = num + 1;
                    }
                }
            }
            let count = maxId;
            for (const el of all) {
                if (!el.hasAttribute('data-a11y-id')) {
                    el.setAttribute('data-a11y-id', 'a' + count);
                    count++;
                }
            }
        }"""
    )


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
                wait_until="domcontentloaded",
                timeout=45000,
            )
            await page.wait_for_timeout(2000)

            # Anti-bot interstitial check (e.g. Cloudflare "Just a moment...")
            page_title = await page.title()
            if "just a moment" in page_title.lower() or "attention required" in page_title.lower():
                logger.info("Anti-bot interstitial detected on %s, fetching via HTTP fallback...", url)
                import urllib.request
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw_html = resp.read().decode("utf-8", errors="replace")
                base_tag = f'<base href="{url}">'
                if "<head>" in raw_html:
                    raw_html = raw_html.replace("<head>", f"<head>{base_tag}", 1)
                else:
                    raw_html = f"{base_tag}{raw_html}"
                await page.set_content(raw_html, wait_until="domcontentloaded")
                await page.wait_for_timeout(1000)
        except Exception as e:
            await page.close()
            raise RuntimeError(f"Page load failed: {e!s}") from e
    elif html:
        content_to_load = html
        if base_url:
            base_tag = f'<base href="{base_url}">'
            if "<head>" in content_to_load:
                content_to_load = content_to_load.replace("<head>", f"<head>{base_tag}", 1)
            else:
                content_to_load = f"{base_tag}{content_to_load}"
        try:
            await page.set_content(content_to_load, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(1000)
        except Exception as e:
            await page.close()
            raise RuntimeError(f"Page load failed: {e!s}") from e
    else:
        await page.close()
        raise ValueError("Either 'url' or 'html' must be provided.")

    # Tag elements with data-a11y-id
    await tag_elements_with_a11y_id(page)
    return page


async def run_axe(page: Page, return_all_keys: bool = False) -> Any:
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
                    if (err) return reject(err);
                    const violations = results.violations || [];
                    const processed = [];
                    const allKeys = [];
                    for (const v of violations) {
                        const ruleId = v.id || 'unknown';
                        const nodes = v.nodes || [];
                        const ruleNodes = [];
                        for (const n of nodes) {
                            if (Array.isArray(n.target) && n.target.length === 1 && typeof n.target[0] === 'string') {
                                try {
                                    const el = document.querySelector(n.target[0]);
                                    const a11yId = el ? el.getAttribute('data-a11y-id') : null;
                                    if (a11yId) {
                                        const sel = `[data-a11y-id="${a11yId}"]`;
                                        allKeys.push([ruleId, sel]);
                                        if (ruleNodes.length < 5) {
                                            ruleNodes.push({
                                                selector: sel,
                                                html: (n.html || '').slice(0, 300),
                                                failureSummary: n.failureSummary || v.help || '',
                                            });
                                        }
                                    }
                                } catch (e) {}
                            }
                        }
                        if (ruleNodes.length > 0) {
                            processed.push({
                                id: ruleId,
                                impact: v.impact || 'minor',
                                tags: v.tags || [],
                                helpUrl: v.helpUrl || null,
                                help: v.help || '',
                                nodes: ruleNodes,
                            });
                        }
                    }
                    resolve({ violations: processed, allKeys: allKeys });
                });
            });
        }""",
        axe_options,
    )

    violations = raw_results.get("violations", [])
    all_keys_raw = raw_results.get("allKeys", [])
    all_keys = {(k[0], k[1]) for k in all_keys_raw}

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
            selector = node.get("selector")
            if not selector:
                continue
            key = (rule_id, selector)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            html_snippet = node.get("html", "")
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
                    fixable=True,
                )
            )
            issue_seq += 1

    if return_all_keys:
        return issues, all_keys
    return issues


async def capture_aria_snapshot(page: Page) -> str:
    """Capture accessibility tree snapshot (Playwright locator aria_snapshot or fallback). Wrapped in try/except returning '' on failure."""
    try:
        body = page.locator("body")
        snapshot = await body.aria_snapshot()
        if snapshot:
            return snapshot[:6000]
    except Exception:
        pass

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
    except Exception:
        pass

    return ""


async def scan_page(
    url: str | None = None,
    html: str | None = None,
    base_url: str | None = None,
) -> tuple[list[Issue], str, str]:
    """Scan a URL or HTML content, returning (issues, aria_snapshot, baseline_html)."""
    browser = await get_browser()
    context = await create_scan_context(browser)
    try:
        page = await load_page(context, url=url, html=html, base_url=base_url)
        issues = await run_axe(page)
        aria = await capture_aria_snapshot(page)
        baseline_html = await page.content()
        await page.close()
        return issues, aria, baseline_html
    finally:
        await context.close()


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
