import re
from typing import Any

from bs4 import BeautifulSoup, Tag


def format_safe_id_selector(elem_id: str) -> str:
    """Safely format an ID as a CSS selector.

    Uses #id if it is a pure CSS identifier, otherwise uses [id="..."] attribute selector.
    """
    clean_id = elem_id.strip()
    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_-]*$", clean_id):
        return f"#{clean_id}"
    escaped = clean_id.replace("\\", "\\\\").replace('"', '\\"')
    return f'[id="{escaped}"]'


def safe_select(soup: BeautifulSoup, selector: str) -> list[Tag]:
    """Execute soup.select safely handling any malformed CSS selector exceptions."""
    if not selector or not selector.strip():
        return []
    try:
        return soup.select(selector)
    except Exception:
        return []


def generate_unique_selector(tag: Tag, soup: BeautifulSoup) -> str:
    """Generate a unique, stable CSS selector for a BeautifulSoup Tag."""
    if not isinstance(tag, Tag):
        return ""

    # Prefer data-a11y-id if present
    a11y_id = tag.get("data-a11y-id")
    if a11y_id and isinstance(a11y_id, str):
        return f'[data-a11y-id="{a11y_id}"]'

    # 1. Prefer unique ID if present
    element_id = tag.get("id")
    if element_id and isinstance(element_id, str) and element_id.strip():
        selector = format_safe_id_selector(element_id)
        if len(safe_select(soup, selector)) == 1:
            return selector

    # 2. Build hierarchical path
    segments = []
    curr: Tag | None = tag

    while curr and curr.name not in ("[document]", "html", "body"):
        # If current element has unique ID, anchor here
        c_id = curr.get("id")
        if c_id and isinstance(c_id, str) and c_id.strip():
            c_sel = format_safe_id_selector(c_id)
            if len(safe_select(soup, c_sel)) == 1:
                segments.insert(0, c_sel)
                break

        tag_name = curr.name
        classes = curr.get("class", [])
        class_str = ""
        if isinstance(classes, list) and classes:
            valid_classes = [
                c.strip()
                for c in classes
                if isinstance(c, str) and re.match(r"^[a-zA-Z_][a-zA-Z0-9_-]*$", c.strip())
            ]
            if valid_classes:
                class_str = "." + ".".join(valid_classes[:2])

        # Calculate nth-of-type
        parent = curr.parent
        if parent and isinstance(parent, Tag):
            siblings = [s for s in parent.children if isinstance(s, Tag) and s.name == tag_name]
            if len(siblings) > 1:
                idx = siblings.index(curr) + 1
                segment = f"{tag_name}{class_str}:nth-of-type({idx})"
            else:
                segment = f"{tag_name}{class_str}"
        else:
            segment = f"{tag_name}{class_str}"

        segments.insert(0, segment)
        curr = curr.parent

    selector = " > ".join(segments) if segments else tag.name

    # Validate selector resolves to exactly one element; fall back to nth-of-type search
    matches = safe_select(soup, selector)
    if len(matches) == 1 and matches[0] is tag:
        return selector

    # Fallback to unique index among all tags of this name
    all_same_tags = soup.find_all(tag.name)
    if tag in all_same_tags:
        idx = all_same_tags.index(tag) + 1
        fallback_selector = f"{tag.name}:nth-of-type({idx})"
        if len(safe_select(soup, fallback_selector)) == 1:
            return fallback_selector

    return selector


def truncate_str(val: str | None, max_len: int = 160) -> str:
    """Trim whitespace and truncate string to max_len chars."""
    if not val:
        return ""
    clean = " ".join(val.split()).strip()
    return clean[:max_len]


def get_nearby_text(tag: Tag, max_len: int = 120) -> str:
    """Extract nearby contextual text around an element."""
    parent = tag.parent
    if not parent or not isinstance(parent, Tag):
        return ""
    text = parent.get_text(" ", strip=True)
    return truncate_str(text, max_len)


