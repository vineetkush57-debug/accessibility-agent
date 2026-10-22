"""Deterministic mock LLM provider for offline testing, demos, and general evaluation."""

import json
import logging
from typing import Any

from backend.config import settings
from backend.demo_fixtures import get_cached_demo_fix, get_cached_demo_semantic_audit

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
            return self._handle_semantic_audit(user, scenario)

        # 2. Explain-and-fix request
        return self._handle_explain_and_fix(user, scenario)

    def _handle_semantic_audit(self, user: str, scenario: str) -> list[dict]:
        # Optional cached demo run path
        if scenario in ("demo", "cached_demo"):
            demo_res = get_cached_demo_semantic_audit(user)
            if demo_res:
                return demo_res

        issues = []
        try:
            # Parse semantic elements from <page_data>
            if "<page_data>" in user and "</page_data>" in user:
                raw_json = user.split("<page_data>")[1].split("</page_data>")[0].strip()
                semantics = json.loads(raw_json)

                # Heuristic audit for images: alt is filename or generic
                for img in semantics.get("images", []):
                    alt = (img.get("alt") or "").strip().lower()
                    sel = img.get("selector")
                    if not sel:
                        continue
                    if any(alt.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".svg", ".gif", ".webp")):
                        issues.append({
                            "rule_id": "llm-alt-quality",
                            "selector": sel,
                            "wcag": ["1.1.1"],
                            "impact": "serious",
                            "message": f"Alt text '{alt}' appears to be a filename rather than a descriptive explanation.",
                        })
                    elif alt in ("image", "photo", "pic", "icon", "placeholder"):
                        issues.append({
                            "rule_id": "llm-alt-quality",
                            "selector": sel,
                            "wcag": ["1.1.1"],
                            "impact": "serious",
                            "message": f"Generic alt text '{alt}' fails to explain image purpose in context.",
                        })

                # Heuristic audit for custom button elements (divs, spans, onclick without native button)
                for btn in semantics.get("buttons", []):
                    sel = btn.get("selector", "")
                    tag = (btn.get("tag") or "").lower()
                    if (tag and tag != "button") or "div" in sel or "span" in sel:
                        issues.append({
                            "rule_id": "llm-button-name",
                            "selector": sel,
                            "wcag": ["2.1.1", "4.1.2"],
                            "impact": "serious",
                            "message": "Custom element styled as button lacks accessible role and keyboard semantics.",
                        })

                # Heuristic audit for links: vague link text (cap max 2 per vague phrase)
                seen_vague_links: dict[str, int] = {}
                for lnk in semantics.get("links", []):
                    txt = (lnk.get("text") or "").strip().lower()
                    sel = lnk.get("selector")
                    if not sel:
                        continue
                    if txt in ("click here", "read more", "more", "here", "learn more", "details"):
                        count = seen_vague_links.get(txt, 0)
                        if count < 2:
                            seen_vague_links[txt] = count + 1
                            issues.append({
                                "rule_id": "llm-link-purpose",
                                "selector": sel,
                                "wcag": ["2.4.4"],
                                "impact": "serious",
                                "message": f"Ambiguous link text '{txt}' lacks destination context for assistive tech.",
                            })
        except Exception as e:
            logger.debug("Mock semantic audit parse error: %s", e)

        return issues

    def _handle_explain_and_fix(self, user: str, scenario: str) -> dict:
        is_retry = "NOTE: A previous patch attempt was rejected" in user

        # Optional cached demo run path
        if scenario in ("demo", "cached_demo"):
            demo_fix = get_cached_demo_fix(user, scenario)
            if demo_fix:
                return demo_fix

        # General rule-based fix generator for any public page
        try:
            if "<page_data>" in user and "</page_data>" in user:
                raw_json = user.split("<page_data>")[1].split("</page_data>")[0].strip()
                issue_info = json.loads(raw_json)
                rule_id = issue_info.get("rule_id", "")
                selector = issue_info.get("selector", "")

                if "fake-btn" in selector or "fake-btn" in user:
                    return {
                        "explanation": "Custom div.fake-btn button requires developer review to replace with native button.",
                        "wcag": "4.1.2",
                        "patch": None,
                        "confidence": 0.40,
                        "needs_human": True,
                        "human_note": "Replace custom div.fake-btn with native <button> or add role='button' and keyboard listeners.",
                    }

                if selector and rule_id in ("color-contrast", "llm-contrast"):
                    if scenario == "retry" and not is_retry:
                        # Intentionally return weak contrast to test retry loop
                        return {
                            "explanation": "Attempting initial slight color contrast tweak.",
                            "wcag": "1.4.3",
                            "patch": {
                                "op": "add_css",
                                "selector": selector,
                                "property": "color",
                                "value": "#888888",
                            },
                            "confidence": 0.85,
                            "needs_human": False,
                            "human_note": None,
                        }
                    return {
                        "explanation": "Darkens the element text color to #111111 to achieve WCAG AA contrast ratio of at least 4.5:1.",
                        "wcag": "1.4.3",
                        "patch": {
                            "op": "add_css",
                            "selector": selector,
                            "property": "color",
                            "value": "#111111",
                        },
                        "confidence": 0.92,
                        "needs_human": False,
                        "human_note": None,
                    }

                if selector and rule_id == "aria-allowed-role":
                    return {
                        "explanation": "Removes the unsupported ARIA role to allow the native element semantics to operate correctly.",
                        "wcag": "4.1.2",
                        "patch": {
                            "op": "remove_attr",
                            "selector": selector,
                            "name": "role",
                        },
                        "confidence": 0.90,
                        "needs_human": False,
                        "human_note": None,
                    }

                if selector and rule_id in ("image-alt", "llm-alt-quality"):
                    return {
                        "explanation": "Adds descriptive alternative text for non-text image content to satisfy WCAG 1.1.1.",
                        "wcag": "1.1.1",
                        "patch": {
                            "op": "set_attr",
                            "selector": selector,
                            "name": "alt",
                            "value": "Descriptive visual content illustration",
                        },
                        "confidence": 0.89,
                        "needs_human": False,
                        "human_note": None,
                    }

                if selector and rule_id in ("link-name", "llm-link-purpose"):
                    return {
                        "explanation": "Adds an accessible aria-label to clarify the link destination for screen reader users.",
                        "wcag": "2.4.4",
                        "patch": {
                            "op": "set_attr",
                            "selector": selector,
                            "name": "aria-label",
                            "value": "More details and information",
                        },
                        "confidence": 0.88,
                        "needs_human": False,
                        "human_note": None,
                    }

                if selector and rule_id in ("button-name", "llm-button-name"):
                    return {
                        "explanation": "Sets an explicit aria-label so assistive devices announce a meaningful button action.",
                        "wcag": "4.1.2",
                        "patch": {
                            "op": "set_attr",
                            "selector": selector,
                            "name": "aria-label",
                            "value": "Perform action",
                        },
                        "confidence": 0.88,
                        "needs_human": False,
                        "human_note": None,
                    }

                if selector and rule_id in ("label", "label-title-only"):
                    return {
                        "explanation": "Associates an explicit visible label with this input field to satisfy WCAG 1.3.1 and 3.3.2.",
                        "wcag": "1.3.1",
                        "patch": {
                            "op": "wrap_label",
                            "selector": selector,
                            "label_text": "Input field",
                        },
                        "confidence": 0.88,
                        "needs_human": False,
                        "human_note": None,
                    }

                if selector and rule_id in ("html-has-lang", "valid-lang"):
                    return {
                        "explanation": "Declares the primary language on the html tag to ensure accurate speech synthesis pronunciation.",
                        "wcag": "3.1.1",
                        "patch": {
                            "op": "set_attr",
                            "selector": "html",
                            "name": "lang",
                            "value": "en",
                        },
                        "confidence": 0.98,
                        "needs_human": False,
                        "human_note": None,
                    }

                if selector and rule_id in ("empty-heading", "llm-heading-logic"):
                    return {
                        "explanation": "Provides meaningful heading text so users navigating by headings can understand document structure.",
                        "wcag": "2.4.6",
                        "patch": {
                            "op": "set_text",
                            "selector": selector,
                            "value": "Section Overview",
                        },
                        "confidence": 0.87,
                        "needs_human": False,
                        "human_note": None,
                    }
        except Exception as e:
            logger.debug("Mock generic fallback parsing error: %s", e)

        # Default fallback for unmapped elements
        return {
            "explanation": "This issue requires developer review to determine the appropriate semantic remediation.",
            "wcag": "1.1.1",
            "patch": None,
            "confidence": 0.35,
            "needs_human": True,
            "human_note": "Please review this element manually in context.",
        }
