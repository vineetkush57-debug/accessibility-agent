/**
 * Issue Card Component.
 * Displays violation details with multi-modal cues (icon + text).
 */

import { escapeHtml } from "./diffView.js";

const IMPACT_CONFIG = {
  critical: { label: "Critical", icon: "⨂", badgeClass: "badge-critical" },
  serious: { label: "Serious", icon: "▲", badgeClass: "badge-serious" },
  moderate: { label: "Moderate", icon: "■", badgeClass: "badge-moderate" },
  minor: { label: "Minor", icon: "●", badgeClass: "badge-minor" },
};

export function renderIssueCard(issue, fixSuggestion = null) {
  const impact = IMPACT_CONFIG[issue.impact] || IMPACT_CONFIG.minor;
  const isAxe = issue.source === "axe";

  const wcagChips = (issue.wcag || []).map((w) =>
    `<span class="chip-wcag" title="WCAG Success Criterion ${escapeHtml(w)}">WCAG ${escapeHtml(w)}</span>`
  ).join(" ");

  let statusBadge = "";
  if (fixSuggestion) {
    statusBadge = `<span class="badge-status status-${fixSuggestion.status}">${fixSuggestion.status.replace("_", " ").toUpperCase()}</span>`;
  }

  return `
    <article class="issue-card" id="${escapeHtml(issue.id)}">
      <div class="issue-header">
        <div class="issue-badges">
          <span class="badge-impact ${impact.badgeClass}">
            <span class="badge-icon" aria-hidden="true">${impact.icon}</span>
            <span>${impact.label}</span>
          </span>
          <span class="badge-source ${isAxe ? 'source-axe' : 'source-ai'}">
            ${isAxe ? '⚡ Rules (axe-core)' : '🤖 AI Semantic'}
          </span>
          ${wcagChips}
        </div>
        ${statusBadge}
      </div>

      <h3 class="issue-title">
        <span class="issue-rule">${escapeHtml(issue.rule_id)}</span>
        <code class="issue-selector">${escapeHtml(issue.selector)}</code>
      </h3>

      <p class="issue-message">${escapeHtml(issue.message)}</p>

      ${issue.html ? `
        <details class="issue-details">
          <summary>Inspect offending code snippet</summary>
          <pre class="snippet-box"><code>${escapeHtml(issue.html)}</code></pre>
        </details>
      ` : ""}
    </article>
  `;
}
