'use strict';
// All displayed data is from local, synthetic records. No third-party scripts.
let caseId = null;
let active = null;
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
    picker.addEventListener('change', () => { caseId = picker.value; refresh(); });
    caseId = cases[0].case_id;
    await refresh();
  } catch (err) { notice(err.message, true); }
}
async function refresh() {
  try {
    active = await api('/api/cases/' + caseId + '/state');
    el('case-heading').textContent = active.case.label;
    render();
  } catch (err) { notice(err.message, true); }
}
function render() {
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
  clear('source-choice');
  for (const source of latest) {
    const label = node('label');
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.value = source.id; checkbox.checked = true;
    label.append(checkbox, node('span', source.document_id + '@' + source.version + ' · ' + source.event_date));
    el('source-choice').append(label);
  }
  if (!latest.length) empty(el('source-choice'), 'No current sources.');
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
          await api('/api/cases/' + caseId + '/snapshots/' + snapshot.id + '/review', { reviewer_label: 'Synthetic reviewer (unverified)' });
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
}
async function openSource(source) {
  try {
    const response = await api('/api/cases/' + caseId + '/sources/' + source.id);
    el('dialog-title').textContent = source.document_id + '@' + source.version + ' · original UTF-8';
    el('dialog-text').textContent = response.text;
    el('source-dialog').showModal();
  } catch (err) { notice(err.message, true); }
}
async function downloadSnapshot(id) {
  try {
    const text = await api('/api/cases/' + caseId + '/snapshots/' + id + '/export');
    const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }));
    const link = document.createElement('a'); link.href = url; link.download = 'synthetic-investigation-' + id + '.md';
    document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(url);
  } catch (err) { notice(err.message, true); }
}
el('dialog-close').addEventListener('click', () => el('source-dialog').close());
el('question-form').addEventListener('submit', async event => {
  event.preventDefault(); try {
    await api('/api/cases/' + caseId + '/questions', { question: el('question-text').value });
    el('question-text').value = ''; notice('Question persisted.'); await refresh();
  } catch (err) { notice(err.message, true); }
});
el('draft-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const sources = [...el('source-choice').querySelectorAll('input:checked')].map(x => Number(x.value));
    const created = await api('/api/cases/' + caseId + '/snapshots', {
      question_id: Number(el('question-choice').value), summary: el('draft-summary').value, source_ids: sources,
    });
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
    const outcome = await api('/api/cases/' + caseId + '/imports', { text: el('report-text').value });
    notice('Import: ' + outcome.result + (outcome.invalidated_snapshots?.length ? ' · ' + outcome.invalidated_snapshots.length + ' investigation(s) marked stale' : ''));
    el('report-text').value = ''; await refresh();
  } catch (err) { notice(err.message, true); }
});
initialize();
