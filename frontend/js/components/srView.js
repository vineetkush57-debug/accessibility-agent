/**
 * Screen Reader (ARIA tree) Before vs After Component.
 */

import { escapeHtml } from "./diffView.js";

export function renderScreenReaderView(ariaBefore, ariaAfter) {
  const beforeText = (ariaBefore || "Accessibility snapshot unavailable").trim();
  const afterText = (ariaAfter || "Re-scan snapshot pending application").trim();

  return `
    <section class="sr-view-container" aria-label="Screen Reader Announcement Comparison">
      <div class="sr-intro">
        <h3>What Assistive Technologies (Screen Readers) Announce</h3>
        <p>This comparison shows the accessibility tree perceived by screen reader users before and after applying approved remediations.</p>
      </div>

      <div class="sr-panels">
        <div class="sr-panel">
          <div class="sr-panel-header sr-before">
            <span class="sr-status-icon" aria-hidden="true">⚠️</span>
            <h4>Before Remediation</h4>
          </div>
          <pre class="sr-pre"><code>${escapeHtml(beforeText)}</code></pre>
        </div>

        <div class="sr-panel">
          <div class="sr-panel-header sr-after">
            <span class="sr-status-icon" aria-hidden="true">✓</span>
            <h4>After Verified Fixes</h4>
          </div>
          <pre class="sr-pre"><code>${escapeHtml(afterText)}</code></pre>
        </div>
      </div>
    </section>
  `;
}
