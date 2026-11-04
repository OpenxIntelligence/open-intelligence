'use strict';
// All displayed data is from local, synthetic records. No third-party scripts.
let caseId = null;
let active = null;
let refreshSequence = 0;
let boardSequence = 0;
let renderedCaseId = null;
// B-01 fictional actor: workflow governance only — not identity verification,
// not a login, not credentialed review. Sent on every API call; the server
// gates case routes on a live grant for this actor and ignores it elsewhere.
let fictionalActor = 'FICTIONAL-NAVIGATOR-A';
let caseCatalog = [];
let incomingBoardSequence = 0;
let draftQuestionFilter = null;
let draftFilterCaseId = null;
const el = (id) => document.getElementById(id);
function node(tag, text, className = '') {
  const item = document.createElement(tag);
  if (text !== undefined && text !== null) item.textContent = String(text);
  if (className) item.className = className;
  return item;
}
function clear(id) { el(id).replaceChildren(); }
function notice(message, error = false) {
  const item = el('notice');
  item.textContent = message;
  item.className = error ? 'notice error' : 'notice';
  item.hidden = false;
}
async function api(path, payload) {
  const actorHeaders = { 'X-Fictional-Actor': fictionalActor };
  const response = await fetch(path, payload === undefined ? { headers: actorHeaders } : {
    method: 'POST', headers: { ...actorHeaders, 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  const type = response.headers.get('content-type') || '';
  const data = type.includes('json') ? await response.json() : await response.text();
  if (!response.ok) {
    const failure = Error(data.error || 'Request failed');
    failure.status = response.status;
    throw failure;
  }
  return data;
}
function pill(value, style = '') { return node('span', value, 'pill ' + style); }
function empty(container, text) { container.append(node('p', text, 'empty')); }
function metric(number, label) {
  const wrap = node('div', null, 'metric');
  wrap.append(node('span', number, 'number'), node('span', label, 'name'));
  return wrap;
}
function focusOverviewFromCasePicker(event) {
  if (event.key !== 'Tab' || event.shiftKey || event.defaultPrevented) return;
  if (document.activeElement !== el('case-picker')) return;
  const overviewLink = document.querySelector('.rail nav a[href="#overview"]');
  if (!overviewLink) return;
  event.preventDefault();
  overviewLink.focus();
}
function unfinishedDraftPresent() {
  return ['draft-observations', 'draft-summary', 'draft-assumptions', 'evidence-rationale',
    'evidence-withdraw-reason', 'option-description', 'synthesis-note-text',
    'synthesis-note-author', 'owner-label-input', 'note-text',
    'scoped-decision-note', 'scoped-dissent-rationale'].some(id => el(id).value.trim());
}
function renderActorIndicator() {
  // The Patient Mission renderer (mission.js) reads this dataset value so
  // both scripts send the same fictional actor without sharing state.
  document.body.dataset.fictionalActor = fictionalActor;
  el('actor-input').value = fictionalActor;
  el('actor-status').textContent = 'Acting as ' + fictionalActor +
    ' (fictional grant only — not identity verification).';
}
async function loadCaseList() {
  const cases = await api('/api/cases');
  const picker = el('case-picker');
  picker.replaceChildren();
  for (const entry of cases) {
    const option = node('option', entry.label.replace(/^Fictional case /, '') + ', ' + entry.case_id);
    option.value = entry.case_id;
    picker.append(option);
  }
  return cases;
}
async function applyActor() {
  const next = el('actor-input').value.trim();
  if (!/^[A-Z][A-Z0-9-]{1,39}$/.test(next)) {
    el('actor-input').value = fictionalActor;
    notice('Fictional actor ids use uppercase A–Z, numbers and hyphens.', true);
    return;
  }
  if (next === fictionalActor) return;
  // An unfinished narrative must never silently become attached to another actor's view.
  if (unfinishedDraftPresent()) {
    el('actor-input').value = fictionalActor;
    notice('Save or explicitly clear the unfinished investigation draft before switching actors.', true);
    return;
  }
  fictionalActor = next;
  renderActorIndicator();
  cancelSourceRead();
  caseId = null;
  active = null; // Reject writes while the next case list is loading.
  if (el('source-dialog').open) el('source-dialog').close();
  if (el('compare-dialog').open) el('compare-dialog').close();
  try {
    const cases = await loadCaseList();
    caseCatalog = cases;
    await renderIncomingBoard(cases);
    if (!cases.length) {
      el('case-heading').textContent = 'No granted cases for this fictional actor';
      renderedCaseId = null;
      clear('metrics');
      clearCaseViews('No case data shown: this fictional actor holds no active grant.');
      el('changes-anchor').textContent = 'Changes unavailable: this fictional actor holds no active grant.';
      el('changes-disclaimer').textContent = '';
      notice('This fictional actor holds no active grant on any case in this demo. Apply a granted fictional actor.', true);
      return;
    }
    caseId = cases[0].case_id;
    await refresh();
  } catch (err) { notice(err.message, true); }
}
function clearCaseViews(denied) {
  for (const id of ['assertion-list', 'question-list', 'snapshot-list', 'source-list',
      'source-change-list', 'asset-list', 'event-list', 'option-list',
      'evidence-assessment-list', 'quarantine-list', 'model-investigation-list',
      'source-choice', 'evidence-choice', 'patient-timeline', 'patient-findings',
      'patient-questions', 'patient-uncertainty', 'changes-new-sources',
      'changes-amendments', 'changes-stale', 'changes-questions',
      // M-3: the mission projection renders case quotes (mission.js
      // renderKnown); it must clear under denial like every other view.
      'mission-summary', 'mission-known', 'mission-unresolved',
      'mission-changes', 'mission-actions']) {
    clear(id);
    empty(el(id), denied);
  }
  // mission-status is a pill, not a list container: replace the prior-case
  // workflow label with the denial text and reset the pill styling.
  el('mission-status').textContent = denied;
  el('mission-status').className = 'pill pill-neutral';
  // mission-guardrails is a <ul>: clear items without injecting a <p>.
  clear('mission-guardrails');
  // Drop the mission section's prior-case binding alongside its content.
  delete el('patient-mission').dataset.caseId;
  el('patient-mission').dataset.workflowStatus = 'unavailable';
  clear('timeline-events');
  const item = node('li', null, 'timeline-entry');
  item.append(node('p', denied, 'muted'));
  el('timeline-events').append(item);
  for (const id of ['question-choice', 'evidence-question-choice', 'evidence-source-choice',
      'evidence-withdraw-id', 'model-investigation-question', 'option-snapshot-choice',
      'dependency-option-choice', 'task-option-choice', 'threat-option-choice',
      'review-option-choice', 'dependency-option-target-choice', 'dependency-source-choice',
      'dependency-assessment-choice', 'dependency-task-choice', 'review-snapshot-choice'])
    clear(id);
  el('option-disclaimer').textContent = '';
}
function renderAccessDenied(requestedCase) {
  // Never leave the previously rendered case visible under a denied case:
  // clear every case-bound view and block writes until a granted case loads.
  active = null;
  renderedCaseId = null;
  el('case-heading').textContent = 'Access denied for this fictional actor';
  el('review-attention-heading').textContent = 'Investigation review status';
  el('review-attention-summary').textContent = 'Review state unavailable: access denied for this fictional actor.';
  el('review-attention').dataset.state = 'no-open-review';
  clear('metrics');
  clearCaseViews('No case data shown: this fictional actor holds no active grant.');
  el('changes-anchor').textContent = 'Changes unavailable: access denied for this fictional actor.';
  el('changes-disclaimer').textContent = '';
  notice('Fictional actor ' + fictionalActor + ' holds no active grant for ' + requestedCase +
    '. Switch to a granted case or apply a granted fictional actor.', true);
}
async function initialize() {
  try {
    renderActorIndicator();
    el('actor-apply').addEventListener('click', applyActor);
    const picker = el('case-picker');
    picker.addEventListener('keydown', focusOverviewFromCasePicker);
    picker.addEventListener('change', () => {
      if (documentIntake.hasDraft()) {
        picker.value = caseId;
        notice('Add the record or discard its intake before switching cases.', true);
        return;
      }
      // An unfinished narrative must never silently become attached to another case.
      if ((['draft-observations', 'draft-summary', 'draft-assumptions', 'evidence-rationale',
            'evidence-withdraw-reason', 'option-description',
            'scoped-decision-note', 'scoped-dissent-rationale',
            'bio-mechanism', 'bio-result-note',
            'goal-statement', 'amend-goal-statement', 'goal-status-reason',
            'amend-note-text', 'ft-title', 'ft-detail', 'ft-reason',
            'ft-update-reason', 'so-question-text', 'so-responder',
            'so-response-text', 'surv-plan-title', 'surv-description',
            'consent-scope', 'consent-withdraw-reason', 'qualifier-text',
            'workspace-question-text', 'workspace-status-reason', 'workspace-status-answer',
            'visit-date', 'visit-type', 'visit-notes', 'visit-anchor',
            'visit-amend-date', 'visit-amend-type', 'visit-amend-notes', 'visit-amend-anchor',
            'counterevidence-reason', 'safety-detail',
            'flag-reason', 'dimension-note',
            'synthesis-note-text', 'synthesis-note-author',
            'question-note-text', 'owner-label-input', 'note-text'].some(id => el(id).value.trim())) ||
          [...el('review-awaiting').querySelectorAll('input, textarea')].some(x => x.value.trim())) {
        picker.value = caseId;
        notice('Save or explicitly clear the unfinished investigation draft before switching cases.', true);
        return;
      }
      cancelSourceRead();
      caseId = picker.value;
      documentIntake.syncCase(caseId);
      active = null; // Reject writes while the next case is loading.
      draftQuestionFilter = null;
      draftFilterCaseId = null;
      for (const id of ['question-text', 'question-owner', 'owner-label-input', 'note-text',
        'question-note-text', 'report-text', 'evidence-rationale', 'draft-observations',
        'draft-summary', 'draft-assumptions', 'synthesis-note-text', 'synthesis-note-author',
        'counterevidence-reason', 'safety-detail',
        'bio-mechanism', 'bio-result-note',
        'flag-reason', 'dimension-note',
        'goal-statement', 'goal-review-trigger',
        'amend-goal-statement', 'amend-goal-review-trigger', 'goal-status-reason',
        'amend-note-text', 'so-question-text', 'so-responder', 'so-response-text',
        'surv-plan-title', 'surv-description', 'surv-date',
        'consent-scope', 'consent-date', 'consent-withdraw-reason',
        'consent-withdraw-date', 'qualifier-text', 'qualifier-date',
        'workspace-question-text', 'workspace-status-reason',
        'workspace-status-answer', 'visit-date', 'visit-type', 'visit-notes',
        'visit-anchor', 'visit-amend-date', 'visit-amend-type', 'visit-amend-notes',
        'visit-amend-anchor']) el(id).value = '';
      if (el('source-dialog').open) el('source-dialog').close();
      if (el('compare-dialog').open) el('compare-dialog').close();
      refresh();
    });
    const cases = await loadCaseList();
    if (!cases.length) {
      el('case-heading').textContent = 'No synthetic cases found';
      notice('Run PYTHONPATH=src python -m open_intelligence seed before opening the demo.', true);
      return;
    }
    await renderIncomingBoard(cases);
    caseId = cases[0].case_id;
    await refresh();
  } catch (err) { notice(err.message, true); }
}
async function renderIncomingBoard(cases) {
  const boardSeq = ++boardSequence;
  const sequence = ++incomingBoardSequence;
  const list = el('incoming-list');
  clear('incoming-list');
  if (!cases.length) { empty(list, 'No fictional cases in this demo.'); return; }
  empty(list, 'Refreshing fictional case summaries; these are not clinical triage.');
  const summaries = [];
  for (const entry of cases) {
    try {
      const state = await api('/api/cases/' + entry.case_id + '/state');
      const latestEvent = state.sources.reduce((max, s) =>
        s.event_date > max ? s.event_date : max, '');
      summaries.push({
        label: entry.label, caseId: entry.case_id, latestEvent,
        currentSources: state.sources.filter(s => s.state === 'current').length,
        openQuestions: state.questions.filter(q => q.state === 'open').length,
        reviewRequired: currentReviewQuestionIds(state).size,
        stale: state.snapshots.filter(s => s.state === 'stale').length,
      });
    } catch (err) {
      summaries.push({ label: entry.label, caseId: entry.case_id, latestEvent: '', error: err.message });
    }
  }
  if (sequence !== incomingBoardSequence) return;
  clear('incoming-list');
  // Most recent source event first. No urgency is inferred: the demo data
  // has no triage field, so sorting is by recency of the record only.
  if (boardSeq !== boardSequence) return;
  summaries.sort((a, b) => b.latestEvent.localeCompare(a.latestEvent));
  for (const summary of summaries) {
    const row = node('div', null, 'question');
    const text = node('div');
    text.append(node('p', summary.label + ' · ' + summary.caseId));
    if (summary.error) text.append(node('p', 'Could not load this case summary: ' + summary.error, 'muted'));
    else text.append(node('p', 'Most recent source event: ' + (summary.latestEvent || 'none recorded') +
      ' · Current source documents: ' + summary.currentSources +
      ' · Open questions: ' + summary.openQuestions +
      ' · Open source-change reviews: ' + summary.reviewRequired +
      ' · Historical stale drafts: ' + summary.stale, 'muted'));
    const open = node('button', 'Open this case', 'button secondary minor');
    open.type = 'button';
    open.addEventListener('click', () => {
      el('case-picker').value = summary.caseId;
      el('case-picker').dispatchEvent(new Event('change'));
      el('overview').scrollIntoView();
    });
    row.append(text, open);
    list.append(row);
  }
}

const CERTAINTY_PLAIN = {
  reported: 'reported', pending: 'still pending', indeterminate: 'not certain yet',
  conflicting: 'different reports disagree', 'not-reported': 'not reported',
  'not-assessed': 'not assessed',
};
function currentReviewQuestionIds(state) {
  // A historical snapshot remains stale after its question is resolved.
  // Count distinct currently open questions, never retained history as work.
  const open = new Set(state.questions.filter(q => q.state === 'open').map(q => Number(q.id)));
  return new Set(state.snapshots.filter(s => s.state === 'stale' && open.has(Number(s.question_id)))
    .map(s => Number(s.question_id)));
}
function renderPatientView() {
  clear('patient-timeline'); clear('patient-findings'); clear('patient-questions'); clear('patient-uncertainty'); clear('patient-attention');
  if (!active) return;
  const groups = groupedTimeline(active.sources).slice().reverse();
  if (!groups.length) empty(el('patient-timeline'), 'No records yet in this fictional case.');
  for (const group of groups) {
    const item = node('div', null, 'question');
    const amended = group.versions.length > 1;
    item.append(node('p', 'Reported event date: ' + group.eventDate + '. ' +
      group.kind + ' report (' + group.documentId + ').' +
      (amended ? ' Multiple versions of this report are kept; their dates are listed separately.' : '')));
    // Event, report issue and workspace receipt are different clocks. A late
    // arrival or amendment must not be presented as a new biological event.
    const dateText = value => typeof value === 'string' && value.trim() ? value : 'not recorded';
    for (const version of group.versions) {
      item.append(node('p', 'Report version ' + version.version + ' (' + version.state + ')' +
        ' · Issued: ' + dateText(version.issued_at) +
        ' · Received by this workspace: ' + dateText(version.received_at), 'snapshot-meta'));
    }
    el('patient-timeline').append(item);
  }
  if (!active.assertions.length) empty(el('patient-findings'), 'No reported findings yet in this fictional case.');
  for (const assertion of active.assertions) {
    const card = node('div', null, 'finding');
    const manual = assertion.classification_origin === 'user_selected';
    card.append(node('strong', 'Source says'), node('p', assertion.quote, 'quoted'),
      node('span', (manual ? 'User-selected status: ' : 'How certain the source is: ') +
        (CERTAINTY_PLAIN[assertion.certainty] || assertion.certainty) +
        ' · Exact source version #' + assertion.source_version_id + ', line ' + assertion.source_line, 'ref'));
    if (manual) card.append(node('p', 'Passage manually selected. Clinical review not performed.', 'muted tiny'));
    el('patient-findings').append(card);
  }
  const open = active.questions.filter(q => q.state === 'open');
  if (!open.length) empty(el('patient-questions'), 'No open questions in this fictional case.');
  for (const question of open) {
    const row = node('div', null, 'question');
    row.append(node('p', question.question));
    el('patient-questions').append(row);
  }
  const stale = active.snapshots.filter(s => s.state === 'stale').length;
  const superseded = active.sources.filter(s => s.state !== 'current').length;
  const reviewRequired = currentReviewQuestionIds(active).size;
  const notes = [reviewRequired + ' open source-change review(s) in this demonstration. ' +
    'This counts open questions with older drafts affected by changed source material, not every historical draft.'];
  if (stale) notes.push(stale + ' older draft(s) are retained as history; they are not current conclusions.');
  if (open.length) notes.push(open.length + ' open question(s) remain unanswered in this demonstration.');
  for (const assertion of active.assertions) {
    if (['pending', 'indeterminate', 'conflicting', 'not-reported', 'not-assessed'].includes(assertion.certainty))
      notes.push('Source says: ' + assertion.finding_key + ' — ' + CERTAINTY_PLAIN[assertion.certainty] +
        '. Exact source version #' + assertion.source_version_id + ', line ' + assertion.source_line + '.');
  }
  if (superseded) notes.push(superseded + ' older report version(s) have been replaced by a newer version; the older versions are still kept and can be inspected.');
  notes.push('This view does not establish that the record is complete. A demo acknowledgment is not clinical sign-off.');
  for (const text of notes) {
    const row = node('div', null, 'question');
    row.append(node('p', text));
    el('patient-uncertainty').append(row);
  }
}

function renderPatientAttention(data) {
  clear('patient-attention');
  const entries = (data && data.entries) || [];
  if (!entries.length) {
    empty(el('patient-attention'), 'Nothing is currently listed as needing attention in this fictional case. This does not mean the case is complete.');
    return;
  }
  for (const entry of entries) {
    const row = node('div', null, 'question');
    row.append(pill('FICTIONAL', 'pill-warn'));
    row.append(pill(String(entry.kind || 'item'), 'pill-neutral'));
    row.append(node('p', String(entry.title || '')));
    const dateText = entry.date_display || entry.recorded_date || 'no date recorded';
    row.append(node('p', 'Recorded date: ' + dateText, 'muted'));
    row.append(node('p', 'Citation: ' + String(entry.record_type || 'record') + ' #' + String(entry.record_id ?? '?'), 'muted'));
    if (entry.review_state) row.append(node('p', 'Review state: ' + String(entry.review_state), 'muted'));
    if (entry.detail) row.append(node('p', String(entry.detail), 'muted'));
    if (entry.source_anchor) row.append(node('p', 'Source anchor: ' + String(entry.source_anchor), 'muted'));
    el('patient-attention').append(row);
  }
}

async function loadPatientAttention() {
  const requested = caseId;
  clear('patient-attention');
  if (!requested) return;
  try {
    const data = await api('/api/cases/' + requested + '/patient-attention');
    // Discard stale attention responses after case changes.
    if (requested !== caseId || !active || active.case.case_id !== requested) return;
    renderPatientAttention(data);
  } catch (err) {
    if (requested !== caseId) return;
    empty(el('patient-attention'), 'Attention list unavailable: ' + err.message);
  }
}

async function refresh() {
  const requestedCase = caseId;
  const sequence = ++refreshSequence;
  try {
    const response = await api('/api/cases/' + requestedCase + '/state');
    // The user can switch cases while a response is in flight. Never render
    // the previous case underneath the newly selected case or its actions.
    if (sequence !== refreshSequence || caseId !== requestedCase) return;
    active = response;
    el('case-heading').textContent = active.case.label;
    render();
    // The incoming board shows per-case counts for every case, so it goes
    // stale after any write. Refresh it alongside the workspace panels.
    api('/api/cases').then(cases => {
      if (sequence !== refreshSequence || caseId !== requestedCase) return;
      renderIncomingBoard(cases);
    }).catch(err => {
      if (sequence === refreshSequence && requestedCase === caseId) notice(err.message, true);
    });
  } catch (err) {
    if (sequence === refreshSequence && requestedCase === caseId) {
      if (err.status === 403) renderAccessDenied(requestedCase);
      else notice(err.message, true);
    }
  }
}
function readyCase() {
  if (!active || !caseId || active.case.case_id !== caseId || renderedCaseId !== caseId)
    throw Error('The selected case is still loading. Try again after it finishes.');
  return caseId;
}
function renderEvidenceChoices() {
  const previouslySelected = new Set([...el('evidence-choice').querySelectorAll('input:checked')]
    .map(x => Number(x.value)));
  clear('evidence-choice');
  const qid = Number(el('question-choice').value);
  const matches = (active.evidence_assessments || []).filter(a => a.question_id === qid &&
    (a.evidence_state === 'current' || previouslySelected.has(a.id)));
  if (!matches.length) return empty(el('evidence-choice'), 'No current evidence assessment for this question (optional).');
  for (const assessment of matches) {
    const label = node('label');
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.value = assessment.id;
    checkbox.checked = previouslySelected.has(assessment.id);
    label.append(checkbox, node('span', assessment.evidence_key + '@' + assessment.version +
      (assessment.evidence_state !== 'current' ? ', Needs review: uncheck and reassess' : '') + ', ' +
      assessment.relation + ', ' + assessment.applicability));
    el('evidence-choice').append(label);
  }
}

function groupedTimeline(sources) {
  const groups = new Map();
  for (const source of sources) {
    // The source ledger rejects changes to event/specimen/type identity
    // within amended document versions; do not count a correction as a new
    // biological event merely because a later report was issued.
    const key = JSON.stringify([source.document_id, source.event_date, source.kind, source.specimen_id || null]);
    if (!groups.has(key)) groups.set(key, {
      documentId: source.document_id, eventDate: source.event_date,
      kind: source.kind, specimenId: source.specimen_id, versions: []
    });
    groups.get(key).versions.push(source);
  }
  return [...groups.values()].map(group => {
    group.versions.sort((a, b) => a.version - b.version);
    return group;
  }).sort((a, b) => b.eventDate.localeCompare(a.eventDate) ||
    a.documentId.localeCompare(b.documentId));
}
function renderTimeline() {
  clear('timeline-events');
  if (!active) return;
  const choice = el('timeline-filter').value;
  const groups = groupedTimeline(active.sources).filter(g =>
    choice === 'all' || g.kind === choice);
  if (!groups.length) {
    const item = node('li', null, 'timeline-entry');
    item.append(node('p', 'No source events of this type in the selected fictional case.', 'muted'));
    el('timeline-events').append(item);
    return;
  }
  for (const group of groups) {
    const latest = group.versions[group.versions.length - 1];
    const entry = node('li', null, 'timeline-entry');
    const head = node('div', null, 'timeline-head');
    const eventTime = node('time', group.eventDate, 'timeline-date');
    eventTime.dateTime = group.eventDate;
    head.append(eventTime, pill(group.kind),
      group.versions.length > 1 ? pill(group.versions.length + ' report versions', 'pill-warn') : pill('One source version', 'pill-neutral'));
    entry.append(head, node('strong', group.documentId, 'timeline-doc'));
    const meta = node('p', 'Latest issue: ' + latest.issued_at +
      ', Received: ' + latest.received_at.slice(0, 10) +
      (group.specimenId ? ', Specimen: ' + group.specimenId : ', No specimen recorded'), 'snapshot-meta');
    entry.append(meta);
    const actions = node('div', null, 'actions');
    for (const version of group.versions) {
      const button = node('button',
        'View ' + group.documentId + '@' + version.version + ' (' + version.state + ')',
        'button secondary minor');
      button.type = 'button';
      button.addEventListener('click', () => openSource(version));
      actions.append(button);
    }
    entry.append(actions);
    const currentAssertions = active.assertions.filter(x =>
      x.source_version_id === latest.id);
    if (currentAssertions.length && latest.state === 'current') {
      const details = node('p', currentAssertions.length + ' current assertion(s)', 'muted tiny');
      entry.append(details);
    }
    el('timeline-events').append(entry);
  }
}

function renderSourceChanges() {
  clear('source-change-list');
  const revisions = active.sources.filter(s => s.supersedes_id !== null && s.supersedes_id !== undefined)
    .sort((a, b) => b.received_at.localeCompare(a.received_at));
  if (!revisions.length) {
    empty(el('source-change-list'), 'No amended report is recorded in these available fictional sources. This does not mean the case is complete.');
    return;
  }
  for (const revision of revisions) {
    const previous = active.sources.find(s => Number(s.id) === Number(revision.supersedes_id));
    const card = node('article', null, 'change-card');
    const heading = node('div', null, 'change-heading');
    heading.append(node('strong', revision.document_id + ': version ' +
      (previous ? previous.version : '?') + ' → ' + revision.version), pill('Document amendment', 'pill-neutral'));
    card.append(heading);
    card.append(node('p', 'Original event: ' + revision.event_date + ', ' + revision.kind +
      (revision.specimen_id ? ', specimen ' + revision.specimen_id : ', no specimen recorded') +
      '. An amended report is not a new biological event.', 'snapshot-meta'));
    if (!previous) {
      card.append(node('p', 'The earlier source version is unavailable here. No textual or clinical comparison is possible.', 'muted'));
    } else {
      const affected = active.snapshots.filter(snapshot =>
        (snapshot.source_ids || []).some(id => Number(id) === Number(previous.id)));
      const openQuestionIds = new Set(affected.filter(snapshot =>
        active.questions.some(q => Number(q.id) === Number(snapshot.question_id) && q.state === 'open'))
        .map(snapshot => Number(snapshot.question_id)));
      card.append(node('p', affected.length + ' saved investigation(s) cite the earlier source version; ' +
        openQuestionIds.size + ' linked question(s) are currently open. Historical snapshots remain intact.', 'change-impact'));
      const actions = node('div', null, 'actions');
      const compare = node('button', 'Compare original versions', 'button secondary minor');
      compare.type = 'button';
      compare.addEventListener('click', () => openComparison(previous, revision));
      const older = node('button', 'Open version ' + previous.version, 'button secondary minor');
      older.type = 'button'; older.addEventListener('click', () => openSource(previous));
      const newer = node('button', 'Open version ' + revision.version, 'button secondary minor');
      newer.type = 'button'; newer.addEventListener('click', () => openSource(revision));
      actions.append(compare, older, newer);
      card.append(actions);
    }
    el('source-change-list').append(card);
  }
}

function renderBiologicalAssets() {
  clear('asset-list');
  const assets = active.biological_assets || [];
  const assertions = active.biological_inventory_assertions || [];
  if (!assets.length) { empty(el('asset-list'), 'No biological assets recorded for this case.'); return; }
  const byId = new Map(assets.map(a => [a.id, a]));
  const fieldText = (item, name) => item[name + '_state'] === 'known'
    ? name + ': ' + item[name + '_value']
    : name.toUpperCase() + ': UNKNOWN (explicit — not absent)';
  for (const asset of assets) {
    // Each asset is rendered separately, grouped by nothing: two tumors or
    // two time points are never merged into one card.
    const card = node('div', null, 'finding');
    const heading = node('div', null, 'finding-head');
    heading.append(node('strong', asset.asset_id + ' · ' + asset.kind),
      pill('Episode ' + asset.episode_id, 'pill-neutral'));
    const parent = asset.parent_asset_id === null ? 'Original — no parent'
      : 'Derived from ' + (byId.get(asset.parent_asset_id)?.asset_id || ('#' + asset.parent_asset_id));
    card.append(heading,
      node('p', 'Observed ' + asset.observed_date + ' · Specimen: ' +
        (asset.specimen_state === 'recorded' ? asset.specimen_id : 'UNKNOWN (explicit — not absent)') +
        ' · ' + parent + ' · Creation anchor: source version #' + asset.anchor_source_version_id, 'snapshot-meta'));
    if (asset.pointer_label) card.append(node('p', 'Pointer label only, no file stored: ' + asset.pointer_label, 'muted tiny'));
    const mine = assertions.filter(a => a.asset_id === asset.id);
    if (!mine.length) {
      card.append(node('p', 'No inventory assertion recorded — inventory unknown, not absent.', 'muted'));
    }
    for (const item of mine) {
      const box = node('div', null, 'snapshot');
      const top = node('div', null, 'topline');
      top.append(node('strong', 'Inventory assertion #' + item.id + ' · ' + item.asserted_by),
        pill(item.state, item.state === 'stale' ? 'pill-alert' : ''));
      box.append(top, node('p', ['location', 'quantity', 'custody', 'consent', 'rights']
        .map(name => fieldText(item, name)).join(' · '), 'snapshot-meta'),
        node('span', 'Source version #' + item.source_version_id +
          (item.state === 'stale' ? ' · STALE: source amended; re-assert against the current version explicitly' : ''), 'ref'));
      card.append(box);
    }
    el('asset-list').append(card);
  }
}
async function loadVisits() {
  const requested = caseId;
  clear('visit-list');
  try {
    const data = await api('/api/cases/' + requested + '/visits');
    if (requested !== caseId || !active || active.case.case_id !== requested) return;
    renderVisits(data);
  } catch (err) {
    if (requested !== caseId) return;
    empty(el('visit-list'), 'Visit history unavailable: ' + err.message);
  }
}
function renderVisits(data) {
  // Plain recorded history only. Every value is rendered with textContent;
  // nothing here is a directive, a due date, or treatment guidance.
  clear('visit-list');
  const recordedLabel = data.recorded_date_label || 'recorded date — not a clinical due date';
  const visits = data.visits || [];
  const select = el('visit-amend-choice');
  const prior = select.value;
  clear('visit-amend-choice');
  for (const visit of visits) {
    const current = visit.current;
    const opt = node('option', 'FICTIONAL visit #' + visit.visit_id +
      (current ? ' · ' + current.visit_type + ' · ' + current.recorded_date : ''));
    opt.value = visit.visit_id;
    select.append(opt);
  }
  if (prior && [...select.options].some(x => x.value === prior)) select.value = prior;
  if (!visits.length) {
    empty(el('visit-list'), 'No fictional visits recorded for this case.');
    return;
  }
  for (const visit of visits) {
    const current = visit.current;
    const box = node('div', null, 'snapshot');
    const top = node('div', null, 'topline');
    top.append(node('strong', 'FICTIONAL visit #' + visit.visit_id),
      pill(current ? current.visit_type : 'no current version', 'pill-neutral'),
      pill('FICTIONAL', 'pill-warn'));
    box.append(top);
    if (current) {
      box.append(node('p', recordedLabel + ': ' + current.recorded_date, 'snapshot-meta'));
      box.append(node('p', current.notes));
      box.append(node('p', 'Source: ' + (current.source_anchor ? current.source_anchor : 'no source recorded'), 'muted'));
      box.append(node('span', 'Review state: ' + current.review_state +
        ' · Version ' + current.version + ' (' + current.state + ')', 'ref'));
    }
    const history = visit.history || [];
    if (history.length > 1) {
      box.append(node('p', 'History (' + history.length + ' versions, oldest first):', 'snapshot-meta'));
      const list = document.createElement('ol');
      for (const version of history) {
        const item = document.createElement('li');
        item.textContent = 'v' + version.version + ' · ' + recordedLabel + ': ' +
          version.recorded_date + ' · ' + version.visit_type + ' · ' + version.notes +
          ' · Source: ' + (version.source_anchor ? version.source_anchor : 'no source recorded') +
          ' · ' + version.state;
        list.append(item);
      }
      box.append(list);
    } else {
      box.append(node('p', 'History: 1 version (current).', 'snapshot-meta'));
    }
    box.append(node('p', 'FICTIONAL recorded history. Never a directive, never a due date, never treatment guidance.', 'muted tiny'));
    el('visit-list').append(box);
  }
}
function renderBioExplanations() {
  clear('bio-explanation-list');
  const list = el('bio-explanation-list');
  const explanations = active.bio_explanations || [];
  const observations = active.bio_assay_observations || [];
  const assets = new Map((active.biological_assets || []).map(a => [a.id, a]));
  if (!explanations.length)
    empty(list, 'No biological explanations proposed for this fictional case yet.');
  for (const explanation of explanations) {
    // One card per explanation: competing hypotheses are never merged.
    const card = node('div', null, 'finding');
    const heading = node('div', null, 'finding-head');
    heading.append(node('strong', explanation.label + ' · Q' + explanation.question_id),
      pill(explanation.state, explanation.state === 'stale' ? 'pill-alert' : ''));
    card.append(heading, node('p', explanation.mechanism_text));
    card.append(node('p', [
      'Episode ' + explanation.episode_id,
      explanation.specimen_state === 'recorded'
        ? 'Specimen ' + explanation.specimen_id
        : 'Specimen unknown (explicit — not absent)',
      explanation.lesion_state === 'recorded'
        ? 'Lesion ' + explanation.lesion_id
        : 'Lesion unknown (explicit — not absent)',
      explanation.clinical_context_state === 'known'
        ? 'Clinical time point: ' + explanation.clinical_context_value
        : 'Clinical time point unknown (explicit — not absent)',
    ].join(' · '), 'snapshot-meta'));
    card.append(node('span', 'Explanation anchor: source version #' + explanation.source_version_id +
      (explanation.state === 'stale'
        ? ' · STALE: source amended; propose a new explanation explicitly'
        : ''), 'ref'));
    const mine = observations.filter(o => o.explanation_id === explanation.id);
    if (!mine.length) {
      card.append(node('p', 'No assay observations recorded — assays unknown, not absent, and nothing pooled.', 'muted'));
    } else {
      // Grouped for reading by tissue block, but every observation keeps its
      // own card: assays from different blocks are never merged.
      const groups = new Map();
      for (const item of mine) {
        const key = item.tissue_block_state === 'recorded'
          ? 'block:' + item.tissue_block_asset_id : 'block:unknown';
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(item);
      }
      for (const [key, items] of groups) {
        const block = key === 'block:unknown' ? null : assets.get(items[0].tissue_block_asset_id);
        card.append(node('p', key === 'block:unknown'
          ? 'Tissue block unknown (explicit — not pooled with any block)'
          : 'Tissue block ' + (block
            ? block.asset_id + ' (' + block.kind + ', ' + block.episode_id + ')'
            : '#' + items[0].tissue_block_asset_id), 'subhead'));
        for (const item of items) {
          const box = node('div', null, 'snapshot');
          const top = node('div', null, 'topline');
          top.append(node('strong', 'Assay observation #' + item.id + ' · ' + item.method_label),
            pill(item.state, item.state === 'stale' ? 'pill-alert' : ''));
          box.append(top, node('p', item.result_note));
          const control = item.matched_control_state === 'recorded'
            ? 'Matched control recorded: ' + item.matched_control_specimen
            : item.matched_control_state === 'missing'
              ? 'Matched control MISSING — no matched control specimen recorded'
              : 'Matched control unknown (explicit — not absent)';
          const reference = item.reference_kind === 'patient_normal'
            ? "Reference: patient's own normal tissue"
            : item.reference_kind === 'external_population'
              ? 'Reference: external reference population (not this patient)'
              : 'Reference unknown (explicit — not absent)';
          box.append(node('p', control + ' · ' + reference, 'snapshot-meta'));
          box.append(node('span', 'Assay anchor: source version #' + item.source_version_id +
            (item.state === 'stale'
              ? ' · STALE: source amended; record a new observation explicitly'
              : ''), 'ref'));
          card.append(box);
        }
      }
    }
    list.append(card);
  }
  const fill = (id, items, labelFn, allowEmpty = false) => {
    const select = el(id);
    const prior = select.value;
    clear(id);
    if (allowEmpty) { const blank = node('option', '—'); blank.value = ''; select.append(blank); }
    for (const item of items) {
      const opt = node('option', labelFn(item));
      opt.value = item.id; select.append(opt);
    }
    if (prior && [...select.options].some(x => x.value === prior)) select.value = prior;
  };
  fill('bio-question-choice', active.questions, q => 'Q' + q.id + ', ' + q.question.slice(0, 62));
  fill('bio-source-choice', active.sources, s => s.document_id + '@' + s.version + ' · ' + s.state);
  fill('bio-assay-explanation-choice', explanations,
    e => 'Explanation #' + e.id + ' · ' + e.label + ' (' + e.state + ')');
  fill('bio-assay-source-choice', active.sources, s => s.document_id + '@' + s.version + ' · ' + s.state);
  fill('bio-block-choice', (active.biological_assets || [])
    .filter(a => a.kind === 'ffpe_block' || a.kind === 'fresh_frozen_aliquot'),
    a => a.asset_id + ' · ' + a.kind + ' · ' + a.episode_id, true);
}
function render() {
  documentIntake.syncCase(caseId);
  const sameCase = renderedCaseId === caseId;
  if (!sameCase) { draftQuestionFilter = null; draftFilterCaseId = null; }
  if (draftFilterCaseId !== null && draftFilterCaseId !== caseId) { draftQuestionFilter = null; draftFilterCaseId = null; }
  const priorQuestion = sameCase ? el('question-choice').value : null;
  const priorInputs = sameCase ? [...el('source-choice').querySelectorAll('input')] : [];
  const priorSourceIds = new Set(priorInputs.filter(x => x.checked).map(x => Number(x.value)));
  const preserveSources = priorInputs.length > 0;
  const priorEvidenceQuestion = sameCase ? el('evidence-question-choice').value : null;
  const priorEvidenceSource = sameCase ? el('evidence-source-choice').value : null;
  const priorWithdrawTarget = sameCase ? el('evidence-withdraw-id').value : null;
  clear('metrics');
  const latest = active.sources.filter(s => s.state === 'current');
  const reviewRequired = currentReviewQuestionIds(active).size;
  const overdueTasks = (active.followthrough && active.followthrough.counts && active.followthrough.counts.overdue) || 0;
  el('metrics').append(
    metric(latest.length, 'Current source documents'), metric(active.assertions.length, 'Reported statements'),
    metric(active.questions.filter(q => q.state === 'open').length, 'Open questions'), metric(reviewRequired, 'Review required'),
    metric(overdueTasks, 'Overdue tasks'));
  const reviewNotice = el('review-attention');
  reviewNotice.dataset.state = reviewRequired ? 'needs-review' : 'no-open-review';
  el('review-attention-heading').textContent = reviewRequired
    ? 'Changed sources need another review'
    : 'Investigation review status';
  const openQuestions = active.questions.filter(q => q.state === 'open').length;
  el('review-attention-summary').textContent = reviewRequired
    ? reviewRequired + ' reopened question(s) have stale source-dependent investigation history. Inspect both versions and prepare a new reviewable draft; no clinical decision is made automatically.'
    : active.snapshots.length
      ? 'No unresolved source-change review is flagged. ' + openQuestions +
        ' open question(s) remain. Historical stale records are retained; a demo acknowledgment is not clinical sign-off.'
      : 'No investigation snapshots exist yet. ' + openQuestions +
        ' open question(s) are recorded. No conclusion is available to review.';
  renderTimeline();
  renderSourceChanges();
  clear('source-list');
  if (!active.sources.length) empty(el('source-list'), 'No records received.');
  for (const source of active.sources) {
    const card = node('article', null, 'source-card');
    const top = node('div', null, 'source-top');
    top.append(node('span', source.document_id + ' @' + source.version, 'source-title'),
      pill(source.state, source.state === 'current' ? '' : 'pill-neutral'));
    const meta = node('div', null, 'source-meta');
    for (const text of [source.kind, 'Event ' + source.event_date, 'Issued ' + source.issued_at,
      'Received ' + source.received_at.substring(0, 10), 'SHA ' + source.sha256.slice(0, 12) + '…']) meta.append(node('span', text));
    const button = node('button', 'View original text', 'button secondary minor');
    button.type = 'button'; button.addEventListener('click', () => openSource(source));
    card.append(top, meta, button);
    if (source.document_intake) {
      card.append(node('p', source.document_intake.filename +
        ' · Manually confirmed passages · Clinical review not performed', 'muted tiny'));
      const download = node('a', 'Download original file', 'button secondary minor');
      download.href = '/api/cases/' + caseId + '/sources/' + source.id + '/download';
      download.download = source.document_intake.filename;
      card.append(download);
    }
    el('source-list').append(card);
  }
  clear('assertion-list');
  if (!active.assertions.length) empty(el('assertion-list'), 'No current reported statements.');
  for (const assertion of active.assertions) {
    const card = node('div', null, 'finding');
    const heading = node('div', null, 'finding-head');
    const labels = node('div', null, 'finding-labels');
    labels.append(pill('Source says', 'pill-neutral'), pill(
      (assertion.classification_origin === 'user_selected' ? 'User-selected: ' : '') + assertion.certainty,
      ['pending', 'indeterminate', 'conflicting', 'not-reported', 'not-assessed'].includes(assertion.certainty) ? 'pill-warn' : ''));
    heading.append(node('strong', assertion.finding_key), labels);
    card.append(heading, node('p', assertion.quote, 'quoted'));
    const supportingSource = active.sources.find(source =>
      Number(source.id) === Number(assertion.source_version_id));
    const sourceButton = node('button', supportingSource
      ? 'Inspect ' + supportingSource.document_id + '@' + supportingSource.version + ', line ' + assertion.source_line
      : 'Exact source version unavailable', 'button secondary minor source-jump');
    sourceButton.type = 'button';
    sourceButton.disabled = !supportingSource;
    if (supportingSource)
      sourceButton.addEventListener('click', () => openSource(supportingSource, Number(assertion.source_line)));
    card.append(sourceButton);
    if (assertion.classification_origin === 'user_selected')
      card.append(node('p', 'Passage and status manually selected. Clinical review not performed.', 'muted tiny'));
    el('assertion-list').append(card);
  }
  renderBiologicalAssets();
  renderBioExplanations();
  clear('question-list'); clear('question-choice');
  clear('owner-question-choice'); clear('triage-question-choice');
  clear('note-question-choice'); clear('rollup-question-choice');
  clear('question-rollup');
  if (!active.questions.length) empty(el('question-list'), 'Add an unresolved question to begin.');
  for (const question of active.questions) {
    const row = node('div', null, 'question');
    row.append(node('p', question.question), pill(question.state, question.state === 'open' ? 'pill-warn' : ''));
    row.append(node('p', 'Owner: ' + (question.owner_label || 'none recorded') +
      ' · Follow-up marker: ' + (question.triage || 'unsorted'), 'muted'));
    const notes = (active.question_evidence_notes || []).filter(n => Number(n.question_id) === Number(question.id));
    if (notes.length) {
      const latest = notes[notes.length - 1];
      row.append(node('p', 'Needed-evidence notes: ' + notes.length +
        ' · Latest (v' + latest.version + '): ' + latest.note, 'muted'));
    }
    const draftsLink = document.createElement('a');
    draftsLink.href = '#investigation-history-heading';
    draftsLink.className = 'button secondary minor';
    draftsLink.textContent = 'Open saved drafts';
    draftsLink.addEventListener('click', () => {
      draftQuestionFilter = question.id;
      draftFilterCaseId = caseId;
      render();
    });
    row.append(draftsLink);
    el('question-list').append(row);
    for (const id of ['question-choice', 'owner-question-choice', 'triage-question-choice',
      'note-question-choice', 'rollup-question-choice']) {
      const opt = node('option', 'Q' + question.id + ', ' + question.question.slice(0, 62));
      opt.value = question.id; el(id).append(opt);
    }
  }
  if (priorQuestion && [...el('question-choice').options].some(x => x.value === priorQuestion))
    el('question-choice').value = priorQuestion;
  renderEvidenceChoices();
  clear('evidence-question-choice'); clear('evidence-source-choice'); clear('evidence-withdraw-id');
  for (const question of active.questions) {
    const opt = node('option', 'Q' + question.id + ', ' + question.question.slice(0, 62));
    opt.value = question.id; el('evidence-question-choice').append(opt);
  }
  if (priorEvidenceQuestion && [...el('evidence-question-choice').options].some(x => x.value === priorEvidenceQuestion))
    el('evidence-question-choice').value = priorEvidenceQuestion;
  clear('evidence-list');
  const evidence = active.evidence || [];
  if (!evidence.length) empty(el('evidence-list'), 'No fictional research evidence registered.');
  for (const item of evidence) {
    const card = node('article', null, 'source-card');
    const heading = node('div', null, 'source-top');
    heading.append(node('strong', item.evidence_key + '@' + item.version),
      pill(item.state, item.state === 'current' ? '' : 'pill-warn'));
    const view = node('button', 'Inspect fictional source', 'button secondary minor');
    view.type = 'button'; view.addEventListener('click', () => openEvidence(item));
    card.append(heading, node('p', item.title), node('p', 'Statement line ' + item.statement_line +
      ', SHA ' + item.sha256.slice(0, 12) + '…', 'snapshot-meta'), view);
    el('evidence-list').append(card);
    if (item.state === 'current') {
      const opt = node('option', item.evidence_key + '@' + item.version + ', ' + item.title);
      opt.value = item.id; el('evidence-source-choice').append(opt);
      const withdraw = node('option', item.evidence_key + '@' + item.version + ', ' + item.title);
      withdraw.value = item.id; el('evidence-withdraw-id').append(withdraw);
    }
  }
  // Leave the withdraw target explicitly unchosen until the user picks one.
  // Without this, the first current item is implicitly selected on first
  // paint, aiming a destructive cross-case withdrawal at whatever sorts
  // first. A prior selection is restored below when still current.
  el('evidence-withdraw-id').selectedIndex = -1;
  if (priorWithdrawTarget) {
    if ([...el('evidence-withdraw-id').options].some(x => x.value === priorWithdrawTarget))
      el('evidence-withdraw-id').value = priorWithdrawTarget;
    else {
      // Do not default to another current item after the selected version
      // was amended or withdrawn, especially when a reason is already drafted.
      el('evidence-withdraw-id').selectedIndex = -1;
      notice('The selected withdrawal target is no longer current. Select a new evidence item explicitly.', true);
    }
  }
  if (priorEvidenceSource && [...el('evidence-source-choice').options].some(x => x.value === priorEvidenceSource))
    el('evidence-source-choice').value = priorEvidenceSource;
  else if (priorEvidenceSource && el('evidence-rationale').value.trim()) {
    const oldItem = evidence.find(x => String(x.id) === priorEvidenceSource);
    if (oldItem) {
      const staleOption = node('option', oldItem.evidence_key + '@' + oldItem.version +
        ', Needs review: choose current evidence and reconsider rationale');
      staleOption.value = oldItem.id;
      el('evidence-source-choice').append(staleOption);
      el('evidence-source-choice').value = priorEvidenceSource;
      notice('The evidence assessment source changed. Explicitly choose a current version and reconsider its applicability.', true);
    }
  }
  clear('evidence-assessment-list');
  const assessments = active.evidence_assessments || [];
  if (!assessments.length) empty(el('evidence-assessment-list'), 'No fictional evidence assessments linked to this case.');
  for (const item of assessments) {
    const box = node('article', null, 'finding');
    const row = node('div', null, 'finding-head');
    row.append(node('strong', item.evidence_key + '@' + item.version + ', Q' + item.question_id),
      pill(item.evidence_state, item.evidence_state === 'current' ? '' : 'pill-alert'));
    box.append(row, node('p', item.relation + ' / ' + item.applicability, 'snapshot-meta'),
      node('p', item.statement, 'quoted'), node('p', item.rationale, 'muted'));
    el('evidence-assessment-list').append(box);
  }
  clear('source-choice');
  // Preserve exact source IDs across refreshes, including now-superseded IDs:
  // a human must explicitly reconcile the bindings with the new source versions.
  const sourcesForDraft = preserveSources
    ? active.sources.filter(x => x.state === 'current' || priorSourceIds.has(x.id))
    : latest;
  for (const source of sourcesForDraft) {
    const label = node('label');
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.value = source.id;
    checkbox.checked = preserveSources ? priorSourceIds.has(source.id) : true;
    label.append(checkbox, node('span', source.document_id + '@' + source.version + ', ' +
      source.event_date + (source.state !== 'current' ? ', Needs review: uncheck and select the replacement explicitly' : '')));
    el('source-choice').append(label);
  }
  if (!latest.length) empty(el('source-choice'), 'No current sources.');
  if ([...priorSourceIds].some(id => !latest.some(x => x.id === id)))
    notice('An investigation source changed while you were editing. Review the narrative and explicitly reconcile source selections before saving.', true);
  clear('snapshot-list');
  if (draftQuestionFilter !== null && draftFilterCaseId === caseId) {
    const filterNotice = node('p', 'Showing drafts for Q' + draftQuestionFilter + ' in this fictional case. This list shows only drafts for that question.', 'muted');
    el('snapshot-list').append(filterNotice);
    const showAll = document.createElement('a');
    showAll.href = '#investigation-history-heading';
    showAll.className = 'button secondary minor';
    showAll.textContent = 'Show all drafts';
    showAll.addEventListener('click', () => {
      draftQuestionFilter = null;
      draftFilterCaseId = null;
      render();
    });
    el('snapshot-list').append(showAll);
  }
  if (!active.snapshots.length) empty(el('snapshot-list'), 'No investigation drafts yet.');
  if (draftQuestionFilter !== null && draftFilterCaseId === caseId && active.snapshots.length && !active.snapshots.some(s => Number(s.question_id) === Number(draftQuestionFilter))) empty(el('snapshot-list'), 'No drafts for this question yet in this fictional case.');
  for (const snapshot of active.snapshots) {
    if (draftQuestionFilter !== null && draftFilterCaseId === caseId && Number(snapshot.question_id) !== Number(draftQuestionFilter)) continue;
    const box = node('div', null, 'snapshot'); const top = node('div', null, 'topline');
    top.append(node('strong', 'Investigation #' + snapshot.id), pill(snapshot.state,
      snapshot.state === 'stale' ? 'pill-alert' : snapshot.state === 'draft' ? 'pill-warn' : ''));
    const description = node('p', snapshot.summary);
    const meta = node('p', 'Sources: ' + snapshot.source_ids.map(x => '#' + x).join(', ') + ', ' + snapshot.created_at, 'snapshot-meta');
    const actions = node('div', null, 'actions');
    const exportButton = node('button', 'Export with sources', 'button secondary minor'); exportButton.type = 'button';
    exportButton.addEventListener('click', () => downloadSnapshot(snapshot.id)); actions.append(exportButton);
    if (snapshot.state === 'draft') {
      const button = node('button', 'Demo review acknowledgment', 'button minor'); button.type = 'button';
      button.addEventListener('click', async () => {
        try {
          const requestedCase = readyCase();
          await api('/api/cases/' + requestedCase + '/snapshots/' + snapshot.id + '/review', { reviewer_label: 'Synthetic reviewer (unverified)' });
          if (requestedCase !== caseId) return;
          notice('Acknowledged in demonstration only. This is not credentialed clinical review.'); await refresh();
        } catch (err) { notice(err.message, true); }
      }); actions.append(button);
    }
    const questionLink = document.createElement('a');
    questionLink.href = '#question-pane-heading';
    questionLink.className = 'button secondary minor';
    questionLink.textContent = 'Back to question Q' + snapshot.question_id;
    actions.append(questionLink);
    if (snapshot.state === 'reviewed_in_demo') {
      const followLink = document.createElement('a');
      followLink.href = '#options';
      followLink.className = 'button secondary minor';
      followLink.textContent = 'Continue to discussion items';
      actions.append(followLink);
    }
    box.append(top, description, meta, actions);
    const scoped = snapshot.scoped_review || {};
    const scopedOpen = scoped.open_items || [];
    box.append(node('p', 'Scoped review: extraction ' + (scoped.extraction || 'unreviewed') +
      ' · interpretation ' + (scoped.interpretation || 'unreviewed') +
      (scopedOpen.length ? ' · Open: ' + scopedOpen.join(', ') : ' · No open scope items') +
      ((scoped.dissents || []).length ? ' · ' + scoped.dissents.length + ' disagreement(s) recorded' : '') +
      (scoped.assignee ? ' · With reviewer: ' + scoped.assignee : ''), 'snapshot-meta'));
    if (snapshot.state === 'stale') box.append(node('p', 'A source was amended. This version remains historical and cannot be acknowledged as current.', 'muted'));
    el('snapshot-list').append(box);
  }
  clear('model-investigation-question');
  for (const question of active.questions) {
    const opt = node('option', question.question);
    opt.value = question.id; el('model-investigation-question').append(opt);
  }
  loadModelInvestigations();
  loadChangesSinceReview();
  loadPacketSummary();
  loadVisits();
  loadWorkspaceQuestions();
  loadEvidenceQuality();
  loadReviewQueue();
  renderSynthesisChoices();
  loadSynthesis();
  loadReReviewTasks();
  clear('quarantine-list');
  for (const entry of active.quarantines) {
    el('quarantine-list').append(node('div', 'Quarantined #' + entry.id + ': declared ' + entry.declared_patient_id + ', not ' + caseId + ', no assertions imported', 'quarantine'));
  }
  clear('event-list');
  for (const event of active.events.slice(0, 12)) {
    const card = node('div', event.kind.replaceAll('_', ' '), 'event');
    card.append(node('small', event.occurred_at)); el('event-list').append(card);
  }
  renderPatientView();
  loadPatientAttention();
  renderOptions();
  renderCareRecords();
  renderFollowthrough();
  renderPatientWords();
  renderPortfolio();
  renderScopedReview();
  renderJourney();
  renderedCaseId = caseId;
}
function renderOriginalSource(text, lineNumber) {
  // Imported source text must never become HTML. Highlight only the exact
  // recorded source line; preserve all other characters and line breaks.
  const viewer = el('dialog-text');
  viewer.replaceChildren();
  const lines = String(text).split('\n');
  const anchored = Number.isInteger(lineNumber) && lineNumber > 0 && lineNumber <= lines.length;
  for (let index = 0; index < lines.length; index++) {
    if (index) viewer.append(document.createTextNode('\n'));
    if (anchored && index + 1 === lineNumber)
      viewer.append(node('mark', lines[index], 'source-highlight'));
    else viewer.append(document.createTextNode(lines[index]));
  }
  return anchored;
}
// Begin source text comparison.
function reportLineTokens(text) {
  // Keep every character, including CRLF, blank lines and the final newline.
  return text.match(/[^\n]*\n|[^\n]+$/g) || [];
}
function compareReportLines(before, after) {
  if (typeof before !== 'string' || typeof after !== 'string')
    throw Error('Original source text is required for comparison.');
  const limited = {status: 'limited', beforeLines: [], afterLines: []};
  // Bound work before allocating the line-alignment table. Never truncate an original.
  if (before.length > 65536 || after.length > 65536) return limited;
  const a = reportLineTokens(before), b = reportLineTokens(after);
  if (a.length > 512 || b.length > 512) return limited;
  if (before === after) return {status: 'identical', beforeLines: [], afterLines: []};
  const width = b.length + 1;
  const table = new Uint16Array((a.length + 1) * width);
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      table[i * width + j] = a[i] === b[j]
        ? table[(i + 1) * width + j + 1] + 1
        : Math.max(table[(i + 1) * width + j], table[i * width + j + 1]);
    }
  }
  const beforeLines = [], afterLines = [];
  let i = 0, j = 0;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) { i++; j++; }
    else if (i < a.length && (j === b.length ||
        table[(i + 1) * width + j] >= table[i * width + j + 1])) beforeLines.push(++i);
    else afterLines.push(++j);
  }
  return {status: 'compared', beforeLines, afterLines};
}
function renderReportLineComparison(before, after) {
  const difference = compareReportLines(before, after);
  const paint = (id, text, changed, label) => {
    const viewer = el(id);
    viewer.replaceChildren();
    if (difference.status === 'limited') { viewer.textContent = text; return; }
    const selected = new Set(changed);
    reportLineTokens(text).forEach((token, index) => {
      if (selected.has(index + 1)) {
        const mark = node('mark', token, 'source-highlight');
        mark.title = label + ' line ' + (index + 1);
        mark.dataset.line = String(index + 1);
        viewer.append(mark);
      } else viewer.append(document.createTextNode(token));
    });
  };
  paint('compare-before', before, difference.beforeLines, 'Previous-only');
  paint('compare-after', after, difference.afterLines, 'Updated-only');
  const listed = numbers => numbers.length ? numbers.slice(0, 20).join(', ') +
    (numbers.length > 20 ? ' (first 20 of ' + numbers.length + ')' : '') : 'none';
  const scope = ' Text-only comparison, including whitespace and line endings. This view makes no clinical or treatment determination.';
  el('compare-context').textContent = difference.status === 'limited'
    ? 'Line highlighting skipped: a source exceeds the 65,536-character or 512-line comparison limit. Both complete original texts remain visible; differences have not been assessed.' + scope
    : difference.status === 'identical'
      ? 'Exact source text is identical. This does not establish clinical equivalence.' + scope
      : difference.beforeLines.length + ' previous-only line(s); ' + difference.afterLines.length +
        ' updated-only line(s). Previous source lines: ' + listed(difference.beforeLines) +
        '. Updated source lines: ' + listed(difference.afterLines) +
        '. Repeated or moved lines use a deterministic text alignment, not a clinical mapping.' + scope;
  return difference;
}
// End source text comparison.
// One read intent across report, evidence and comparison views. Checking only
// caseId misses same-case reordering and a case A -> B -> A round trip.
let sourceReadSequence = 0;
function cancelSourceRead() { sourceReadSequence++; }
function beginSourceRead() {
  const selectedCase = readyCase();
  return {caseId: selectedCase, sequence: ++sourceReadSequence};
}
function sourceReadIsCurrent(read) {
  return read.sequence === sourceReadSequence && read.caseId === caseId &&
    active?.case.case_id === caseId && renderedCaseId === caseId;
}
function sourceReadRecord(records, requested, label) {
  if (!requested || !Number.isSafeInteger(requested.id) || requested.id <= 0)
    throw Error('Invalid ' + label + ' identifier.');
  const record = records.find(item => item.id === requested.id);
  if (!record) throw Error('The requested ' + label + ' is unavailable in this case view.');
  // Labels and lineage come from the active case response, not caller objects.
  return record;
}
function showSourceView(dialogId) {
  for (const id of ['source-dialog', 'compare-dialog']) {
    if (id !== dialogId && el(id).open) el(id).close();
  }
  if (!el(dialogId).open) el(dialogId).showModal();
}
function originalText(response) {
  if (!response || typeof response.text !== 'string')
    throw Error('Original source text is unavailable. No comparison was produced.');
  return response.text;
}
async function openSource(requested, lineNumber = null) {
  let read;
  try {
    read = beginSourceRead();
    const source = sourceReadRecord(active.sources, requested, 'source');
    const response = await api('/api/cases/' + read.caseId + '/sources/' + source.id);
    if (!sourceReadIsCurrent(read)) return;
    const text = originalText(response);
    el('dialog-title').textContent = source.document_id + '@' + source.version + ', original UTF-8';
    const anchored = renderOriginalSource(text, lineNumber);
    el('dialog-context').textContent = anchored
      ? 'Source-reported statement, highlighted original line ' + lineNumber + '. Not clinically reviewed.'
      : lineNumber === null
        ? 'Exact original report and source version. Not clinically reviewed.'
        : 'Requested source line is not present in this version. Original text is preserved below.';
    showSourceView('source-dialog');
    if (anchored) el('dialog-text').querySelector('mark.source-highlight')?.scrollIntoView({block:'center'});
  } catch (err) {
    if (!read || sourceReadIsCurrent(read)) notice(err.message, true);
  }
}
async function openComparison(requestedPrevious, requestedCurrent) {
  let read;
  try {
    read = beginSourceRead();
    const previous = sourceReadRecord(active.sources, requestedPrevious, 'source');
    const current = sourceReadRecord(active.sources, requestedCurrent, 'source');
    // Membership alone is not amendment lineage. Never label unrelated reports
    // as before/after versions merely because they belong to the same case.
    if (current.supersedes_id !== previous.id || current.version !== previous.version + 1 ||
        current.document_id !== previous.document_id || current.kind !== previous.kind ||
        current.event_date !== previous.event_date ||
        (current.specimen_id ?? null) !== (previous.specimen_id ?? null))
      throw Error('Only linked consecutive versions of the same report and specimen can be compared.');
    const [before, after] = await Promise.all([previous, current].map(source =>
      api('/api/cases/' + read.caseId + '/sources/' + source.id)));
    if (!sourceReadIsCurrent(read)) return;
    const beforeText = originalText(before), afterText = originalText(after);
    el('compare-title').textContent = current.document_id + ': original versions ' +
      previous.version + ' and ' + current.version;
    el('compare-before-title').textContent = previous.document_id + '@' + previous.version + ' · ' + previous.state;
    el('compare-after-title').textContent = current.document_id + '@' + current.version + ' · ' + current.state;
    renderReportLineComparison(beforeText, afterText);
    showSourceView('compare-dialog');
  } catch (err) {
    if (!read || sourceReadIsCurrent(read)) notice(err.message, true);
  }
}
async function openEvidence(requested) {
  let read;
  try {
    read = beginSourceRead();
    const item = sourceReadRecord(active.evidence || [], requested, 'fictional evidence');
    const response = await api('/api/evidence/' + item.id);
    if (!sourceReadIsCurrent(read)) return;
    const text = originalText(response);
    el('dialog-title').textContent = item.evidence_key + '@' + item.version + ', fictional source';
    el('dialog-context').textContent = 'Fictional evidence text, not independent clinical appraisal.';
    el('dialog-text').textContent = text;
    showSourceView('source-dialog');
  } catch (err) {
    if (!read || sourceReadIsCurrent(read)) notice(err.message, true);
  }
}
async function downloadSnapshot(id) {
  try {
    const requestedCase = readyCase();
    const text = await api('/api/cases/' + requestedCase + '/snapshots/' + id + '/export');
    if (requestedCase !== caseId) return;
    const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }));
    const link = document.createElement('a'); link.href = url; link.download = 'synthetic-investigation-' + id + '.md';
    document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(url);
  } catch (err) { notice(err.message, true); }
}
async function downloadPacket(format) {
  try {
    const requestedCase = readyCase();
    const suffix = format === 'text' ? '?format=text' : '';
    const data = await api('/api/cases/' + requestedCase + '/packet' + suffix);
    if (requestedCase !== caseId) return;
    const text = format === 'text' ? data : JSON.stringify(data, null, 2);
    const mime = format === 'text' ? 'text/plain' : 'application/json';
    const ext = format === 'text' ? '.txt' : '.json';
    const url = URL.createObjectURL(new Blob([text], { type: mime }));
    const link = document.createElement('a'); link.href = url; link.download = 'synthetic-packet-' + requestedCase + ext;
    document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    notice('Fictional demo packet downloaded for ' + requestedCase + '.');
  } catch (err) { notice(err.message, true); }
}
async function loadPacketSummary() {
  const requested = caseId;
  const statusEl = el('packet-status');
  if (statusEl) statusEl.textContent = 'Loading fictional packet summary…';
  clear('packet-summary');
  try {
    const data = await api('/api/cases/' + requested + '/packet');
    if (requested !== caseId || !active || active.case.case_id !== requested) return;
    renderPacketSummary(data);
  } catch (err) {
    if (requested !== caseId) return;
    if (statusEl) statusEl.textContent = 'Packet summary unavailable: ' + err.message;
    empty(el('packet-summary'), 'Fictional packet summary unavailable.');
  }
}
function renderPacketSummary(data) {
  const cover = data.cover || {};
  const position = cover.report_position || {};
  const statusEl = el('packet-status');
  if (statusEl) statusEl.textContent = 'Fictional demo packet for ' + (cover.case_id || caseId) +
    ' at event #' + (position.as_of_event_id ?? 'none') + '. Same sections as the workspace, same source references.';
  clear('packet-summary');
  const journey = data.journey_stage || {};
  const where = journey.where_am_i || {};
  const timeline = data.timeline || {};
  const counts = timeline.counts || {};
  const changes = data.changes_since_review || {};
  const changeCounts = changes.counts || {};
  const rows = [
    ['Journey stage', String(journey.workflow_status || 'unknown') + ' · ' +
      (where.current_source_documents ?? 0) + ' current sources, ' +
      (where.open_questions ?? 0) + ' open questions'],
    ['Reported findings', String((data.reported_findings || {}).count ?? 0) + ' source statements'],
    ['Timeline', String(counts.entries ?? 0) + ' entries, ' + String(counts.gaps ?? 0) +
      ' gaps, ' + String(counts.conflicts ?? 0) + ' conflicts'],
    ['Questions', String((data.questions || {}).items ? data.questions.items.length : 0) + ' recorded'],
    ['Investigations', String((data.investigations || {}).snapshots ? data.investigations.snapshots.length : 0) +
      ' drafts, ' + String((data.investigations || {}).model_investigations ? data.investigations.model_investigations.length : 0) +
      ' hypotheses pending review'],
    ['Evidence', String((data.evidence || {}).assessments ? data.evidence.assessments.length : 0) + ' assessments'],
    ['Sources', String((data.sources || {}).items ? data.sources.items.length : 0) + ' versions'],
    ['Changes since review', String(changeCounts.new_sources ?? 0) + ' new, ' +
      String(changeCounts.amendments ?? 0) + ' amendments, ' +
      String(changeCounts.stale_investigations ?? 0) + ' stale'],
    ['Options', String((data.options || {}).items ? data.options.items.length : 0) + ' proposed'],
    ['Follow ups', String((data.follow_ups || {}).next_actions ? data.follow_ups.next_actions.length : 0) + ' bounded actions'],
    ['Biological assets', String((data.biological_assets || {}).assets ? data.biological_assets.assets.length : 0) + ' recorded'],
    ['Recent activity', String((data.activity || {}).items ? data.activity.items.length : 0) + ' ledger events'],
    ['Limitations', String((data.limitations || {}).items ? data.limitations.items.length : 0) + ' limits noted'],
  ];
  for (const [label, detail] of rows) {
    const card = node('article', null, 'source-card');
    const top = node('div', null, 'source-top');
    top.append(node('span', label, 'source-title'), pill('FICTIONAL DEMO DATA', 'pill-warn'));
    card.append(top, node('p', detail, 'snapshot-meta'));
    el('packet-summary').append(card);
  }
}
el('packet-download-json').addEventListener('click', () => downloadPacket('json'));
el('packet-download-text').addEventListener('click', () => downloadPacket('text'));
el('packet-print').addEventListener('click', () => {
  try { readyCase(); window.print(); } catch (err) { notice(err.message, true); }
});
el('dialog-close').addEventListener('click', () => { cancelSourceRead(); el('source-dialog').close(); });
el('compare-close').addEventListener('click', () => { cancelSourceRead(); el('compare-dialog').close(); });
// Native Escape dispatches cancel before closing. Avoid a close-event handler:
// queued programmatic close events must not cancel a newer read intent.
function renderQuestionRollup(data) {
  // Read-only ledger facts only: unresolved items with anchors, bound
  // snapshots, versioned notes, owner history, and case coverage context.
  clear('question-rollup');
  const box = el('question-rollup');
  const question = data.question || {};
  box.append(node('p', 'Q' + question.id + ': ' + (question.question || '')));
  box.append(node('p', 'State: ' + (question.state || '') + ' · Follow-up marker: ' +
    (question.triage || '') + ' · Owner: ' + (question.owner_label || 'none recorded'), 'muted'));
  box.append(node('p', data.ordering_rule || '', 'muted'));
  const items = data.unresolved_items || [];
  box.append(node('p', 'Unresolved source items: ' + items.length, 'subhead'));
  if (!items.length) empty(box, 'No unresolved source items in this fictional case.');
  for (const item of items) {
    const row = node('div', null, 'question');
    row.append(node('p', item.finding_key + ' · ' + item.state),
      node('p', 'Source #' + item.source_version_id + ' (' + item.document_id + '@' + item.version +
        '), line ' + item.source_line + ' · Occurred ' + item.occurred +
        ' · Documented ' + item.documented, 'muted'),
      node('p', item.quote || '', 'quoted'));
    box.append(row);
  }
  const snapshots = data.snapshots || [];
  box.append(node('p', 'Bound snapshots: ' + snapshots.length, 'subhead'));
  for (const snapshot of snapshots) {
    box.append(node('p', 'Snapshot #' + snapshot.id + ' · ' + snapshot.state +
      ' · Sources: ' + (snapshot.source_ids || []).join(', '), 'muted'));
  }
  const notes = data.needed_evidence_notes || [];
  box.append(node('p', 'Needed-evidence notes: ' + notes.length, 'subhead'));
  for (const note of notes) {
    box.append(node('p', 'v' + note.version + ' · ' + note.created_at + ': ' + note.note, 'muted'));
  }
  const history = data.owner_history || [];
  box.append(node('p', 'Owner history: ' + history.length + ' assignment(s)', 'subhead'));
  for (const entry of history) {
    box.append(node('p', entry.owner_label + ' · ' + entry.assigned_at, 'muted'));
  }
  const coverage = data.case_coverage_context || {};
  box.append(node('p', 'Case coverage context: ' + (coverage.gaps || []).length +
    ' gap(s), ' + (coverage.date_conflicts || []).length + ' date conflict(s). ' +
    (coverage.note || ''), 'muted'));
  box.append(node('p', data.disclaimer || '', 'muted tiny'));
}
for (const id of ['source-dialog', 'compare-dialog'])
  el(id).addEventListener('cancel', cancelSourceRead);
