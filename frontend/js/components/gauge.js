/**
 * Accessible SVG Gauge Component.
 * Color is accompanied by clear text and aria-label.
 */

export function renderGauge(score, label = "Accessibility Score") {
  const safeScore = Math.max(0, Math.min(100, Math.round(score)));
  
  // Calculate stroke dashoffset for a 280-degree circular arc
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (safeScore / 100) * (circumference * 0.75);

  let color = "#C23B3B"; // Red
  if (safeScore >= 85) color = "#0F766E"; // Teal / Green
  else if (safeScore >= 60) color = "#F2A33A"; // Amber

  return `
    <div class="gauge-container" role="img" aria-label="${label}: ${safeScore} out of 100">
      <svg class="gauge-svg" width="140" height="140" viewBox="0 0 140 140">
        <!-- Background Track -->
        <circle
          cx="70"
          cy="70"
          r="${radius}"
          fill="none"
          stroke="var(--color-gauge-bg, #E2E8F0)"
          stroke-width="12"
          stroke-dasharray="${circumference * 0.75} ${circumference * 0.25}"
          stroke-dashoffset="0"
          transform="rotate(135 70 70)"
          stroke-linecap="round"
        />
        <!-- Active Value Track -->
        <circle
          cx="70"
          cy="70"
          r="${radius}"
          fill="none"
          stroke="${color}"
          stroke-width="12"
          stroke-dasharray="${circumference * 0.75} ${circumference * 0.25}"
          stroke-dashoffset="${strokeDashoffset}"
          transform="rotate(135 70 70)"
          stroke-linecap="round"
        />
        <!-- Score Value Text -->
        <text x="70" y="68" class="gauge-score-text" text-anchor="middle" dominant-baseline="central">${safeScore}</text>
        <text x="70" y="90" class="gauge-total-text" text-anchor="middle">/ 100</text>
      </svg>
      <div class="gauge-caption">${label}</div>
    </div>
  `;
}
