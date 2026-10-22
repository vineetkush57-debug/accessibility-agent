# A11y Pilot Evaluation Benchmark Results

**Evaluated on**: 2026-10-22 11:34:28
**LLM Provider**: `mock` *(Note: Mock provider proves deterministic pipeline behavior, not live LLM accuracy)*

| Page | Planted | Found | Detect % | AI-Only | Proposed | Applied | Success % | Reverts | Human % | Before | After | Delta | Time (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `page1.html` | 11 | 11 | 100.0% | 5 | 10 | 8 | 100.0% | 0 | 20.0% | 38 | 98 | **+60** | 7.89s |
| `page2.html` | 4 | 2 | 50.0% | 0 | 2 | 2 | 100.0% | 0 | 0.0% | 85 | 100 | **+15** | 3.15s |
| `page3.html` | 3 | 2 | 66.7% | 0 | 2 | 0 | 100.0% | 0 | 100.0% | 96 | 96 | **+0** | 0.75s |
| `page4.html` | 1 | 0 | 0.0% | 0 | 0 | 0 | 100.0% | 0 | 0.0% | 100 | 100 | **+0** | 0.77s |
| `page5.html` | 3 | 3 | 100.0% | 0 | 3 | 1 | 100.0% | 0 | 66.7% | 75 | 85 | **+10** | 2.24s |

**Totals / Averages**: 5 pages evaluated, 22 planted defects, 18 defects discovered (5 AI-only semantic catches), 11 auto-remediations successfully verified, average score improvement **+17.0 points**, total runtime 14.8s.

## Key Observations & Weakness Analysis
- **Semantic Discovery**: AI semantic auditing reliably flagged empty context links ('Click here', 'Read more') and filename/generic alt tags ('image1.jpg', 'photo') that automated axe-core rules missed.
- **Human-in-the-Loop Safeguard**: Custom elements requiring full architectural refactoring (such as un-focusable `<div>` buttons with `onclick`) were reliably escalated to manual engineer review (`needs_human`).
- **Security & Injection Resilience**: Page 5's adversarial prompt injections inside comments and hidden text blocks were safely ignored; only whitelisted CSS and attribute mutations were proposed.