"""Whitelist HTML patching engine and diff generator.

Enforces strict AST modifications via BeautifulSoup4 + lxml.
Rejects all non-whitelisted operations, attribute modifications, and injections.
"""

import difflib
import logging
import re
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup, Tag

from backend.schemas import Patch, parse_patch

logger = logging.getLogger(__name__)

WHITELISTED_OPS = {
    "set_attr",
    "remove_attr",
    "set_text",
    "wrap_label",
    "add_css",
    "change_tag",
}

FORBIDDEN_TAGS = {"script", "iframe", "object", "embed", "link", "meta"}


@dataclass
class PatchResult:
    html_after: str
    before_snippet: str
    after_snippet: str
    diff: str
    ok: bool
    error: str | None = None


def make_unified_diff(before: str, after: str) -> str:
    """Generate a clean unified diff formatted on HTML tag boundaries."""
    b_lines = [line.strip() for line in re.split(r"(<[^>]+>)", before) if line.strip()]
    a_lines = [line.strip() for line in re.split(r"(<[^>]+>)", after) if line.strip()]
    diff = difflib.unified_diff(
        b_lines,
        a_lines,
        fromfile="before",
        tofile="after",
        lineterm="",
    )
    return "\n".join(diff)


def serialize_soup(soup: BeautifulSoup) -> str:
    """Serialize BeautifulSoup to HTML string."""
    return str(soup)


def ensure_head(soup: BeautifulSoup) -> Tag:
    """Ensure <head> tag exists in soup and return it."""
    head = soup.find("head")
    if head:
        return head
    head = soup.new_tag("head")
    if soup.html:
        soup.html.insert(0, head)
    else:
        soup.insert(0, head)
    return head


