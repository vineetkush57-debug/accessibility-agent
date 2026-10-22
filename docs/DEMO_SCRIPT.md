# 3-Minute Live Hackathon Demo Script: A11y Pilot

> **Goal**: Present A11y Pilot to hackathon judges in under 3 minutes, showcasing why the agentic loop (scan -> audit -> explain -> human approve -> verify/retry/revert) is uniquely powerful.

---

## ⏱️ Timeline & Talking Points

### 0:00 - 0:30 | The Problem & The Pitch
- *"Most accessibility tools tell you what is broken, but they leave developers with cryptic error messages, and they miss context-dependent semantic defects entirely."*
- *"A11y Pilot does not just flag errors; it understands the page meaning, drafts safe code fixes, puts a human in the loop, and then verifies each fix in a live browser to guarantee no regressions."*
- Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Click the quick-start button **"Page 1: Sunrise College"**.
- Click **"Start Accessibility Audit"**.

### 0:30 - 1:15 | The Multi-Engine Scan & Live Timeline
- Show the **Live Agent Timeline**:
  - *"Watch the agent work in real-time over Server-Sent Events. First, Playwright launches headless Chromium and executes axe-core. Next, our semantic extractor feeds structured elements to our AI auditor."*
  - *"Notice the baseline score is 38/100."*
- Point out the **AI-Only Catches** in the issues list:
  - *"Look at these two gallery images: one had alt='image1.jpg' and the other had alt='photo'. Axe-core passed them because alt was technically present! But our AI recognized these are meaningless to a blind user."*
  - *"Notice the five links with text 'Click here'. The AI flagged that non-visual users navigating links out of context have no idea where they lead."*

### 1:15 - 2:00 | Human-in-the-Loop & The Diff Review
- Show the **Unified Diff View**:
  - *"Every proposal is constrained by a strict AST whitelist. No raw HTML strings or script injections."*
  - *"Notice the unified diff: green additions with '+' markers and red deletions with '-' markers so color is never the only visual cue."*
- Point to **Issue #10 (Custom `<div>` button)**:
  - *"Notice Issue #10 is marked 'Needs Human Review' with a confidence of 40%. A custom `<div>` with an `onclick` handler cannot be safely fixed with a simple attribute; an engineer must refactor it. A11y Pilot is honest about its boundaries."*
- Click **"Apply Approved Fixes"**.

### 2:00 - 2:40 | The Closed-Loop Verification & Re-Scan
- Show the verify step:
  - *"Here is where A11y Pilot becomes truly agentic: it applies each patch one by one, immediately re-scans the resulting DOM in headless Chromium, and verifies that the issue actually disappeared without causing any regressions."*
- Show the **Before vs After Report**:
  - *"Our score jumped from 38/100 to 98/100 (+60 points)!"*
  - *"Look at the Screen Reader panel: before, assistive technology heard 'image1 dot jpg' and 'link click here'. Now, it announces 'Students working in modern chemistry research laboratory' and 'Read the admissions guide'."*

### 2:40 - 3:00 | Safe Export & Honest Disclaimer
- Click **"Download Fixed HTML"** to demonstrate the export of the remediated DOM snapshot.
- Point to the **Limitations & Manual Checks list**:
  - *"We include an explicit limitations disclosure: automated tools cannot certify legal compliance; keyboard navigation and manual assistive testing are still essential."*

---

## 🛡️ Backup Plan (No Network / High-Stakes Demo)

1. **Deterministic Mock Mode**:
   - The entire demo works 100% offline with zero API keys using `LLM_PROVIDER=mock`.
   - To demonstrate the retry and revert paths, launch with:
     ```bash
     MOCK_SCENARIO=retry python scripts/dev.py demo
     ```
2. **Pre-Warmed Cache**:
   - If using Gemini or OpenAI live, run the demo once online prior to the presentation. The responses will be cached under `data/cache/llm/`. Subsequent runs will replay instantly with 0ms latency.
