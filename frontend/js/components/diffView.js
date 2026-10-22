/**
 * Unified Diff Component.
 * Color is accompanied by explicit + and - symbols for accessibility.
 * All text is escaped to protect against XSS from untrusted audited HTML.
 */

export function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

export function renderDiffView(diffStr, beforeSnippet, afterSnippet) {
  if (diffStr && diffStr.trim()) {
    const lines = diffStr.split("\n");
    const diffLinesHtml = lines.map((line) => {
      let lineClass = "diff-ctx";
      let prefix = " ";
      if (line.startsWith("---") || line.startsWith("+++") || line.startsWith("@@")) {
        lineClass = "diff-meta";
        return `<div class="${lineClass}"><span class="diff-sign"> </span><span class="diff-text">${escapeHtml(line)}</span></div>`;
      } else if (line.startsWith("+")) {
        lineClass = "diff-add";
        prefix = "+";
        line = line.substring(1);
      } else if (line.startsWith("-")) {
        lineClass = "diff-del";
        prefix = "-";
        line = line.substring(1);
      }
      return `<div class="${lineClass}"><span class="diff-sign" aria-hidden="true">${prefix}</span><span class="diff-text">${escapeHtml(line)}</span></div>`;
    }).join("");

    return `
      <div class="diff-container" role="region" aria-label="Code change diff">
        <div class="diff-header">
          <span class="diff-badge-before">Original</span>
          <span class="diff-arrow">→</span>
          <span class="diff-badge-after">Patched</span>
        </div>
        <pre class="diff-pre"><code>${diffLinesHtml}</code></pre>
      </div>
    `;
  }

  // Fallback to before / after snippets
  return `
    <div class="diff-container fallback-diff" role="region" aria-label="Code change snippets">
      <div class="diff-split">
        <div class="diff-col">
          <div class="diff-label">Before:</div>
          <pre class="snippet-box"><code>${escapeHtml(beforeSnippet || "N/A")}</code></pre>
        </div>
        <div class="diff-col">
          <div class="diff-label">Proposed Fix:</div>
          <pre class="snippet-box"><code>${escapeHtml(afterSnippet || "N/A")}</code></pre>
        </div>
      </div>
    </div>
  `;
}
