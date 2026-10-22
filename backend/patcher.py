"""Whitelist HTML patching engine and diff generator.

Enforces strict AST modifications via BeautifulSoup4 + lxml.
Rejects all non-whitelisted operations, attribute modifications, and injections.
"""

import difflib
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from backend.schemas import (
    Patch,
)

VALID_ARIA_ROLES = {
    "alert",
    "alertdialog",
    "application",
    "article",
    "banner",
    "button",
    "cell",
    "checkbox",
    "columnheader",
    "combobox",
    "complementary",
    "contentinfo",
    "definition",
    "dialog",
    "directory",
    "document",
    "feed",
    "figure",
    "form",
    "grid",
    "gridcell",
    "group",
    "heading",
    "img",
    "link",
    "list",
    "listbox",
    "listitem",
    "log",
    "main",
    "marquee",
    "math",
    "menu",
    "menubar",
    "menuitem",
    "menuitemcheckbox",
    "menuitemradio",
    "navigation",
    "none",
    "note",
    "option",
    "presentation",
    "progressbar",
    "radio",
    "radiogroup",
    "region",
    "row",
    "rowgroup",
    "rowheader",
    "scrollbar",
    "search",
    "searchbox",
    "separator",
    "slider",
    "spinbutton",
    "status",
    "switch",
    "tab",
    "table",
    "tablist",
    "tabpanel",
    "term",
    "textbox",
    "timer",
    "toolbar",
    "tooltip",
    "tree",
    "treegrid",
    "treeitem",
}

ALLOWED_SET_ATTRS = {
    "alt",
    "aria-label",
    "aria-labelledby",
    "aria-describedby",
    "aria-hidden",
    "lang",
    "role",
    "title",
    "for",
    "id",
    "tabindex",
}

ALLOWED_REMOVE_ATTRS = {
    "aria-hidden",
    "tabindex",
    "role",
    "title",
    "aria-label",
    "aria-labelledby",
    "aria-describedby",
}

ALLOWED_SET_TEXT_TAGS = {
    "a",
    "button",
    "label",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "span",
    "summary",
    "legend",
}

ALLOWED_CSS_PROPERTIES = {
    "color",
    "background-color",
    "font-size",
    "outline",
    "outline-offset",
    "text-decoration",
    "min-width",
    "min-height",
}

FORBIDDEN_TAGS = {"script", "style", "iframe", "object", "embed", "link", "meta"}


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
    # Split on tag boundaries for readability
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
    """Serialize BeautifulSoup to HTML string preserving doctype."""
    return str(soup)


def validate_css_value(prop: str, val: str) -> bool:
    """Validate CSS property value against strict safety regex."""
    if not val or not isinstance(val, str):
        return False
    # Check for forbidden injection keywords
    forbidden = ["url(", "expression", ";", "{", "}", "\\", "@import", "javascript:"]
    val_lower = val.lower()
    if any(f in val_lower for f in forbidden):
        return False

    # Regex patterns for colors, dimensions, etc.
    if prop in ("color", "background-color"):
        # Hex color: #fff, #123456, or rgb/rgba or named colors
        return bool(
            re.match(
                r"^#(?:[0-9a-fA-F]{3}){1,2}$|^rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)$|^[a-zA-Z]+$",
                val.strip(),
            )
        )
    elif prop in ("font-size", "min-width", "min-height", "outline-offset"):
        return bool(re.match(r"^\d+(?:\.\d+)?(?:px|rem|em|%)?$", val.strip()))
    elif prop in ("outline", "text-decoration"):
        return bool(re.match(r"^[0-9a-zA-Z\s#\.]+$", val.strip()) and len(val.strip()) < 50)

    return False


