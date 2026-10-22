/**
 * Main Single Page Application Router and State Controller for A11y Pilot.
 */

import { applyFixes, getRun, startScan, subscribeToEvents } from "./api.js";
import { escapeHtml, renderDiffView } from "./components/diffView.js";
import { renderGauge } from "./components/gauge.js";
import { renderIssueCard } from "./components/issueCard.js";
import { renderScreenReaderView } from "./components/srView.js";
import { renderTimeline } from "./components/timeline.js";
import { strings } from "./strings.js";

// Global App State
const state = {
  activeTab: "url", // "url" | "html"
  currentRunId: null,
  report: null,
  events: [],
  selectedFixIds: new Set(),
  activeFilter: "all", // "all" | "axe" | "llm"
  activeEventSub: null,
  errorMessage: null,
};

const appContainer = document.getElementById("app");
const langSelect = document.getElementById("lang-select");

// ---- Router ----
function initRouter() {
  window.addEventListener("hashchange", handleRoute);
  handleRoute();
}

function navigateTo(hash) {
  window.location.hash = hash;
}

async function handleRoute() {
  const hash = window.location.hash || "#/";
  if (hash.startsWith("#/run/")) {
    const runId = hash.replace("#/run/", "").trim();
    if (runId && runId !== state.currentRunId) {
      state.currentRunId = runId;
      state.report = null;
      state.events = [];
      await loadRun(runId);
    }
  } else {
    // Clean up subscription if returning to home
    if (state.activeEventSub) {
      state.activeEventSub.close();
      state.activeEventSub = null;
    }
    state.currentRunId = null;
    renderHomeView();
  }
}

// ---- Run Management ----
async function loadRun(runId) {
  try {
    state.report = await getRun(runId);
    renderCurrentRunState();

    // If still in scanning, fixing, or applying, subscribe to SSE
    if (["created", "scanning", "scanned", "auditing", "fixing", "applying"].includes(state.report.status)) {
      if (!state.activeEventSub) {
        state.activeEventSub = subscribeToEvents(
          runId,
          (ev) => {
            state.events.push(ev);
            if (ev.type === "step_completed" || ev.type === "verification_done" || ev.type === "run_completed") {
              // Refresh full report data
              getRun(runId).then((updated) => {
                state.report = updated;
                renderCurrentRunState();
              });
            } else {
              renderCurrentRunState();
            }
          },
          (err) => console.warn("Event stream notice:", err)
        );
      }
    }
  } catch (err) {
    state.errorMessage = `Error loading run: ${err.message}`;
    renderHomeView();
  }
}

function renderCurrentRunState() {
  if (!state.report) {
    appContainer.innerHTML = `<div class="loading-state" role="status">Loading audit run ${state.currentRunId}...</div>`;
    return;
  }

  const status = state.report.status;
  if (status === "awaiting_review") {
    // Populate default approved fixes if not already set
    if (state.selectedFixIds.size === 0 && state.report.fixes) {
      for (const fix of state.report.fixes) {
        if (!fix.needs_human && fix.confidence >= 0.6) {
          state.selectedFixIds.add(fix.id);
        }
      }
    }
    renderReviewView();
  } else if (status === "completed") {
    renderReportView();
  } else {
    renderScanningView();
  }
}

