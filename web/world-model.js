// Source-linked Patient World Model inspector. Synthetic-only; no second patient store.
(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const picker = byId("case-picker");
  const detail = byId("world-model-detail");
  const status = byId("world-model-status");
  const summary = byId("world-model-summary");
  const observations = byId("world-model-observations");
  const conflicts = byId("world-model-conflicts");
  const history = byId("world-model-history");
  const eventList = byId("event-list");
  if (![picker, detail, status, summary, observations, conflicts, history].every(Boolean)) return;

  let requestSequence = 0;
  let scheduled = false;
  const txt = (value) => value == null ? "not supplied" : String(value);

  function line(parent, value) {
    const item = document.createElement("li");
    item.textContent = value; // A quoted source is always TEXT, never HTML.
    parent.append(item);
  }
  function clear() {
    summary.replaceChildren();
    observations.replaceChildren();
    conflicts.replaceChildren();
    history.replaceChildren();
    delete detail.dataset.caseId;
  }
  function render(payload, expectedCase) {
    if (payload.contract !== "oi.synthetic-world-model/1" ||
        payload.synthetic !== true || payload.case_id !== expectedCase ||
        payload.authority !== "source_report_only_unreviewed") {
      throw new Error("World Model source/scope contract mismatch");
    }
    const s = payload.summary;
    if (!s || !Array.isArray(payload.observations) ||
        !Array.isArray(payload.conflicts) || !Array.isArray(payload.history)) {
      throw new Error("Incomplete World Model source projection");
    }
    const metrics = [
      ["Current sources", s.current_sources],
      ["Reported observations", s.current_observations],
      ["Unresolved reported states", s.unresolved_observations],
      ["Unadjudicated source disagreements", s.source_disagreements],
    ];
    for (const [name, value] of metrics) {
      const p = document.createElement("p");
      p.textContent = name + ": " + txt(value);
      summary.append(p);
    }
    const maxVisible = 30;
    for (const finding of payload.observations.slice(0, maxVisible)) {
      const source = txt(finding.document_id) + " v" + txt(finding.document_version) +
        ", source #" + txt(finding.source_version_id) + " line " + txt(finding.source_line);
      line(observations, txt(finding.finding_key) + " · " +
        txt(finding.reported_state) + " · " + txt(finding.source_statement) +
        " — " + source + "; event " + txt(finding.event_date) +
        "; issued " + txt(finding.issued_at) + "; received " + txt(finding.received_at) +
        "; SHA-256 " + txt(finding.source_sha256));
    }
    if (!payload.observations.length) line(observations, "No current source-reported observations.");
    if (payload.observations.length > maxVisible) {
      line(observations, "Showing the first 30 source observations; inspect the original records for the full case.");
    }
    for (const conflict of payload.conflicts) {
      const refs = (conflict.observation_refs || []).map(
        (r) => "#" + txt(r.assertion_id) + " (source " + txt(r.source_version_id) +
          ", line " + txt(r.source_line) + ")"
      );
      line(conflicts, "Unresolved: " + txt(conflict.finding_key) + ", specimen " +
        txt(conflict.specimen_id) + ", event " + txt(conflict.event_date) +
        "; opposing records: " + refs.join("; "));
    }
    if (!payload.conflicts.length) {
      line(conflicts, "No narrowly defined same-specimen disagreement found. This does not establish clinical agreement.");
    }
    const review = payload.review_needed || {};
    const reviewLine = document.createElement("p");
    reviewLine.textContent = "Open question IDs: " + txt((review.open_question_ids || []).join(", ") || "none recorded") +
      ". Draft snapshots: " + txt((review.draft_snapshot_ids || []).join(", ") || "none") +
      ". Historical stale reports: " + txt((review.stale_snapshot_ids || []).join(", ") || "none") + ".";
    history.append(reviewLine);
    for (const older of payload.history.slice(0, maxVisible)) {
      const p = document.createElement("p");
      p.textContent = "Superseded: " + txt(older.document_id) + " v" + txt(older.version) +
        " (source #" + txt(older.source_version_id) + ", SHA-256 " +
        txt(older.source_sha256) + ")";
      history.append(p);
    }
    if (payload.history.length > maxVisible) {
      const p = document.createElement("p");
      p.textContent = "More prior versions remain available in the original source record.";
      history.append(p);
    }
    detail.dataset.caseId = expectedCase;
    status.textContent = "Fictional source observations · no clinical interpretation or review attestation.";
  }
  async function refresh() {
    const expectedCase = picker.value;
    const currentRequest = ++requestSequence;
    clear(); // Never leave case A's facts visible while case B is loading.
    if (!detail.open || !expectedCase) {
      status.textContent = "Expand to inspect source-linked observations.";
      return;
    }
    status.textContent = "Loading source provenance…";
    try {
      const response = await fetch("/api/cases/" + encodeURIComponent(expectedCase) +
        "/world-model", {cache: "no-store"});
      const payload = await response.json();
      if (currentRequest !== requestSequence || !detail.open ||
          picker.value !== expectedCase) return;
      if (!response.ok) throw new Error(payload.error || "World Model request failed");
      render(payload, expectedCase);
    } catch (err) {
      if (currentRequest !== requestSequence || !detail.open ||
          picker.value !== expectedCase) return;
      clear();
      status.textContent = "World Model unavailable: " +
        (err instanceof Error ? err.message : "unknown error");
    }
  }
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      if (detail.open) refresh();
    });
  }
  picker.addEventListener("change", () => {
    // Invalidate immediately, then let app.js accept or veto the selection.
    // Its draft guard is installed after asynchronous initialization and can
    // restore the prior case without emitting another change event.
    ++requestSequence;
    clear();
    status.textContent = detail.open ? "Loading source provenance…" :
      "Expand to inspect source-linked observations.";
    schedule();
  });
  detail.addEventListener("toggle", refresh);
  if (eventList) new MutationObserver(schedule).observe(eventList, {childList: true});
})();
