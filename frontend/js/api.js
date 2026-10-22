/**
 * API client and Server-Sent Events (SSE) connector.
 */

const BASE_URL = "/api";

export async function checkHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function startScan({ url, html, base_url = null, language = "en" }) {
  const payload = { url, html, base_url, language };
  const res = await fetch(`${BASE_URL}/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown scan error" }));
    throw new Error(err.detail || `Scan request failed (${res.status})`);
  }
  return res.json();
}

export async function getRun(runId) {
  const res = await fetch(`${BASE_URL}/runs/${runId}`);
  if (!res.ok) throw new Error(`Failed to fetch run: ${res.status}`);
  return res.json();
}

export async function applyFixes(runId, approvedFixIds) {
  const res = await fetch(`${BASE_URL}/runs/${runId}/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved_fix_ids: approvedFixIds }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown apply error" }));
    throw new Error(err.detail || `Apply fixes failed (${res.status})`);
  }
  return res.json();
}

export function subscribeToEvents(runId, onEvent, onError) {
  let eventSource = null;
  let pollingInterval = null;
  let lastSeq = 0;
  let isClosed = false;

  // Try Server-Sent Events first
  if (typeof EventSource !== "undefined") {
    try {
      eventSource = new EventSource(`${BASE_URL}/runs/${runId}/events`);
      eventSource.addEventListener("agent_event", (e) => {
        try {
          const ev = JSON.parse(e.data);
          lastSeq = Math.max(lastSeq, ev.seq);
          onEvent(ev);
          if (ev.type === "run_completed" || ev.type === "error") {
            close();
          }
        } catch (err) {
          console.error("Error parsing SSE event:", err);
        }
      });

      eventSource.onerror = () => {
        // Fallback to polling if SSE disconnected
        if (!isClosed && !pollingInterval) {
          console.warn("SSE connection error; falling back to event polling.");
          if (eventSource) {
            eventSource.close();
            eventSource = null;
          }
          startPolling();
        }
      };
    } catch (e) {
      console.warn("EventSource setup failed, falling back to polling", e);
      startPolling();
    }
  } else {
    startPolling();
  }

  function startPolling() {
    pollingInterval = setInterval(async () => {
      if (isClosed) return;
      try {
        const res = await fetch(`${BASE_URL}/runs/${runId}/events?after=${lastSeq}`);
        if (!res.ok) return;
        const events = await res.json();
        for (const ev of events) {
          lastSeq = Math.max(lastSeq, ev.seq);
          onEvent(ev);
          if (ev.type === "run_completed" || ev.type === "error") {
            close();
          }
        }
      } catch (err) {
        if (onError) onError(err);
      }
    }, 1000);
  }

  function close() {
    isClosed = true;
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  }

  return { close };
}
