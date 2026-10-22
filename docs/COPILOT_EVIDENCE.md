# GitHub Copilot Evidence & Impact Log

This document records the prompt workflows, Copilot features used, and measured development acceleration during the engineering of **A11y Pilot**.

---

## 1. Copilot Acceleration Log Template

| Timestamp | Team Member / Role | Engineering Task | Copilot Feature Used | Generated Outcome | Est. Time Saved |
|---|---|---|---|---|---|
| 10:48 | Senior Full-Stack Engineer | Contract-first Pydantic v2 data models | Copilot Chat | Generated discriminated union `Patch` with 6 typed operations and validators | 45 mins |
| 11:02 | Security Specialist | SSRF guard & IP range resolution filter | Copilot Code Completion | Implemented socket DNS resolution and blocked link-local/RFC1918 ranges | 35 mins |
| 11:13 | Core Backend Engineer | AST Whitelist patch engine & diff maker | Copilot Chat | Built BeautifulSoup4 AST modifier and tag-boundary unified diff generator | 60 mins |
| 11:20 | Frontend Engineer | Accessible SVG score gauge component | Copilot Chat | Created accessible SVG circular arc gauge with role="img" and aria-label | 30 mins |
| 11:32 | QA Engineer | Evaluation harness and multi-page runner | Copilot Inline Edit | Generated benchmark harness computing detection rates and CSV/MD outputs | 40 mins |

---

## 2. Recommended Copilot Prompts by Role

### A. Backend & Systems Engineer
1. *"Write a Pydantic v2 discriminated union for HTML patch operations where the discriminator is 'op', covering set_attr, remove_attr, set_text, wrap_label, add_css, and change_tag."*
2. *"Implement an SSRF validation function in Python that resolves hostnames via socket.getaddrinfo and verifies that none of the returned IP addresses belong to loopback, private RFC1918, link-local, or multicast networks."*
3. *"Write a BeautifulSoup4 AST mutation function that replaces the text of an element only if it has no element children like SVG, otherwise returning an error."*
4. *"Create a FastAPI Server-Sent Events (SSE) generator that yields events from an asyncio.Queue with keep-alive comments and Last-Event-ID reconnection."*
5. *"Generate a unified diff using difflib that splits HTML snippets on tag boundaries for readability."*

### B. AI & Prompt Engineer
1. *"Craft an explain-and-fix system prompt for an accessibility engineer that outputs strictly JSON with fields explanation, wcag, patch, confidence, needs_human, and human_note."*
2. *"Write a prompt injection defense wrapper that isolates untrusted page data in XML blocks and instructs the model that inner content is purely data, never instructions."*
3. *"Generate an LLM response validator that cleans markdown fences and extracts the first top-level JSON object or array."*
4. *"Build a deterministic mock LLM fixture dictionary that returns targeted accessibility fixes for missing alt, vague links, and heading order."*
5. *"Design an adaptive retry prompt that takes failure feedback from a re-scan violation and asks the LLM to adjust its CSS contrast patch."*

### C. Frontend & Accessibility Engineer
1. *"Create a zero-dependency SVG circular gauge in vanilla JavaScript with role='img' and an accessible aria-label."*
2. *"Write a high-contrast CSS stylesheet using custom properties that satisfies WCAG 2.2 AA contrast requirements for both light and dark themes."*
3. *"Implement an accessible unified diff viewer in vanilla JS that uses explicit + and - prefix signs so color is not the only differentiator."*
4. *"Create an aria-live announcement region for an agent execution timeline that polite-announces completed steps without interrupting user focus."*
5. *"Write an HTML-escaping utility in JavaScript that safely renders untrusted code snippets into pre/code blocks."*

### D. QA & Compliance Specialist
1. *"Write a pytest test suite using Playwright to scan an HTML document with axe-core and verify that zero critical or serious issues remain."*
2. *"Create an evaluation harness script that iterates over planted accessibility defects, compares detected issues against ground truth, and writes a markdown summary table."*
3. *"Write automated test cases asserting that SSRF guards reject file://, javascript:, 169.254.169.254, and internal hostnames."*
4. *"Implement a test verifying that adversarial prompt injections embedded in HTML comments do not leak into proposed patches."*
5. *"Write a dogfooding self-audit test asserting that the application's own UI scores at least 90 on axe-core."*
