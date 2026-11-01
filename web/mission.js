(() => {
  "use strict";

  const picker = document.querySelector("#case-picker");
  const section = document.querySelector("#patient-mission");
  const status = document.querySelector("#mission-status");
  const summary = document.querySelector("#mission-summary");
  const known = document.querySelector("#mission-known");
  const unresolved = document.querySelector("#mission-unresolved");
  const changes = document.querySelector("#mission-changes");
  const actions = document.querySelector("#mission-actions");
  const guardrails = document.querySelector("#mission-guardrails");
  const eventList = document.querySelector("#event-list");

  if (!picker || !section || !status || !summary || !known || !unresolved ||
      !changes || !actions || !guardrails) {
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

  function tokenLabel(value) {
    const words = String(value || "unknown").split("_");
    const label = words.join(" ");
    return label.charAt(0).toUpperCase() + label.slice(1);
  }

  function empty(container, message) {
    container.replaceChildren(element("p", "empty", message));
  }

  function renderMetrics(mission) {
    const metrics = mission.where_am_i;
    const values = [
      [metrics.current_source_documents, "Current source documents"],
      [metrics.reported_statements, "Source-reported statements"],
      [metrics.open_questions, "Open questions"],
      [metrics.stale_investigations, "Stale investigations"],
      [metrics.quarantined_deliveries, "Quarantined deliveries"],
    ];
    summary.replaceChildren(...values.map(([number, name]) => {
      const card = element("div", "metric");
      card.append(element("span", "number", number), element("span", "name", name));
      return card;
    }));
  }

  function findingCard(item) {
    const card = element("article", "finding");
    const head = element("div", "finding-head");
    head.append(
      element("strong", "", item.finding_key),
      element("span", "pill pill-neutral", tokenLabel(item.state)),
    );
    card.append(
      head,
      element("p", "quoted", item.statement),
      element(
        "div",
        "ref",
        `Source version #${item.source_version_id} · line ${item.source_line}`,
      ),
    );
    return card;
  }

  function renderKnown(mission) {
    const items = mission.what_we_know || [];
    if (!items.length) {
      empty(known, "No current source-reported statements are available.");
      return;
    }
    known.replaceChildren(...items.map(findingCard));
  }

  function renderUnresolved(mission) {
    const state = mission.what_remains_unresolved || {};
    const items = [];
    for (const finding of state.source_findings || []) {
      const card = findingCard(finding);
      card.prepend(element("div", "eyebrow", "SOURCE STATE REQUIRES INTERPRETATION"));
      items.push(card);
    }
    for (const question of state.questions || []) {
      const card = element("article", "source-card");
      card.append(
        element("strong", "source-title", `Q${question.question_id}`),
        element("p", "", question.question),
        element("div", "source-meta", `Recorded ${question.created_at}`),
      );
      items.push(card);
    }
    for (const investigationId of state.stale_investigation_ids || []) {
      const card = element("article", "source-card");
      card.append(
        element("strong", "source-title", `Investigation #${investigationId}`),
        element("p", "", "Stale because a bound source or evidence version changed."),
      );
      items.push(card);
    }
    for (const deliveryId of state.quarantined_delivery_ids || []) {
      const card = element("article", "source-card");
      card.append(
        element("strong", "source-title", `Quarantined delivery #${deliveryId}`),
        element("p", "", "No statements were imported from this mismatched delivery."),
      );
      items.push(card);
    }
    if (!items.length) {
      empty(unresolved, "No unresolved workflow item is represented in the current synthetic ledger.");
      return;
    }
    unresolved.replaceChildren(...items);
  }

  function renderChanges(mission) {
    const items = mission.material_changes || [];
    if (!items.length) {
      empty(changes, "No material amendment, invalidation, or quarantine event is recorded.");
      return;
    }
    changes.replaceChildren(...items.map((item) => {
      const card = element("article", "event");
      card.append(
        element("strong", "", tokenLabel(item.kind)),
        element("p", "", item.summary),
        element("small", "", item.occurred_at || "Time unavailable"),
      );
      return card;
    }));
  }

  function renderActions(mission) {
    const items = mission.next_actions || [];
    if (!items.length) {
      empty(actions, "No bounded workflow action is available.");
      return;
    }
    actions.replaceChildren(...items.map((item) => {
      const card = element("article", "source-card");
      card.append(
        element("strong", "source-title", item.label),
        element("p", "", item.reason),
        element("span", "pill pill-neutral", tokenLabel(item.kind)),
      );
      return card;
    }));
  }

  function renderGuardrails(mission) {
    const items = mission.guardrails || [];
    guardrails.replaceChildren(...items.map((item) => element("li", "", item)));
  }

  function renderMission(mission, caseId) {
    section.dataset.caseId = caseId;
    section.dataset.workflowStatus = mission.workflow_status;
    status.textContent = tokenLabel(mission.workflow_status);
    status.className = mission.workflow_status === "review_required"
      ? "pill pill-alert"
      : mission.workflow_status === "awaiting_sources"
        ? "pill pill-warn"
        : "pill";
    renderMetrics(mission);
    renderKnown(mission);
    renderUnresolved(mission);
    renderChanges(mission);
    renderActions(mission);
    renderGuardrails(mission);
  }

  async function refreshMission() {
    const caseId = picker.value;
    if (!caseId) return;
    const sequence = ++requestSequence;
    status.textContent = "Loading…";
    status.className = "pill pill-neutral";
    try {
      const response = await fetch(`/api/cases/${encodeURIComponent(caseId)}/mission`, {
        cache: "no-store",
      });
      const payload = await response.json();
      if (sequence !== requestSequence || picker.value !== caseId) return;
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      renderMission(payload, caseId);
    } catch (error) {
      if (sequence !== requestSequence || picker.value !== caseId) return;
      section.dataset.caseId = caseId;
      section.dataset.workflowStatus = "unavailable";
      status.textContent = "Unavailable";
      status.className = "pill pill-alert";
      summary.replaceChildren();
      empty(known, "Patient Mission projection could not be loaded.");
      empty(unresolved, "No workflow interpretation was produced.");
      empty(changes, "No material-change view was produced.");
      empty(actions, error instanceof Error ? error.message : "Unknown error");
      guardrails.replaceChildren();
    }
  }

  function scheduleRefresh() {
    if (refreshScheduled) return;
    refreshScheduled = true;
    queueMicrotask(() => {
      refreshScheduled = false;
      refreshMission();
    });
  }

  picker.addEventListener("change", scheduleRefresh);
  if (eventList) {
    const observer = new MutationObserver(scheduleRefresh);
    observer.observe(eventList, {childList: true});
  }
  scheduleRefresh();
})();
