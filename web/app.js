'use strict';
// All displayed data is from local, synthetic records. No third-party scripts.
let caseId = null;
let active = null;
let refreshSequence = 0;
let renderedCaseId = null;
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
  const response = await fetch(path, payload === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  const type = response.headers.get('content-type') || '';
  const data = type.includes('json') ? await response.json() : await response.text();
  if (!response.ok) throw Error(data.error || 'Request failed');
  return data;
}
function pill(value, style = '') { return node('span', value, 'pill ' + style); }
function empty(container, text) { container.append(node('p', text, 'empty')); }
function metric(number, label) {
  const wrap = node('div', null, 'metric');
  wrap.append(node('span', number, 'number'), node('span', label, 'name'));
  return wrap;
}
async function initialize() {
  try {
    const cases = await api('/api/cases');
    const picker = el('case-picker');
    for (const entry of cases) {
      const option = node('option', entry.label + ' · ' + entry.case_id);
      option.value = entry.case_id;
      picker.append(option);
    }
    if (!cases.length) {
      el('case-heading').textContent = 'No synthetic cases found';
      notice('Run PYTHONPATH=src python -m open_intelligence seed before opening the demo.', true);
      return;
    }
    picker.addEventListener('change', () => {
      // An unfinished narrative must never silently become attached to another case.
      if ((el('draft-summary').value.trim() || el('evidence-rationale').value.trim() ||
          el('evidence-withdraw-reason').value.trim())) {
        picker.value = caseId;
        notice('Save or explicitly clear the unfinished investigation draft before switching cases.', true);
        return;
      }
      caseId = picker.value;
      active = null; // Reject writes while the next case is loading.
      for (const id of ['question-text', 'report-text', 'evidence-rationale']) el(id).value = '';
      if (el('source-dialog').open) el('source-dialog').close();
      refresh();
    });
    caseId = cases[0].case_id;
    await refresh();
  } catch (err) { notice(err.message, true); }
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
  } catch (err) {
    if (sequence === refreshSequence && requestedCase === caseId) notice(err.message, true);
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
      (assessment.evidence_state !== 'current' ? ' · STALE: uncheck and reassess' : '') + ' · ' +
      assessment.relation + ' · ' + assessment.applicability));
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
      ' · Received: ' + latest.received_at.slice(0, 10) +
      (group.specimenId ? ' · Specimen: ' + group.specimenId : ' · No specimen recorded'), 'snapshot-meta');
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
      const details = node('p', currentAssertions.length +
        ' current authored assertion(s); click source to inspect exact report text.', 'muted tiny');
      entry.append(details);
    }
    el('timeline-events').append(entry);
  }
}