// ---- Screen 1: Home View ----
function renderHomeView() {
  appContainer.innerHTML = `
    <div class="card-box">
      <h2>Web Accessibility Scanner &amp; Remediation Agent</h2>
      <p class="tagline">${escapeHtml(strings.tagline)}</p>

      ${state.errorMessage ? `
        <div class="alert-box alert-error" role="alert">
          <strong>Error:</strong> ${escapeHtml(state.errorMessage)}
        </div>
      ` : ""}

      <div class="tabs-nav" role="tablist" aria-label="Input format">
        <button
          class="tab-btn"
          role="tab"
          id="tab-url"
          aria-selected="${state.activeTab === 'url'}"
          aria-controls="panel-url"
        >${escapeHtml(strings.tabScanUrl)}</button>
        <button
          class="tab-btn"
          role="tab"
          id="tab-html"
          aria-selected="${state.activeTab === 'html'}"
          aria-controls="panel-html"
        >${escapeHtml(strings.tabPasteHtml)}</button>
      </div>

      <div id="panel-url" role="tabpanel" aria-labelledby="tab-url" ${state.activeTab !== 'url' ? 'hidden' : ''}>
        <div class="form-group">
          <label for="input-url">Website URL to Audit:</label>
          <input
            type="url"
            id="input-url"
            placeholder="${escapeHtml(strings.urlPlaceholder)}"
            value="http://127.0.0.1:8000/demo/page1.html"
          >
        </div>
      </div>

      <div id="panel-html" role="tabpanel" aria-labelledby="tab-html" ${state.activeTab !== 'html' ? 'hidden' : ''}>
        <div class="form-group">
          <label for="input-html">Paste Full HTML Content:</label>
          <textarea
            id="input-html"
            rows="8"
            placeholder="${escapeHtml(strings.htmlPlaceholder)}"
          ></textarea>
        </div>
      </div>

      <div class="action-bar">
        <button id="btn-start-scan" class="btn btn-primary">
          <span class="btn-icon" aria-hidden="true">🔍</span>
          <span>${escapeHtml(strings.btnScan)}</span>
        </button>
      </div>
    </div>

    <div class="card-box">
      <h3>${escapeHtml(strings.quickStartTitle)}</h3>
      <p>Quickly test A11y Pilot against planted accessibility defect pages:</p>
      <div class="demo-grid">
        <button class="btn btn-demo" data-url="http://127.0.0.1:8000/demo/page1.html">
          <strong>Page 1: Sunrise College</strong>
          <div>10 Planted Issues (Hero Demo)</div>
        </button>
        <button class="btn btn-demo" data-url="http://127.0.0.1:8000/demo/page2.html">
          <strong>Page 2: Contact Form</strong>
          <div>Unlabelled Inputs &amp; Contrast</div>
        </button>
        <button class="btn btn-demo" data-url="http://127.0.0.1:8000/demo/page3.html">
          <strong>Page 3: News Portal</strong>
          <div>Vague Links &amp; Heading Skips</div>
        </button>
        <button class="btn btn-demo" data-url="http://127.0.0.1:8000/demo/page4.html">
          <strong>Page 4: Clean Page</strong>
          <div>High Baseline Benchmark</div>
        </button>
        <button class="btn btn-demo" data-url="http://127.0.0.1:8000/demo/page5.html">
          <strong>Page 5: Security Test</strong>
          <div>Prompt Injection Defense</div>
        </button>
      </div>
    </div>
  `;

  // Attach event handlers
  document.getElementById("tab-url")?.addEventListener("click", () => {
    state.activeTab = "url";
    renderHomeView();
  });
  document.getElementById("tab-html")?.addEventListener("click", () => {
    state.activeTab = "html";
    renderHomeView();
  });

  // Demo buttons
  document.querySelectorAll(".btn-demo").forEach((btn) => {
    btn.addEventListener("click", () => {
      const url = btn.getAttribute("data-url");
      state.activeTab = "url";
      renderHomeView();
      const urlInput = document.getElementById("input-url");
      if (urlInput) urlInput.value = url;
    });
  });

  // Start Scan
  document.getElementById("btn-start-scan")?.addEventListener("click", handleStartScan);
}

async function handleStartScan() {
  state.errorMessage = null;
  const lang = langSelect?.value || "en";
  let payload = { language: lang };

  if (state.activeTab === "url") {
    const urlInput = document.getElementById("input-url");
    const url = urlInput?.value?.trim();
    if (!url) {
      state.errorMessage = "Please enter a valid website URL to scan.";
      renderHomeView();
      return;
    }
    payload.url = url;
  } else {
    const htmlInput = document.getElementById("input-html");
    const html = htmlInput?.value?.trim();
    if (!html) {
      state.errorMessage = "Please paste HTML content to audit.";
      renderHomeView();
      return;
    }
    payload.html = html;
  }

  try {
    const btn = document.getElementById("btn-start-scan");
    if (btn) {
      btn.disabled = true;
      btn.textContent = strings.btnScanning;
    }
    const res = await startScan(payload);
    navigateTo(`#/run/${res.run_id}`);
  } catch (err) {
    state.errorMessage = err.message;
    renderHomeView();
  }
}