def apply_single_patch_ast(soup: BeautifulSoup, patch: Any) -> tuple[str, str]:
    """Apply a single patch to soup AST. Returns (before_snippet, after_snippet) or raises ValueError."""
    # 1. Validate op in whitelist
    op = getattr(patch, "op", None) or (patch.get("op") if isinstance(patch, dict) else None)
    if op not in WHITELISTED_OPS:
        raise ValueError(f"Operation '{op}' is not in the whitelist {list(WHITELISTED_OPS)}.")

    selector = getattr(patch, "selector", None) or (patch.get("selector") if isinstance(patch, dict) else None)
    if not selector or not isinstance(selector, str) or not selector.strip():
        raise ValueError("Missing or invalid 'selector'.")

    # 2. Locate target element
    try:
        matches = soup.select(selector)
    except Exception as e:
        raise ValueError(f"Invalid CSS selector '{selector}': {e}") from e

    if not matches:
        raise ValueError(f"Selector '{selector}' not found in DOM (matched 0 elements).")
    if len(matches) > 1:
        raise ValueError(f"Selector '{selector}' matched {len(matches)} elements (must be unique).")

    target: Tag = matches[0]
    if target.name in FORBIDDEN_TAGS:
        raise ValueError(f"Targeting <{target.name}> tag is forbidden.")

    before_snippet = str(target)[:400]

    # 3. Execute op
    if op == "set_attr":
        name = (getattr(patch, "name", None) or (patch.get("name") if isinstance(patch, dict) else "")).lower().strip()
        val = str(getattr(patch, "value", None) or (patch.get("value") if isinstance(patch, dict) else "")).strip()

        if not name:
            raise ValueError("Missing attribute name.")
        if name.startswith("on") or name in ("srcdoc", "href", "src"):
            raise ValueError(f"Attribute '{name}' is forbidden for security.")
        if name == "tabindex" and val not in ("0", "-1"):
            raise ValueError("tabindex value must be '0' or '-1'.")
        if len(val) > 160 or "<" in val or ">" in val:
            raise ValueError("Attribute value exceeds 160 chars or contains HTML brackets.")

        target[name] = val
        after_snippet = str(target)[:400]

    elif op == "remove_attr":
        name = (getattr(patch, "name", None) or (patch.get("name") if isinstance(patch, dict) else "")).lower().strip()
        if not name:
            raise ValueError("Missing attribute name.")
        if name in target.attrs:
            del target[name]
        after_snippet = str(target)[:400]

    elif op == "set_text":
        val = str(getattr(patch, "value", None) or (patch.get("value") if isinstance(patch, dict) else "")).strip()
        if "<" in val or ">" in val:
            raise ValueError("Text value contains forbidden HTML angle brackets.")
        has_child_elements = any(isinstance(c, Tag) for c in target.children)
        if has_child_elements:
            raise ValueError("Element contains child elements (e.g. SVG). Use set_attr aria-label instead.")
        target.string = val
        after_snippet = str(target)[:400]

    elif op == "wrap_label":
        label_text = str(getattr(patch, "label_text", None) or (patch.get("label_text") if isinstance(patch, dict) else "")).strip()
        if not label_text:
            raise ValueError("wrap_label requires non-empty 'label_text'.")
        if "<" in label_text or ">" in label_text:
            raise ValueError("label_text contains forbidden angle brackets.")

        # Ensure target input has an id
        field_id = target.get("id")
        if not field_id:
            count = 1
            while soup.select_one(f"#a11y-field-{count}"):
                count += 1
            field_id = f"a11y-field-{count}"
            target["id"] = field_id

        # Create and insert label before target
        new_label = soup.new_tag("label", attrs={"for": field_id})
        new_label.string = label_text
        target.insert_before(new_label)
        after_snippet = f"{new_label!s} {target!s}"[:400]

    elif op == "add_css":
        prop = (getattr(patch, "property", None) or (patch.get("property") if isinstance(patch, dict) else "")).lower().strip()
        val = str(getattr(patch, "value", None) or (patch.get("value") if isinstance(patch, dict) else "")).strip()
        if not prop or not val:
            raise ValueError("add_css requires 'property' and 'value'.")

        forbidden = ["url(", "expression", ";", "{", "}", "\\", "@import", "javascript:"]
        if any(f in val.lower() for f in forbidden):
            raise ValueError(f"Invalid or unsafe CSS value '{val}' for property '{prop}'.")

        # Emit <style> rule using the selector with !important into <head>
        head = ensure_head(soup)
        style_tag = head.find("style", id="a11y-pilot-styles")
        if not style_tag:
            style_tag = soup.new_tag("style", id="a11y-pilot-styles")
            head.append(style_tag)

        css_rule = f"{selector} {{ {prop}: {val} !important; }}\n"
        existing_css = style_tag.string or ""
        style_tag.string = existing_css + css_rule

        # Also set inline style for immediate DOM reflection
        existing_style = target.get("style", "")
        style_parts = [s.strip() for s in existing_style.split(";") if s.strip() and not s.strip().startswith(f"{prop}:")]
        style_parts.append(f"{prop}: {val}")
        target["style"] = "; ".join(style_parts) + ";"

        after_snippet = str(target)[:400]

    elif op == "change_tag":
        new_tag = (getattr(patch, "new_tag", None) or (patch.get("new_tag") if isinstance(patch, dict) else "")).lower().strip()
        if not new_tag:
            raise ValueError("change_tag requires 'new_tag'.")
        if new_tag in FORBIDDEN_TAGS:
            raise ValueError(f"change_tag to <{new_tag}> is forbidden.")
        target.name = new_tag
        after_snippet = str(target)[:400]

    else:
        raise ValueError(f"Unsupported operation '{op}'.")

    return before_snippet, after_snippet


def apply_patch(html: str, patch: Patch | dict) -> PatchResult:
    """Apply a single patch and return PatchResult with snippets and unified diff."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as e:
        return PatchResult(html, "", "", "", False, f"Failed to parse HTML: {e}")

    try:
        before_snippet, after_snippet = apply_single_patch_ast(soup, patch)
        html_after = serialize_soup(soup)
        diff_str = make_unified_diff(before_snippet, after_snippet)
        return PatchResult(html_after, before_snippet, after_snippet, diff_str, True)
    except Exception as e:
        return PatchResult(html, "", "", "", False, str(e))


def dry_run(html: str, patch: Patch | dict) -> PatchResult:
    """Execute patch in dry-run mode to compute snippets and diff without side effects."""
    return apply_patch(html, patch)


def apply_patches(html: str, patches: list[Any]) -> tuple[str, list[Any], list[dict[str, Any]]]:
    """Apply a sequence of patches to HTML.
    
    Must NEVER raise. Returns (new_html, applied, failed).
    A missing selector, unknown op, or bad params goes into `failed` with the error text,
    and the loop continues.
    """
    applied = []
    failed = []

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as e:
        for p in patches:
            failed.append({"patch": p, "error": f"Failed to parse HTML: {e}"})
        return html, applied, failed

    for patch in patches:
        try:
            apply_single_patch_ast(soup, patch)
            applied.append(patch)
        except Exception as e:
            failed.append({"patch": patch, "error": str(e)})

    try:
        new_html = serialize_soup(soup)
    except Exception as e:
        logger.error("Error serializing soup in apply_patches: %s", e)
        new_html = html

    return new_html, applied, failed