def apply_patch(html: str, patch: Patch) -> PatchResult:
    """Apply a whitelisted patch to HTML using BeautifulSoup AST manipulations."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as e:
        return PatchResult(html, "", "", "", False, f"Failed to parse HTML: {e}")

    # 1. Resolve selector
    try:
        matches = soup.select(patch.selector)
    except Exception as e:
        return PatchResult(html, "", "", "", False, f"Invalid CSS selector '{patch.selector}': {e}")

    if len(matches) == 0:
        return PatchResult(
            html, "", "", "", False, f"Selector '{patch.selector}' matched 0 elements."
        )
    if len(matches) > 1:
        return PatchResult(
            html,
            "",
            "",
            "",
            False,
            f"Selector '{patch.selector}' matched {len(matches)} elements (must be unique).",
        )

    target: Tag = matches[0]

    # 2. Check forbidden contexts
    if target.name in FORBIDDEN_TAGS:
        return PatchResult(html, "", "", "", False, f"Targeting tag <{target.name}> is forbidden.")
    for ancestor in target.parents:
        if ancestor.name in FORBIDDEN_TAGS:
            return PatchResult(
                html,
                "",
                "",
                "",
                False,
                f"Target element resides inside forbidden <{ancestor.name}> tag.",
            )

    before_snippet = str(target)[:400]

    # 3. Process operation
    if patch.op == "set_attr":
        name = patch.name.lower().strip()
        val = patch.value.strip()

        # Check forbidden attribute names
        if name.startswith("on") or name in ("src", "href", "srcdoc", "style"):
            return PatchResult(
                html,
                before_snippet,
                "",
                "",
                False,
                f"Setting attribute '{name}' is forbidden.",
            )
        if name not in ALLOWED_SET_ATTRS:
            return PatchResult(
                html,
                before_snippet,
                "",
                "",
                False,
                f"Attribute '{name}' is not in whitelist.",
            )

        # Validate specific attribute values
        if name == "tabindex":
            if val not in ("0", "-1"):
                return PatchResult(
                    html,
                    before_snippet,
                    "",
                    "",
                    False,
                    "tabindex value must be '0' or '-1'.",
                )
        elif name == "role":
            if val.lower() not in VALID_ARIA_ROLES:
                return PatchResult(
                    html,
                    before_snippet,
                    "",
                    "",
                    False,
                    f"Role '{val}' is not a valid ARIA role.",
                )
        elif name == "aria-hidden":
            if val.lower() not in ("true", "false"):
                return PatchResult(
                    html,
                    before_snippet,
                    "",
                    "",
                    False,
                    "aria-hidden value must be 'true' or 'false'.",
                )
        elif name == "lang":
            if not re.match(r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})*$", val):
                return PatchResult(
                    html,
                    before_snippet,
                    "",
                    "",
                    False,
                    f"Invalid BCP 47 language tag: '{val}'.",
                )
        else:
            if len(val) > 160 or "<" in val or ">" in val:
                return PatchResult(
                    html,
                    before_snippet,
                    "",
                    "",
                    False,
                    "Attribute value exceeds 160 chars or contains HTML brackets.",
                )

        target[name] = val

    elif patch.op == "remove_attr":
        name = patch.name.lower().strip()
        if name not in ALLOWED_REMOVE_ATTRS:
            return PatchResult(
                html,
                before_snippet,
                "",
                "",
                False,
                f"Removing attribute '{name}' is not permitted.",
            )
        if name in target.attrs:
            del target[name]

    elif patch.op == "set_text":
        if target.name not in ALLOWED_SET_TEXT_TAGS:
            return PatchResult(
                html,
                before_snippet,
                "",
                "",
                False,
                f"set_text cannot be applied to <{target.name}>.",
            )
        val = patch.value.strip()
        if not val or len(val) > 120 or "<" in val or ">" in val:
            return PatchResult(
                html,
                before_snippet,
                "",
                "",
                False,
                "Text value must be non-empty, plain text, max 120 chars.",
            )

        # Check if target contains element children like <svg>
        has_child_elements = any(isinstance(c, Tag) for c in target.children)
        if has_child_elements:
            return PatchResult(
                html,
                before_snippet,
                "",
                "",
                False,
                "Element contains child elements (e.g. SVG). Use set_attr aria-label instead.",
            )

        target.string = val

    elif patch.op == "wrap_label":
        if target.name not in ("input", "select", "textarea"):
            return PatchResult(
                html,
                before_snippet,
                "",
                "",
                False,
                f"wrap_label target must be a form control, not <{target.name}>.",
            )
        if target.name == "input":
            in_type = target.get("type", "text").lower()
            if in_type in ("hidden", "submit", "button", "reset", "image"):
                return PatchResult(
                    html,
                    before_snippet,
                    "",
                    "",
                    False,
                    f"Cannot wrap label around input type '{in_type}'.",
                )

        label_txt = patch.label_text.strip()
        if not label_txt or len(label_txt) > 80 or "<" in label_txt or ">" in label_txt:
            return PatchResult(
                html,
                before_snippet,
                "",
                "",
                False,
                "label_text must be plain text and <= 80 characters.",
            )

        # Ensure target has an ID
        field_id = target.get("id")
        if not field_id:
            # Generate unique ID
            count = 1
            while soup.select_one(f"#a11y-field-{count}"):
                count += 1
            field_id = f"a11y-field-{count}"
            target["id"] = field_id

        # Create and insert label before target
        new_label = soup.new_tag("label", attrs={"for": field_id})
        new_label.string = label_txt
        target.insert_before(new_label)

        # For wrap_label, snippet includes the inserted label + target
        after_snippet = f"{new_label!s}{target!s}"[:400]
        html_after = serialize_soup(soup)
        diff_str = make_unified_diff(before_snippet, after_snippet)
        return PatchResult(html_after, before_snippet, after_snippet, diff_str, True)

    elif patch.op == "add_css":
        prop = patch.property.lower().strip()
        val = patch.value.strip()
        if prop not in ALLOWED_CSS_PROPERTIES:
            return PatchResult(
                html,
                before_snippet,
                "",
                "",
                False,
                f"CSS property '{prop}' is not in whitelist.",
            )
        if not validate_css_value(prop, val):
            return PatchResult(
                html,
                before_snippet,
                "",
                "",
                False,
                f"Invalid or unsafe CSS value '{val}' for property '{prop}'.",
            )

        # Parse existing style attribute
        style_dict = {}
        existing_style = target.get("style", "")
        if existing_style:
            for decl in existing_style.split(";"):
                decl = decl.strip()
                if ":" in decl:
                    p, v = decl.split(":", 1)
                    style_dict[p.strip().lower()] = v.strip()

        style_dict[prop] = val
        target["style"] = "; ".join(f"{p}: {v}" for p, v in style_dict.items()) + ";"

    elif patch.op == "change_tag":
        if target.name not in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return PatchResult(
                html,
                before_snippet,
                "",
                "",
                False,
                f"change_tag only allowed on h1..h6, not <{target.name}>.",
            )
        new_tag = patch.new_tag.lower().strip()
        if new_tag not in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return PatchResult(
                html,
                before_snippet,
                "",
                "",
                False,
                f"new_tag must be one of h1..h6, got '{new_tag}'.",
            )

        target.name = new_tag

    else:
        return PatchResult(
            html,
            before_snippet,
            "",
            "",
            False,
            f"Unknown patch operation '{getattr(patch, 'op', None)}'.",
        )

    after_snippet = str(target)[:400]
    html_after = serialize_soup(soup)
    diff_str = make_unified_diff(before_snippet, after_snippet)
    return PatchResult(html_after, before_snippet, after_snippet, diff_str, True)


def dry_run(html: str, patch: Patch) -> PatchResult:
    """Execute patch in dry-run mode to compute snippets and diff without side effects."""
    return apply_patch(html, patch)