// ---- Screen 2: Scanning / Active Pipeline View ----
function renderScanningView() {
  const currentStep = state.report?.status === "applying" ? "verify" : "scan";
  appContainer.innerHTML = `
    <div class="card-box">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <h2>Accessibility Audit in Progress</h2>
        <a href="#/" class="btn btn-secondary">Cancel / Back</a>
      </div>
      <p>Target: <code>${escapeHtml(state.report?.source_url || "Pasted HTML Document")}</code></p>
      ${renderTimeline(currentStep, state.events, state.report?.status)}
    </div>
  `;
}

// ---- Screen 3 & 4: Review View ----
function renderReviewView() {
  const score = state.report?.score_before?.score ?? 50;
  const issues = state.report?.issues || [];
  const fixes = state.report?.fixes || [];

  // Filter issues
  const filteredIssues = issues.filter((iss) => {
    if (state.activeFilter === "axe") return iss.source === "axe";
    if (state.activeFilter === "llm") return iss.source === "llm";
    return true;
  });

  const fixesByIssueId = new Map(fixes.map((f) => [f.issue_id, f]));

  // Build fix cards HTML
  const fixCardsHtml = fixes.map((fix) => {
    const isApproved = state.selectedFixIds.has(fix.id);
    const issue = issues.find((i) => i.id === fix.issue_id);

    let confidenceClass = "badge-moderate";
    let confLabel = "Medium";
    if (fix.confidence >= 0.8) {
      confidenceClass = "badge-minor";
      confLabel = "High";
    } else if (fix.confidence < 0.6) {
      confidenceClass = "badge-critical";
      confLabel = "Low";
    }

    return `
      <div class="card-box fix-card ${fix.needs_human ? 'fix-needs-human' : ''}">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px;">
          <div>
            <span class="badge-confidence ${confidenceClass}">Confidence: ${confLabel} (${Math.round(fix.confidence * 100)}%)</span>
            <span class="chip-wcag">WCAG ${escapeHtml(fix.wcag)}</span>
            ${fix.needs_human ? '<span class="badge-status status-needs_human">Requires Manual Check</span>' : ''}
          </div>

          <label class="approve-toggle" style="display: flex; align-items: center; gap: 8px; font-weight: 700; cursor: pointer;">
            <input
              type="checkbox"
              class="fix-checkbox"
              data-fix-id="${escapeHtml(fix.id)}"
              ${isApproved ? 'checked' : ''}
              ${fix.needs_human ? 'disabled' : ''}
            >
            <span>${fix.needs_human ? 'Manual Intervention Needed' : (isApproved ? 'Approved for Auto-Fix' : 'Approve')}</span>
          </label>
        </div>

        <h3 style="margin: 12px 0 6px 0;">${escapeHtml(fix.explanation)}</h3>
        <p style="margin: 0 0 10px 0; color: var(--color-muted);">
          Rule: <code>${escapeHtml(issue?.rule_id || "a11y-rule")}</code> on <code>${escapeHtml(issue?.selector || "")}</code>
        </p>

        ${fix.human_note ? `
          <div class="alert-box alert-warning" style="background: var(--color-amber-bg); padding: 10px; border-radius: var(--radius-sm); margin: 10px 0;">
            <strong>Human Reviewer Checklist:</strong> ${escapeHtml(fix.human_note)}
          </div>
        ` : ""}

        ${renderDiffView(fix.diff, fix.before_snippet, fix.after_snippet)}
      </div>
    `;
  }).join("");

  appContainer.innerHTML = `
    <div class="card-box" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 20px;">
      <div>
        <h2>Accessibility Audit Results &amp; Human Review</h2>
        <p>Page: <strong>${escapeHtml(state.report?.page_title || state.report?.source_url || "Document")}</strong></p>
        <p><small>${escapeHtml(strings.scoreDisclaimer)}</small></p>
      </div>
      <div>
        ${renderGauge(score, "Baseline Score")}
      </div>
    </div>

    <!-- Review Action Bar -->
    <div class="card-box" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
      <div style="display: flex; gap: 12px;">
        <button id="btn-select-all" class="btn btn-secondary">${escapeHtml(strings.btnSelectAllSafe)}</button>
        <button id="btn-reject-all" class="btn btn-secondary">${escapeHtml(strings.btnRejectAll)}</button>
      </div>
      <button id="btn-apply-fixes" class="btn btn-primary" ${state.selectedFixIds.size === 0 ? 'disabled' : ''}>
        ${escapeHtml(strings.btnApplyFixes)} (${state.selectedFixIds.size})
      </button>
    </div>

    <!-- Proposed Fixes List -->
    <h2>Proposed Remediations (${fixes.length})</h2>
    ${fixCardsHtml}
  `;

  // Attach handlers
  document.querySelectorAll(".fix-checkbox").forEach((cb) => {
    cb.addEventListener("change", (e) => {
      const fixId = e.target.getAttribute("data-fix-id");
      if (e.target.checked) state.selectedFixIds.add(fixId);
      else state.selectedFixIds.delete(fixId);
      renderReviewView();
    });
  });

  document.getElementById("btn-select-all")?.addEventListener("click", () => {
    fixes.forEach((f) => {
      if (!f.needs_human) state.selectedFixIds.add(f.id);
    });
    renderReviewView();
  });

  document.getElementById("btn-reject-all")?.addEventListener("click", () => {
    state.selectedFixIds.clear();
    renderReviewView();
  });

  document.getElementById("btn-apply-fixes")?.addEventListener("click", handleApplyFixes);
}

