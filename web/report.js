(() => {
  "use strict";

  const picker = document.querySelector("#case-picker");
  const section = document.querySelector("#patient-report");
  const notice = document.querySelector("#report-reading-note");
  const meta = document.querySelector("#report-meta");
  const actions = document.querySelector(".report-actions");
  const printButton = document.querySelector("#report-print");
  const textLink = document.querySelector("#report-text-link");
  const container = document.querySelector("#report-sections");
  const eventList = document.querySelector("#event-list");

  if (!picker || !section || !notice || !meta || !actions ||
      !printButton || !textLink || !container) {
    return;
  }

  let requestSequence = 0;
  let refreshScheduled = false;

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

  function renderReport(report, caseId) {
    section.dataset.caseId = caseId;
    notice.textContent = report.reading_note;
    const asOf = report.as_of || {};
    meta.textContent = `Fictional case ${report.case_id} (${report.case_label}). ` +
      `Made from recorded case data only. Record position: event ${asOf.event_id} at ${asOf.occurred_at}.`;
    textLink.href = `/api/cases/${encodeURIComponent(caseId)}/patient-report?format=text`;
    textLink.download = `${caseId}-plain-language-report.txt`;
    container.replaceChildren(...report.sections.map(renderSection));
  }

  async function refreshReport() {
    const caseId = picker.value;
    if (!caseId) return;
    const sequence = ++requestSequence;
    meta.textContent = "Loading the plain-language report…";
    try {
      const response = await fetch(`/api/cases/${encodeURIComponent(caseId)}/patient-report`, {
        cache: "no-store",
      });
      const payload = await response.json();
      if (sequence !== requestSequence || picker.value !== caseId) return;
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      renderReport(payload, caseId);
    } catch (error) {
      if (sequence !== requestSequence || picker.value !== caseId) return;
      section.dataset.caseId = caseId;
      notice.textContent = "";
      meta.textContent = "Plain-language report unavailable.";
      container.replaceChildren(element(
        "p", "empty", error instanceof Error ? error.message : "Unknown error",
      ));
    }
  }

  function scheduleRefresh() {
    if (refreshScheduled) return;
    refreshScheduled = true;
    queueMicrotask(() => {
      refreshScheduled = false;
      refreshReport();
    });
  }

  printButton.addEventListener("click", () => window.print());
  picker.addEventListener("change", scheduleRefresh);
  if (eventList) {
    const observer = new MutationObserver(scheduleRefresh);
    observer.observe(eventList, {childList: true});
  }
  scheduleRefresh();
})();