def extract_page_semantics(html: str) -> dict[str, Any]:
    """Build compact JSON summary of the page for LLM semantic audit.

    Caps each category at 40 items and strings at 160 chars.
    """
    soup = BeautifulSoup(html, "lxml")

    # Page metadata
    title_tag = soup.find("title")
    title = truncate_str(title_tag.get_text() if title_tag else "", 120)

    html_tag = soup.find("html")
    lang = None
    if html_tag and isinstance(html_tag, Tag):
        lang = html_tag.get("lang")

    # 1. Images (cap 40)
    images: list[dict[str, Any]] = []
    for img in soup.find_all("img"):
        if len(images) >= 40:
            break
        sel = generate_unique_selector(img, soup)
        src = img.get("src", "")
        src_file = src.split("/")[-1].split("?")[0] if src else ""
        in_link = bool(img.find_parent("a"))
        images.append(
            {
                "selector": sel,
                "src_file": truncate_str(src_file, 60),
                "alt": img.get("alt"),
                "nearby_text": get_nearby_text(img, 120),
                "in_link": in_link,
            }
        )

    # 2. Links (cap 40)
    links: list[dict[str, Any]] = []
    for a in soup.find_all("a"):
        if len(links) >= 40:
            break
        sel = generate_unique_selector(a, soup)
        link_text = truncate_str(a.get_text(), 80)
        href = a.get("href", "")
        context = get_nearby_text(a, 160)
        links.append(
            {
                "selector": sel,
                "text": link_text,
                "href": truncate_str(href, 100),
                "context": context,
            }
        )

    # 3. Headings (cap 40)
    headings: list[dict[str, Any]] = []
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if len(headings) >= 40:
            break
        sel = generate_unique_selector(h, soup)
        level = int(h.name[1])
        headings.append(
            {
                "selector": sel,
                "level": level,
                "text": truncate_str(h.get_text(), 120),
            }
        )

    # 4. Form fields (cap 40)
    fields: list[dict[str, Any]] = []
    for field in soup.find_all(["input", "select", "textarea"]):
        if len(fields) >= 40:
            break
        f_type = field.get("type", "text").lower() if field.name == "input" else field.name
        if f_type in ("hidden", "submit", "image", "button", "reset"):
            continue

        sel = generate_unique_selector(field, soup)
        f_id = field.get("id")
        label_text = None
        if f_id:
            lbl = soup.find("label", attrs={"for": f_id})
            if lbl:
                label_text = truncate_str(lbl.get_text(), 80)
        if not label_text:
            parent_lbl = field.find_parent("label")
            if parent_lbl:
                label_text = truncate_str(parent_lbl.get_text(), 80)

        fields.append(
            {
                "selector": sel,
                "type": f_type,
                "label_text": label_text,
                "placeholder": truncate_str(field.get("placeholder"), 60),
                "aria_label": field.get("aria-label"),
            }
        )

    # 5. Buttons (cap 40)
    buttons: list[dict[str, Any]] = []
    seen_button_tags = set()
    button_candidates = (
        soup.find_all(["button"])
        + [el for el in soup.find_all(attrs={"onclick": True}) if el.name != "button"]
        + [el for el in soup.find_all(attrs={"role": "button"}) if el.name != "button"]
    )

    for btn in button_candidates:
        if len(buttons) >= 40:
            break
        if btn in seen_button_tags:
            continue
        seen_button_tags.add(btn)
        sel = generate_unique_selector(btn, soup)
        has_svg = bool(btn.find("svg"))
        buttons.append(
            {
                "selector": sel,
                "tag": btn.name,
                "text": truncate_str(btn.get_text(), 80),
                "aria_label": btn.get("aria-label"),
                "has_svg": has_svg,
            }
        )

    return {
        "title": title,
        "lang": lang,
        "images": images,
        "links": links,
        "headings": headings,
        "fields": fields,
        "buttons": buttons,
    }
