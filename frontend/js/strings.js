/**
 * Centralized user-visible strings for A11y Pilot.
 */
export const strings = {
  appName: "A11y Pilot",
  tagline: "Finding accessibility issues is easy; understanding and fixing them is hard. A11y Pilot scans, explains, fixes and verifies.",
  skipLink: "Skip to main content",
  
  // Tabs
  tabScanUrl: "Scan a URL",
  tabPasteHtml: "Paste HTML",
  
  // Inputs
  urlPlaceholder: "https://example.com or http://127.0.0.1:8000/demo/page1.html",
  htmlPlaceholder: "Paste full HTML source code here (<!DOCTYPE html>...)",
  languageLabel: "Explanation Language:",
  
  // Buttons
  btnScan: "Start Accessibility Audit",
  btnScanning: "Auditing & Fixing...",
  btnApplyFixes: "Apply Approved Fixes",
  btnDownloadHtml: "Download Fixed HTML",
  btnDownloadReport: "Download Report JSON",
  btnSelectAllSafe: "Approve All Safe Fixes",
  btnRejectAll: "Reject All",
  btnBackHome: "← Scan Another Page",
  
  // Quick Start Demo
  quickStartTitle: "Quick Start: Benchmark Demo Pages",
  demoPage1: "Page 1: Sunrise College Hero (10 issues)",
  demoPage2: "Page 2: Contact Form",
  demoPage3: "Page 3: News Portal",
  demoPage4: "Page 4: Clean Benchmark",
  demoPage5: "Page 5: Prompt Injection Test",
  
  // Statuses
  statusProposed: "Proposed",
  statusNeedsHuman: "Needs Human Review",
  statusRejected: "Rejected",
  statusApplied: "Applied",
  statusRetriedApplied: "Applied after Retry",
  statusReverted: "Reverted (Regression Guard)",
  statusFailed: "Failed",
  
  // Warnings & Disclaimers
  scoreDisclaimer: "Illustrative heuristic score, not an official legal WCAG metric.",
  limitationsTitle: "Audit Limitations & Disclaimers",
  manualChecksTitle: "Required Manual Accessibility Checks",
};
