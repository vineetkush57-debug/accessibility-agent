"""Deterministic mock LLM provider for offline testing and demonstrations."""

import logging
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)


class MockLLMClient:
    name = "mock"

    def __init__(self):
        self._retry_counts: dict[str, int] = {}

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> Any:
        scenario = settings.MOCK_SCENARIO.lower()

        # 1. Semantic audit request
        if "MEANING problems that automated" in system:
            return self._handle_semantic_audit(user)

        # 2. Explain-and-fix request
        return self._handle_explain_and_fix(user, scenario)

    def _handle_semantic_audit(self, user: str) -> list[dict]:
        issues = []
        # Page 1 planted semantic issues:
        # Gallery image 1
        if "image1.jpg" in user:
            issues.append(
                {
                    "rule_id": "llm-alt-quality",
                    "selector": "img.gallery-img-1",
                    "wcag": ["1.1.1"],
                    "impact": "serious",
                    "message": "Alt text 'image1.jpg' is a filename and does not describe the image.",
                }
            )
        # Gallery image 2
        if '"photo"' in user:
            issues.append(
                {
                    "rule_id": "llm-alt-quality",
                    "selector": "img.gallery-img-2",
                    "wcag": ["1.1.1"],
                    "impact": "serious",
                    "message": "Alt text 'photo' is generic and fails to convey the image purpose.",
                }
            )
        # Vague Click here links
        if "Click here" in user:
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

        # Custom div button without role or keyboard access
        if "fake-btn" in user or "Submit Enquiry" in user:
            issues.append(
                {
                    "rule_id": "llm-button-name",
                    "selector": "div.fake-btn",
                    "wcag": ["2.1.1", "4.1.2"],
                    "impact": "serious",
                    "message": "Custom <div> button with onclick lacks keyboard focus and ARIA button role.",
                }
            )

        return issues

    def _handle_explain_and_fix(self, user: str, scenario: str) -> dict:
        # Retry scenario check
        is_retry = "NOTE: A previous patch attempt was rejected" in user

        # 1. Hero image (axe: image-alt)
        if "hero-image" in user or "hero.svg" in user:
            return {
                "explanation": "The hero banner image has no alt text, leaving screen reader users without context. Adding descriptive text conveys the campus setting.",
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

        # 2. Gallery images (llm-alt-quality)
        if "gallery-img-1" in user:
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

        if "gallery-img-2" in user:
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

        # 3. Contrast issue (color-contrast)
        if "note" in user and ("color-contrast" in user or "#aaaaaa" in user):
            if scenario == "retry" and not is_retry:
                # Deliberately propose an insufficient color (#999999, still failing) to trigger retry
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
            # Otherwise return high-contrast color #222222 (contrast > 10:1)
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

        # 4. Form input label (label or #email)
        if "#email" in user or "email" in user:
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

        # 5. Hamburger menu button (button-name)
        if "menu-btn" in user:
            return {
                "explanation": "The icon-only hamburger button lacks an accessible name, making its purpose unknown to screen readers.",
                "wcag": "4.1.2",
                "patch": {
                    "op": "set_attr",
                    "selector": "button.menu-btn",
                    "name": "aria-label",
                    "value": "Open navigation menu",
                },
                "confidence": 0.96,
                "needs_human": False,
                "human_note": None,
            }

        # 6. Click here links (llm-link-purpose)
        if "quick-link-1" in user:
            return {
                "explanation": "Changing generic 'Click here' to descriptive destination text allows screen reader users browsing links out of context to understand it.",
                "wcag": "2.4.4",
                "patch": {
                    "op": "set_text",
                    "selector": "a.quick-link-1",
                    "value": "Read the admissions guide",
                },
                "confidence": 0.91,
                "needs_human": False,
                "human_note": None,
            }

        # 7. Heading skip (heading-order or section-title)
        if "section-title" in user or "heading-order" in user:
            return {
                "explanation": "Jumping from h1 directly to h4 breaks the semantic hierarchy for assistive navigation. Correcting it to h2 maintains structure.",
                "wcag": "1.3.1",
                "patch": {
                    "op": "change_tag",
                    "selector": "h4.section-title",
                    "new_tag": "h2",
                },
                "confidence": 0.93,
                "needs_human": False,
                "human_note": None,
            }

        # 8. Missing html lang (html-has-lang)
        if "html-has-lang" in user or '"selector": "html"' in user:
            return {
                "explanation": "The root <html> tag lacks a lang attribute, preventing screen readers from selecting the correct pronunciation and voice synthesizer.",
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

        # 9. Empty icon link (link-name or social-link)
        if "social-link" in user or "link-name" in user:
            if scenario == "revert":
                # Deliberately remove the link content to trigger regression
                return {
                    "explanation": "Test regression patch that causes failure.",
                    "wcag": "2.4.4",
                    "patch": {
                        "op": "set_text",
                        "selector": "a.social-link",
                        "value": "",
                    },
                    "confidence": 0.70,
                    "needs_human": False,
                    "human_note": None,
                }
            return {
                "explanation": "The icon link lacks an accessible name, preventing screen reader users from identifying the destination.",
                "wcag": "2.4.4",
                "patch": {
                    "op": "set_attr",
                    "selector": "a.social-link",
                    "name": "aria-label",
                    "value": "Follow Sunrise College on social media",
                },
                "confidence": 0.92,
                "needs_human": False,
                "human_note": None,
            }

        # 10. Div styled as button (fake-btn) - MUST be needs_human per spec
        if "fake-btn" in user:
            return {
                "explanation": "A <div> element is styled as a button with an onclick handler, but lacks keyboard focusability (tabindex) and button semantics.",
                "wcag": "2.1.1",
                "patch": None,
                "confidence": 0.40,
                "needs_human": True,
                "human_note": "A human engineer should refactor this <div> into a native <button type='submit'> element or add tabindex='0', role='button', and an onkeydown Enter/Space listener.",
            }

        # Page 2: Contact Form Fixtures
        if "full-name" in user:
            return {
                "explanation": "Form field full-name lacks an associated label. Wrapping with a label provides accessible name.",
                "wcag": "1.3.1",
                "patch": {
                    "op": "wrap_label",
                    "selector": "#full-name",
                    "label_text": "Full legal name",
                },
                "confidence": 0.95,
                "needs_human": False,
                "human_note": None,
            }
        if "phone" in user:
            return {
                "explanation": "Phone input field requires an associated label for screen reader users.",
                "wcag": "1.3.1",
                "patch": {
                    "op": "wrap_label",
                    "selector": "#phone",
                    "label_text": "Phone number",
                },
                "confidence": 0.95,
                "needs_human": False,
                "human_note": None,
            }
        if "error-text" in user:
            return {
                "explanation": "Low contrast error text (#999999) fails WCAG AA 4.5:1 ratio. Darkening to #222222 restores readability.",
                "wcag": "1.4.3",
                "patch": {
                    "op": "add_css",
                    "selector": "p.error-text",
                    "property": "color",
                    "value": "#222222",
                },
                "confidence": 0.95,
                "needs_human": False,
                "human_note": None,
            }
        if "department" in user:
            return {
                "explanation": "Department dropdown requires a descriptive label for assistive technologies.",
                "wcag": "1.3.1",
                "patch": {
                    "op": "wrap_label",
                    "selector": "#department",
                    "label_text": "Intended department",
                },
                "confidence": 0.92,
                "needs_human": False,
                "human_note": None,
            }

        # Page 3: News Portal Fixtures
        if "subhead" in user:
            return {
                "explanation": "Heading level jumps from h1 to h4. Adjusting to h2 preserves document hierarchy.",
                "wcag": "1.3.1",
                "patch": {
                    "op": "change_tag",
                    "selector": "h4.subhead",
                    "new_tag": "h2",
                },
                "confidence": 0.95,
                "needs_human": False,
                "human_note": None,
            }
        if "news-link-1" in user:
            return {
                "explanation": "Vague link 'Read more' lacks contextual destination. Adding article title clarifies destination.",
                "wcag": "2.4.4",
                "patch": {
                    "op": "set_text",
                    "selector": "a.news-link-1",
                    "value": "Read more about quantum computing research",
                },
                "confidence": 0.90,
                "needs_human": False,
                "human_note": None,
            }
        if "news-link-2" in user:
            return {
                "explanation": "Vague link 'Read more' should be descriptive of the symposium destination.",
                "wcag": "2.4.4",
                "patch": {
                    "op": "set_text",
                    "selector": "a.news-link-2",
                    "value": "Read more about research symposium",
                },
                "confidence": 0.90,
                "needs_human": False,
                "human_note": None,
            }

        # Page 4: Clean Page Minor Check
        if "minor-note" in user:
            return {
                "explanation": "Adjusting subtle contrast on advisory paragraph to guarantee 4.5:1 ratio.",
                "wcag": "1.4.3",
                "patch": {
                    "op": "add_css",
                    "selector": "p.minor-note",
                    "property": "color",
                    "value": "#333333",
                },
                "confidence": 0.92,
                "needs_human": False,
                "human_note": None,
            }

        # Page 5: Security Benchmark Fixtures (Resisting prompt injection)
        if "sec-img-1" in user:
            return {
                "explanation": "Image lacks alt attribute. Adding descriptive alt conveys test image purpose.",
                "wcag": "1.1.1",
                "patch": {
                    "op": "set_attr",
                    "selector": "#sec-img-1",
                    "name": "alt",
                    "value": "Campus administration building",
                },
                "confidence": 0.95,
                "needs_human": False,
                "human_note": None,
            }
        if "sec-note" in user:
            return {
                "explanation": "Security note text contrast is below 4.5:1. Darkening to #222222 fixes contrast.",
                "wcag": "1.4.3",
                "patch": {
                    "op": "add_css",
                    "selector": "#sec-note",
                    "property": "color",
                    "value": "#222222",
                },
                "confidence": 0.95,
                "needs_human": False,
                "human_note": None,
            }
        if "sec-btn" in user:
            return {
                "explanation": "Icon button has no accessible name. Adding aria-label identifies its purpose.",
                "wcag": "4.1.2",
                "patch": {
                    "op": "set_attr",
                    "selector": "#sec-btn",
                    "name": "aria-label",
                    "value": "Security status indicator",
                },
                "confidence": 0.94,
                "needs_human": False,
                "human_note": None,
            }

        # Default fallback for unmapped elements
        return {
            "explanation": "This issue requires developer review to determine the appropriate semantic remediation.",
            "wcag": "1.1.1",
            "patch": None,
            "confidence": 0.35,
            "needs_human": True,
            "human_note": "Please review this element manually in context.",
        }
