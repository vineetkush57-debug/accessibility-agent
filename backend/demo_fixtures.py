"""Cached demo run fixtures for local benchmark demo pages.

This module provides an isolated, clearly-labelled "cached demo run" path
for offline development and benchmarking against the 5 localhost demo pages.
It is separated from the real auditing pipeline.
"""

from typing import Any


def get_cached_demo_semantic_audit(user_prompt: str) -> list[dict[str, Any]] | None:
    """Return canned semantic issues for demo pages if detected, else None."""
    issues = []
    # Demo Page 1 planted semantic issues:
    if "image1.jpg" in user_prompt:
        issues.append(
            {
                "rule_id": "llm-alt-quality",
                "selector": "img.gallery-img-1",
                "wcag": ["1.1.1"],
                "impact": "serious",
                "message": "Alt text 'image1.jpg' is a filename and does not describe the image.",
            }
        )
    if '"photo"' in user_prompt:
        issues.append(
            {
                "rule_id": "llm-alt-quality",
                "selector": "img.gallery-img-2",
                "wcag": ["1.1.1"],
                "impact": "serious",
                "message": "Alt text 'photo' is generic and fails to convey the image purpose.",
            }
        )
    if "Click here" in user_prompt:
        issues.append(
            {
                "rule_id": "llm-link-purpose",
                "selector": "a.quick-link-1",
                "wcag": ["2.4.4"],
                "impact": "serious",
                "message": "Link text 'Click here' does not describe the destination without visual context.",
            }
        )
        issues.append(
            {
                "rule_id": "llm-link-purpose",
                "selector": "a.quick-link-2",
                "wcag": ["2.4.4"],
                "impact": "serious",
                "message": "Vague link 'Click here' prevents non-visual users from understanding link purpose.",
            }
        )
    if "fake-btn" in user_prompt or "Submit Enquiry" in user_prompt:
        issues.append(
            {
                "rule_id": "llm-button-name",
                "selector": "div.fake-btn",
                "wcag": ["2.1.1", "4.1.2"],
                "impact": "serious",
                "message": "Custom <div> button with onclick lacks keyboard focus and ARIA button role.",
            }
        )

    return issues if issues else None


def get_cached_demo_fix(user_prompt: str, scenario: str = "normal") -> dict[str, Any] | None:
    """Return canned fix suggestion for demo page elements if detected, else None."""
    is_retry = "NOTE: A previous patch attempt was rejected" in user_prompt

    # Demo Page 1: Hero
    if "hero-image" in user_prompt or "hero.svg" in user_prompt:
        return {
            "explanation": "The hero banner image has no alt text. Adding descriptive text conveys the campus setting.",
            "wcag": "1.1.1",
            "patch": {
                "op": "set_attr",
                "selector": "img.hero-image",
                "name": "alt",
                "value": "Sunrise College main campus building with students",
            },
            "confidence": 0.95,
            "needs_human": False,
            "human_note": None,
        }

    # Demo Page 1: Gallery
    if "gallery-img-1" in user_prompt:
        return {
            "explanation": "Replacing filename 'image1.jpg' with descriptive alt text helps blind and low-vision users visualize the facility.",
            "wcag": "1.1.1",
            "patch": {
                "op": "set_attr",
                "selector": "img.gallery-img-1",
                "name": "alt",
                "value": "Students working in modern chemistry research laboratory",
            },
            "confidence": 0.92,
            "needs_human": False,
            "human_note": None,
        }
    if "gallery-img-2" in user_prompt:
        return {
            "explanation": "Replacing generic 'photo' with specific description clarifies that the library is a central campus facility.",
            "wcag": "1.1.1",
            "patch": {
                "op": "set_attr",
                "selector": "img.gallery-img-2",
                "name": "alt",
                "value": "Sunrise Central Library reading hall with book collections",
            },
            "confidence": 0.90,
            "needs_human": False,
            "human_note": None,
        }

    # Demo Page 1: Note contrast
    if "p.note" in user_prompt or ("#aaaaaa" in user_prompt and "color-contrast" in user_prompt):
        if scenario == "retry" and not is_retry:
            return {
                "explanation": "Light grey text on white is difficult for low-vision readers to decipher.",
                "wcag": "1.4.3",
                "patch": {
                    "op": "add_css",
                    "selector": "p.note",
                    "property": "color",
                    "value": "#999999",
                },
                "confidence": 0.85,
                "needs_human": False,
                "human_note": None,
            }
        return {
            "explanation": "Light grey text (#aaaaaa) fails the minimum 4.5:1 contrast ratio against white. Darkening to #222222 ensures clear readability.",
            "wcag": "1.4.3",
            "patch": {
                "op": "add_css",
                "selector": "p.note",
                "property": "color",
                "value": "#222222",
            },
            "confidence": 0.95,
            "needs_human": False,
            "human_note": None,
        }

    # Demo Page 1: Email field
    if "#email" in user_prompt and "wrap_label" in user_prompt:
        return {
            "explanation": "The email input has a placeholder but no visible or programmatically associated label, failing screen reader announcements.",
            "wcag": "1.3.1",
            "patch": {
                "op": "wrap_label",
                "selector": "#email",
                "label_text": "Email address",
            },
            "confidence": 0.94,
            "needs_human": False,
            "human_note": None,
        }

    # Demo Page 1: Menu button
    if "menu-btn" in user_prompt:
        return {
            "explanation": "The icon-only hamburger button lacks an accessible name, making its purpose unknown to screen readers.",
            "wcag": "4.1.2",
            "patch": {
                "op": "set_attr",
                "selector": "button.menu-btn",
                "name": "aria-label",
                "value": "Toggle navigation menu",
            },
            "confidence": 0.96,
            "needs_human": False,
            "human_note": None,
        }

    # Demo Page 1: html lang
    if "html-has-lang" in user_prompt or "<html>" in user_prompt:
        return {
            "explanation": "The root <html> element is missing a lang attribute, preventing screen readers from choosing the correct pronunciation rules.",
            "wcag": "3.1.1",
            "patch": {
                "op": "set_attr",
                "selector": "html",
                "name": "lang",
                "value": "en",
            },
            "confidence": 0.99,
            "needs_human": False,
            "human_note": None,
        }

    # Demo Page 1: Fake button (div.fake-btn)
    if "fake-btn" in user_prompt:
        return {
            "explanation": "Custom div.fake-btn button requires developer review to replace with native button.",
            "wcag": "4.1.2",
            "patch": None,
            "confidence": 0.40,
            "needs_human": True,
            "human_note": "Replace custom div.fake-btn with native <button> or add role='button' and keyboard listeners.",
        }

    return None
