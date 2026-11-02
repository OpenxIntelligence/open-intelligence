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

// Begin question review handoff.
// Derived from existing question/snapshot/source links; never a second review ledger.
function questionReviewItems(state) {
  const required = currentReviewQuestionIds(state);
  const sources = new Map(state.sources.map(s => [Number(s.id), s]));
  const evidence = new Map((state.evidence || []).map(e => [Number(e.id), e]));
  const assessments = new Map((state.evidence_assessments || []).map(a => [Number(a.id), a]));
  const links = new Map((state.broker_links || []).map(l => [Number(l.id), l]));
  const sameReport = (before, after) => after.supersedes_id === before.id &&
    after.version === before.version + 1 && after.document_id === before.document_id &&
    after.kind === before.kind && after.event_date === before.event_date &&
    (after.specimen_id ?? null) === (before.specimen_id ?? null);
  return state.questions.filter(q => required.has(Number(q.id))).map(question => {
    const snapshots = state.snapshots.filter(s => s.state === 'stale' &&
      Number(s.question_id) === Number(question.id));
    const sourceIds = new Set(snapshots.flatMap(s => s.source_ids || []).map(Number));
    const assessmentIds = new Set(snapshots.flatMap(s => s.evidence_assessment_ids || []).map(Number));
    const linkIds = new Set(snapshots.flatMap(s => s.broker_link_ids || []).map(Number));
    const reportChanges = [];
    for (const id of sourceIds) {
      const source = sources.get(id);
      if (source?.state === 'current') continue;
      const pairs = [], visited = new Set([id]);
      let before = source;
      while (before && pairs.length < state.sources.length) {
        const next = state.sources.filter(s => sameReport(before, s));
        // Missing/ambiguous lineage is not a comparison. Do not jump from v1 to v3.
        if (next.length !== 1 || visited.has(Number(next[0].id))) break;
        pairs.push({before, after: next[0]});
        before = next[0]; visited.add(Number(before.id));
      }
      reportChanges.push({id, source: source || null, pairs});
    }
    const evidenceChanges = [];
    for (const id of assessmentIds) {
      const assessment = assessments.get(id);
      const scoped = assessment && assessment.case_id === state.case.case_id &&
        Number(assessment.question_id) === Number(question.id);
      const source = scoped ? evidence.get(Number(assessment.evidence_version_id)) : null;
      if (source?.state !== 'current') evidenceChanges.push({id, source: source || null});
    }
    const rightsChanges = [];
    for (const id of linkIds) {
      const link = links.get(id);
      if (link?.rights_state !== 'active') rightsChanges.push({id, state: link?.rights_state || 'unavailable'});
    }
    return {question, snapshots, reportChanges, evidenceChanges, rightsChanges};
  });
}
function questionReviewAction(context, action) {
  try {
    if (context.caseId !== readyCase() || context.sequence !== refreshSequence)
      throw Error('The case or review state changed. Use the current review list after loading.');
    action();
  } catch (err) { notice(err.message, true); }
}
function prepareQuestionReview(questionId, context) {
  questionReviewAction(context, () => {
    const question = active.questions.find(q => Number(q.id) === Number(questionId));
    if (!question || !currentReviewQuestionIds(active).has(Number(question.id)))
      throw Error('This question no longer has an open source-change review. Refresh the review list.');
    const selector = el('question-choice');
    const switching = selector.value !== String(question.id);
    const unfinished = ['draft-observations', 'draft-summary', 'draft-assumptions']
      .some(id => el(id).value.trim()) || el('evidence-choice').querySelectorAll('input:checked').length > 0;
    if (switching && unfinished)
      throw Error('Save or explicitly clear the unfinished draft and evidence selections before changing questions.');
    if (![...selector.options].some(option => option.value === String(question.id)))
      throw Error('The requested question is not available in this case form.');
    if (switching) {
      selector.value = String(question.id);
      selector.dispatchEvent(new Event('change'));
    }
    el('draft-form').scrollIntoView({block: 'center'});
    el('draft-observations').focus();
    notice('Reviewing question #' + question.id + '. Source selections are unchanged: reconcile superseded reports and evidence explicitly. Nothing was saved or approved.');
  });
}
function renderQuestionReviews() {
  clear('review-question-list');
  const items = questionReviewItems(active);
  const context = {caseId, sequence: refreshSequence};
  if (!items.length) {
    empty(el('review-question-list'), 'No open source-change review is listed. This does not establish a complete or clinically reviewed record.');
    return;
  }
  for (const item of items) {
    const row = node('article', null, 'source-card review-question');
    row.dataset.questionId = String(item.question.id);
    row.append(node('h3', 'Q' + item.question.id + ': ' + item.question.question));
    row.append(node('p', item.snapshots.length + ' historical stale draft(s). Original sources and prior drafts are retained.', 'muted tiny'));
    const compared = new Set();
    for (const change of item.reportChanges) {
      if (!change.source) {
        row.append(node('p', 'Source version #' + change.id + ' is unavailable; no amendment comparison inferred.', 'muted tiny'));
        continue;
      }
      const source = change.source;
      row.append(node('p', source.document_id + '@' + source.version + ' · ' + source.state +
        ' · Event ' + source.event_date + ' · Specimen ' + (source.specimen_id || 'not recorded'), 'snapshot-meta'));
      const sourceAction = node('button', 'Open ' + source.document_id + '@' + source.version, 'button secondary minor');
      sourceAction.type = 'button';
      sourceAction.addEventListener('click', () => questionReviewAction(context, () => openSource(source)));
      row.append(sourceAction);
      for (const pair of change.pairs) {
        const key = pair.before.id + ':' + pair.after.id;
        if (compared.has(key)) continue;
        compared.add(key);
        const compare = node('button', 'Compare ' + source.document_id + ' v' + pair.before.version + ' → v' + pair.after.version,
          'button secondary minor');
        compare.type = 'button';
        compare.addEventListener('click', () => questionReviewAction(context, () => openComparison(pair.before, pair.after)));
        row.append(compare);
      }
      if (!change.pairs.length)
        row.append(node('p', 'Linked consecutive replacement unavailable. Inspect history; no clinical change inferred.', 'muted tiny'));
    }
    for (const change of item.evidenceChanges) {
      const source = change.source;
      row.append(node('p', source ? 'Fictional evidence ' + source.evidence_key + '@' + source.version + ' is ' + source.state + '.' :
        'Evidence assessment #' + change.id + ' or its exact source is unavailable.', 'muted tiny'));
      if (source) {
        const view = node('button', 'Inspect fictional evidence ' + source.evidence_key + '@' + source.version, 'button secondary minor');
        view.type = 'button';
        view.addEventListener('click', () => questionReviewAction(context, () => openEvidence(source)));
        row.append(view);
      }
    }
    for (const change of item.rightsChanges)
      row.append(node('p', 'Content-rights link #' + change.id + ': ' + change.state + '. Restricted content is not displayed here.', 'muted tiny'));
    if (!item.reportChanges.length && !item.evidenceChanges.length && !item.rightsChanges.length)
      row.append(node('p', 'Changed dependency details are unavailable here. Inspect saved history; no cause or resolution is inferred.', 'muted tiny'));
    const prepare = node('button', 'Prepare review for Q' + item.question.id, 'button minor');
    prepare.type = 'button';
    prepare.addEventListener('click', () => prepareQuestionReview(item.question.id, context));
    row.append(prepare);
    el('review-question-list').append(row);
  }
}
// End question review handoff.

// Extend the existing mission/overview projection without a new route or store.
(() => {
  const attention = document.getElementById('review-attention');
  const events = document.getElementById('event-list');
  if (!attention || !events || document.getElementById('review-question-list')) return;
  const list = document.createElement('div');
  list.id = 'review-question-list';
  list.className = 'questions';
  list.setAttribute('aria-label', 'Open questions requiring source-change review');
  attention.insertBefore(list, attention.querySelector('a[href="#investigations"]'));
  let scheduled = false;
  function refreshReviewList() {
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      try { readyCase(); renderQuestionReviews(); }
      catch (err) {
        list.replaceChildren();
        empty(list, 'Waiting for the selected case. No current review conclusion is available.');
      }
    });
  }
  new MutationObserver(refreshReviewList).observe(events, {childList: true});
  document.getElementById('case-picker')?.addEventListener('change', refreshReviewList);
  refreshReviewList();
})();
