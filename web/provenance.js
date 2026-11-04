(() => {
  "use strict";

  const picker = document.querySelector("#case-picker");
  const section = document.querySelector("#provenance");
  const status = document.querySelector("#provenance-status");
  const list = document.querySelector("#provenance-list");
  const eventList = document.querySelector("#event-list");

  if (!picker || !section || !status || !list) {
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

  function empty(container, message) {
    container.replaceChildren(element("p", "empty", message));
  }

  function stateLabel(state) {
    if (state === "current") return "CURRENT";
    if (state === "superseded") return "SUPERSEDED — kept for history";
    return String(state || "unknown");
  }

  function reviewLabel(state) {
    if (state === "draft") return "draft (not yet reviewed)";
    if (state === "reviewed_in_demo") return "reviewed in demo (not clinical sign-off)";
    if (state === "stale") return "stale (needs another look)";
    return String(state || "unknown");
  }

  function versionCard(link, caseId) {
    const card = element("div", "snapshot");
    const top = element("div", "topline");
    const statePill = link.state === "current"
      ? element("span", "pill", stateLabel(link.state))
      : element("span", "pill pill-warn", stateLabel(link.state));
    top.append(
      element("strong", "", link.anchor + " · version " + link.version),
      statePill,
      element("span", "pill pill-neutral", "FICTIONAL")
    );
    card.append(top);
    const supersedes = link.supersedes_source_id === null || link.supersedes_source_id === undefined
      ? "Original version; it amends nothing."
      : "Amends source version #" + link.supersedes_source_id + ".";
    const supersededBy = link.superseded_by_source_id === null || link.superseded_by_source_id === undefined
      ? "No later version has replaced it."
      : "Replaced by source version #" + link.superseded_by_source_id + "; this version is kept.";
    card.append(element("p", "snapshot-meta",
      "Received " + link.received_date + " · Issued " + link.issued_at +
      " · Event " + link.event_date + " · SHA " + String(link.sha256).slice(0, 12) + "…"));
    card.append(element("p", "muted", supersedes + " " + supersededBy));
    card.append(element("p", "ref", "Exact anchor: " + link.anchor));
    const citing = link.citing_snapshots || [];
    if (!citing.length) {
      card.append(element("p", "muted", "No saved investigations cite this version."));
    } else {
      for (const cite of citing) {
        card.append(element("p", "muted",
          "Cited by Investigation #" + cite.snapshot_id +
          " (question Q" + cite.question_id + "): " + reviewLabel(cite.state) + "."));
      }
    }
    const actions = element("div", "actions");
    const validSource = Number.isSafeInteger(link.source_id) && link.source_id > 0;
    const button = element("button", "button secondary minor",
      validSource ? "View " + link.anchor + " original text" : "Exact source version unavailable");
    button.type = "button";
    button.disabled = !validSource;
    const pre = document.createElement("pre");
    pre.hidden = true;
    let loaded = false;
    let loading = false;
    button.addEventListener("click", async () => {
      if (loading || !validSource) return;
      if (loaded && !pre.hidden) {
        pre.hidden = true;
        button.textContent = "View " + link.anchor + " original text";
        return;
      }
      if (loaded && pre.hidden) {
        pre.hidden = false;
        button.textContent = "Hide " + link.anchor + " original text";
        return;
      }
      const requestedCase = picker.value;
      if (!requestedCase || requestedCase !== caseId) return;
      loading = true;
      button.disabled = true;
      button.textContent = "Loading " + link.anchor + "…";
      try {
        const response = await fetch(
          "/api/cases/" + encodeURIComponent(requestedCase) + "/sources/" + link.source_id,
          {cache: "no-store"}
        );
        const payload = await response.json();
        if (picker.value !== requestedCase || section.dataset.caseId !== requestedCase) return;
        if (!response.ok) throw new Error(payload.error || ("HTTP " + response.status));
        if (typeof payload.text !== "string") throw new Error("Original source text is unavailable.");
        pre.textContent = payload.text;
        pre.hidden = false;
        loaded = true;
        button.textContent = "Hide " + link.anchor + " original text";
      } catch (error) {
        if (picker.value !== requestedCase) return;
        pre.textContent = error instanceof Error ? error.message : "Unknown error";
        pre.hidden = false;
        button.textContent = "View " + link.anchor + " original text";
      } finally {
        loading = false;
        button.disabled = false;
      }
    });
    actions.append(button);
    card.append(actions);
    card.append(pre);
    return card;
  }

  function documentCard(doc, caseId) {
    const card = element("article", "source-card");
    const top = element("div", "source-top");
    const count = doc.chain_length === 1 ? "1 version" : doc.chain_length + " versions";
    top.append(
      element("span", "source-title", doc.document_id + " · FICTIONAL"),
      element("span", "pill pill-neutral", count),
      element("span", "pill pill-warn", "FICTIONAL")
    );
    card.append(top);
    card.append(element("p", "snapshot-meta",
      doc.kind + " · Event " + doc.event_date +
      (doc.specimen_id ? " · Specimen " + doc.specimen_id : " · No specimen recorded")));
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = doc.chain_length === 1
      ? "View the single version (no amendments)"
      : "View the version chain, oldest first (" + doc.chain_length + " versions)";
    details.append(summary);
    for (const link of doc.chain || []) {
      details.append(versionCard(link, caseId));
    }
    const events = doc.chain_events || [];
    for (const event of events) {
      const invalidated = (event.invalidated_snapshots || []).length
        ? "Marked stale: Investigation " + event.invalidated_snapshots.map((id) => "#" + id).join(", ") + "."
        : "No saved investigation cited the replaced version.";
      details.append(element("p", "muted tiny",
        "FICTIONAL chain event: version " + event.version + " received (" +
        (event.occurred_at || "time unavailable") + "). " +
        (event.amends_source_id === null || event.amends_source_id === undefined
          ? "Original version. "
          : "Replaced source version #" + event.amends_source_id + ". ") + invalidated));
    }
    card.append(details);
    return card;
  }

  function renderProvenance(payload, caseId) {
    section.dataset.caseId = caseId;
    const documents = payload.documents || [];
    const counts = payload.counts || {};
    status.textContent = documents.length === 1
      ? "1 document · " + (counts.versions || documents.length) + " versions"
      : documents.length + " documents · " + (counts.versions || 0) + " versions";
    status.className = "pill";
    if (!documents.length) {
      empty(list, "No source documents in this fictional case yet.");
      return;
    }
    list.replaceChildren(...documents.map((doc) => documentCard(doc, caseId)));
  }

  async function refreshProvenance() {
    const caseId = picker.value;
    if (!caseId) return;
    const sequence = ++requestSequence;
    status.textContent = "Loading…";
    status.className = "pill pill-neutral";
    list.replaceChildren();
    try {
      const response = await fetch("/api/cases/" + encodeURIComponent(caseId) + "/provenance", {
        cache: "no-store",
      });
      const payload = await response.json();
      if (sequence !== requestSequence || picker.value !== caseId) return;
      if (!response.ok) throw new Error(payload.error || ("HTTP " + response.status));
      renderProvenance(payload, caseId);
    } catch (error) {
      if (sequence !== requestSequence || picker.value !== caseId) return;
      section.dataset.caseId = caseId;
      status.textContent = "Unavailable";
      status.className = "pill pill-alert";
      empty(list, error instanceof Error ? error.message : "Unknown error");
    }
  }

  function scheduleRefresh() {
    if (refreshScheduled) return;
    refreshScheduled = true;
    queueMicrotask(() => {
      refreshScheduled = false;
      refreshProvenance();
    });
  }

  picker.addEventListener("change", scheduleRefresh);
  if (eventList) {
    const observer = new MutationObserver(scheduleRefresh);
    observer.observe(eventList, {childList: true});
  }
  scheduleRefresh();
})();