el('question-form').addEventListener('submit', async event => {
  event.preventDefault(); try {
    const requestedCase = readyCase();
    await api('/api/cases/' + requestedCase + '/questions', {
      question: el('question-text').value, owner_label: el('question-owner').value || null,
    });
    if (requestedCase !== caseId) return;
    el('question-text').value = ''; el('question-owner').value = '';
    notice('Question persisted.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('question-owner-form').addEventListener('submit', async event => {
  event.preventDefault(); try {
    const requestedCase = readyCase();
    const qid = Number(el('owner-question-choice').value);
    await api('/api/cases/' + requestedCase + '/questions/' + qid + '/owner', {
      owner_label: el('owner-label-input').value,
    });
    if (requestedCase !== caseId) return;
    el('owner-label-input').value = ''; notice('Owner label assigned.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('question-triage-form').addEventListener('submit', async event => {
  event.preventDefault(); try {
    const requestedCase = readyCase();
    const qid = Number(el('triage-question-choice').value);
    await api('/api/cases/' + requestedCase + '/questions/' + qid + '/triage', {
      triage: el('triage-value').value,
    });
    if (requestedCase !== caseId) return;
    notice('Follow-up marker updated.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('question-note-form').addEventListener('submit', async event => {
  event.preventDefault(); try {
    const requestedCase = readyCase();
    const qid = Number(el('note-question-choice').value);
    await api('/api/cases/' + requestedCase + '/questions/' + qid + '/evidence-notes', {
      note: el('question-note-text').value,
    });
    if (requestedCase !== caseId) return;
    el('question-note-text').value = ''; notice('Needed-evidence note appended.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('rollup-button').addEventListener('click', async () => {
  try {
    const requestedCase = readyCase();
    const qid = Number(el('rollup-question-choice').value);
    const data = await api('/api/cases/' + requestedCase + '/questions/' + qid + '/rollup');
    if (requestedCase !== caseId || !active || active.case.case_id !== requestedCase) return;
    renderQuestionRollup(data);
  } catch (err) { notice(err.message, true); }
});
el('draft-form').addEventListener('submit', async event => {
  event.preventDefault();
  const observations = el('draft-observations').value.trim();
  if (!observations) {
    el('draft-observations').focus();
    notice('Add reported observations before saving.', true);
    return;
  }
  try {
    const requestedCase = readyCase();
    const sources = [...el('source-choice').querySelectorAll('input:checked')].map(x => Number(x.value));
    const summary = [
      ['Reported observations', observations],
      ['Working hypothesis or mechanism', el('draft-summary').value],
      ['Assumptions, contradictions, and gaps', el('draft-assumptions').value],
    ].filter(([, text]) => text.trim())
      .map(([label, text]) => label + ':\n' + text.trim())
      .join('\n\n');
    const created = await api('/api/cases/' + requestedCase + '/snapshots', {
      question_id: Number(el('question-choice').value), summary, source_ids: sources,
      evidence_assessment_ids: [...el('evidence-choice').querySelectorAll('input:checked')].map(x => Number(x.value)),
    });
    if (requestedCase !== caseId) return;
    for (const id of ['draft-observations', 'draft-summary', 'draft-assumptions']) el(id).value = '';
    notice('Draft #' + created.snapshot_id + ' saved with exact source versions.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('example-button').addEventListener('click', async () => {
  try { el('report-text').value = (await api('/api/examples/amendment')).text; notice('Example amendment loaded; import it into CASE-ALPHA to trigger review.'); }
  catch (err) { notice(err.message, true); }
});
el('import-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const outcome = await api('/api/cases/' + requestedCase + '/imports', { text: el('report-text').value });
    if (requestedCase !== caseId) return;
    notice('Import: ' + outcome.result + (outcome.invalidated_snapshots?.length ? ', ' + outcome.invalidated_snapshots.length + ' investigation(s) marked stale' : ''));
    el('report-text').value = ''; await refresh();
  } catch (err) { notice(err.message, true); }
});

el('question-choice').addEventListener('change', () => {
  // A different question must never inherit the former question's evidence choices.
  clear('evidence-choice');
  renderEvidenceChoices();
});
el('example-evidence-button').addEventListener('click', async () => {
  try {
    el('evidence-text').value = (await api('/api/examples/evidence')).text;
    notice('Original fictional evidence example loaded.');
  } catch (err) { notice(err.message, true); }
});
el('evidence-import-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const outcome = await api('/api/evidence/imports', { text: el('evidence-text').value });
    notice('Fictional evidence: ' + outcome.result +
      (outcome.invalidated_snapshots?.length ? ', ' + outcome.invalidated_snapshots.length + ' draft(s) stale' : ''));
    el('evidence-text').value = ''; await refresh();
  } catch (err) { notice(err.message, true); }
});
el('evidence-assessment-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const outcome = await api('/api/cases/' + requestedCase + '/evidence-assessments', {
      question_id: Number(el('evidence-question-choice').value),
      evidence_version_id: Number(el('evidence-source-choice').value),
      relation: el('evidence-relation').value, applicability: el('evidence-applicability').value,
      rationale: el('evidence-rationale').value,
    });
    if (requestedCase !== caseId) return;
    notice('Human-authored fictional assessment #' + outcome.assessment_id + ' recorded.');
    el('evidence-rationale').value = ''; await refresh();
  } catch (err) { notice(err.message, true); }
});
el('evidence-withdraw-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const outcome = await api('/api/evidence/' + Number(el('evidence-withdraw-id').value) + '/withdraw', {
      reason: el('evidence-withdraw-reason').value,
    });
    if (requestedCase !== caseId) return;
    notice('Synthetic evidence withdrawn, ' + outcome.invalidated_snapshots.length + ' dependent draft(s) stale.');
    el('evidence-withdraw-reason').value = ''; await refresh();
  } catch (err) { notice(err.message, true); }
});
el('bio-explanation-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const text = id => el(id).value.trim();
    const created = await api('/api/cases/' + requestedCase + '/bio-explanations', {
      question_id: Number(el('bio-question-choice').value),
      label: text('bio-label'), mechanism_text: el('bio-mechanism').value,
      episode_id: text('bio-episode'), source_version_id: Number(el('bio-source-choice').value),
      specimen_state: el('bio-specimen-state').value,
      specimen_id: text('bio-specimen-id') || null,
      lesion_state: el('bio-lesion-state').value,
      lesion_id: text('bio-lesion-id') || null,
      clinical_context_state: el('bio-clinical-state').value,
      clinical_context_value: text('bio-clinical-value') || null,
    });
    if (requestedCase !== caseId) return;
    for (const id of ['bio-label', 'bio-mechanism', 'bio-episode', 'bio-specimen-id',
      'bio-lesion-id', 'bio-clinical-value']) el(id).value = '';
    notice('Biological explanation #' + created.bio_explanation_id +
      ' proposed; competing hypotheses stay side by side.');
    await refresh();
  } catch (err) { notice(err.message, true); }
});
el('bio-assay-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const text = id => el(id).value.trim();
    const blockChoice = el('bio-block-choice').value;
    const created = await api('/api/cases/' + requestedCase + '/bio-explanations/' +
      Number(el('bio-assay-explanation-choice').value) + '/assay-observations', {
      method_label: text('bio-method'), result_note: el('bio-result-note').value,
      source_version_id: Number(el('bio-assay-source-choice').value),
      reference_kind: el('bio-reference-kind').value,
      tissue_block_state: el('bio-block-state').value,
      tissue_block_asset_id: blockChoice === '' ? null : Number(blockChoice),
      matched_control_state: el('bio-control-state').value,
      matched_control_specimen: text('bio-control-specimen') || null,
    });
    if (requestedCase !== caseId) return;
    for (const id of ['bio-method', 'bio-result-note', 'bio-control-specimen']) el(id).value = '';
    notice('Assay observation #' + created.bio_assay_observation_id +
      ' recorded against one tissue context.');
    await refresh();
  } catch (err) { notice(err.message, true); }
});
el('option-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const created = await api('/api/cases/' + requestedCase + '/options', {
      snapshot_id: Number(el('option-snapshot-choice').value), label: el('option-label').value,
      description: el('option-description').value, epistemic_status: el('option-epistemic').value,
    });
    if (requestedCase !== caseId) return;
    el('option-label').value = ''; el('option-description').value = '';
    notice('Option #' + created.option_id + ' proposed for review.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('option-dependency-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const kind = el('dependency-kind').value;
    const pick = id => { const v = el(id).value; return v === '' ? null : Number(v); };
    const created = await api('/api/cases/' + requestedCase + '/options/' +
      Number(el('dependency-option-choice').value) + '/dependencies', {
      kind, source_version_id: kind === 'source' ? pick('dependency-source-choice') : null,
      evidence_assessment_id: kind === 'evidence_assessment' ? pick('dependency-assessment-choice') : null,
      preparation_task_id: kind === 'preparation_task' ? pick('dependency-task-choice') : null,
      depends_on_option_id: kind === 'option' ? pick('dependency-option-target-choice') : null,
      lead_time_days: el('dependency-lead').value === '' ? null : Number(el('dependency-lead').value),
      deadline_date: el('dependency-deadline').value || null,
      deadline_basis: el('dependency-basis').value, anchor: el('dependency-anchor').value,
    });
    if (requestedCase !== caseId) return;
    notice('Dependency #' + created.dependency_id + ' added.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('option-task-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const created = await api('/api/cases/' + requestedCase + '/options/' +
      Number(el('task-option-choice').value) + '/tasks', {
      label: el('task-label').value, owner_label: el('task-owner').value,
      lead_time_days: el('task-lead').value === '' ? null : Number(el('task-lead').value),
    });
    if (requestedCase !== caseId) return;
    el('task-label').value = ''; el('task-owner').value = ''; el('task-lead').value = '';
    notice('Preparation task #' + created.task_id + ' added.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('option-threat-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const created = await api('/api/cases/' + requestedCase + '/options/' +
      Number(el('threat-option-choice').value) + '/threats', {
      kind: el('threat-kind').value, description: el('threat-description').value,
      threat_date: el('threat-date').value || null, threat_basis: el('threat-basis').value,
      anchor: el('threat-anchor').value,
    });
    if (requestedCase !== caseId) return;
    el('threat-description').value = ''; el('threat-date').value = ''; el('threat-anchor').value = '';
    notice('Threat #' + created.threat_id + ' added.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('option-counterevidence-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const kind = el('counterevidence-trigger-kind').value;
    const pick = id => { const v = el(id).value; return v === '' ? null : Number(v); };
    const created = await api('/api/cases/' + requestedCase + '/options/' +
      Number(el('counterevidence-option-choice').value) + '/counterevidence', {
      effect: el('counterevidence-effect').value, reason: el('counterevidence-reason').value,
      source_version_id: kind === 'source' ? pick('counterevidence-source-choice') : null,
      evidence_assessment_id: kind === 'evidence_assessment' ? pick('counterevidence-assessment-choice') : null,
    });
    if (requestedCase !== caseId) return;
    el('counterevidence-reason').value = '';
    notice('Counterevidence #' + created.counterevidence_id + ' recorded.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('option-safety-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const kind = el('safety-trigger-kind').value;
    const pick = id => { const v = el(id).value; return v === '' ? null : Number(v); };
    const created = await api('/api/cases/' + requestedCase + '/options/' +
      Number(el('safety-option-choice').value) + '/safety-flags', {
      category: el('safety-category').value, detail: el('safety-detail').value,
      source_version_id: kind === 'source' ? pick('safety-source-choice') : null,
      evidence_assessment_id: kind === 'evidence_assessment' ? pick('safety-assessment-choice') : null,
    });
    if (requestedCase !== caseId) return;
    el('safety-detail').value = '';
    notice('Safety uncertainty #' + created.safety_flag_id + ' recorded.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('option-review-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const outcome = await api('/api/cases/' + requestedCase + '/options/' +
      Number(el('review-option-choice').value) + '/review', {
      reviewer_label: el('reviewer-label').value, action: el('review-action').value,
      scope: el('review-scope').value,
      snapshot_id: el('review-snapshot-choice').value === '' ? null : Number(el('review-snapshot-choice').value),
    });
    if (requestedCase !== caseId) return;
    el('review-scope').value = '';
    notice('Reviewer action recorded: ' + outcome.result + '.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('visit-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const created = await api('/api/cases/' + requestedCase + '/visits', {
      recorded_date: el('visit-date').value,
      visit_type: el('visit-type').value,
      notes: el('visit-notes').value,
      source_anchor: el('visit-anchor').value.trim() ? el('visit-anchor').value : null,
    });
    if (requestedCase !== caseId) return;
    for (const id of ['visit-date', 'visit-type', 'visit-notes', 'visit-anchor']) el(id).value = '';
    notice('FICTIONAL visit #' + created.visit_id + ' recorded as history.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('visit-amend-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const outcome = await api('/api/cases/' + requestedCase + '/visits/' +
      Number(el('visit-amend-choice').value) + '/amend', {
      recorded_date: el('visit-amend-date').value,
      visit_type: el('visit-amend-type').value,
      notes: el('visit-amend-notes').value,
      source_anchor: el('visit-amend-anchor').value.trim() ? el('visit-amend-anchor').value : null,
    });
    if (requestedCase !== caseId) return;
    for (const id of ['visit-amend-date', 'visit-amend-type', 'visit-amend-notes', 'visit-amend-anchor']) el(id).value = '';
    notice('FICTIONAL visit amended; version ' + outcome.version + ' is current, history preserved.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('followthrough-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const pick = id => { const v = el(id).value; return v === '' ? null : Number(v); };
    const created = await api('/api/cases/' + requestedCase + '/followthrough-tasks', {
      title: el('ft-title').value, detail: el('ft-detail').value || null,
      due_date: el('ft-due').value || null, review_trigger: el('ft-trigger').value || null,
      question_id: pick('ft-question'), source_version_id: pick('ft-source'),
      actor_label: el('ft-actor').value, reason: el('ft-reason').value || null,
    });
    if (requestedCase !== caseId) return;
    for (const id of ['ft-title', 'ft-detail', 'ft-due', 'ft-trigger', 'ft-actor', 'ft-reason']) el(id).value = '';
    notice('Follow-through task #' + created.task_id + ' recorded. Nothing was acted on.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('followthrough-update-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const payload = {
      status: el('ft-status').value, actor_label: el('ft-update-actor').value,
      reason: el('ft-update-reason').value, owner_label: el('ft-owner').value || null,
    };
    if (el('ft-clear-due').checked) payload.due_date = null;
    else if (el('ft-update-due').value) payload.due_date = el('ft-update-due').value;
    const outcome = await api('/api/cases/' + requestedCase + '/followthrough-tasks/' +
      Number(el('ft-task-choice').value) + '/status', payload);
    if (requestedCase !== caseId) return;
    el('ft-owner').value = ''; el('ft-update-due').value = '';
    el('ft-clear-due').checked = false;
    el('ft-update-actor').value = ''; el('ft-update-reason').value = '';
    notice('Task #' + outcome.task_id + ' is now ' + outcome.result + '. History preserved.'); await refresh();
  } catch (err) { notice(err.message, true); }
});

el('goal-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const created = await api('/api/cases/' + requestedCase + '/patient-goals', {
      statement: el('goal-statement').value, stated_date: el('goal-stated-date').value,
      review_trigger: el('goal-review-trigger').value,
      review_date: el('goal-review-date').value || null,
    });
    if (requestedCase !== caseId) return;
    el('goal-statement').value = ''; el('goal-stated-date').value = '';
    el('goal-review-trigger').value = ''; el('goal-review-date').value = '';
    notice('Fictional goal #' + created.goal_id + ' recorded in the patient\'s own words.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('goal-amend-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const outcome = await api('/api/cases/' + requestedCase + '/patient-goals/' +
      Number(el('amend-goal-choice').value) + '/amendments', {
      statement: el('amend-goal-statement').value, stated_date: el('amend-goal-stated-date').value,
      review_trigger: el('amend-goal-review-trigger').value,
      review_date: el('amend-goal-review-date').value || null,
    });
    if (requestedCase !== caseId) return;
    el('amend-goal-statement').value = ''; el('amend-goal-stated-date').value = '';
    el('amend-goal-review-trigger').value = ''; el('amend-goal-review-date').value = '';
    notice('Goal #' + outcome.goal_id + ' version ' + outcome.version + ' saved; earlier wording kept.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('goal-status-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const outcome = await api('/api/cases/' + requestedCase + '/patient-goals/' +
      Number(el('status-goal-choice').value) + '/status', {
      status: el('goal-status').value, reason: el('goal-status-reason').value,
    });
    if (requestedCase !== caseId) return;
    el('goal-status-reason').value = '';
    notice('Goal #' + outcome.goal_id + ' marked ' + outcome.status + ' with reason.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('note-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const created = await api('/api/cases/' + requestedCase + '/patient-notes', {
      kind: el('note-kind').value, text: el('note-text').value,
      noted_date: el('note-noted-date').value,
    });
    if (requestedCase !== caseId) return;
    el('note-text').value = ''; el('note-noted-date').value = '';
    notice('Fictional note #' + created.note_id + ' recorded in the patient\'s own words.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('note-amend-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const outcome = await api('/api/cases/' + requestedCase + '/patient-notes/' +
      Number(el('amend-note-choice').value) + '/amendments', {
      text: el('amend-note-text').value, noted_date: el('amend-note-noted-date').value,
    });
    if (requestedCase !== caseId) return;
    el('amend-note-text').value = ''; el('amend-note-noted-date').value = '';
    notice('Note #' + outcome.note_id + ' version ' + outcome.version + ' saved; earlier wording kept.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('portfolio-flag-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const pick = id => { const v = el(id).value; return v === '' ? null : Number(v); };
    const created = await api('/api/cases/' + requestedCase + '/options/' +
      Number(el('flag-option-choice').value) + '/flags', {
      kind: el('flag-kind').value, label: el('flag-label').value,
      reason: el('flag-reason').value, author_label: el('flag-author').value,
      source_version_id: pick('flag-source-choice'),
      evidence_assessment_id: pick('flag-assessment-choice'),
    });
    if (requestedCase !== caseId) return;
    el('flag-label').value = ''; el('flag-reason').value = '';
    notice('Flag #' + created.flag_id + ' recorded.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('portfolio-flag-resolve-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const outcome = await api('/api/cases/' + requestedCase + '/flags/' +
      Number(el('flag-resolve-choice').value) + '/resolve', {
      reviewer_label: el('flag-resolve-reviewer').value, action: el('flag-resolve-action').value,
      scope: el('flag-resolve-scope').value,
    });
    if (requestedCase !== caseId) return;
    el('flag-resolve-scope').value = '';
    notice('Flag decision recorded: ' + outcome.result + '.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('portfolio-dimension-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const pick = id => { const v = el(id).value; return v === '' ? null : Number(v); };
    const created = await api('/api/cases/' + requestedCase + '/options/' +
      Number(el('dimension-option-choice').value) + '/dimension-notes', {
      dimension: el('dimension-kind').value, note: el('dimension-note').value,
      anchor: el('dimension-anchor').value, reviewer_label: el('dimension-recorder').value,
      source_version_id: pick('dimension-source-choice'),
      evidence_assessment_id: pick('dimension-assessment-choice'),
    });
    if (requestedCase !== caseId) return;
    el('dimension-note').value = ''; el('dimension-anchor').value = '';
    notice('Dimension note #' + created.dimension_note_id + ' recorded as pending.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('portfolio-dimension-ack-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    await api('/api/cases/' + requestedCase + '/dimension-notes/' +
      Number(el('dimension-ack-choice').value) + '/acknowledge', {
      reviewer_label: el('dimension-ack-reviewer').value, scope: el('dimension-ack-scope').value,
    });
    if (requestedCase !== caseId) return;
    el('dimension-ack-scope').value = '';
    notice('Dimension note acknowledged as seen; this is not authorization.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('scoped-decision-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const outcome = await api('/api/cases/' + requestedCase + '/snapshots/' +
      Number(el('scoped-decision-snapshot').value) + '/scoped-decisions', {
      reviewer_label: el('scoped-decision-reviewer').value, scope: el('scoped-decision-scope').value,
      note: el('scoped-decision-note').value,
    });
    if (requestedCase !== caseId) return;
    el('scoped-decision-note').value = '';
    notice('Scope note recorded: ' + outcome.scope + '.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('scoped-dissent-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const outcome = await api('/api/cases/' + requestedCase + '/snapshots/' +
      Number(el('scoped-dissent-snapshot').value) + '/scoped-dissents', {
      reviewer_label: el('scoped-dissent-reviewer').value, claim_ref: el('scoped-dissent-claim').value,
      rationale: el('scoped-dissent-rationale').value,
    });
    if (requestedCase !== caseId) return;
    el('scoped-dissent-claim').value = ''; el('scoped-dissent-rationale').value = '';
    notice('Disagreement recorded on finding ' + outcome.claim_ref + '.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('scoped-handoff-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const outcome = await api('/api/cases/' + requestedCase + '/snapshots/' +
      Number(el('scoped-handoff-snapshot').value) + '/scoped-handoffs', {
      from_reviewer: el('scoped-handoff-from').value, to_reviewer: el('scoped-handoff-to').value,
    });
    if (requestedCase !== caseId) return;
    notice('Open items handed to ' + el('scoped-handoff-to').value + ' (handoff #' + outcome.handoff_id + ').'); await refresh();
  } catch (err) { notice(err.message, true); }
});

el('so-request-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const created = await api('/api/cases/' + requestedCase + '/second-opinion-requests', {
      question_id: Number(el('so-question-choice').value),
      question_text: el('so-question-text').value,
      source_version_ids: [...el('so-source-choice').querySelectorAll('input:checked')].map(x => Number(x.value)),
      snapshot_id: el('so-snapshot-choice').value === '' ? null : Number(el('so-snapshot-choice').value),
    });
    if (requestedCase !== caseId) return;
    el('so-question-text').value = '';
    notice('Second-opinion request #' + created.request_id + ' recorded with pinned source versions.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('so-response-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const created = await api('/api/cases/' + requestedCase + '/second-opinion-requests/' +
      Number(el('so-request-choice').value) + '/response', {
      responder_label: el('so-responder').value,
      response_text: el('so-response-text').value,
      anchor_source_version_id: Number(el('so-anchor-choice').value),
    });
    if (requestedCase !== caseId) return;
    el('so-responder').value = ''; el('so-response-text').value = '';
    notice('Separate second-opinion response #' + created.response_id + ' recorded. The original conclusion is unchanged.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('surv-plan-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const created = await api('/api/cases/' + requestedCase + '/survivorship-plans', {
      title: el('surv-plan-title').value,
    });
    if (requestedCase !== caseId) return;
    el('surv-plan-title').value = '';
    notice('Survivorship plan #' + created.plan_id + ' recorded.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('surv-item-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const created = await api('/api/cases/' + requestedCase + '/survivorship-plans/' +
      Number(el('surv-plan-choice').value) + '/items', {
      kind: el('surv-kind').value,
      description: el('surv-description').value,
      recorded_date: el('surv-date').value || null,
      anchor_source_version_id: Number(el('surv-anchor-choice').value),
    });
    if (requestedCase !== caseId) return;
    el('surv-description').value = ''; el('surv-date').value = '';
    notice('Plan item #' + created.item_id + ' recorded as a plain description.'); await refresh();
  } catch (err) { notice(err.message, true); }
});

function renderPatientWords() {
  el('patient-words-disclaimer').textContent = active.patient_words_disclaimer || '';
  const goals = active.patient_goals || [];
  const notes = active.patient_notes || [];
  const fill = (id, items, labelFn) => {
    const select = el(id);
    const prior = select.value;
    clear(id);
    for (const item of items) {
      const opt = node('option', labelFn(item));
      opt.value = item.value; select.append(opt);
    }
    if (prior && [...select.options].some(x => x.value === prior)) select.value = prior;
  };
  const goalLabel = g => 'Goal #' + g.goal_id + ' · ' + (g.current ? g.current.status : 'unknown');
  fill('amend-goal-choice', goals.map(g => ({ value: g.goal_id, label: g })), x => goalLabel(x.label));
  fill('status-goal-choice', goals.map(g => ({ value: g.goal_id, label: g })), x => goalLabel(x.label));
  fill('amend-note-choice', notes.map(n => ({ value: n.note_id, label: n })),
    x => 'Note #' + x.label.note_id + ' · ' + (x.label.kind === 'symptom' ? 'symptom note' : 'lived experience'));
  clear('goal-list');
  if (!goals.length) empty(el('goal-list'), 'No fictional patient goals recorded for this case yet.');
  for (const goal of goals) {
    const current = goal.current || {};
    const box = node('div', null, 'snapshot');
    const top = node('div', null, 'topline');
    top.append(node('strong', 'Fictional goal #' + goal.goal_id + ' · patient\'s own words'),
      pill(current.status || 'unknown', current.status === 'active' ? 'pill-warn' : ''),
      pill('FICTIONAL', 'pill-neutral'));
    box.append(top, node('p', current.statement || ''));
    box.append(node('p', 'Stated ' + (current.stated_date || 'date unknown') +
      ' · Look at it again: ' + (current.review_trigger || 'not recorded') +
      (current.review_date ? ' · Review date ' + current.review_date : ' · No review date') +
      ' · Version ' + (current.version || '?') + ' of ' + goal.versions.length, 'snapshot-meta'));
    if (current.status_reason) box.append(node('p', 'Standing reason: ' + current.status_reason, 'muted'));
    if (goal.versions.length > 1) {
      box.append(node('p', 'Earlier wording kept: ' + goal.versions
        .filter(v => v.record_state !== 'current')
        .map(v => 'v' + v.version + ' (' + v.stated_date + '): ' + v.statement).join(' | '), 'muted tiny'));
    }
    box.append(node('p', 'Not a diagnosis, staging, response claim, or recommendation.', 'muted tiny'));
    el('goal-list').append(box);
  }
  clear('note-list');
  if (!notes.length) empty(el('note-list'), 'No fictional lived-experience or symptom notes recorded yet.');
  for (const item of notes) {
    const current = item.current || {};
    const box = node('div', null, 'snapshot');
    const top = node('div', null, 'topline');
    const kindLabel = item.kind === 'symptom' ? 'Symptom note · what the patient noticed' : 'Lived experience · daily life';
    top.append(node('strong', 'Fictional note #' + item.note_id + ' · ' + kindLabel),
      pill('patient-reported', 'pill-neutral'), pill('FICTIONAL', 'pill-neutral'));
    box.append(top, node('p', current.note_text || ''));
    box.append(node('p', 'Noted ' + (current.noted_date || 'date unknown') +
      ' · Version ' + (current.version || '?') + ' of ' + item.versions.length, 'snapshot-meta'));
    if (item.versions.length > 1) {
      box.append(node('p', 'Earlier wording kept: ' + item.versions
        .filter(v => v.record_state !== 'current')
        .map(v => 'v' + v.version + ' (' + v.noted_date + '): ' + v.note_text).join(' | '), 'muted tiny'));
    }
    box.append(node('p', 'Patient-reported only. Never a diagnosis, staging, or response claim.', 'muted tiny'));
    el('note-list').append(box);
  }
}
function journeyStep(prefix, pillText, statusText) {
  // textContent assignment atomically replaces the previous case's text,
  // so no stale list content survives a case switch. render() is already
  // case-guarded, and this runs only inside render().
  el(prefix + '-pill').textContent = pillText;
  el(prefix + '-status').textContent = statusText;
}
function renderJourney() {
  if (!active) return;
  const sources = active.sources || [];
  const current = sources.filter(s => s.state === 'current').length;
  const documents = new Set(sources.map(s => s.document_id)).size;
  const quarantined = (active.quarantines || []).length;
  const questions = active.questions || [];
  const openQuestions = questions.filter(q => q.state === 'open').length;
  const snapshots = active.snapshots || [];
  const stale = snapshots.filter(s => s.state === 'stale').length;
  const drafts = snapshots.filter(s => s.state === 'draft').length;
  const reviewed = snapshots.filter(s => s.state === 'reviewed_in_demo').length;
  const options = active.options || [];
  const openTasks = options.flatMap(o => o.preparation_tasks || [])
    .filter(t => t.status === 'not_started' || t.status === 'in_progress' || t.status === 'blocked').length;
  const pillFor = (count) => count ? 'Has entries' : 'Nothing yet';
  journeyStep('journey-intake', pillFor(sources.length), sources.length
    ? documents + ' fictional report(s) received across ' + sources.length + ' version(s). ' +
      quarantined + ' mismatched item(s) kept out of the case.'
    : 'No reports have been added to this fictional case yet. Adding the first report starts step 2.');
  journeyStep('journey-sources', pillFor(sources.length), sources.length
    ? current + ' current source document(s) · ' + (active.assertions || []).length + ' reported statement(s).'
    : 'No records are available to read yet. This step fills in once intake holds a report.');
  journeyStep('journey-questions', pillFor(questions.length), questions.length
    ? openQuestions + ' open question(s) of ' + questions.length + ' recorded.'
    : 'No questions have been written down yet. Later steps work from the questions listed here.');
  journeyStep('journey-review',
    snapshots.length ? (stale + drafts ? 'Needs a look' : 'Nothing flagged') : 'Nothing yet',
    snapshots.length
      ? stale + ' draft(s) needing another look · ' + drafts + ' draft(s) awaiting review · ' +
        reviewed + ' acknowledged in demo.' + (stale + drafts ? '' : ' No draft currently needs another look.')
      : 'No drafts exist yet, so there is nothing to re-check.');
  journeyStep('journey-report', pillFor(snapshots.length), snapshots.length
    ? snapshots.length + ' saved draft(s): ' + drafts + ' awaiting review · ' + stale +
      ' needing another look · ' + reviewed + ' acknowledged in demo. ' +
      'Each draft stays pinned to the exact source versions it used.'
    : 'No drafts have been saved yet. A draft appears here once a question has a written narrative.');
  journeyStep('journey-followthrough', pillFor(options.length), options.length
    ? options.length + ' discussion item(s) · ' + openTasks + ' open preparation task(s).'
    : 'No discussion items have been proposed yet. An item appears here once a draft exists to discuss.');
}
function renderOptions() {
  el('option-disclaimer').textContent = [active.option_disclaimer, active.option_receipt_disclaimer]
    .filter(x => x).join(' ');
  const sameCase = renderedCaseId === caseId;
  const options = active.options || [];
  const fill = (id, items, labelFn, allowEmpty = false) => {
    const select = el(id);
    const prior = sameCase ? select.value : '';
    clear(id);
    if (allowEmpty) { const blank = node('option', '—'); blank.value = ''; select.append(blank); }
    for (const item of items) {
      const opt = node('option', labelFn(item));
      opt.value = item.id; select.append(opt);
    }
    if (prior && [...select.options].some(x => x.value === prior)) select.value = prior;
  };
  fill('option-snapshot-choice', active.snapshots, s => 'Investigation #' + s.id + ' · ' + s.state);
  fill('review-snapshot-choice', active.snapshots, s => 'Investigation #' + s.id + ' · ' + s.state, true);
  const optionLabel = o => 'Option #' + o.id + ' · ' + o.label + ' (' + o.display_operational_status + ')';
  fill('dependency-option-choice', options, optionLabel);
  fill('task-option-choice', options, optionLabel);
  fill('threat-option-choice', options, optionLabel);
  fill('counterevidence-option-choice', options, optionLabel);
  fill('safety-option-choice', options, optionLabel);
  fill('review-option-choice', options, optionLabel);
  fill('dependency-option-target-choice', options, optionLabel, true);
  fill('dependency-source-choice', active.sources, s => s.document_id + '@' + s.version + ' · ' + s.state, true);
  fill('dependency-assessment-choice', active.evidence_assessments || [],
    a => a.evidence_key + '@' + a.version + ' · ' + a.relation, true);
  fill('counterevidence-source-choice', active.sources, s => s.document_id + '@' + s.version + ' · ' + s.state, true);
  fill('counterevidence-assessment-choice', active.evidence_assessments || [],
    a => a.evidence_key + '@' + a.version + ' · ' + a.relation, true);
  fill('safety-source-choice', active.sources, s => s.document_id + '@' + s.version + ' · ' + s.state, true);
  fill('safety-assessment-choice', active.evidence_assessments || [],
    a => a.evidence_key + '@' + a.version + ' · ' + a.relation, true);
  const tasks = options.flatMap(o => o.preparation_tasks.map(t => ({ ...t, optionLabel: o.label })));
  fill('dependency-task-choice', tasks, t => 'Task #' + t.id + ' · ' + t.label + ' (' + t.status + ')', true);
  clear('option-list');
  if (!options.length) empty(el('option-list'), 'No options proposed for this case yet.');
  for (const option of options) {
    const box = node('div', null, 'snapshot');
    const top = node('div', null, 'topline');
    top.append(node('strong', 'Option #' + option.id + ' · ' + option.label),
      pill(option.derived_epistemic_status, option.derived_epistemic_status === 'contradicted' ? 'pill-alert' : ''),
      pill(option.display_operational_status, option.display_operational_status === 'held' ? 'pill-alert' : ''),
      pill('review: ' + option.review_state, option.review_state === 'needs_review' ? 'pill-warn' : ''));
    if (option.dependency_loss && option.dependency_loss.present) {
      top.append(pill('dependency loss: ' + option.dependency_loss.causes.length + ' cause(s)', 'pill-alert'));
    }
    box.append(top, node('p', option.description),
      node('p', 'Based on investigation #' + option.snapshot_id + ' (' + option.snapshot_state + ') · ' +
        option.potential_discussion_deadline.label, 'snapshot-meta'));
    if (option.dependency_loss && option.dependency_loss.present) {
      box.append(node('p', 'Dependency loss (derived, never a stored threat): ' +
        option.dependency_loss.causes.join('; '), 'snapshot-meta'));
    }
    if (option.dependencies.length) {
      const deps = node('ul');
      for (const dep of option.dependencies) {
        const line = node('li', dep.kind + ': ' + dep.target +
          (dep.deadline_date ? ' · deadline ' + dep.deadline_date + ' (' + dep.deadline_basis + ')' : ' · deadline unknown') +
          (dep.lead_time_days !== null && dep.lead_time_days !== undefined ? ' · lead ' + dep.lead_time_days + 'd' : ''));
        deps.append(line);
      }
      box.append(node('p', 'Dependencies:', 'snapshot-meta'), deps);
    }
    if (option.preparation_tasks.length) {
      box.append(node('p', 'Preparation tasks: ' + option.preparation_tasks.map(t =>
        t.label + ' · owner ' + t.owner_label + ' · ' + t.status +
        (t.receipt_id ? ' · receipt #' + t.receipt_id :
          (t.receipt_marker === 'receipt_predates_slice' ? ' · receipt predates this view' : ' · no receipt')) +
        (t.lead_time_days !== null && t.lead_time_days !== undefined ? ' · lead ' + t.lead_time_days + 'd' : '')).join('; '), 'snapshot-meta'));
      if (Array.isArray(option.open_task_ids) && Array.isArray(option.receipted_task_ids)) {
        const open = option.open_task_ids.map(n => '#' + n).join(', ') || 'none';
        const receipted = option.receipted_task_ids.map(n => '#' + n).join(', ') || 'none';
        box.append(node('p', 'Open tasks: ' + open + ' · Receipted tasks: ' + receipted, 'snapshot-meta'));
      }
    }
    if (option.threats.length) {
      box.append(node('p', 'Optionality threats: ' + option.threats.map(t =>
        t.kind + ': ' + t.description +
        (t.threat_date ? ' · ' + t.threat_date + ' (' + t.threat_basis + ')' : ' · date unknown')).join(' ; '), 'snapshot-meta'));
    }
    if ((option.counterevidence || []).length) {
      const list = node('ul');
      for (const item of option.counterevidence) {
        list.append(node('li', 'Fictional counterevidence #' + item.id + ' · ' + item.effect +
          ' · triggered by ' + item.trigger + ' (' + item.trigger_state + ') · reason: ' + item.reason));
      }
      box.append(node('p', 'Counterevidence (holds and invalidations stay visible):', 'snapshot-meta'), list);
    }
    if ((option.safety_flags || []).length) {
      const list = node('ul');
      for (const flag of option.safety_flags) {
        // The server label is rendered verbatim and never stripped: it is
        // what keeps a single-modality note from reading as established
        // benefit/toxicity and a preclinical note from reading as a
        // patient response or permission.
        list.append(node('li', 'Fictional safety note #' + flag.id + ' · ' + flag.display_label +
          ' Detail: ' + flag.detail + ' · triggered by ' + flag.trigger + ' (' + flag.trigger_state + ')'));
      }
      box.append(node('p', 'Safety uncertainties (visible before any promotion):', 'snapshot-meta'), list);
    }
    if (option.safety_block) {
      box.append(node('p', 'Promotion blocked: ' + option.safety_block + '.', 'snapshot-meta'));
    }
    if (option.review_events.length) {
      box.append(node('p', 'Review history: ' + option.review_events.map(e =>
        e.action + ' by ' + e.reviewer_label + ' · scope: ' + e.scope).join(' ; '), 'snapshot-meta'));
    }
    const investigationLink = document.createElement('a');
    investigationLink.href = '#investigation-history-heading';
    investigationLink.className = 'button secondary minor';
    investigationLink.textContent = 'View investigation #' + option.snapshot_id;
    box.append(investigationLink);
    el('option-list').append(box);
  }
}
function renderTaskList(id, tasks, emptyText) {
  clear(id);
  if (!tasks.length) { empty(el(id), emptyText); return; }
  for (const task of tasks) {
    const box = node('div', null, 'snapshot');
    const top = node('div', null, 'topline');
    top.append(node('strong', 'Task #' + task.id + ' · ' + task.title),
      pill(task.status, task.is_overdue ? 'pill-alert' : task.status === 'completed' ? '' : 'pill-warn'));
    if (task.is_overdue) top.append(pill('overdue', 'pill-alert'));
    if (task.is_due_soon) top.append(pill('due soon', 'pill-warn'));
    if (task.needs_recheck) top.append(pill('linked source amended — re-check', 'pill-warn'));
    box.append(top);
    if (task.detail) box.append(node('p', task.detail));
    box.append(node('p', 'Owner: ' + (task.owner_label || 'not assigned yet') +
      ' · Due: ' + (task.due_date || 'no due date') +
      (task.review_trigger ? ' · Revisit: ' + task.review_trigger : '') +
      (task.question_id ? ' · Question Q' + task.question_id + ' (' + (task.question_state || 'unknown') + ')' : '') +
      (task.source_version_id ? ' · Source #' + task.source_version_id + ' (' + (task.source_state || 'unknown') + ')' : ''),
      'snapshot-meta'));
    if (task.status === 'completed') {
      box.append(node('p', task.human_action_recorded
        ? 'Recorded as done by a human after acknowledgment. Full history is kept below.'
        : 'Completion is recorded without an acknowledgment path; treat this record as unreliable.', 'muted'));
    } else {
      box.append(node('p', 'No action taken by the platform. This record waits for a human to act.', 'muted tiny'));
    }
    if (task.history && task.history.length) {
      box.append(node('p', 'History: ' + task.history.map(entry =>
        (entry.previous_status ? entry.previous_status + ' → ' : '') + entry.new_status +
        ' by ' + entry.actor_label + ' at ' + entry.noted_at +
        (entry.reason ? ' — ' + entry.reason : '')).join(' ; '), 'snapshot-meta'));
    }
    el(id).append(box);
  }
}
function renderFollowthrough() {
  const data = active.followthrough || { tasks: [], counts: {}, disclaimer: '' };
  el('followthrough-disclaimer').textContent = data.disclaimer || '';
  const tasks = data.tasks || [];
  const overdueIds = new Set(data.overdue_task_ids || []);
  const dueSoonIds = new Set(data.due_soon_task_ids || []);
  const counts = data.counts || {};
  const attention = el('followthrough-attention');
  attention.dataset.state = overdueIds.size ? 'needs-review' : 'no-open-review';
  el('followthrough-attention-heading').textContent = overdueIds.size
    ? overdueIds.size + ' overdue task(s) need a human to act'
    : 'Follow-through reminders';
  el('followthrough-attention-summary').textContent = overdueIds.size || dueSoonIds.size
    ? overdueIds.size + ' overdue · ' + dueSoonIds.size + ' due within 7 days · ' +
      (counts.open || 0) + ' open in total. These are records for humans; nothing here acts on its own.'
    : tasks.length
      ? 'No overdue or due-soon tasks. ' + (counts.open || 0) +
        ' open task(s) remain. Completed tasks stay in history below.'
      : 'No follow-through tasks recorded for this fictional case yet.';
  const fill = (id, items, labelFn, allowEmpty = false) => {
    const select = el(id);
    const prior = select.value;
    clear(id);
    if (allowEmpty) { const blank = node('option', '—'); blank.value = ''; select.append(blank); }
    for (const item of items) {
      const opt = node('option', labelFn(item));
      opt.value = item.id; select.append(opt);
    }
    if (prior && [...select.options].some(x => x.value === prior)) select.value = prior;
  };
  fill('ft-question', active.questions || [], q => 'Q' + q.id + ', ' + q.question.slice(0, 62), true);
  fill('ft-source', (active.sources || []).filter(s => s.state === 'current'),
    s => s.document_id + '@' + s.version + ', ' + s.event_date, true);
  fill('ft-task-choice', tasks, t => 'Task #' + t.id + ' · ' + t.title + ' (' + t.status + ')');
  renderTaskList('ft-overdue', tasks.filter(t => overdueIds.has(t.id)),
    'No overdue tasks. An overdue task would appear here until a human records its progress.');
  renderTaskList('ft-duesoon', tasks.filter(t => dueSoonIds.has(t.id)),
    'No tasks due within the next 7 days.');
  renderTaskList('ft-open', tasks.filter(t => ['created', 'assigned', 'acknowledged'].includes(t.status)),
    'No open tasks in this fictional case.');
  renderTaskList('ft-deferred', tasks.filter(t => t.status === 'deferred'),
    'No deferred tasks. A deferral keeps its reason in history.');
  renderTaskList('ft-completed', tasks.filter(t => t.status === 'completed'),
    'No completed tasks yet. Completed tasks stay here as history.');
}

function reviewAgeText(days) {
  if (!Number.isInteger(days) || days <= 0) return 'added today';
  return days === 1 ? '1 day old' : days + ' days old';
}
async function loadReviewQueue() {
  const requested = caseId;
  for (const id of ['review-awaiting', 'review-resolved', 'review-receipts']) clear(id);
  el('review-queue-disclaimer').textContent = '';
  try {
    const data = await api('/api/cases/' + requested + '/review-queue');
    if (requested !== caseId || !active || active.case.case_id !== requested) return;
    renderReviewQueue(data);
  } catch (err) {
    if (requested !== caseId) return;
    el('review-queue-disclaimer').textContent = 'Review queue unavailable: ' + err.message;
    empty(el('review-awaiting'), 'Review queue unavailable.');
    empty(el('review-resolved'), 'Review queue unavailable.');
    empty(el('review-receipts'), 'Review queue unavailable.');
  }
}
function renderReviewQueue(data) {
  el('review-queue-disclaimer').textContent = (data.synthetic ? 'Fictional synthetic data only. ' : '') + (data.disclaimer || '');
  clear('review-awaiting');
  const awaiting = data.awaiting || [];
  if (!awaiting.length) empty(el('review-awaiting'), 'Nothing waiting for review in this fictional case.');
  for (const item of awaiting) {
    const box = node('div', null, 'snapshot');
    const top = node('div', null, 'topline');
    top.append(node('strong', item.title),
      pill(item.kind, 'pill-neutral'),
      pill(item.status === 'returned' ? 'returned' : 'waiting', item.status === 'returned' ? 'pill-warn' : 'pill-alert'),
      pill(reviewAgeText(item.age_days)));
    box.append(top, node('p', item.detail),
      node('p', 'Listed since ' + item.created_at + '.', 'snapshot-meta'));
    if (item.reopened_after_change)
      box.append(node('p', 'Reopened after a change. Earlier decisions are kept below; they no longer cover the current version.', 'muted'));
    if (item.status === 'returned')
      box.append(node('p', 'Returned by ' + item.returned_by + ': ' + item.return_reason, 'muted'));
    for (const prior of item.prior_receipts || [])
      box.append(node('p', 'Earlier: ' + prior.action + ' by ' + prior.reviewer_label +
        ' on ' + prior.created_at + ' (older version).', 'muted tiny'));
    const form = document.createElement('form');
    form.className = 'withdraw-form';
    const reviewerLabel = document.createElement('label');
    reviewerLabel.textContent = 'Reviewer label (unverified demo label)';
    const reviewer = document.createElement('input');
    reviewer.type = 'text'; reviewer.maxLength = 80; reviewer.required = true;
    reviewer.placeholder = 'Synthetic reviewer (unverified)';
    reviewerLabel.append(reviewer);
    const actionLabel = document.createElement('label');
    actionLabel.textContent = 'Decision';
    const action = document.createElement('select');
    for (const [value, text] of [['reviewed', 'Reviewed — I looked at this item'],
        ['acknowledged', 'Acknowledged — I saw this item'],
        ['returned', 'Returned — needs more work (reason required)']]) {
      const opt = node('option', text); opt.value = value; action.append(opt);
    }
    actionLabel.append(action);
    const reasonLabel = document.createElement('label');
    reasonLabel.textContent = 'Reason (required when returned)';
    const reason = document.createElement('textarea');
    reason.rows = 2; reason.maxLength = 600;
    reason.placeholder = 'What did you look at, or what is still needed? No treatment language.';
    reasonLabel.append(reason);
    const submit = node('button', 'Record sign-off', 'button minor');
    submit.type = 'submit';
    form.append(reviewerLabel, actionLabel, reasonLabel, submit);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      try {
        const requestedCase = readyCase();
        await api('/api/cases/' + requestedCase + '/review-queue/receipts', {
          queue_key: item.queue_key, action: action.value,
          reviewer_label: reviewer.value, reason: reason.value.trim() || null,
        });
        if (requestedCase !== caseId) return;
        notice(action.value === 'returned'
          ? 'Returned with reason. The item stays visibly queued.'
          : 'Sign-off recorded. This is an acknowledgment, not a treatment authorization.');
        await refresh();
      } catch (err) { notice(err.message, true); }
    });
    box.append(form);
    el('review-awaiting').append(box);
  }
  clear('review-resolved');
  const resolved = data.resolved || [];
  if (!resolved.length) empty(el('review-resolved'), 'No recorded decisions yet in this fictional case.');
  for (const item of resolved) {
    const box = node('div', null, 'snapshot');
    const top = node('div', null, 'topline');
    top.append(node('strong', item.title), pill(item.kind, 'pill-neutral'), pill('decided'));
    box.append(top, node('p', item.detail, 'muted'));
    const by = item.resolved_by || {};
    box.append(node('p', (by.action || 'decided') + ' by ' + (by.reviewer_label || 'unknown reviewer') +
      ' on ' + (by.created_at || 'unknown time') +
      (by.reason ? '. Note: ' + by.reason : ''), 'snapshot-meta'));
    el('review-resolved').append(box);
  }
  clear('review-receipts');
  const receipts = data.receipts || [];
  if (!receipts.length) empty(el('review-receipts'), 'No sign-off records yet. Records are append-only and never edited or deleted.');
  for (const receipt of receipts.slice().reverse()) {
    const card = node('div', receipt.queue_key + ' — ' + receipt.action + ' by ' + receipt.reviewer_label, 'event');
    card.append(node('small', receipt.created_at + (receipt.reason ? ' · ' + receipt.reason : '')));
    el('review-receipts').append(card);
  }
}
function renderPortfolio() {
  const portfolio = active.portfolio || { options: [], disclaimer: '', counts: {} };
  el('portfolio-disclaimer').textContent = portfolio.disclaimer || '';
  const entries = portfolio.options || [];
  const fill = (id, items, labelFn, allowEmpty = false) => {
    const select = el(id);
    const prior = select.value;
    clear(id);
    if (allowEmpty) { const blank = node('option', '—'); blank.value = ''; select.append(blank); }
    for (const item of items) {
      const opt = node('option', labelFn(item));
      opt.value = item.id; select.append(opt);
    }
    if (prior && [...select.options].some(x => x.value === prior)) select.value = prior;
  };
  const entryLabel = o => 'Option #' + o.id + ' · ' + o.label + ' (' + o.portfolio_status + ')';
  fill('flag-option-choice', entries, entryLabel);
  fill('dimension-option-choice', entries, entryLabel);
  fill('flag-source-choice', active.sources, s => s.document_id + '@' + s.version + ' · ' + s.state, true);
  fill('dimension-source-choice', active.sources, s => s.document_id + '@' + s.version + ' · ' + s.state, true);
  fill('flag-assessment-choice', active.evidence_assessments || [],
    a => a.evidence_key + '@' + a.version + ' · ' + a.relation, true);
  fill('dimension-assessment-choice', active.evidence_assessments || [],
    a => a.evidence_key + '@' + a.version + ' · ' + a.relation, true);
  const flags = entries.flatMap(o => [...o.objections.open, ...o.objections.resolved, ...o.holds, ...o.past_holds]
    .map(f => ({ ...f, optionId: o.id })));
  fill('flag-resolve-choice', flags,
    f => 'Flag #' + f.id + ' · ' + f.kind + ' · ' + f.label + ' (' + f.state + ')');
  const pendingNotes = entries.flatMap(o => Object.values(o.dimensions).flatMap(d => d.notes)
    .map(n => ({ ...n, optionId: o.id }))).filter(n => n.state === 'pending');
  fill('dimension-ack-choice', pendingNotes,
    n => 'Note #' + n.id + ' · ' + n.dimension.replaceAll('_', ' ') + ' · Option #' + n.optionId);
  clear('portfolio-list');
  if (!entries.length) empty(el('portfolio-list'), 'No options proposed for this fictional case yet.');
  const counts = portfolio.counts || {};
  const summary = Object.keys(counts).sort().map(k => k + ': ' + counts[k]).join(' · ');
  if (summary) el('portfolio-list').append(node('p', 'Preserved entries by status — ' + summary + '.', 'snapshot-meta'));
  for (const entry of entries) {
    const box = node('div', null, 'snapshot');
    const top = node('div', null, 'topline');
    top.append(node('strong', 'Option #' + entry.id + ' · ' + entry.label),
      pill(entry.portfolio_status, ['held', 'rejected', 'deferred'].includes(entry.portfolio_status) ? 'pill-alert' : ''),
      pill('review: ' + entry.review_state, entry.review_state === 'needs_review' ? 'pill-warn' : ''));
    box.append(top, node('p', entry.description));
    const dimLine = Object.values(entry.dimensions).map(d => d.label + ': ' + d.state.replaceAll('_', ' ')).join(' · ');
    box.append(node('p', 'Reviewable dimensions — ' + dimLine +
      '. Each note stays pending until a clinician acknowledges it.', 'snapshot-meta'));
    if (entry.prerequisites.length) {
      const deps = node('ul');
      for (const dep of entry.prerequisites) {
        deps.append(node('li', 'Needs: ' + dep.kind + ' — ' + dep.target +
          (dep.deadline_date ? ' · date ' + dep.deadline_date + ' (' + dep.deadline_basis + ')' : ' · date unknown') +
          (dep.lead_time_days !== null && dep.lead_time_days !== undefined ? ' · lead ' + dep.lead_time_days + 'd' : '')));
      }
      box.append(node('p', 'Prerequisites:', 'snapshot-meta'), deps);
    } else {
      box.append(node('p', 'Prerequisites: none recorded.', 'snapshot-meta'));
    }
    const openObjections = entry.objections.open;
    box.append(node('p', openObjections.length
      ? 'Objections: ' + openObjections.map(f => f.label + ' — ' + f.reason +
        (f.premise ? ' (premise: ' + f.premise + ')' : '')).join(' ; ')
      : 'Objections: none open.', 'snapshot-meta'));
    const accessNotes = entry.dimensions.access.notes;
    box.append(node('p', accessNotes.length
      ? 'Access notes: ' + accessNotes.map(n => n.note + ' [' + n.state + '; anchor: ' + n.anchor +
        (n.premise ? '; premise: ' + n.premise : '') + ']').join(' ; ')
      : 'Access: nothing recorded; unknown.', 'snapshot-meta'));
    const ready = node('ul');
    for (const item of entry.readiness) ready.append(node('li', item));
    box.append(node('p', 'Still missing or needed:', 'snapshot-meta'), ready);
    box.append(node('p', entry.lead_time.label, 'snapshot-meta'));
    if (entry.triggers.length) {
      const trig = node('ul');
      for (const text of entry.triggers) trig.append(node('li', text));
      box.append(node('p', 'Expiration and review triggers:', 'snapshot-meta'), trig);
    }
    if (entry.review_events.length) {
      box.append(node('p', 'Review history: ' + entry.review_events.map(e =>
        e.action + ' by ' + e.reviewer_label + ' · scope: ' + e.scope).join(' ; '), 'snapshot-meta'));
    }
    el('portfolio-list').append(box);
  }
}
function renderScopedReview() {
  const fill = (id, items, labelFn) => {
    const select = el(id);
    const prior = select.value;
    clear(id);
    for (const item of items) {
      const opt = node('option', labelFn(item));
      opt.value = item.id; select.append(opt);
    }
    if (prior && [...select.options].some(x => x.value === prior)) select.value = prior;
  };
  const label = s => 'Investigation #' + s.id + ' · ' + s.state;
  fill('scoped-decision-snapshot', active.snapshots, label);
  fill('scoped-dissent-snapshot', active.snapshots, label);
  fill('scoped-handoff-snapshot', active.snapshots, label);
  clear('scoped-review-list');
  if (!active.snapshots.length) empty(el('scoped-review-list'), 'No investigation drafts yet.');
  for (const snapshot of active.snapshots) {
    const scoped = snapshot.scoped_review || {
      extraction: 'unreviewed', interpretation: 'unreviewed',
      open_items: [], decisions: [], dissents: [], handoffs: [],
    };
    const box = node('div', null, 'snapshot');
    const top = node('div', null, 'topline');
    top.append(node('strong', 'Investigation #' + snapshot.id),
      pill('extraction: ' + scoped.extraction, scoped.extraction === 'extraction_accepted' ? '' : 'pill-warn'),
      pill('interpretation: ' + scoped.interpretation, scoped.interpretation === 'interpretation_endorsed' ? '' : 'pill-warn'));
    box.append(top);
    if ((scoped.open_items || []).length)
      box.append(node('p', 'Open scope items: ' + scoped.open_items.join(', ') + ' — no settled note recorded.', 'snapshot-meta'));
    else box.append(node('p', 'No open scope items: both dimensions have a settled note.', 'snapshot-meta'));
    for (const item of (scoped.decisions || [])) {
      box.append(node('p', 'Note #' + item.id + ' by ' + item.reviewer_label + ': ' + item.scope +
        ' · sources ' + (item.source_version_ids.map(x => '#' + x).join(', ') || 'none') +
        ' · ' + item.decided_at, 'snapshot-meta'), node('p', item.note, 'muted'));
    }
    for (const item of (scoped.dissents || [])) {
      box.append(node('p', 'Disagreement #' + item.id + ' by ' + item.reviewer_label + ' on finding `' +
        item.claim_ref + '` · ' + item.dissented_at + ' (noted views above are unchanged).', 'snapshot-meta'),
        node('p', item.rationale, 'muted'));
    }
    for (const item of (scoped.handoffs || [])) {
      box.append(node('p', 'Handoff #' + item.id + ': ' + item.from_reviewer + ' handed open items to ' +
        item.to_reviewer + ' · snapshot #' + item.snapshot_id + ' · sources ' +
        (item.source_version_ids.map(x => '#' + x).join(', ') || 'none') + ' · prior decisions ' +
        (item.prior_decision_ids.map(x => '#' + x).join(', ') || 'none') + ' · ' + item.handed_at, 'snapshot-meta'));
    }
    el('scoped-review-list').append(box);
  }
}

function renderCareRecords() {
  el('second-opinion-disclaimer').textContent = active.second_opinion_disclaimer || '';
  el('survivorship-disclaimer').textContent = active.survivorship_disclaimer || '';
  const requests = active.second_opinions || [];
  const plans = active.survivorship_plans || [];
  const currentSources = active.sources.filter(s => s.state === 'current');
  const fill = (id, items, labelFn, allowEmpty = false, emptyLabel = '—') => {
    const select = el(id);
    const prior = select.value;
    clear(id);
    if (allowEmpty) { const blank = node('option', emptyLabel); blank.value = ''; select.append(blank); }
    for (const item of items) {
      const opt = node('option', labelFn(item));
      opt.value = item.id; select.append(opt);
    }
    if (prior && [...select.options].some(x => x.value === prior)) select.value = prior;
  };
  fill('so-question-choice', active.questions, q => 'Q' + q.id + ', ' + q.question.slice(0, 62));
  fill('so-snapshot-choice', active.snapshots, s => 'Investigation #' + s.id + ' · ' + s.state, true, 'No linked conclusion');
  fill('so-request-choice', requests, r => 'Request #' + r.id + ' · ' + r.status + ' · ' + r.question_text.slice(0, 52));
  fill('so-anchor-choice', currentSources, s => s.document_id + '@' + s.version);
  fill('surv-plan-choice', plans, p => 'Plan #' + p.id + ' · ' + p.title);
  fill('surv-anchor-choice', currentSources, s => s.document_id + '@' + s.version);
  // Materials: preserve checked current sources across same-case refreshes.
  // A source that is no longer current is dropped with a notice, never
  // rebound. A case switch never inherits the previous case's selection.
  const sameCareCase = renderedCaseId === caseId;
  const priorChecked = sameCareCase
    ? new Set([...el('so-source-choice').querySelectorAll('input:checked')].map(x => Number(x.value)))
    : new Set();
  const hadChoices = sameCareCase && el('so-source-choice').querySelectorAll('input').length > 0;
  clear('so-source-choice');
  if (!currentSources.length) empty(el('so-source-choice'), 'No current sources to share.');
  for (const source of currentSources) {
    const label = node('label');
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.value = source.id;
    checkbox.checked = hadChoices ? priorChecked.has(source.id) : true;
    label.append(checkbox, node('span', source.document_id + '@' + source.version + ', ' + source.event_date));
    el('so-source-choice').append(label);
  }
  if (hadChoices && [...priorChecked].some(id => !currentSources.some(x => x.id === id)))
    notice('A shared-material source changed while you were editing. Review the request and explicitly reconcile the shared materials before recording.', true);
  clear('second-opinion-list');
  if (!requests.length) empty(el('second-opinion-list'), 'No second-opinion requests recorded for this fictional case.');
  for (const req of requests) {
    const box = node('div', null, 'snapshot');
    const top = node('div', null, 'topline');
    top.append(node('strong', 'Second-opinion request #' + req.id),
      pill('Fictional record', 'pill-neutral'),
      pill(req.status, req.status === 'requested' ? 'pill-warn' : ''),
      pill('review: ' + req.review_state, req.review_state === 'needs_review' ? 'pill-alert' : ''));
    box.append(top,
      node('p', 'Asked about Q' + req.question_id + ': ' + req.question),
      node('p', 'Question asked: ' + req.question_text),
      node('p', 'Materials shared by reference: ' + (req.materials.length
        ? req.materials.map(m => m.document_id + '@' + m.version + ' (' + m.state + ')').join(', ')
        : 'none recorded') + ' · ' + req.created_at, 'snapshot-meta'));
    const grid = node('div', null, 'comparison-grid');
    const originalPane = node('section', null, 'comparison-pane');
    originalPane.append(node('h3', 'Original case conclusion (unchanged)'));
    if (req.original_snapshot && !req.original_snapshot.missing) {
      const card = node('div', null, 'source-card');
      card.append(node('p', 'Investigation #' + req.original_snapshot.id + ' · ' + req.original_snapshot.state),
        node('p', req.original_snapshot.summary));
      originalPane.append(card);
    } else {
      originalPane.append(node('p', 'No original conclusion was linked to this request.', 'muted'));
    }
    const responsePane = node('section', null, 'comparison-pane');
    responsePane.append(node('h3', 'Second-opinion response (separate record)'));
    if (req.response) {
      const card = node('div', null, 'source-card');
      card.append(node('p', 'Responder: ' + req.response.responder_label + ' (fictional, unverified)'),
        node('p', req.response.response_text),
        node('p', 'Anchored to ' + req.response.anchor.document_id + '@' + req.response.anchor.version +
          ' (' + req.response.anchor.state + ') · ' + req.response.created_at, 'snapshot-meta'));
      responsePane.append(card);
    } else {
      responsePane.append(node('p', 'No response recorded yet.', 'muted'));
    }
    grid.append(originalPane, responsePane);
    box.append(grid);
    if (req.review_events.length) {
      box.append(node('p', 'Review history: ' + req.review_events.map(e =>
        e.action + ' by ' + e.reviewer_label + ' · scope: ' + e.scope).join(' ; '), 'snapshot-meta'));
    }
    if (req.review_state === 'pending') {
      const actions = node('div', null, 'actions');
      const button = node('button', 'Demo review acknowledgment', 'button minor'); button.type = 'button';
      button.addEventListener('click', async () => {
        try {
          const requestedCase = readyCase();
          await api('/api/cases/' + requestedCase + '/second-opinion-requests/' + req.id + '/review',
            { reviewer_label: 'Synthetic reviewer (unverified)', scope: 'Demo-only acknowledgment of this fictional second-opinion record.' });
          if (requestedCase !== caseId) return;
          notice('Acknowledged in demonstration only. This is not credentialed clinical review.'); await refresh();
        } catch (err) { notice(err.message, true); }
      });
      actions.append(button);
      box.append(actions);
    } else if (req.review_state === 'needs_review') {
      box.append(node('p', 'Shared materials changed since this request. This record stays historical; record a new request against current versions.', 'muted'));
    }
    el('second-opinion-list').append(box);
  }
  clear('survivorship-list');
  if (!plans.length) empty(el('survivorship-list'), 'No survivorship plans recorded for this fictional case.');
  for (const plan of plans) {
    const box = node('div', null, 'snapshot');
    const top = node('div', null, 'topline');
    top.append(node('strong', 'Survivorship plan #' + plan.id + ' · ' + plan.title),
      pill('Fictional record', 'pill-neutral'));
    box.append(top, node('p', 'Recorded plan only — these notes never direct care. · ' + plan.created_at, 'snapshot-meta'));
    if (!plan.items.length) box.append(node('p', 'No items recorded in this plan yet.', 'muted'));
    for (const item of plan.items) {
      const card = node('div', null, 'source-card');
      card.append(node('p', item.kind + ' item #' + item.id + ': ' + item.description));
      card.append(node('p', item.recorded_date_label + ' · Anchored to ' +
        item.anchor.document_id + '@' + item.anchor.version + ' (' + item.anchor.state + ') · ' +
        item.created_at, 'snapshot-meta'));
      const pills = node('div', null, 'actions');
      pills.append(pill(item.state, item.state === 'triggered' ? '' : 'pill-neutral'),
        pill('review: ' + item.review_state, item.review_state === 'needs_review' ? 'pill-alert' : ''));
      card.append(pills);
      if (item.review_events.length) {
        card.append(node('p', 'Review history: ' + item.review_events.map(e =>
          e.action + ' by ' + e.reviewer_label + ' · scope: ' + e.scope).join(' ; '), 'snapshot-meta'));
      }
      const actions = node('div', null, 'actions');
      if (item.review_state === 'pending') {
        const review = node('button', 'Demo review acknowledgment', 'button minor'); review.type = 'button';
        review.addEventListener('click', async () => {
          try {
            const requestedCase = readyCase();
            await api('/api/cases/' + requestedCase + '/survivorship-items/' + item.id + '/review',
              { reviewer_label: 'Synthetic reviewer (unverified)', scope: 'Demo-only acknowledgment of this fictional survivorship record.' });
            if (requestedCase !== caseId) return;
            notice('Acknowledged in demonstration only. This is not credentialed clinical review.'); await refresh();
          } catch (err) { notice(err.message, true); }
        });
        actions.append(review);
      }
      if (item.kind === 'trigger' && item.state === 'recorded' && item.review_state !== 'needs_review') {
        const trigger = node('button', 'Mark trigger as observed', 'button secondary minor'); trigger.type = 'button';
        trigger.addEventListener('click', async () => {
          try {
            const requestedCase = readyCase();
            await api('/api/cases/' + requestedCase + '/survivorship-items/' + item.id + '/trigger',
              { reason: 'The described condition was observed in the fictional record.' });
            if (requestedCase !== caseId) return;
            notice('Trigger marked as observed in this fictional record.'); await refresh();
          } catch (err) { notice(err.message, true); }
        });
        actions.append(trigger);
      }
      if (actions.children.length) card.append(actions);
      if (item.review_state === 'needs_review') {
        card.append(node('p', 'The anchor source changed since this item was recorded. This record stays historical; record a new item against the current version.', 'muted'));
      }
      box.append(card);
    }
    el('survivorship-list').append(box);
  }
}

function renderBibliography(record) {
  clear('bibliography-result');
  const card = node('article', null, 'source-card');
  card.append(node('strong', record.title));
  const meta = node('p', [record.journal, record.year, record.publication_type]
    .filter(x => x !== null && x !== undefined && x !== '').join(', '), 'snapshot-meta');
  card.append(meta);
  if (Array.isArray(record.authors) && record.authors.length) {
    card.append(node('p', 'Authors: ' + record.authors.join(', '), 'muted'));
  }
  card.append(node('p', 'Source: ' + record.source.provider + ', retrieved ' +
    record.source.retrieved_at, 'snapshot-meta'));
  const link = document.createElement('a');
  // The local backend constructs this from an ASCII validated DOI. Defence
  // in depth: do not follow a publisher-provided arbitrary URL in the UI.
  if (typeof record.canonical_url === 'string' &&
      record.canonical_url.startsWith('https://doi.org/')) {
    link.href = record.canonical_url;
    link.textContent = 'Open DOI landing page';
    link.target = '_blank'; link.rel = 'noopener noreferrer';
    card.append(link);
  }
  card.append(node('p', record.kind === 'bibliographic_metadata_only' ?
    'Bibliographic metadata only. No abstract, full text, medical evidence appraisal or patient linkage.' :
    'Unrecognized record type; do not treat this as clinical evidence.', 'muted tiny'));
  el('bibliography-result').append(card);
}
async function initializeBibliography() {
  try {
    const status = await api('/api/bibliography/status');
    const enabled = status.live_enabled === true;
    el('bibliography-live-button').disabled = !enabled;
    el('bibliography-mode').textContent = enabled ?
      'Live public DOI-only lookup enabled by local operator. No case data is sent.' :
      'Offline by default. Only original fictional metadata can be loaded here.';
  } catch (err) {
    el('bibliography-live-button').disabled = true;
    el('bibliography-mode').textContent = 'Bibliography service unavailable; live lookup disabled.';
  }
}

el('bibliography-example-button').addEventListener('click', async () => {
  try {
    const record = await api('/api/bibliography/example');
    renderBibliography(record);
    notice('Fictional bibliography example loaded; not a real scientific publication.');
  } catch (err) { notice(err.message, true); }
});
el('bibliography-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (el('bibliography-live-button').disabled) {
    return notice('Live DOI lookups are disabled in this local demo.', true);
  }
  try {
    const record = await api('/api/bibliography/lookup', { doi: el('bibliography-doi').value.trim() });
    renderBibliography(record);
    notice('Crossref bibliographic metadata retrieved. No paper content or patient context was used.');
  } catch (err) { notice(err.message, true); }
});
el('timeline-filter').addEventListener('change', renderTimeline);
async function loadModelTemplates() {
  try {
    const data = await api('/api/investigations/templates');
    clear('model-investigation-template');
    for (const template of data.templates) {
      const opt = node('option', template.id);
      opt.value = template.id; el('model-investigation-template').append(opt);
    }
  } catch (err) { notice(err.message, true); }
}
async function loadModelInvestigations() {
  const requested = caseId;
  try {
    const data = await api('/api/cases/' + caseId + '/investigations');
    if (requested !== caseId) return;
    clear('model-investigation-list');
    const items = data.investigations || [];
    if (!items.length) { empty(el('model-investigation-list'), 'No model investigations yet.'); return; }
    for (const item of items) {
      const detail = await api('/api/cases/' + caseId + '/investigations/' + item.id);
      if (requested !== caseId) return;
      const box = node('div', null, 'snapshot');
      const top = node('div', null, 'topline');
      top.append(node('strong', 'Model investigation #' + detail.id),
        pill(detail.template), pill(detail.status), pill(detail.mode),
        pill(detail.kind || 'hypothesis'),
        pill('Review: ' + (detail.review_state || 'pending'),
          detail.stale ? 'pill-alert' : 'pill-warn'));
      box.append(top, node('p', detail.model + ' · ' + detail.created_at, 'snapshot-meta'));
      for (const claim of detail.claims || []) {
        box.append(node('p', claim.text));
        box.append(node('p', 'Uncertainty: ' + claim.uncertainty + ' · Cited: ' +
          (claim.citations || []).map(x => x.type + ' #' + x.id).join(', '), 'muted'));
        if (claim.limits) box.append(node('p', 'Limits: ' + claim.limits, 'muted'));
      }
      for (const abstention of detail.abstentions || []) {
        box.append(node('p', 'Abstained: ' + abstention.reason + ' (' + abstention.topic + ')', 'muted'));
      }
      if ((detail.dropped || []).length) {
        box.append(node('p', detail.dropped.length + ' claim(s) dropped by validation, never repaired', 'muted'));
      }
      if (detail.stale) box.append(node('p', 'A source was amended. This investigation is stale until reconciled.', 'muted'));
      box.append(node('p', detail.disclaimer || 'Research demonstration only.', 'muted'));
      el('model-investigation-list').append(box);
    }
  } catch (err) {
    if (requested === caseId) notice(err.message, true);
  }
}
async function loadWorkspaceQuestions() {
  const requested = caseId;
  const priorLinkQuestion = el('workspace-link-question').value;
  const priorStatusQuestion = el('workspace-status-question').value;
  const priorLinkSource = el('workspace-link-source').value;
  clear('workspace-question-list');
  try {
    const data = await api('/api/cases/' + requested + '/workspace-questions');
    if (requested !== caseId || !active || active.case.case_id !== requested) return;
    renderWorkspaceQuestions(data.workspace_questions || [],
      { priorLinkQuestion, priorStatusQuestion, priorLinkSource });
  } catch (err) {
    if (requested !== caseId) return;
    empty(el('workspace-question-list'), 'Investigation questions unavailable: ' + err.message);
  }
}
function workspaceStatusPill(status) {
  return pill(status, status === 'answered' ? '' : status === 'needs_review' ? 'pill-alert' : 'pill-warn');
}
function renderWorkspaceQuestions(items, prior) {
  // An answer is shown only for answered questions. History keeps earlier
  // recorded answers so a reopened question can still be reviewed.
  clear('workspace-link-question'); clear('workspace-status-question'); clear('workspace-link-source');
  for (const item of items) {
    const label = 'WQ' + item.id + ', ' + String(item.question).slice(0, 62);
    const linkOpt = node('option', label); linkOpt.value = item.id;
    el('workspace-link-question').append(linkOpt);
    const statusOpt = node('option', label); statusOpt.value = item.id;
    el('workspace-status-question').append(statusOpt);
  }
  for (const source of (active.sources || []).filter(s => s.state === 'current')) {
    const opt = node('option', source.document_id + '@' + source.version + ', ' + source.event_date);
    opt.value = source.id; el('workspace-link-source').append(opt);
  }
  const restore = (id, value) => {
    if (value && [...el(id).options].some(x => x.value === value)) el(id).value = value;
  };
  restore('workspace-link-question', prior.priorLinkQuestion);
  restore('workspace-status-question', prior.priorStatusQuestion);
  restore('workspace-link-source', prior.priorLinkSource);
  if (!items.length) { empty(el('workspace-question-list'), 'No investigation questions yet. Add one above.'); return; }
  for (const item of items) {
    const box = node('div', null, 'question');
    const top = node('div', null, 'topline');
    top.append(node('strong', 'Investigation question WQ' + item.id),
      workspaceStatusPill(item.status), pill('FICTIONAL', 'pill-neutral'));
    box.append(top, node('p', item.question));
    box.append(node('p', 'Created ' + (item.created_date || '') + ' · Review state: ' + item.status, 'snapshot-meta'));
    if (item.status === 'answered' && item.answer) {
      box.append(node('p', 'Recorded answer (human-entered, fictional):', 'muted'));
      box.append(node('p', item.answer, 'quoted'));
    } else {
      box.append(node('p', 'No recorded answer.', 'muted'));
    }
    const links = item.links || [];
    box.append(node('p', links.length ? 'Linked source versions:' : 'No linked source versions yet.', 'muted'));
    for (const link of links) {
      box.append(node('p', (link.source_anchor || ('#' + link.source_version_id)) +
        ' · source ' + (link.source_state || 'unknown') +
        ' · link ' + link.state, 'snapshot-meta'));
      if (link.state === 'active') {
        const unlink = node('button', 'Unlink ' + (link.source_anchor || ('#' + link.source_version_id)), 'button secondary minor');
        unlink.type = 'button';
        unlink.addEventListener('click', async () => {
          try {
            const requestedCase = readyCase();
            await api('/api/cases/' + requestedCase + '/workspace-questions/' + item.id + '/links/' + link.id + '/unlink', {});
            if (requestedCase !== caseId) return;
            notice('Link superseded; the record is kept as history.');
            await refresh();
          } catch (err) { notice(err.message, true); }
        });
        box.append(unlink);
      }
    }
    const history = item.history || [];
    box.append(node('p', 'History (' + history.length + ' entr' + (history.length === 1 ? 'y' : 'ies') + '):', 'muted'));
    for (const entry of history) {
      box.append(node('p', (entry.previous_status || 'recorded') + ' → ' + entry.new_status +
        ': ' + entry.reason + ' · ' + (entry.recorded_at || ''), 'snapshot-meta'));
      if (entry.answer) box.append(node('p', 'Earlier recorded answer (kept for review): ' + entry.answer, 'quoted'));
    }
    el('workspace-question-list').append(box);
  }
}
el('workspace-question-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    await api('/api/cases/' + requestedCase + '/workspace-questions', { question: el('workspace-question-text').value });
    if (requestedCase !== caseId) return;
    el('workspace-question-text').value = '';
    notice('Investigation question recorded.');
    await refresh();
  } catch (err) { notice(err.message, true); }
});
el('workspace-link-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    await api('/api/cases/' + requestedCase + '/workspace-questions/' + el('workspace-link-question').value + '/links', {
      source_version_id: Number(el('workspace-link-source').value),
    });
    if (requestedCase !== caseId) return;
    notice('Source version linked.');
    await refresh();
  } catch (err) { notice(err.message, true); }
});
el('workspace-status-form').addEventListener('submit', async event => {
  event.preventDefault();
  const answer = el('workspace-status-answer').value.trim();
  try {
    const requestedCase = readyCase();
    const payload = { status: el('workspace-status-value').value, reason: el('workspace-status-reason').value };
    if (answer) payload.answer = answer;
    await api('/api/cases/' + requestedCase + '/workspace-questions/' + el('workspace-status-question').value + '/status', payload);
    if (requestedCase !== caseId) return;
    el('workspace-status-reason').value = ''; el('workspace-status-answer').value = '';
    notice('Status change recorded.');
    await refresh();
  } catch (err) { notice(err.message, true); }
});
async function loadChangesSinceReview() {
  const requested = caseId;
  const anchorEl = el('changes-anchor');
  if (anchorEl) anchorEl.textContent = 'Loading changes since the last review…';
  for (const id of ['changes-new-sources', 'changes-amendments', 'changes-stale', 'changes-questions']) clear(id);
  try {
    const data = await api('/api/cases/' + requested + '/changes-since-review');
    if (requested !== caseId || !active || active.case.case_id !== requested) return;
    renderChangesSinceReview(data);
  } catch (err) {
    if (requested !== caseId) return;
    if (anchorEl) anchorEl.textContent = 'Changes since last review unavailable: ' + err.message;
    el('changes-disclaimer').textContent = '';
    empty(el('changes-new-sources'), 'Change listing unavailable.');
    empty(el('changes-amendments'), 'Change listing unavailable.');
    empty(el('changes-stale'), 'Change listing unavailable.');
    empty(el('changes-questions'), 'Change listing unavailable.');
  }
}
function renderChangesSinceReview(data) {
  // Ledger facts only. Reported states are quoted verbatim; the finding-key
  // diff is a mechanical comparison, never an interpretation of significance.
  const anchor = data.anchor || {};
  const counts = data.counts || {};
  const anchorLabel = anchor.kind === 'demo_review_acknowledged'
    ? 'latest demo-review acknowledgment'
    : anchor.kind === 'case_created'
      ? 'case creation (nothing demo-acknowledged yet)'
      : String(anchor.kind || 'unknown anchor');
  el('changes-anchor').textContent = 'Anchor: event #' + anchor.event_id + ' (' + anchorLabel +
    ') at ' + (anchor.occurred_at || 'unknown time') +
    '. New sources: ' + (counts.new_sources || 0) +
    ' · Amendments: ' + (counts.amendments || 0) +
    ' · Stale investigations: ' + (counts.stale_investigations || 0) +
    ' · New questions: ' + (counts.new_questions || 0) + '.';
  el('changes-disclaimer').textContent = (data.synthetic ? 'Fictional synthetic data only. ' : '') +
    (data.disclaimer || '');
  clear('changes-new-sources');
  const newSources = data.new_sources || [];
  if (!newSources.length) empty(el('changes-new-sources'), 'No new source documents recorded after the anchor event.');
  for (const item of newSources) {
    const card = node('article', null, 'source-card');
    const top = node('div', null, 'source-top');
    top.append(node('span', item.document_id + ' @' + item.version, 'source-title'),
      pill(item.kind || 'source', 'pill-neutral'));
    card.append(top);
    card.append(node('p', 'Event #' + item.event_id + ' at ' + item.occurred_at +
      ' · Source version #' + item.source_id +
      ' · Event date ' + item.event_date + ', issued ' + item.issued_at + ', received ' + item.received_at,
      'snapshot-meta'));
    const findings = item.reported_findings || [];
    card.append(node('p', findings.length
      ? (item.classification_origin === 'user_selected' ? 'User-selected finding statuses: ' : 'Reported findings: ') +
        findings.map(entry => entry.finding_key + ' (' + entry.reported_state + ')').join('; ')
      : 'No reported findings recorded for this source version.', 'muted'));
    el('changes-new-sources').append(card);
  }
  clear('changes-amendments');
  const amendments = data.amendments || [];
  if (!amendments.length) empty(el('changes-amendments'), 'No amended source versions recorded after the anchor event.');
  for (const item of amendments) {
    const card = node('article', null, 'source-card');
    const top = node('div', null, 'source-top');
    top.append(node('span', item.document_id + ': version ' + item.superseded_version + ' → ' + item.version, 'source-title'),
      pill('Document amendment', 'pill-neutral'));
    card.append(top);
    card.append(node('p', 'Event #' + item.event_id + ' at ' + item.occurred_at +
      ' · Source version #' + item.source_id + ' supersedes #' + item.supersedes_source_id +
      ' · ' + item.kind + ', event ' + item.event_date + ', received ' + item.received_at, 'snapshot-meta'));
    const diff = item.finding_key_diff || {};
    if (item.classification_origin === 'user_selected' || item.previous_classification_origin === 'user_selected')
      card.append(node('p', 'This comparison includes user-selected statuses. Clinical review not performed.', 'muted tiny'));
    const added = diff.added_finding_keys || [];
    const removed = diff.removed_finding_keys || [];
    const stateChanges = diff.reported_state_changes || [];
    card.append(node('p', 'Mechanical finding-key diff — added: ' + (added.length ? added.join(', ') : 'none') +
      ' · removed: ' + (removed.length ? removed.join(', ') : 'none') + '.', 'change-impact'));
    if (!stateChanges.length)
      card.append(node('p', 'No finding key carries a different reported state between these versions.', 'muted'));
    for (const change of stateChanges)
      card.append(node('p', change.finding_key + ': reported state ' +
        change.previous_reported_state + ' → ' + change.reported_state, 'muted'));
    const invalidated = item.invalidated_snapshot_ids || [];
    card.append(node('p', invalidated.length
      ? 'Marked stale by this amendment: investigation ' + invalidated.map(id => '#' + id).join(', ') + '.'
      : 'No saved investigation cited the superseded version.', 'muted'));
    el('changes-amendments').append(card);
  }
  clear('changes-stale');
  const staleList = data.stale_investigations || [];
  if (!staleList.length) empty(el('changes-stale'), 'No saved investigation was marked stale after the anchor event.');
  for (const item of staleList) {
    const box = node('div', null, 'snapshot');
    const top = node('div', null, 'topline');
    top.append(node('strong', 'Investigation #' + item.snapshot_id),
      pill(item.current_state || 'unknown', item.current_state === 'stale' ? 'pill-alert' : 'pill-neutral'));
    box.append(top);
    box.append(node('p', 'Question Q' + item.question_id + (item.question ? ': ' + item.question : '') +
      ' (question state: ' + (item.question_state || 'unknown') + ')', 'snapshot-meta'));
    for (const cause of item.causes || []) {
      const causeText = cause.cause === 'source_amendment'
        ? 'Stale because a bound source was amended (event #' + cause.event_id + ' at ' + cause.occurred_at + ').'
        : cause.cause === 'evidence_change'
          ? 'Stale because fictional evidence changed (event #' + cause.event_id + ' at ' + cause.occurred_at +
            (cause.evidence_version_id ? ', evidence version #' + cause.evidence_version_id : '') +
            (cause.reason ? ', reason: ' + cause.reason : '') + ').'
          : 'Stale (' + (cause.cause || 'unknown cause') + ', event #' + cause.event_id +
            ' at ' + cause.occurred_at + ').';
      box.append(node('p', causeText, 'muted'));
    }
    const staleDraftsLink = document.createElement('a');
    staleDraftsLink.href = '#investigation-history-heading';
    staleDraftsLink.className = 'button secondary minor';
    staleDraftsLink.textContent = 'Open saved drafts';
    box.append(staleDraftsLink);
    el('changes-stale').append(box);
  }
  clear('changes-questions');
  const newQuestions = data.new_questions || [];
  if (!newQuestions.length) empty(el('changes-questions'), 'No questions created after the anchor event.');
  for (const item of newQuestions) {
    const row = node('div', null, 'question');
    row.append(node('p', 'Q' + item.question_id + ': ' + item.question),
      node('p', 'Event #' + item.event_id + ' · State: ' + item.state + ' · Created ' + item.created_at, 'muted'));
    el('changes-questions').append(row);
  }
}
async function loadEvidenceQuality() {
  const requested = caseId;
  for (const id of ['evidence-quality-current', 'evidence-quality-superseded']) clear(id);
  try {
    const data = await api('/api/cases/' + requested + '/evidence-quality');
    if (requested !== caseId || !active || active.case.case_id !== requested) return;
    renderEvidenceQuality(data);
  } catch (err) {
    if (requested !== caseId) return;
    empty(el('evidence-quality-current'), 'Evidence quality notes unavailable: ' + err.message);
    empty(el('evidence-quality-superseded'), 'Evidence quality notes unavailable.');
  }
}
function renderEvidenceQuality(data) {
  // Descriptive notes only. A source with no note renders "not assessed";
  // no rating, score, or quality is ever guessed. All text via textContent.
  const renderList = (containerId, entries, emptyText) => {
    const container = el(containerId);
    clear(containerId);
    if (!entries.length) { empty(container, emptyText); return; }
    for (const entry of entries) {
      const card = node('article', null, 'source-card');
      const top = node('div', null, 'source-top');
      top.append(node('span', entry.document_id + ' @' + entry.version, 'source-title'),
        pill('FICTIONAL', 'pill-warn'));
      card.append(top);
      card.append(node('p', 'Citation anchor: ' + entry.citation_anchor, 'snapshot-meta'));
      if (entry.assessment_status !== 'assessed' || !(entry.assessments || []).length) {
        card.append(node('p', 'Not assessed — no quality note was recorded for this fictional source version. No quality is guessed.', 'muted'));
      } else {
        for (const note of entry.assessments) {
          const box = node('div', null, 'finding');
          const head = node('div', null, 'finding-head');
          head.append(node('strong', 'FICTIONAL note #' + note.id + ' · ' + note.assessor_label),
            pill('FICTIONAL note', 'pill-neutral'));
          box.append(head);
          box.append(node('p', 'Date recorded: ' + note.date_recorded, 'snapshot-meta'));
          box.append(node('p', 'What is covered: ' + note.completeness_note));
          box.append(node('p', 'Limits: ' + note.limitations_text, 'muted'));
          box.append(node('p', 'Disagreements or conflicts: ' + note.conflict_note, 'muted'));
          box.append(node('span', 'Source version #' + note.source_version_id + ' · recorded ' + note.created_at, 'ref'));
          card.append(box);
        }
      }
      container.append(card);
    }
  };
  renderList('evidence-quality-current', data.current || [], 'No current fictional sources in this case.');
  renderList('evidence-quality-superseded', data.superseded || [], 'No superseded fictional source versions.');
}
async function loadReReviewTasks() {
  const requested = caseId;
  clear('re-review-list');
  try {
    const data = await api('/api/cases/' + requested + '/re-review-tasks');
    if (requested !== caseId || !active || active.case.case_id !== requested) return;
    renderReReviewTasks(data);
  } catch (err) {
    if (requested !== caseId) return;
    empty(el('re-review-list'), 'Re-review task listing unavailable: ' + err.message);
  }
}
function renderReReviewTasks(tasks) {
  // Ledger facts only: owner labels are fictional attribution, due dates are
  // descriptive, and rows stay in creation order. Never infer importance.
  clear('re-review-list');
  const list = el('re-review-list');
  if (!tasks.length) {
    empty(list, 'No re-review tasks recorded for this fictional case.');
    return;
  }
  const causeText = {
    source_amendment: 'a bound source was amended',
    evidence_change: 'fictional evidence changed',
    revocation: 'a rights source was revoked',
    correction: 'a rights source was corrected',
    review: 'a broker link was re-reviewed',
  };
  for (const task of tasks) {
    const box = node('div', null, 'snapshot');
    const top = node('div', null, 'topline');
    top.append(node('strong', 'Re-review task #' + task.id),
      pill(task.status, task.status === 'open' ? 'pill-warn' : 'pill-neutral'));
    if (task.overdue) top.append(pill('past due', 'pill-alert'));
    box.append(top);
    box.append(node('p', 'Earlier draft #' + task.snapshot_id + ' for question Q' + task.question_id +
      ' was marked stale because ' + (causeText[task.cause] || task.cause) +
      ' (recorded under event #' + task.invalidating_event_id + ').', 'snapshot-meta'));
    const diff = task.finding_key_diff || {};
    const added = diff.added_finding_keys || [];
    const removed = diff.removed_finding_keys || [];
    const stateChanges = diff.reported_state_changes || [];
    if (task.cause === 'source_amendment') {
      box.append(node('p', 'Superseding source version #' + task.superseding_source_version_id +
        ' replaces #' + task.superseded_source_version_id +
        '. Mechanical finding-key diff — added: ' + (added.length ? added.join(', ') : 'none') +
        ' · removed: ' + (removed.length ? removed.join(', ') : 'none') + '.', 'muted'));
      for (const change of stateChanges)
        box.append(node('p', change.finding_key + ': reported state ' +
          change.previous_reported_state + ' → ' + change.reported_state, 'muted'));
    } else if (task.evidence_version_id) {
      box.append(node('p', 'Changed fictional evidence version #' + task.evidence_version_id + '.', 'muted'));
    } else if (task.rights_source_id) {
      box.append(node('p', 'Rights source row #' + task.rights_source_id +
        (task.superseding_rights_source_id ? ' superseded by row #' + task.superseding_rights_source_id : '') +
        (task.broker_link_id ? ', broker link #' + task.broker_link_id : '') + '.', 'muted'));
    }
    box.append(node('p', 'Recorded owner (fictional label): ' + task.assignee_label +
      ' · ' + (task.due_date ? 'Due ' + task.due_date : 'No due date recorded') +
      ' · Created ' + task.created_at + '.', 'muted'));
    if (task.status !== 'open') {
      box.append(node('p', task.closing_snapshot_id
        ? 'Closed with replacement draft #' + task.closing_snapshot_id + ' at ' + task.closed_at + '. The earlier draft stays in history.'
        : 'Closed with a recorded no-change note at ' + task.closed_at + ': ' + (task.close_note || ''), 'muted'));
    } else {
      const form = node('div', null, 'actions');
      const noteInput = node('input', null, '');
      noteInput.type = 'text';
      noteInput.placeholder = 'No-change note (10–600 characters)';
      noteInput.setAttribute('aria-label', 'No-change note for task ' + task.id);
      const draftInput = node('input', null, '');
      draftInput.type = 'text';
      draftInput.placeholder = 'Replacement draft #';
      draftInput.setAttribute('aria-label', 'Replacement draft id for task ' + task.id);
      const closeButton = node('button', 'Close task', 'button secondary minor');
      closeButton.type = 'button';
      closeButton.addEventListener('click', async () => {
        try {
          const current = readyCase();
          const note = noteInput.value.trim();
          const draftRaw = draftInput.value.trim();
          if (draftRaw && !/^[0-9]+$/.test(draftRaw)) {
            notice('Replacement draft must be a snapshot number.', true);
            return;
          }
          const payload = {};
          if (note) payload.no_change_note = note;
          if (draftRaw) payload.closing_snapshot_id = Number(draftRaw);
          await api('/api/cases/' + current + '/re-review-tasks/' + task.id + '/close', payload);
          notice('Re-review task #' + task.id + ' recorded as done. The earlier draft stays in history.');
          await refresh();
        } catch (err) { notice(err.message, true); }
      });
      form.append(noteInput, draftInput, closeButton);
      box.append(form);
    }
    list.append(box);
  }
}
el('model-investigation-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    await api('/api/cases/' + requestedCase + '/investigations', {
      question_id: Number(el('model-investigation-question').value),
      template: el('model-investigation-template').value,
      mode: el('model-investigation-mode').value,
    });
    if (requestedCase !== caseId) return;
    notice('Model investigation stored as a hypothesis pending review.');
    await refresh();
  } catch (err) { notice(err.message, true); }
});
const documentIntake = window.OpenIntelligenceIntake.mount({
  api, getCase: readyCase,
  onImported: () => refresh(),
  onSource: async sourceId => {
    const requestedCase = readyCase();
    await refresh();
    if (requestedCase !== caseId) return;
    const source = active.sources.find(item => item.id === sourceId);
    if (source) await openSource(source);
  },
  onQuestion: () => {
    el('question-text').scrollIntoView({block: 'center'});
    el('question-text').focus();
  },
});
// Begin contradiction synthesis (B-08): read-only grouping plus human notes.
const SYNTHESIS_GROUPS = [
  ['supporting', 'Supporting items'],
  ['contradicting', 'Contradicting items'],
  ['context', 'Context items'],
  ['unknown_limited', 'Unknown or limited items'],
];
const SYNTHESIS_EMPTY = {
  supporting: 'None included; no supporting item is linked at this cutoff.',
  contradicting: 'None included; no contradicting item is linked at this cutoff.',
  context: 'None included; no context item is linked at this cutoff.',
  unknown_limited: 'None included; no unknown or limited item is linked at this cutoff.',
};
function fillSelect(id, options, keepValue) {
  const select = el(id);
  const prior = keepValue ? select.value : null;
  clear(id);
  for (const [value, label] of options) {
    const opt = node('option', label);
    opt.value = value;
    select.append(opt);
  }
  if (prior && [...select.options].some(opt => opt.value === prior)) select.value = prior;
}
function renderSynthesisChoices() {
  if (!active) return;
  const sameCase = renderedCaseId === caseId;
  const questionOptions = active.questions.map(q => [String(q.id), 'Q' + q.id + ': ' + q.question]);
  const snapshotOptions = active.snapshots.map(s =>
    [String(s.id), 'Snapshot #' + s.id + ' · Q' + s.question_id + ' · ' + s.state]);
  fillSelect('synthesis-question-choice', questionOptions.length ? questionOptions : [['', 'No questions yet']], sameCase);
  fillSelect('synthesis-snapshot-choice', snapshotOptions.length ? snapshotOptions : [['', 'No snapshots yet']], sameCase);
  fillSelect('synthesis-note-question', questionOptions.length ? questionOptions : [['', 'No questions yet']], sameCase);
  renderSynthesisNoteTargets();
}
function renderSynthesisNoteTargets() {
  if (!active) return;
  const qid = Number(el('synthesis-note-question').value);
  const kind = el('synthesis-note-target-kind').value;
  let options = [];
  if (kind === 'assessment') {
    options = (active.evidence_assessments || []).filter(a => a.question_id === qid)
      .map(a => [String(a.id), 'Assessment #' + a.id + ' · ' + a.evidence_key + '@' + a.version + ' · ' + a.relation]);
  } else {
    options = (active.broker_links || []).filter(a => a.question_id === qid)
      .map(a => [String(a.id), 'Link #' + a.id + ' · ' + a.source_key + ' ' + (a.version_label || '') + ' · ' + a.relation]);
  }
  fillSelect('synthesis-note-target', options.length ? options : [['', 'No records for this question yet']], false);
}
function synthesisItemLabel(item) {
  const anchor = item.anchor || {};
  if (item.kind === 'evidence_assessment') {
    return 'Assessment #' + item.id + ' · ' + anchor.evidence_key + '@' + anchor.version +
      ' · line ' + anchor.statement_line;
  }
  return 'Link #' + item.id + ' · ' + anchor.source_key + ' ' + (anchor.version_label || '') +
    ' · ' + (anchor.mode || 'citation identity');
}
function renderSynthesisGroups(data) {
  clear('synthesis-groups');
  const counts = data.counts || {};
  const head = node('div', null, 'question');
  head.append(node('p', 'Linked items: ' + (counts.total || 0) +
    ' (supporting ' + (counts.supporting || 0) +
    ' · contradicting ' + (counts.contradicting || 0) +
    ' · context ' + (counts.context || 0) +
    ' · unknown/limited ' + (counts.unknown_limited || 0) + ')'));
  const cutoff = data.cutoff || {};
  head.append(node('p', 'Cutoff event #' + cutoff.event_id + ' at ' + (cutoff.occurred_at || 'unknown time') +
    '. No quality number is computed here.', 'muted'));
  el('synthesis-groups').append(head);
  for (const [key, title] of SYNTHESIS_GROUPS) {
    const items = (data.groups || {})[key] || [];
    const box = node('div', null, 'snapshot');
    const top = node('div', null, 'topline');
    top.append(node('strong', title + ' (' + items.length + ')'),
      pill(key === 'contradicting' && items.length ? 'dissent visible' : 'listed', 'pill-neutral'));
    box.append(top);
    if (!items.length) box.append(node('p', SYNTHESIS_EMPTY[key], 'muted'));
    for (const item of items) {
      box.append(node('p', synthesisItemLabel(item) + ' · ' + item.relation + ', ' + item.applicability +
        ' · review state: ' + item.review_state));
      box.append(node('p', 'Reviewer rationale: ' + item.rationale, 'muted'));
      for (const note of item.limitation_notes || []) {
        box.append(node('p', 'Limitation note by ' + note.author_label + ': ' + note.note, 'muted'));
      }
    }
    el('synthesis-groups').append(box);
  }
}
async function loadSynthesis() {
  const requested = caseId;
  clear('synthesis-groups');
  clear('synthesis-report-meta');
  const qid = Number(el('synthesis-question-choice').value);
  const sid = Number(el('synthesis-snapshot-choice').value);
  if (!qid) {
    empty(el('synthesis-groups'), 'No question selected in this fictional case.');
    return;
  }
  try {
    const data = await api('/api/cases/' + requested + '/questions/' + qid + '/synthesis');
    if (requested !== caseId || !active || active.case.case_id !== requested) return;
    renderSynthesisGroups(data);
    if (sid) {
      const snapshotData = await api('/api/cases/' + requested + '/snapshots/' + sid + '/synthesis');
      if (requested !== caseId || !active || active.case.case_id !== requested) return;
      const basis = snapshotData.basis || {};
      const meta = node('div', null, 'question');
      meta.append(node('p', 'Snapshot #' + sid + ' · state: ' + (basis.snapshot_state || 'unknown') +
        ' · cutoff event #' + ((snapshotData.cutoff || {}).event_id || '?')));
      meta.append(node('p', basis.stale_basis
        ? 'REVIEW-PENDING: the record changed after this snapshot. The bounded report reads as history.'
        : 'No basis change is recorded at this cutoff. The bounded report still needs human review.', 'muted'));
      el('synthesis-report-meta').append(meta);
    } else {
      empty(el('synthesis-report-meta'), 'No snapshot selected in this fictional case.');
    }
  } catch (err) {
    if (requested !== caseId) return;
    empty(el('synthesis-groups'), 'Synthesis unavailable: ' + err.message);
    empty(el('synthesis-report-meta'), 'Report cutoff unavailable.');
  }
}
async function openSynthesisReport(patient) {
  let read;
  try {
    read = beginSourceRead();
    const sid = Number(el('synthesis-snapshot-choice').value);
    if (!sid) throw Error('Select an investigation snapshot first.');
    const suffix = patient ? '/synthesis-report-patient' : '/synthesis-report';
    const text = await api('/api/cases/' + read.caseId + '/snapshots/' + sid + suffix);
    if (!sourceReadIsCurrent(read)) return;
    if (typeof text !== 'string' || !text) throw Error('Bounded report text is unavailable.');
    el('dialog-title').textContent = patient
      ? 'Snapshot #' + sid + ', plain-words bounded report'
      : 'Snapshot #' + sid + ', workspace bounded report';
    renderOriginalSource(text, null);
    el('dialog-context').textContent = 'FICTIONAL DEMO DATA. Bounded to its cutoff; a REVIEW-PENDING banner means the record changed after it.';
    showSourceView('source-dialog');
  } catch (err) {
    if (!read || sourceReadIsCurrent(read)) notice(err.message, true);
  }
}
el('synthesis-question-choice').addEventListener('change', () => { loadSynthesis(); });
el('synthesis-snapshot-choice').addEventListener('change', () => { loadSynthesis(); });
el('synthesis-note-question').addEventListener('change', () => { renderSynthesisNoteTargets(); });
el('synthesis-note-target-kind').addEventListener('change', () => { renderSynthesisNoteTargets(); });
el('synthesis-report-button').addEventListener('click', () => { openSynthesisReport(false); });
el('synthesis-patient-report-button').addEventListener('click', () => { openSynthesisReport(true); });
el('synthesis-note-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const kind = el('synthesis-note-target-kind').value;
    const targetId = Number(el('synthesis-note-target').value);
    if (!targetId) throw Error('Select a target record for this note.');
    const payload = {
      question_id: Number(el('synthesis-note-question').value),
      note: el('synthesis-note-text').value,
      author_label: el('synthesis-note-author').value,
    };
    if (kind === 'assessment') payload.assessment_id = targetId;
    else payload.broker_link_id = targetId;
    await api('/api/cases/' + requestedCase + '/limitation-notes', payload);
    if (requestedCase !== caseId) return;
    el('synthesis-note-text').value = '';
    notice('Limitation note recorded. Notes stay in history and are never rewritten.');
    await refresh();
  } catch (err) { notice(err.message, true); }
});
// End contradiction synthesis (B-08).
function renderMetricsAggregate(containerId, block) {
  // Descriptive fixture counts only; every value arrives as a number or a
  // fixed label string, rendered via textContent-only node().
  clear(containerId);
  const container = el(containerId);
  const aggregate = (block && block.aggregate) || {};
  const corrections = aggregate.corrections || {};
  const lag = (aggregate.stale_lag && aggregate.stale_lag.summary) || {};
  container.append(
    metric(aggregate.case_count || 0, 'Cases in set'),
    metric(corrections.total || 0, 'Corrections (amendments + evidence changes)'),
    metric(aggregate.abstention_entries || 0, 'Abstention entries'),
    metric(aggregate.guard_drop_entries || 0, 'Guard-drop entries'),
    metric(aggregate.invalidated_total || 0, 'Invalidated items'),
    metric(aggregate.untouched_total || 0, 'Untouched items'));
  const lagText = 'Stale-item lag over ' + (lag.resolved || 0) + ' resolved correction(s)' +
    ', ' + (lag.pending || 0) + ' pending' +
    (lag.resolved ? ': min ' + lag.min_seconds + 's, median ' + lag.median_seconds +
      's, max ' + lag.max_seconds + 's (ledger timestamps).' : ' (ledger timestamps).');
  container.append(node('p', lagText, 'muted'));
  const abstentions = aggregate.abstentions_by_reason || {};
  const drops = aggregate.guard_drops_by_reason || {};
  const reasons = Object.keys(abstentions).sort()
    .map(reason => reason + ': ' + abstentions[reason]).join('; ') || 'none recorded';
  const dropReasons = Object.keys(drops).sort()
    .map(reason => reason + ': ' + drops[reason]).join('; ') || 'none recorded';
  container.append(node('p', 'Abstentions by reason — ' + reasons, 'muted tiny'));
  container.append(node('p', 'Guard drops by reason — ' + dropReasons, 'muted tiny'));
}
function renderSyntheticMetrics(data) {
  const run = data.run || {};
  const manifest = run.manifest || {};
  el('metrics-status').textContent = 'Run ' + (run.run_id || 'unknown') +
    ' as of ledger time ' + (run.as_of_ledger_time || 'unknown') +
    '. Dev: ' + (manifest.dev_cases || []).join(', ') +
    '. Held-out: ' + ((manifest.held_out_cases || []).join(', ') || 'none') +
    '. Synthetic fixtures only — non-transferable.';
  el('metrics-disclaimer').textContent = ((data.dev && data.dev.labels) || []).join('. ') +
    '. ' + ((data.dev && data.dev.disclaimer) || '');
  renderMetricsAggregate('metrics-dev', data.dev);
  renderMetricsAggregate('metrics-heldout', data.held_out);
  clear('metrics-run');
  const runBox = el('metrics-run');
  const card = node('article', null, 'source-card');
  const positions = run.ledger_positions || {};
  card.append(node('p', 'Run id ' + (run.run_id || 'unknown') +
    ' reflects ledger positions ' + Object.keys(positions).sort()
      .map(name => name + ' @ event #' + positions[name].latest_event_id).join('; ') +
    '. Recompute any time: derived values come from the ledger, not from a stored metric history.'));
  runBox.append(card);
}
async function loadSyntheticMetrics() {
  const devRaw = el('metrics-dev-input').value;
  const heldOutRaw = el('metrics-heldout-input').value;
  el('metrics-status').textContent = 'Computing fixture metrics…';
  try {
    const data = await api('/api/metrics/synthetic?dev=' + encodeURIComponent(devRaw) +
      '&held_out=' + encodeURIComponent(heldOutRaw));
    // The manifest may change while a response is in flight; never render
    // counts underneath a manifest they were not computed for.
    if (el('metrics-dev-input').value !== devRaw || el('metrics-heldout-input').value !== heldOutRaw) return;
    renderSyntheticMetrics(data);
  } catch (err) {
    if (el('metrics-dev-input').value !== devRaw || el('metrics-heldout-input').value !== heldOutRaw) return;
    el('metrics-status').textContent = 'Fixture metrics unavailable: ' + err.message;
  }
}
el('metrics-form').addEventListener('submit', event => {
  event.preventDefault();
  loadSyntheticMetrics();
});
initialize();
initializeBibliography();
loadModelTemplates();

const sectionMenu = document.querySelector('.section-menu');
const workspaceNav = document.querySelector('#workspace-nav');
if (workspaceNav) {
  const sectionLinks = [...workspaceNav.querySelectorAll('a[href^="#"]')];
  const syncCurrentSection = () => {
    const current = window.location.hash || '#overview';
    sectionLinks.forEach(link => {
      if (link.getAttribute('href') === current) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  };
  syncCurrentSection();
  window.addEventListener('hashchange', syncCurrentSection);
  if (sectionMenu) {
    const mobileSections = window.matchMedia('(max-width: 60rem)');
    const syncSectionMenu = () => { sectionMenu.open = !mobileSections.matches; };
    syncSectionMenu();
    mobileSections.addEventListener('change', syncSectionMenu);
    workspaceNav.addEventListener('click', event => {
      if (mobileSections.matches && event.target.closest('a')) sectionMenu.open = false;
    });
  }
}
