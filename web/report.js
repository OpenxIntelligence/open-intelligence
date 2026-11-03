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

  function validateSourceReferences(report) {
    // These checks preserve the server snapshot's declared associations. The
    // source owner remains responsible for authenticating its actual records.
    const baseFields = ['assertion_id', 'source_version_id', 'document_id',
      'document_version', 'sha256', 'source_line'];
    const manualFields = ['classification_origin', 'annotation_method', 'clinical_review',
      'annotation_revision_id', 'annotation_revision', 'initial_transcription_review_sha256',
      'transcription_review_sha256'];
    const pdfFields = ['text_origin', 'extraction_sha256', 'source_page', 'page_line', 'page_text_sha256'];
    const sourceFields = ['source_version_id', 'document_id', 'document_version', 'sha256',
      ...manualFields, 'text_origin', 'extraction_sha256'];
    const bySource = new Map(), byRevision = new Map(), byAssertion = new Map();
    const byPage = new Map(), byExtractionLine = new Map(), byPageLine = new Map();
    const positive = value => Number.isSafeInteger(value) && value > 0;
    const digest = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
    const fail = () => { throw new Error('Report source revision provenance is incomplete or inconsistent.'); };
    for (const reportSection of report.sections) {
      for (const item of reportSection.items || []) {
        if (!Object.prototype.hasOwnProperty.call(item, 'source_reference')) continue;
        const reference = item.source_reference;
        if (!reference || typeof reference !== 'object' || Array.isArray(reference)) fail();
        const pdf = reference.text_origin === 'pdf_extraction';
        const fields = [...baseFields, ...manualFields, ...(pdf ? pdfFields : [])];
        if (Object.keys(reference).length !== fields.length ||
            fields.some(field => !Object.prototype.hasOwnProperty.call(reference, field))) fail();
        if (!['assertion_id', 'source_version_id', 'document_version', 'source_line',
          'annotation_revision_id', 'annotation_revision'].every(field => positive(reference[field])) ||
            reference.source_line > 512 ||
            typeof reference.document_id !== 'string' || !reference.document_id.trim() ||
            !['sha256', 'initial_transcription_review_sha256', 'transcription_review_sha256']
              .every(field => digest(reference[field])) ||
            reference.classification_origin !== 'user_selected' ||
            reference.clinical_review !== 'not_performed' ||
            reference.annotation_method !== (pdf ? 'manual-exact-extraction-line-selection' : 'manual-exact-line-selection') ||
            (reference.annotation_revision === 1 &&
              reference.initial_transcription_review_sha256 !== reference.transcription_review_sha256)) fail();
        if (pdf && (!positive(reference.source_page) || reference.source_page > 20 ||
            !positive(reference.page_line) || reference.page_line > reference.source_line ||
            !digest(reference.extraction_sha256) || !digest(reference.page_text_sha256))) fail();
        if (pdf) {
          // A frozen extraction has one digest per page and a one-to-one
          // mapping between global lines and page-local coordinates. Different
          // assertions may cite that same location, including across sections.
          const page = JSON.stringify([reference.source_version_id, reference.source_page]);
          const line = JSON.stringify([reference.source_version_id, reference.source_line]);
          const pageLine = JSON.stringify([reference.source_version_id, reference.source_page, reference.page_line]);
          if ((byPage.has(page) && byPage.get(page) !== reference.page_text_sha256) ||
              (byExtractionLine.has(line) && byExtractionLine.get(line) !== pageLine) ||
              (byPageLine.has(pageLine) && byPageLine.get(pageLine) !== line)) fail();
          byPage.set(page, reference.page_text_sha256);
          byExtractionLine.set(line, pageLine);
          byPageLine.set(pageLine, line);
        }
        const sourceIdentity = JSON.stringify(sourceFields.map(field => reference[field]));
        const assertionIdentity = JSON.stringify(fields.map(field => reference[field]));
        if ((bySource.has(reference.source_version_id) &&
              bySource.get(reference.source_version_id) !== sourceIdentity) ||
            (byRevision.has(reference.annotation_revision_id) &&
              byRevision.get(reference.annotation_revision_id) !== reference.source_version_id) ||
            (byAssertion.has(reference.assertion_id) &&
              byAssertion.get(reference.assertion_id) !== assertionIdentity)) fail();
        bySource.set(reference.source_version_id, sourceIdentity);
        byRevision.set(reference.annotation_revision_id, reference.source_version_id);
        byAssertion.set(reference.assertion_id, assertionIdentity);
      }
    }
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
      validateSourceReferences(payload);
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