function render() {
  const sameCase = renderedCaseId === caseId;
  const priorQuestion = sameCase ? el('question-choice').value : null;
  const priorInputs = sameCase ? [...el('source-choice').querySelectorAll('input')] : [];
  const priorSourceIds = new Set(priorInputs.filter(x => x.checked).map(x => Number(x.value)));
  const preserveSources = priorInputs.length > 0;
  const priorEvidenceQuestion = sameCase ? el('evidence-question-choice').value : null;
  const priorEvidenceSource = sameCase ? el('evidence-source-choice').value : null;
  const priorWithdrawTarget = sameCase ? el('evidence-withdraw-id').value : null;
  clear('metrics');
  const latest = active.sources.filter(s => s.state === 'current');
  const stale = active.snapshots.filter(s => s.state === 'stale');
  // A stale snapshot is retained as history after a replacement is acknowledged.
  // Only questions still open due to stale snapshots need *current* attention.
  const reopenedQuestionIds = new Set(stale
    .filter(s => active.questions.some(q => Number(q.id) === Number(s.question_id) && q.state === 'open'))
    .map(s => Number(s.question_id)));
  const reviewRequired = reopenedQuestionIds.size;
  el('metrics').append(
    metric(latest.length, 'Current source documents'), metric(active.assertions.length, 'Reported statements'),
    metric(active.questions.filter(q => q.state === 'open').length, 'Open questions'), metric(reviewRequired, 'Review required'));
  const reviewNotice = el('review-attention');
  reviewNotice.dataset.state = reviewRequired ? 'needs-review' : 'no-open-review';
  el('review-attention-title').textContent = reviewRequired
    ? 'Source changes require renewed review'
    : 'Investigation review status';
  el('review-attention-summary').textContent = reviewRequired
    ? reviewRequired + ' reopened question(s) have source- or evidence-stale investigation history. Inspect changes and record a new scoped demo review; historical snapshots remain accessible.'
    : active.snapshots.length
      ? 'No unresolved source-change review is flagged. Historical stale snapshots remain visible. Demo acknowledgments do not establish clinical review or case completeness.'
      : 'No investigation snapshots exist yet. Start with a source-linked question; there is no clinical conclusion to review.';
  renderTimeline();
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
    card.append(top, meta, button); el('source-list').append(card);
  }
  clear('assertion-list');
  if (!active.assertions.length) empty(el('assertion-list'), 'No current reported statements.');
  for (const assertion of active.assertions) {
    const card = node('div', null, 'finding');
    const heading = node('div', null, 'finding-head');
    const labels = node('div', null, 'finding-labels');
    labels.append(pill('Source says', 'pill-neutral'), pill(assertion.certainty,
      ['pending', 'indeterminate', 'conflicting', 'not-reported', 'not-assessed'].includes(assertion.certainty) ? 'pill-warn' : ''));
    heading.append(node('strong', assertion.finding_key), labels);
    card.append(heading, node('p', assertion.quote, 'quoted'));
    const supportingSource = active.sources.find(s => Number(s.id) === Number(assertion.source_version_id));
    const sourceButton = node('button', supportingSource
      ? 'Inspect ' + supportingSource.document_id + '@' + supportingSource.version + ' · source line ' + assertion.source_line
      : 'Source version #' + assertion.source_version_id + ' unavailable',
      'button secondary minor source-jump');
    sourceButton.type = 'button';
    sourceButton.disabled = !supportingSource;
    if (supportingSource) sourceButton.addEventListener('click', () => openSource(supportingSource, Number(assertion.source_line)));
    card.append(sourceButton);
    el('assertion-list').append(card);
  }
  clear('question-list'); clear('question-choice');
  if (!active.questions.length) empty(el('question-list'), 'Add an unresolved question to begin.');
  for (const question of active.questions) {
    const row = node('div', null, 'question');
    row.append(node('p', question.question), pill(question.state, question.state === 'open' ? 'pill-warn' : ''));
    el('question-list').append(row);
    const opt = node('option', 'Q' + question.id + ' · ' + question.question.slice(0, 62));
    opt.value = question.id; el('question-choice').append(opt);
  }
  if (priorQuestion && [...el('question-choice').options].some(x => x.value === priorQuestion))
    el('question-choice').value = priorQuestion;
  renderEvidenceChoices();
  clear('evidence-question-choice'); clear('evidence-source-choice'); clear('evidence-withdraw-id');
  for (const question of active.questions) {
    const opt = node('option', 'Q' + question.id + ' · ' + question.question.slice(0, 62));
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
      ' · SHA ' + item.sha256.slice(0, 12) + '…', 'snapshot-meta'), view);
    el('evidence-list').append(card);
    if (item.state === 'current') {
      const opt = node('option', item.evidence_key + '@' + item.version + ' · ' + item.title);
      opt.value = item.id; el('evidence-source-choice').append(opt);
      const withdraw = node('option', item.evidence_key + '@' + item.version + ' · ' + item.title);
      withdraw.value = item.id; el('evidence-withdraw-id').append(withdraw);
    }
  }
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
        ' · STALE: choose current evidence and reconsider rationale');
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
    row.append(node('strong', item.evidence_key + '@' + item.version + ' · Q' + item.question_id),
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
    label.append(checkbox, node('span', source.document_id + '@' + source.version + ' · ' +
      source.event_date + (source.state !== 'current' ? ' · STALE: uncheck and select the replacement explicitly' : '')));
    el('source-choice').append(label);
  }
  if (!latest.length) empty(el('source-choice'), 'No current sources.');
  if ([...priorSourceIds].some(id => !latest.some(x => x.id === id)))
    notice('An investigation source changed while you were editing. Review the narrative and explicitly reconcile source selections before saving.', true);
  clear('snapshot-list');
  if (!active.snapshots.length) empty(el('snapshot-list'), 'No investigation drafts yet.');
  for (const snapshot of active.snapshots) {
    const box = node('div', null, 'snapshot'); const top = node('div', null, 'topline');
    top.append(node('strong', 'Investigation #' + snapshot.id), pill(snapshot.state,
      snapshot.state === 'stale' ? 'pill-alert' : snapshot.state === 'draft' ? 'pill-warn' : ''));
    const description = node('p', snapshot.summary);
    const meta = node('p', 'Sources: ' + snapshot.source_ids.map(x => '#' + x).join(', ') + ' · ' + snapshot.created_at, 'snapshot-meta');
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
    box.append(top, description, meta, actions);
    if (snapshot.state === 'stale') box.append(node('p', 'A source was amended. This version remains historical and cannot be acknowledged as current.', 'muted'));
    el('snapshot-list').append(box);
  }
  clear('quarantine-list');
  for (const entry of active.quarantines) {
    el('quarantine-list').append(node('div', 'Quarantined #' + entry.id + ': declared ' + entry.declared_patient_id + ', not ' + caseId + ' · no assertions imported', 'quarantine'));
  }
  clear('event-list');
  for (const event of active.events.slice(0, 12)) {
    const card = node('div', event.kind.replaceAll('_', ' '), 'event');
    card.append(node('small', event.occurred_at)); el('event-list').append(card);
  }
  renderedCaseId = caseId;
}
function renderOriginalSource(text, lineNumber) {
  // Never insert imported source text as HTML. Preserve each character and
  // original line break while marking only the requested anchored line.
  const viewer = el('dialog-text');
  viewer.replaceChildren();
  const lines = String(text).split('\n');
  const hasAnchor = Number.isInteger(lineNumber) && lineNumber > 0 && lineNumber <= lines.length;
  for (let index = 0; index < lines.length; index++) {
    if (index) viewer.append(document.createTextNode('\n'));
    if (hasAnchor && index + 1 === lineNumber) {
      viewer.append(node('mark', lines[index], 'source-highlight'));
    } else {
      viewer.append(document.createTextNode(lines[index]));
    }
  }
  return hasAnchor;
}
async function openSource(source, lineNumber = null) {
  try {
    const requestedCase = readyCase();
    const response = await api('/api/cases/' + requestedCase + '/sources/' + source.id);
    if (requestedCase !== caseId) return;
    el('dialog-title').textContent = source.document_id + '@' + source.version + ' · original UTF-8';
    const highlighted = renderOriginalSource(response.text, lineNumber);
    el('dialog-context').textContent = highlighted
      ? 'Source-reported statement · highlighted original line ' + lineNumber + '. Not clinically reviewed.'
      : lineNumber === null
        ? 'Original report text, including exact source version. Not clinically reviewed.'
        : 'The requested line is not present in this source version; inspect the unaltered report text.';
    el('source-dialog').showModal();
    if (highlighted) el('dialog-text').querySelector('mark.source-highlight')?.scrollIntoView({block:'center'});
  } catch (err) { notice(err.message, true); }
}
async function openEvidence(item) {
  try {
    const requestedCase = readyCase();
    const response = await api('/api/evidence/' + item.id);
    if (requestedCase !== caseId) return;
    el('dialog-title').textContent = item.evidence_key + '@' + item.version + ' · fictional source';
    el('dialog-context').textContent = 'Fictional evidence text · human-authored demo, not clinical appraisal.';
    el('dialog-text').textContent = response.text;
    el('source-dialog').showModal();
  } catch (err) { notice(err.message, true); }
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
el('dialog-close').addEventListener('click', () => el('source-dialog').close());
el('question-form').addEventListener('submit', async event => {
  event.preventDefault(); try {
    const requestedCase = readyCase();
    await api('/api/cases/' + requestedCase + '/questions', { question: el('question-text').value });
    if (requestedCase !== caseId) return;
    el('question-text').value = ''; notice('Question persisted.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('draft-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const sources = [...el('source-choice').querySelectorAll('input:checked')].map(x => Number(x.value));
    const created = await api('/api/cases/' + requestedCase + '/snapshots', {
      question_id: Number(el('question-choice').value), summary: el('draft-summary').value, source_ids: sources,
      evidence_assessment_ids: [...el('evidence-choice').querySelectorAll('input:checked')].map(x => Number(x.value)),
    });
    if (requestedCase !== caseId) return;
    el('draft-summary').value = ''; notice('Draft #' + created.snapshot_id + ' saved with exact source versions.'); await refresh();
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
    notice('Import: ' + outcome.result + (outcome.invalidated_snapshots?.length ? ' · ' + outcome.invalidated_snapshots.length + ' investigation(s) marked stale' : ''));
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
      (outcome.invalidated_snapshots?.length ? ' · ' + outcome.invalidated_snapshots.length + ' draft(s) stale' : ''));
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
    notice('Synthetic evidence withdrawn · ' + outcome.invalidated_snapshots.length + ' dependent draft(s) stale.');
    el('evidence-withdraw-reason').value = ''; await refresh();
  } catch (err) { notice(err.message, true); }
});


function renderBibliography(record) {
  clear('bibliography-result');
  const card = node('article', null, 'source-card');
  card.append(node('strong', record.title));
  const meta = node('p', [record.journal, record.year, record.publication_type]
    .filter(x => x !== null && x !== undefined && x !== '').join(' · '), 'snapshot-meta');
  card.append(meta);
  if (Array.isArray(record.authors) && record.authors.length) {
    card.append(node('p', 'Authors: ' + record.authors.join(', '), 'muted'));
  }
  card.append(node('p', 'Source: ' + record.source.provider + ' · Retrieved ' +
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
initialize();
initializeBibliography();
