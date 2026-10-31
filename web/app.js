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
      if ((el('draft-summary').value.trim() || el('evidence-rationale').value.trim())) {
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
  clear('evidence-choice');
  const qid = Number(el('question-choice').value);
  const matches = (active.evidence_assessments || []).filter(a => a.question_id === qid && a.evidence_state === 'current');
  if (!matches.length) return empty(el('evidence-choice'), 'No current evidence assessment for this question (optional).');
  for (const assessment of matches) {
    const label = node('label');
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.value = assessment.id;
    label.append(checkbox, node('span', assessment.evidence_key + '@' + assessment.version + ' · ' +
      assessment.relation + ' · ' + assessment.applicability));
    el('evidence-choice').append(label);
  }
}
function render() {
  const sameCase = renderedCaseId === caseId;
  const priorQuestion = sameCase ? el('question-choice').value : null;
  const priorInputs = sameCase ? [...el('source-choice').querySelectorAll('input')] : [];
  const priorSourceIds = new Set(priorInputs.filter(x => x.checked).map(x => Number(x.value)));
  const preserveSources = priorInputs.length > 0;
  clear('metrics');
  const latest = active.sources.filter(s => s.state === 'current');
  const stale = active.snapshots.filter(s => s.state === 'stale');
  el('metrics').append(
    metric(latest.length, 'Current source documents'), metric(active.assertions.length, 'Reported statements'),
    metric(active.questions.filter(q => q.state === 'open').length, 'Open questions'), metric(stale.length, 'Review required'));
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
    heading.append(node('strong', assertion.finding_key), pill(assertion.certainty,
      ['pending', 'indeterminate', 'conflicting', 'not-reported', 'not-assessed'].includes(assertion.certainty) ? 'pill-warn' : ''));
    card.append(heading, node('p', assertion.quote, 'quoted'), node('span', 'Exact source version #' + assertion.source_version_id + ' · line ' + assertion.source_line, 'ref'));
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
  clear('evidence-question-choice'); clear('evidence-source-choice');
  for (const question of active.questions) {
    const opt = node('option', 'Q' + question.id + ' · ' + question.question.slice(0, 62));
    opt.value = question.id; el('evidence-question-choice').append(opt);
  }
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
async function openSource(source) {
  try {
    const requestedCase = readyCase();
    const response = await api('/api/cases/' + requestedCase + '/sources/' + source.id);
    if (requestedCase !== caseId) return;
    el('dialog-title').textContent = source.document_id + '@' + source.version + ' · original UTF-8';
    el('dialog-text').textContent = response.text;
    el('source-dialog').showModal();
  } catch (err) { notice(err.message, true); }
}
async function openEvidence(item) {
  try {
    const requestedCase = readyCase();
    const response = await api('/api/evidence/' + item.id);
    if (requestedCase !== caseId) return;
    el('dialog-title').textContent = item.evidence_key + '@' + item.version + ' · fictional source';
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

el('question-choice').addEventListener('change', renderEvidenceChoices);
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
    el('evidence-withdraw-id').value = ''; el('evidence-withdraw-reason').value = ''; await refresh();
  } catch (err) { notice(err.message, true); }
});

initialize();
