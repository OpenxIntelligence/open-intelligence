(() => {
  "use strict";

  // Read-only B-11 enrichment panels. Each panel projects one GET route over
  // the existing synthetic case ledger; nothing here writes, infers clinical
  // meaning, or creates a second record. All text is set via textContent.

  const picker = document.querySelector("#case-picker");
  const eventList = document.querySelector("#event-list");

  const visitsSection = document.querySelector("#enrichment-visits");
  const visitsStatus = document.querySelector("#visits-status");
  const visitsList = document.querySelector("#visits-list");
  const visitsUngrouped = document.querySelector("#visits-ungrouped");

  const journeySection = document.querySelector("#enrichment-journey");
  const journeyStatus = document.querySelector("#journey-status");
  const journeyRule = document.querySelector("#journey-rule");
  const journeyStages = document.querySelector("#journey-stages");
  const journeyEvents = document.querySelector("#journey-events");

  const biologySection = document.querySelector("#enrichment-biology");
  const biologyStatus = document.querySelector("#biology-status");
  const biologyList = document.querySelector("#biology-list");

  if (!picker || !visitsSection || !visitsStatus || !visitsList || !visitsUngrouped ||
      !journeySection || !journeyStatus || !journeyRule || !journeyStages || !journeyEvents ||
      !biologySection || !biologyStatus || !biologyList) {
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

  function tokenLabel(value) {
    const words = String(value || "unknown").split("_");
    const label = words.join(" ");
    return label.charAt(0).toUpperCase() + label.slice(1);
  }

  function sourceRef(source) {
    let text = `${source.document_id}@${source.version} · ${source.kind} · ` +
      `event ${source.occurred} · issued ${source.documented} · ${source.state}`;
    if (source.state === "superseded" && source.superseded_by_source_id) {
      text += ` · superseded by source #${source.superseded_by_source_id}`;
    }
    return element("div", "ref", text);
  }

  function renderVisits(payload, caseId) {
    visitsSection.dataset.caseId = caseId;
    visitsStatus.textContent = `${payload.counts.visits} grouping(s)`;
    visitsStatus.className = "pill";
    if (payload.empty_statement) {
      empty(visitsList, payload.empty_statement);
    } else {
      visitsList.replaceChildren(...payload.visits.map((group) => {
        const card = element("article", "source-card");
        const head = element("div", "source-top");
        head.append(
          element("strong", "source-title", `Occurred ${group.occurred}`),
          element("span", "pill pill-neutral", "Date grouping · not an entity"),
        );
        card.append(head);
        for (const source of group.sources) {
          card.append(sourceRef(source));
        }
        for (const historic of group.superseded_versions) {
          card.append(element("div", "ref",
            `${historic.document_id}@${historic.version} · superseded · ` +
            `history preserved · superseded by source #${historic.superseded_by_source_id}`));
          for (const finding of historic.reported_findings || []) {
            card.append(element("p", "muted tiny",
              `Superseded finding: ${finding.finding_key} (${finding.reported_state}) · ` +
              `source #${historic.source_id} · line ${finding.source_line}`));
          }
        }
        for (const assertion of group.assertions) {
          card.append(element("p", "quoted",
            `${assertion.finding_key} (${assertion.reported_state}): ${assertion.statement}`));
          card.append(element("div", "ref",
            `Source version #${assertion.source_version_id} · line ${assertion.source_line}`));
        }
        for (const snapshot of group.snapshots) {
          let text = `Investigation #${snapshot.snapshot_id} · question #${snapshot.question_id} · ${snapshot.state}`;
          for (const pointer of snapshot.supersession_pointers) {
            text += ` · stale on ${pointer.document_id} #${pointer.superseded_source_id}, ` +
              `superseded by #${pointer.superseded_by_source_id}`;
          }
          card.append(element("p", "", text));
        }
        for (const question of group.questions) {
          card.append(element("p", "muted",
            `Q${question.question_id} (${question.state}): ${question.question}`));
        }
        return card;
      }));
    }
    const ungroupedItems = [];
    for (const historic of payload.ungrouped_history || []) {
      const card = element("article", "source-card");
      card.append(
        element("strong", "source-title",
          `${historic.document_id}@${historic.version} · superseded history without a current grouping date`),
        element("div", "source-meta",
          `Occurred ${historic.occurred} · superseded by source #${historic.superseded_by_source_id}`),
      );
      ungroupedItems.push(card);
    }
    for (const question of payload.ungrouped_questions) {
      const card = element("article", "source-card");
      card.append(
        element("strong", "source-title", `Q${question.question_id} (${question.state})`),
        element("p", "", question.question),
        element("div", "source-meta", question.reason),
      );
      ungroupedItems.push(card);
    }
    if (!ungroupedItems.length) {
      empty(visitsUngrouped, "Every recorded question is grouped under an occurred date.");
    } else {
      visitsUngrouped.replaceChildren(...ungroupedItems);
    }
  }

  function renderJourney(payload, caseId) {
    journeySection.dataset.caseId = caseId;
    journeySection.dataset.currentStage = payload.current_stage;
    journeyStatus.textContent = tokenLabel(payload.current_stage);
    journeyStatus.className = payload.current_stage === "review_required"
      ? "pill pill-alert"
      : payload.current_stage === "pre_first_source"
        ? "pill pill-warn"
        : "pill";
    const ruleList = element("ul", "muted tiny");
    for (const item of payload.rule.mapping) {
      ruleList.append(element("li", "", `${item.label}: ${item.condition}`));
    }
    journeyRule.replaceChildren(
      element("p", "", `${payload.rule.name} v${payload.rule.version}: ${payload.rule.description}`),
      ruleList,
    );
    if (payload.empty_statement) {
      empty(journeyStages, payload.empty_statement);
    } else {
      journeyStages.replaceChildren(...payload.stages.map((stage) => {
        const card = element("article", "source-card");
        const head = element("div", "source-top");
        head.append(
          element("strong", "source-title", stage.label),
          element("span", stage.current ? "pill" : "pill pill-neutral",
            stage.current ? "Current stage" : "Not current"),
        );
        card.append(head, element("p", "muted", stage.condition));
        const facts = stage.supporting_facts;
        const lines = [];
        if (facts.current_source_count !== undefined) {
          lines.push(`Current sources: ${facts.current_source_count}`);
        }
        if (facts.current_source_ids) {
          lines.push(`Current source ids: ${facts.current_source_ids.join(", ") || "none"}`);
        }
        if (facts.open_question_ids) {
          lines.push(`Open questions: ${facts.open_question_ids.map((id) => `Q${id}`).join(", ") || "none"}`);
          lines.push(`Draft investigations: ${facts.draft_snapshot_ids.map((id) => `#${id}`).join(", ") || "none"}`);
        }
        if (facts.stale_snapshot_ids) {
          lines.push(`Stale investigations: ${facts.stale_snapshot_ids.map((id) => `#${id}`).join(", ") || "none"}`);
          lines.push(`Quarantined deliveries: ${facts.quarantine_ids.map((id) => `#${id}`).join(", ") || "none"}`);
        }
        if (facts.reviewed_snapshot_ids) {
          lines.push(`Reviewed investigations: ${facts.reviewed_snapshot_ids.map((id) => `#${id}`).join(", ") || "none"}`);
        }
        for (const line of lines) {
          card.append(element("div", "source-meta", line));
        }
        return card;
      }));
    }
    const span = payload.timeline_span;
    const spanText = span.first_occurred
      ? `Timeline span: ${span.first_occurred} to ${span.last_occurred} · ` +
        `${span.entries} current source(s) · ${span.gaps} gap(s) · ` +
        `${span.conflicts} conflict(s) · ${span.superseded_versions} superseded version(s).`
      : "Timeline span: no current sources recorded.";
    if (!payload.stage_evidence_events.length) {
      journeyEvents.replaceChildren(
        element("p", "muted", spanText),
        element("p", "empty", "No stage-evidence events recorded."),
      );
    } else {
      journeyEvents.replaceChildren(
        element("p", "muted", spanText),
        ...payload.stale_investigation_pointers.map((pointer) => {
          const cited = pointer.cited_sources.map((source) =>
            `${source.document_id}@${source.version} (${source.state}` +
            (source.state === "superseded" && source.superseded_by_source_id
              ? `, superseded by #${source.superseded_by_source_id}` : "") + ")").join("; ");
          return element("p", "", `Investigation #${pointer.snapshot_id} is stale · cites: ${cited || "none"}.`);
        }),
        ...payload.stage_evidence_events.map((event) => {
          const card = element("article", "event");
          card.append(
            element("strong", "", tokenLabel(event.kind)),
            element("p", "", event.summary),
            element("small", "", event.occurred_at || "Time unavailable"),
          );
          return card;
        }),
      );
    }
  }

  function renderBiology(payload, caseId) {
    biologySection.dataset.caseId = caseId;
    biologyStatus.textContent = `${payload.counts.assets} asset(s)`;
    biologyStatus.className = "pill";
    if (payload.empty_statement) {
      empty(biologyList, payload.empty_statement);
      return;
    }
    biologyList.replaceChildren(...payload.assets.map((asset) => {
      const card = element("article", "finding");
      const head = element("div", "finding-head");
      head.append(
        element("strong", "", `${asset.asset_id} · ${asset.kind}`),
        element("span", "pill pill-neutral", `Episode ${asset.episode_id}`),
      );
      card.append(head, element("p", "", asset.description));
      const anchor = asset.creation_anchor;
      let anchorText = `Creation anchor: source #${anchor.source_version_id}`;
      if (anchor.known) {
        anchorText += ` (${anchor.document_id}@${anchor.version} · ${anchor.state})`;
        if (anchor.state === "superseded" && anchor.superseded_by_source_id) {
          anchorText += ` · superseded by source #${anchor.superseded_by_source_id}`;
        }
      }
      card.append(element("div", "ref", anchorText));
      if (asset.parent) {
        card.append(element("p", "muted tiny",
          `Derived from ${asset.parent.asset_id} (${asset.parent.kind}); lineage shown, never merged.`));
      } else {
        card.append(element("p", "muted tiny", "Original — no parent."));
      }
      if (asset.pointer_label) {
        card.append(element("p", "muted tiny",
          `Pointer label only, no file stored: ${asset.pointer_label}`));
      }
      if (asset.inventory_note) {
        card.append(element("p", "muted", asset.inventory_note));
      }
      for (const item of asset.inventory_assertions) {
        const box = element("div", "snapshot");
        const top = element("div", "topline");
        top.append(
          element("strong", "", `Inventory assertion #${item.id} · ${item.asserted_by}`),
          element("span", item.state === "stale" ? "pill pill-alert" : "pill pill-neutral", item.state),
        );
        box.append(top);
        for (const [name, field] of Object.entries(item.fields)) {
          box.append(element("p", "snapshot-meta", field.state === "known"
            ? `${name}: ${field.value}`
            : `${name.toUpperCase()}: UNKNOWN (explicit — not absent)`));
        }
        let ref = `Source version #${item.anchor.source_version_id}`;
        if (item.anchor.known) {
          ref += ` (${item.anchor.document_id}@${item.anchor.version} · ${item.anchor.state})`;
          if (item.anchor.state === "superseded" && item.anchor.superseded_by_source_id) {
            ref += ` · STALE: source amended; superseded by #${item.anchor.superseded_by_source_id}`;
          }
        }
        box.append(element("span", "ref", ref));
        card.append(box);
      }
      return card;
    }));
  }

  async function refreshEnrichments() {
    const caseId = picker.value;
    if (!caseId) return;
    const sequence = ++requestSequence;
    visitsStatus.textContent = "Loading…";
    journeyStatus.textContent = "Loading…";
    biologyStatus.textContent = "Loading…";
    try {
      const paths = ["visits", "journey-stages", "biological-context"];
      const responses = await Promise.all(paths.map((name) =>
        fetch(`/api/cases/${encodeURIComponent(caseId)}/${name}`, {cache: "no-store"})));
      const payloads = await Promise.all(responses.map((response) => response.json()));
      if (sequence !== requestSequence || picker.value !== caseId) return;
      const failed = responses.findIndex((response) => !response.ok);
      if (failed !== -1) {
        throw new Error(payloads[failed].error || `HTTP ${responses[failed].status}`);
      }
      const [visits, journey, biology] = payloads;
      if (visits.case_id !== caseId || journey.case_id !== caseId || biology.case_id !== caseId) return;
      renderVisits(visits, caseId);
      renderJourney(journey, caseId);
      renderBiology(biology, caseId);
    } catch (error) {
      if (sequence !== requestSequence || picker.value !== caseId) return;
      visitsSection.dataset.caseId = caseId;
      journeySection.dataset.caseId = caseId;
      biologySection.dataset.caseId = caseId;
      visitsStatus.textContent = "Unavailable";
      visitsStatus.className = "pill pill-alert";
      journeyStatus.textContent = "Unavailable";
      journeyStatus.className = "pill pill-alert";
      biologyStatus.textContent = "Unavailable";
      biologyStatus.className = "pill pill-alert";
      empty(visitsList, "Visit groupings could not be loaded.");
      empty(visitsUngrouped, "No grouping view was produced.");
      empty(journeyStages, "Journey stages could not be loaded.");
      empty(journeyEvents, error instanceof Error ? error.message : "Unknown error");
      journeyRule.replaceChildren();
      empty(biologyList, "Biological context could not be loaded.");
    }
  }

  function scheduleRefresh() {
    if (refreshScheduled) return;
    refreshScheduled = true;
    queueMicrotask(() => {
      refreshScheduled = false;
      refreshEnrichments();
    });
  }

  picker.addEventListener("change", scheduleRefresh);
  if (eventList) {
    const observer = new MutationObserver(scheduleRefresh);
    observer.observe(eventList, {childList: true});
  }
  scheduleRefresh();
})();
