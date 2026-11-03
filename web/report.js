(() => {
  "use strict";

  const picker = document.querySelector("#case-picker");
  const section = document.querySelector("#patient-report");
  const notice = document.querySelector("#report-reading-note");
  const meta = document.querySelector("#report-meta");
  const actions = document.querySelector(".report-actions");
  const printButton = document.querySelector("#report-print");
  const refreshButton = document.querySelector("#report-refresh");
  const textLink = document.querySelector("#report-text-link");
  const container = document.querySelector("#report-sections");

  if (!picker || !section || !notice || !meta || !actions || !refreshButton ||
      !printButton || !textLink || !container) {
    return;
  }

  let requestSequence = 0;
  let refreshScheduled = false;
  let scheduledSequence = null;
  let acceptedSequence = null;
  let acceptedCase = null;
  let downloadUrl = null;
  let globalPendingWrites = 0;
  const pendingWrites = new Map();

  function recordPendingWrites(detail) {
    if (!detail || !Number.isInteger(detail.pendingWrites) || detail.pendingWrites < 0) return;
    if (detail.scope === "all-cases") {
      globalPendingWrites = detail.pendingWrites;
    } else if (typeof detail.caseId === "string") {
      pendingWrites.set(detail.caseId, detail.pendingWrites);
    }
  }

  function hasPendingWrites(caseId = picker.value) {
    return globalPendingWrites > 0 || (pendingWrites.get(caseId) || 0) > 0;
  }

  function invalidateReport() {
    ++requestSequence;
    scheduledSequence = null;
    acceptedSequence = null;
    acceptedCase = null;
    if (downloadUrl !== null) URL.revokeObjectURL(downloadUrl);
    downloadUrl = null;
    printButton.disabled = true;
    textLink.removeAttribute("href");
    textLink.removeAttribute("download");
    textLink.setAttribute("aria-disabled", "true");
    textLink.tabIndex = -1;
    delete section.dataset.caseId;
    section.setAttribute("aria-busy", "false");
    notice.textContent = "";
    container.replaceChildren();
    refreshButton.disabled = hasPendingWrites();
    meta.textContent = hasPendingWrites()
      ? "Saving changes. Report refresh is unavailable until they finish."
      : "Report waiting for current case information.";
  }

  function reportIsCurrent() {
    return downloadUrl !== null && acceptedCase === picker.value &&
      acceptedSequence === requestSequence && !hasPendingWrites();
  }

  function element(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = String(text);
    return item;
  }

  function renderItem(item, number) {
    const entry = element("li", "report-item");
    entry.append(
      element("p", "quoted", `${number}. ${item.text}`),
      element("p", "", item.detail),
      element("p", "ref", `Source: ${item.citation}`),
    );
    return entry;
  }

  function renderSection(reportSection) {
    const block = element("article", "report-section");
    block.dataset.sectionId = reportSection.id;
    const head = element("div", "report-section-head");
    head.append(
      element("h3", "", reportSection.title),
      element("span", "pill pill-warn", "FICTIONAL DEMO"),
    );
    block.append(head, element("p", "", reportSection.summary));
    if (reportSection.items && reportSection.items.length) {
      const list = element("ol", "report-items");
      reportSection.items.forEach((item, index) => {
        list.append(renderItem(item, index + 1));
      });
      block.append(list);
    } else {
      block.append(element("p", "empty", reportSection.empty_text));
    }
    block.append(element("p", "ref", reportSection.sources_note));
    return block;
  }

  function renderReport(report, caseId, sequence) {
    // The server supplies structured sections and text from the same state.
    // Download that accepted text instead of fetching a newer report later.
    const sections = report.sections.map(renderSection);
    downloadUrl = URL.createObjectURL(new Blob([report.text], {
      type: "text/plain;charset=utf-8",
    }));
    section.dataset.caseId = caseId;
    notice.textContent = report.reading_note;
    const asOf = report.as_of || {};
    meta.textContent = `Fictional case ${report.case_id} (${report.case_label}). ` +
      `Made from recorded case data only. Record position: event ${asOf.event_id} at ${asOf.occurred_at}.`;
    textLink.href = downloadUrl;
    textLink.download = `${caseId}-plain-language-report.txt`;
    container.replaceChildren(...sections);
    acceptedCase = caseId;
    acceptedSequence = sequence;
    textLink.setAttribute("aria-disabled", "false");
    textLink.tabIndex = 0;
    printButton.disabled = false;
    section.setAttribute("aria-busy", "false");
  }

  async function refreshReport(sequence) {
    const caseId = picker.value;
    if (!caseId || hasPendingWrites(caseId)) return;
    meta.textContent = "Loading the plain-language report…";
    section.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(`/api/cases/${encodeURIComponent(caseId)}/patient-report`, {
        cache: "no-store",
      });
      const payload = await response.json();
      if (sequence !== requestSequence || picker.value !== caseId || hasPendingWrites(caseId)) return;
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      if (!payload || payload.case_id !== caseId || typeof payload.text !== "string" ||
          !Array.isArray(payload.sections)) {
        throw new Error("Report does not match the selected case or lacks its text snapshot.");
      }
      renderReport(payload, caseId, sequence);
    } catch (error) {
      if (sequence !== requestSequence || picker.value !== caseId) return;
      invalidateReport();
      meta.textContent = "Plain-language report unavailable.";
      container.replaceChildren(element(
        "p", "empty", error instanceof Error ? error.message : "Unknown error",
      ));
    }
  }

  function scheduleRefresh() {
    // Invalidate synchronously, including an older in-flight same-case read.
    invalidateReport();
    if (hasPendingWrites()) return;
    scheduledSequence = requestSequence;
    if (refreshScheduled) return;
    refreshScheduled = true;
    queueMicrotask(() => {
      refreshScheduled = false;
      const sequence = scheduledSequence;
      scheduledSequence = null;
      // A mutation can invalidate a queued refresh before this microtask runs.
      if (sequence === requestSequence) refreshReport(sequence);
    });
  }

  printButton.addEventListener("click", () => {
    if (!reportIsCurrent()) return;
    document.body.classList.add("printing-patient-report");
    try {
      window.print();
    } finally {
      document.body.classList.remove("printing-patient-report");
    }
  });
  textLink.addEventListener("click", event => {
    if (!reportIsCurrent()) event.preventDefault();
  });
  refreshButton.addEventListener("click", scheduleRefresh);
  picker.addEventListener("change", scheduleRefresh);
  document.addEventListener("oi:case-state-invalidated", event => {
    // State-read refreshes omit the count; they must not erase pending writes.
    recordPendingWrites(event.detail);
    if (event.detail?.scope === "all-cases" || event.detail?.caseId === picker.value) {
      invalidateReport();
    }
  });
  document.addEventListener("oi:case-state-write-settled", event => {
    recordPendingWrites(event.detail);
    if (event.detail?.scope !== "all-cases" && event.detail?.caseId !== picker.value) return;
    refreshButton.disabled = hasPendingWrites();
    if (!hasPendingWrites() && acceptedCase === null) {
      meta.textContent = "Refresh the report to check the current record.";
    }
    // A successful write is followed by the host's accepted state update.
    // A failed write only unlocks manual retry; it cannot restore old content.
  });
  document.addEventListener("oi:case-state-updated", event => {
    if (event.detail?.caseId === picker.value) scheduleRefresh();
  });
  window.addEventListener("pagehide", invalidateReport);
  window.addEventListener("pageshow", event => {
    if (event.persisted) scheduleRefresh();
  });
  scheduleRefresh();
})();
