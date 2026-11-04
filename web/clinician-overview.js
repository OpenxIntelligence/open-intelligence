(() => {
  "use strict";

  const picker = document.querySelector("#case-picker");
  const section = document.querySelector("#clinician-overview");
  const stage = document.querySelector("#clinician-overview-stage");
  const disclaimer = document.querySelector("#clinician-overview-disclaimer");
  const counts = document.querySelector("#clinician-overview-counts");
  const sources = document.querySelector("#clinician-overview-sources");
  const questions = document.querySelector("#clinician-overview-questions");
  const pending = document.querySelector("#clinician-overview-pending");
  const tasks = document.querySelector("#clinician-overview-tasks");
  const goals = document.querySelector("#clinician-overview-goals");
  const journey = document.querySelector("#clinician-overview-journey");
  const eventList = document.querySelector("#event-list");

  if (!picker || !section || !stage || !disclaimer || !counts || !sources ||
      !questions || !pending || !tasks || !goals || !journey) {
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

  function fictionalPill() {
    return element("span", "pill pill-neutral", "FICTIONAL");
  }

  function renderCounts(overview) {
    const values = [
      [(overview.current_sources || []).length, "Current sources"],
      [(overview.open_questions || []).length, "Open questions"],
      [(overview.pending_reviews || []).length, "Pending reviews"],
      [(overview.follow_up_tasks || []).length, "Follow-up tasks"],
      [overview.goals ? overview.goals.count : 0, "Goals recorded"],
    ];
    counts.replaceChildren(...values.map(([number, name]) => {
      const card = element("div", "metric");
      card.append(element("span", "number", number), element("span", "name", name));
      return card;
    }));
  }

  function renderSources(overview) {
    const items = overview.current_sources || [];
    if (!items.length) {
      empty(sources, "No current sources recorded for this fictional case.");
      return;
    }
    sources.replaceChildren(...items.map((item) => {
      const card = element("article", "source-card");
      const top = element("div", "source-top");
      top.append(
        element("span", "source-title", `${item.document_id}@${item.version}`),
        fictionalPill(),
      );
      card.append(
        top,
        element("div", "source-meta", `${item.kind} · Event ${item.event_date} · Issued ${item.issued_at}`),
        element("div", "source-meta", String(item.citation)),
      );
      return card;
    }));
  }

  function renderQuestions(overview) {
    const items = overview.open_questions || [];
    if (!items.length) {
      empty(questions, "No open questions recorded for this fictional case.");
      return;
    }
    questions.replaceChildren(...items.map((item) => {
      const row = element("div", "question");
      const text = element("div");
      text.append(
        element("p", "", item.question),
        element("p", "muted tiny", `${item.citation} · Recorded ${item.created_at}`),
      );
      row.append(text, fictionalPill());
      return row;
    }));
  }

  function renderPending(overview) {
    const items = overview.pending_reviews || [];
    if (!items.length) {
      empty(pending, "No items waiting for review in this fictional case.");
      return;
    }
    pending.replaceChildren(...items.map((item) => {
      const box = element("div", "snapshot");
      const top = element("div", "topline");
      const title = item.kind === "snapshot_draft" || item.kind === "snapshot_stale"
        ? `Snapshot #${item.snapshot_id}`
        : item.kind === "option_needs_review"
          ? `Option #${item.option_id}`
          : `Quarantined delivery #${item.quarantine_id}`;
      top.append(element("strong", "", title), fictionalPill());
      box.append(top);
      box.append(element("p", "snapshot-meta", `${tokenLabel(item.kind)} · ${item.citation}`));
      if (item.kind === "option_needs_review" && item.label) {
        box.append(element("p", "", item.label));
      }
      if (item.review_state) {
        box.append(element("span", "pill pill-warn", tokenLabel(item.review_state)));
      }
      return box;
    }));
  }

  function renderTasks(overview) {
    const items = overview.follow_up_tasks || [];
    if (!items.length) {
      empty(tasks, "No follow-up tasks recorded for this fictional case.");
      return;
    }
    tasks.replaceChildren(...items.map((item) => {
      const card = element("article", "source-card");
      const top = element("div", "source-top");
      top.append(element("span", "source-title", item.label), fictionalPill());
      card.append(
        top,
        element("p", "snapshot-meta", `Held by ${item.owner_label} · ${tokenLabel(item.status)}`),
        element("div", "source-meta", String(item.citation)),
      );
      return card;
    }));
  }

  function renderGoals(overview) {
    const data = overview.goals || {count: 0, items: [], note: "", citation: ""};
    if (!data.items || !data.items.length) {
      const card = element("article", "source-card");
      card.append(
        element("span", "source-title", `Goals recorded: ${data.count}`),
        element("p", "", data.note || "No goals recorded in this fictional case file."),
        element("div", "source-meta", String(data.citation || "")),
        fictionalPill(),
      );
      goals.replaceChildren(card);
      return;
    }
    goals.replaceChildren(...data.items.map((item) => {
      const card = element("article", "source-card");
      card.append(
        element("span", "source-title", String(item.label || "Goal")),
        element("div", "source-meta", String(item.citation || "")),
        fictionalPill(),
      );
      return card;
    }));
  }

  function renderJourney(overview) {
    const data = overview.journey_stage;
    if (!data || !data.stage) {
      empty(journey, "Journey stage unavailable for this fictional case.");
      return;
    }
    const basis = data.basis || {};
    const card = element("article", "source-card");
    card.append(
      element("span", "source-title", data.label),
      element("p", "snapshot-meta",
        `Sources ${basis.current_source_documents} · Open questions ${basis.open_questions} · ` +
        `Pending reviews ${basis.pending_reviews} · Pending tasks ${basis.pending_tasks}`),
      element("div", "source-meta", String(data.citation || "")),
      fictionalPill(),
    );
    journey.replaceChildren(card);
  }

  function renderOverview(overview, caseId) {
    section.dataset.caseId = caseId;
    section.dataset.journeyStage = overview.journey_stage.stage;
    stage.textContent = overview.journey_stage.label;
    stage.className = overview.journey_stage.stage === "review_required"
      ? "pill pill-alert"
      : overview.journey_stage.stage === "awaiting_sources"
        ? "pill pill-warn"
        : "pill";
    disclaimer.textContent = overview.disclaimer;
    renderCounts(overview);
    renderSources(overview);
    renderQuestions(overview);
    renderPending(overview);
    renderTasks(overview);
    renderGoals(overview);
    renderJourney(overview);
  }

  async function refreshOverview() {
    const caseId = picker.value;
    if (!caseId) return;
    const sequence = ++requestSequence;
    stage.textContent = "Loading…";
    stage.className = "pill pill-neutral";
    try {
      const response = await fetch(`/api/cases/${encodeURIComponent(caseId)}/clinician-overview`, {
        cache: "no-store",
      });
      const payload = await response.json();
      if (sequence !== requestSequence || picker.value !== caseId) return;
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      renderOverview(payload, caseId);
    } catch (error) {
      if (sequence !== requestSequence || picker.value !== caseId) return;
      section.dataset.caseId = caseId;
      section.dataset.journeyStage = "unavailable";
      stage.textContent = "Unavailable";
      stage.className = "pill pill-alert";
      counts.replaceChildren();
      empty(sources, "Clinician overview could not be loaded.");
      empty(questions, "No question view was produced.");
      empty(pending, "No review view was produced.");
      empty(tasks, "No task view was produced.");
      empty(goals, "No goals view was produced.");
      empty(journey, error instanceof Error ? error.message : "Unknown error");
    }
  }

  function scheduleRefresh() {
    if (refreshScheduled) return;
    refreshScheduled = true;
    queueMicrotask(() => {
      refreshScheduled = false;
      refreshOverview();
    });
  }

  picker.addEventListener("change", scheduleRefresh);
  if (eventList) {
    const observer = new MutationObserver(scheduleRefresh);
    observer.observe(eventList, {childList: true});
  }
  scheduleRefresh();
})();