async function handleApplyFixes() {
  const approvedIds = Array.from(state.selectedFixIds);
  if (approvedIds.length === 0) return;

  try {
    const btn = document.getElementById("btn-apply-fixes");
    if (btn) btn.disabled = true;
    await applyFixes(state.currentRunId, approvedIds);
    // Reload run to trigger verify screen
    await loadRun(state.currentRunId);
  } catch (err) {
    alert(`Failed to trigger remediation: ${err.message}`);
  }
}

// ---- Screen 5: Final Report View ----
function renderReportView() {
  const scoreBefore = state.report?.score_before?.score ?? 0;
  const scoreAfter = state.report?.score_after?.score ?? 0;
  const delta = scoreAfter - scoreBefore;

  const fixes = state.report?.fixes || [];

  const fixRowsHtml = fixes.map((f) => {
    let statusClass = "status-applied";
    let statusText = f.status.toUpperCase();
    if (f.status === "retried_applied") statusText = "APPLIED (AFTER RETRY)";
    if (f.status === "reverted") statusClass = "status-reverted";
    if (f.status === "needs_human") statusClass = "status-needs_human";
    if (f.status === "rejected") statusClass = "status-rejected";

    return `
      <tr>
        <td><code>${escapeHtml(f.id)}</code></td>
        <td>${escapeHtml(f.explanation)}</td>
        <td><span class="chip-wcag">WCAG ${escapeHtml(f.wcag)}</span></td>
        <td><span class="badge-status ${statusClass}">${statusText}</span></td>
        <td>${f.attempts || 1}</td>
        <td><small>${escapeHtml(f.verification_note || "Resolved successfully")}</small></td>
      </tr>
    `;
  }).join("");

  const limitationsHtml = (state.report?.limitations || []).map((l) =>
    `<li>${escapeHtml(l)}</li>`
  ).join("");

  const manualChecksHtml = (state.report?.needs_manual_checks || []).map((m) =>
    `<li>${escapeHtml(m)}</li>`
  ).join("");

  appContainer.innerHTML = `
    <!-- Top Score Summary Banner -->
    <div class="card-box" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 24px;">
      <div>
        <h2>Accessibility Audit &amp; Remediation Report</h2>
        <p>Page: <strong>${escapeHtml(state.report?.page_title || state.report?.source_url || "Audited Page")}</strong></p>
        <p style="font-size: 1.2rem; font-weight: 700; color: ${delta >= 0 ? 'var(--color-teal)' : 'var(--color-red)'};">
          Score Progression: ${scoreBefore} → ${scoreAfter} (${delta >= 0 ? '+' : ''}${delta} points)
        </p>
        <p><small>${escapeHtml(strings.scoreDisclaimer)}</small></p>
      </div>

      <div style="display: flex; gap: 20px;">
        ${renderGauge(scoreBefore, "Before Score")}
        ${renderGauge(scoreAfter, "After Score")}
      </div>
    </div>

    <!-- Download & Export Actions -->
    <div class="card-box" style="display: flex; gap: 16px; flex-wrap: wrap; align-items: center;">
      <a href="/api/runs/${escapeHtml(state.currentRunId)}/download" class="btn btn-primary" download="fixed.html">
        <span aria-hidden="true">⬇</span>
        <span>${escapeHtml(strings.btnDownloadHtml)}</span>
      </a>
      <a href="/api/runs/${escapeHtml(state.currentRunId)}/report.json" class="btn btn-secondary" download="report.json">
        <span aria-hidden="true">📄</span>
        <span>${escapeHtml(strings.btnDownloadReport)}</span>
      </a>
      <button id="btn-toggle-preview" class="btn btn-secondary">
        <span aria-hidden="true">👁️</span>
        <span>Toggle Preview</span>
      </button>
      <a href="#/" class="btn btn-secondary">
        <span>${escapeHtml(strings.btnBackHome)}</span>
      </a>
    </div>

    <!-- Optional Remediated Page Preview (srcdoc) -->
    <div id="preview-container" class="card-box" style="display: none;">
      <h3>Remediated Page Preview</h3>
      <p style="margin-top: 0; color: var(--color-muted);"><small>Rendered safely via isolated iframe <code>srcdoc</code>. Scripts are stripped.</small></p>
      <iframe id="remediated-preview-frame" sandbox="allow-same-origin" style="width: 100%; height: 500px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: #ffffff;"></iframe>
    </div>

    <!-- Per-Fix Remediation Summary Table -->
    <div class="card-box">
      <h3>Remediation Results &amp; Verification Status</h3>
      <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.95rem;">
          <thead>
            <tr style="border-bottom: 2px solid var(--color-border);">
              <th style="padding: 10px;">ID</th>
              <th style="padding: 10px;">Remediation Description</th>
              <th style="padding: 10px;">WCAG</th>
              <th style="padding: 10px;">Status</th>
              <th style="padding: 10px;">Attempts</th>
              <th style="padding: 10px;">Verification Outcome</th>
            </tr>
          </thead>
          <tbody>
            ${fixRowsHtml}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Screen Reader Comparison -->
    <div class="card-box">
      ${renderScreenReaderView(state.report?.aria_before, state.report?.aria_after)}
    </div>

    <!-- Limitations & Manual Checks -->
    <div class="card-box">
      <h3>${escapeHtml(strings.limitationsTitle)}</h3>
      <ul>${limitationsHtml}</ul>

      <h3>${escapeHtml(strings.manualChecksTitle)}</h3>
      <ul>${manualChecksHtml}</ul>
    </div>
  `;

  document.getElementById("btn-toggle-preview")?.addEventListener("click", async () => {
    const container = document.getElementById("preview-container");
    const iframe = document.getElementById("remediated-preview-frame");
    if (!container || !iframe) return;

    if (container.style.display === "none") {
      container.style.display = "block";
      if (!iframe.srcdoc) {
        try {
          const resp = await fetch(`/api/runs/${state.currentRunId}/preview`);
          if (resp.ok) {
            const htmlText = await resp.text();
            iframe.srcdoc = htmlText;
          } else {
            iframe.srcdoc = "<p style='padding:20px; font-family:sans-serif;'>Preview unavailable.</p>";
          }
        } catch (err) {
          iframe.srcdoc = `<p style='padding:20px; font-family:sans-serif; color:red;'>Failed to load preview: ${err.message}</p>`;
        }
      }
    } else {
      container.style.display = "none";
    }
  });
}

// Start application
initRouter();
