/**
 * Agent Timeline Component.
 * Displays multi-step agentic progress and live event stream.
 */

import { escapeHtml } from "./diffView.js";

const STEPS = [
  { id: "scan", label: "Automated Rules Scan" },
  { id: "audit", label: "AI Semantic Audit" },
  { id: "fix", label: "Draft Safe Fixes" },
  { id: "verify", label: "Apply & Verify Loop" },
  { id: "report", label: "Final Report" },
];

export function renderTimeline(activeStepId = "scan", events = [], status = "scanning") {
  const stepItemsHtml = STEPS.map((s, idx) => {
    let stateClass = "pending";
    let icon = `${idx + 1}`;

    const stepIdx = STEPS.findIndex((x) => x.id === activeStepId);
    if (idx < stepIdx || status === "completed") {
      stateClass = "completed";
      icon = "✓";
    } else if (idx === stepIdx) {
      if (status === "failed") {
        stateClass = "failed";
        icon = "✗";
      } else {
        stateClass = "active";
        icon = "⟳";
      }
    }

    return `
      <div class="timeline-step step-${stateClass}" id="step-${s.id}">
        <div class="step-indicator" aria-hidden="true">${icon}</div>
        <div class="step-label">${escapeHtml(s.label)}</div>
      </div>
    `;
  }).join("");

  const recentEvents = events.slice(-12).reverse();
  const eventsHtml = recentEvents.map((ev) => {
    const timeStr = new Date(ev.ts * 1000).toLocaleTimeString([], { hour12: false });
    return `
      <li class="event-item type-${ev.type}">
        <span class="event-time">${timeStr}</span>
        <span class="event-step">[${escapeHtml(ev.step || "agent")}]</span>
        <span class="event-msg">${escapeHtml(ev.message)}</span>
      </li>
    `;
  }).join("");

  return `
    <section class="timeline-container" aria-label="Agent Execution Timeline">
      <div class="timeline-steps" role="list">
        ${stepItemsHtml}
      </div>

      <div class="timeline-events-box">
        <h3 class="events-title">Live Agent Event Log</h3>
        <ul class="timeline-events-list" aria-live="polite" aria-atomic="false">
          ${eventsHtml || '<li class="event-item-empty">Awaiting agent start...</li>'}
        </ul>
      </div>
    </section>
  `;
}
