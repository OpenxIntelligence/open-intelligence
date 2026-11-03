'use strict';
// All displayed data is from local, synthetic records. No third-party scripts.
let caseId = null;
let active = null;
let refreshSequence = 0;
let renderedCaseId = null;
// Worklist generations describe rendered summaries, never chart readiness.
let incomingBoardSequence = 0;
let incomingRowRevision = 0;
let incomingRosterUnavailable = false;
// Startup describes the first roster request, not chart state or readiness.
let workspaceStartupPhase = 'loading';
let workspaceStartupSequence = 0;
let workspaceStartupPreferredCase = null;
const el = (id) => document.getElementById(id);
function node(tag, text, className = '') {
  const item = document.createElement(tag);
  if (text !== undefined && text !== null) item.textContent = String(text);
  if (className) item.className = className;
  return item;
}
function clear(id) { el(id).replaceChildren(); }
function notice(message, error = false, ownerCase = null) {
  const item = el('notice');
  item.textContent = message;
  item.className = error ? 'notice error' : 'notice';
  if (ownerCase) item.dataset.caseId = ownerCase;
  else delete item.dataset.caseId;
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
function hasUnfinishedCaseWork() {
  return Boolean(el('source-file')?.files?.length) ||
    ['question-text', 'report-text', 'draft-observations', 'draft-summary',
     'draft-assumptions', 'evidence-rationale', 'evidence-withdraw-reason',
     'option-description'].some(id => el(id)?.value.trim());
}
function presentWorkspaceStartup(phase) {
  workspaceStartupPhase = phase;
  const loading = phase === 'loading', region = el('workspace-startup');
  region.hidden = phase === 'available';
  region.className = phase === 'failed' ? 'notice error' : 'notice';
  region.setAttribute('aria-busy', String(loading));
  el('workspace-startup-message').textContent = loading ? 'Loading the case list…' : phase === 'failed'
    ? 'The case list is unavailable. Retry loading to open your workspace.'
    : phase === 'empty' ? 'No case workspaces are available yet. Create a workspace or refresh the list after a case is added.' : '';
  el('workspace-startup-retry').textContent = loading ? 'Loading…' : phase === 'empty' ? 'Refresh list' : 'Retry loading';
  el('workspace-startup-retry').disabled = loading;
  el('case-picker').disabled = phase !== 'available';
  el('worklist-refresh').disabled = loading;
  if (phase !== 'available') {
    el('incoming-list').setAttribute('aria-busy', String(loading));
    el('worklist-status').textContent = loading ? 'Loading the case list…' : phase === 'failed'
      ? 'The case list is unavailable. Retry loading to check for cases.' : 'No case workspaces are available yet.';
  }
  document.dispatchEvent(new Event('oi:workspace-startup-changed'));
}
async function initialize(preferredCaseId) {
  // Once established, selection and retry belong to the existing chart owner.
  if (caseId) return true;
  if (preferredCaseId) workspaceStartupPreferredCase = preferredCaseId;
  const sequence = ++workspaceStartupSequence;
  const current = () => sequence === workspaceStartupSequence && !caseId;
  // Creation may supersede an initializer already reading its board summaries.
  ++incomingBoardSequence;
  presentWorkspaceStartup('loading');
  try {
    const response = await api('/api/cases');
    if (!current()) return false;
    if (!Array.isArray(response) || response.some(entry => !entry ||
      typeof entry.case_id !== 'string' || !entry.case_id.trim() || typeof entry.label !== 'string'))
      throw Error('Case list unavailable.');
    const seen = new Set();
    const cases = response.filter(entry => {
      if (seen.has(entry.case_id)) return false;
      seen.add(entry.case_id); return true;
    });
    if (workspaceStartupPreferredCase && !seen.has(workspaceStartupPreferredCase))
      throw Error('Created workspace not available yet.');
    const picker = el('case-picker');
    picker.replaceChildren();
    for (const entry of cases) {
      const option = node('option', entry.label.replace(/^Fictional case /, '') + ', ' + entry.case_id);
      option.value = entry.case_id;
      picker.append(option);
    }
    // Keep the initial list ahead of canonical chart projection, as before.
    await renderIncomingBoard(cases);
    if (!current()) return false;
    if (!cases.length) {
      el('case-heading').textContent = 'No synthetic cases found';
      presentWorkspaceStartup('empty');
      return true;
    }
    caseId = workspaceStartupPreferredCase || cases[0].case_id;
    workspaceStartupPreferredCase = null;
    picker.value = caseId;
    presentWorkspaceStartup('available');
    document.dispatchEvent(new Event('oi:case-selection-changed'));
    await refresh();
    return true;
  } catch (_) {
    if (current()) presentWorkspaceStartup('failed');
    return false;
  }
}
el('workspace-startup-retry').addEventListener('click', () => initialize());
// Bind once, independently of how many initial roster requests are retried.
el('case-picker').addEventListener('change', () => {
  if (!caseId) return;
  const picker = el('case-picker');
  // Reopening a ready chart preserves drafts. Reopening an unavailable
  // chart retries its existing state owner without resetting local inputs.
  if (picker.value === caseId) {
    try { readyCase(); } catch (_) { refresh(); }
    return;
  }
  // A selected File is unfinished work even before its original bytes finish
  // loading. Use this same guard for the connected workspace creation flow.
  if (hasUnfinishedCaseWork()) {
    picker.value = caseId;
    notice('Save or explicitly clear the unfinished investigation draft, question or pasted record, or discard the selected source before switching cases.', true, caseId);
    return;
  }
  cancelSourceRead();
  // Saved-report actions and switch warnings belong to the original chart.
  // Unrelated global notices keep their existing lifetime.
  if (el('notice').dataset.caseId === caseId) {
    el('notice').replaceChildren();
    el('notice').hidden = true;
    delete el('notice').dataset.caseId;
  }
  caseId = picker.value;
  active = null; // Reject writes while the next case is loading.
  for (const id of ['question-text', 'report-text', 'evidence-rationale', 'draft-observations',
    'draft-summary', 'draft-assumptions']) el(id).value = '';
  if (el('source-dialog').open) el('source-dialog').close();
  if (el('compare-dialog').open) el('compare-dialog').close();
  // Notify consumers only after the canonical selection has been accepted.
  // Native select events can run microtasks between their individual listeners.
  document.dispatchEvent(new Event('oi:case-selection-changed'));
  refresh();
});
function incomingRows() {
  return [...el('incoming-list').children].filter(row => row.dataset.caseId);
}
function incomingRow(id) { return incomingRows().find(row => row.dataset.caseId === id); }
function incomingSummary(entry, state) {
  if (state?.case?.case_id !== entry.case_id) throw Error('Case summary identity mismatch.');
  return {
    label: entry.label, caseId: entry.case_id,
    latestEvent: state.sources.reduce((max, source) => source.event_date > max ? source.event_date : max, ''),
    currentSources: state.sources.filter(source => source.state === 'current').length,
    openQuestions: state.questions.filter(question => question.state === 'open').length,
    stale: state.snapshots.filter(snapshot => snapshot.state === 'stale').length,
  };
}
function newIncomingRow(id) {
  const row = node('div', null, 'question');
  row.dataset.caseId = id;
  const open = node('button', 'Open this case', 'button secondary minor');
  open.type = 'button';
  open.addEventListener('click', () => {
    el('case-picker').value = id;
    el('case-picker').dispatchEvent(new Event('change'));
    if (caseId === id && el('case-picker').value === id) workspacePresentation.navigate('overview');
  });
  row.append(node('div'), open);
  return row;
}
function writeIncomingRow(row, summary) {
  row.dataset.caseLabel = summary.label;
  row.dataset.caseSearch = summary.label + ' ' + summary.caseId;
  row.dataset.latestEvent = summary.latestEvent || '';
  row.dataset.summaryState = summary.error ? 'unavailable' : 'ready';
  row.dataset.worklistRevision = String(++incomingRowRevision);
  const description = summary.error ? 'Case summary unavailable. Refresh list to try again.' :
    'Most recent source event: ' + (summary.latestEvent || 'none recorded') +
    ' · Current source documents: ' + summary.currentSources +
    ' · Open questions: ' + summary.openQuestions +
    ' · Historical drafts marked stale: ' + summary.stale;
  // Preserve the actual Open button, including its focus and listener.
  row.firstElementChild.replaceChildren(node('p', summary.label + ' · ' + summary.caseId),
    node('p', description, 'muted'));
}
function orderIncomingRows(rows = incomingRows()) {
  // Source event recency is not receipt time, amendment issue time or urgency.
  rows.sort((a, b) => b.dataset.latestEvent.localeCompare(a.dataset.latestEvent) ||
    Number(a.dataset.rosterOrder) - Number(b.dataset.rosterOrder));
  const list = el('incoming-list'), previous = [...list.children], focused = document.activeElement;
  if (previous.length !== rows.length || previous.some((row, index) => row !== rows[index])) {
    list.replaceChildren(...rows);
    if (focused?.isConnected && rows.some(row => row.contains(focused))) focused.focus({ preventScroll: true });
  }
}
function incomingStatus() {
  if (el('incoming-list').getAttribute('aria-busy') === 'true') return;
  const unavailable = incomingRows().filter(row => row.dataset.summaryState === 'unavailable').length;
  el('worklist-status').textContent = incomingRosterUnavailable
    ? 'Could not refresh the case list. Refresh list to try again.'
    : unavailable ? unavailable + (unavailable === 1 ? ' case summary is' : ' case summaries are') +
      ' unavailable. Refresh list to try again.' : 'Case summaries updated.';
}
function projectIncomingCase(state) {
  const row = incomingRow(state.case.case_id);
  if (!row) return; // Membership still comes from the existing roster owner.
  writeIncomingRow(row, incomingSummary(state.case, state));
  orderIncomingRows();
  incomingStatus();
}
async function renderIncomingBoard(cases) {
  const sequence = ++incomingBoardSequence, list = el('incoming-list');
  const button = el('worklist-refresh'), restoreButtonFocus = document.activeElement === button;
  const previousRevisions = new Map(incomingRows().map(row => [row.dataset.caseId, row.dataset.worklistRevision]));
  list.setAttribute('aria-busy', 'true');
  button.disabled = true;
  el('worklist-status').textContent = 'Updating case summaries…';
  try {
    if (cases === undefined) cases = await api('/api/cases');
    if (sequence !== incomingBoardSequence) return;
    if (!Array.isArray(cases)) throw Error('Case list unavailable.');
    incomingRosterUnavailable = false;
    const summaries = [];
    for (const entry of cases) {
      const revision = incomingRow(entry.case_id)?.dataset.worklistRevision;
      let summary;
      try {
        summary = incomingSummary(entry, await api('/api/cases/' + entry.case_id + '/state'));
      } catch (_) {
        summary = { label: entry.label, caseId: entry.case_id, latestEvent: '', error: true };
      }
      if (sequence !== incomingBoardSequence) return;
      summaries.push({ summary, revision });
    }
    const rows = summaries.map(({ summary, revision }, index) => {
      let row = incomingRow(summary.caseId);
      if (!row) {
        row = newIncomingRow(summary.caseId);
        writeIncomingRow(row, summary);
      } else if (row.dataset.worklistRevision === revision) writeIncomingRow(row, summary);
      // A newer canonical projection wins over this read, including its error.
      row.dataset.rosterOrder = String(index);
      return row;
    });
    const picker = el('case-picker'), selected = picker.value;
    for (const entry of cases) {
      if (![...picker.options].some(option => option.value === entry.case_id)) {
        const option = node('option', entry.label.replace(/^Fictional case /, '') + ', ' + entry.case_id);
        option.value = entry.case_id; picker.append(option);
      }
    }
    if (selected) picker.value = selected;
    orderIncomingRows(rows);
    if (!rows.length) empty(list, 'No fictional cases in this demo.');
    // Presentation consumers may finish a saved creation after this accepted
    // roster read. Selection still goes through the existing picker owner.
    document.dispatchEvent(new Event('oi:worklist-updated'));
  } catch (_) {
    if (sequence !== incomingBoardSequence) return;
    incomingRosterUnavailable = true;
    for (const row of incomingRows()) {
      if (row.dataset.worklistRevision === previousRevisions.get(row.dataset.caseId)) {
        writeIncomingRow(row, { label: row.dataset.caseLabel, caseId: row.dataset.caseId, error: true });
      }
    }
    orderIncomingRows();
    if (!incomingRows().length) {
      list.replaceChildren();
      empty(list, 'Case list unavailable. Refresh list to try again.');
    }
  } finally {
    if (sequence === incomingBoardSequence) {
      list.setAttribute('aria-busy', 'false');
      button.disabled = !caseId && workspaceStartupPhase === 'loading';
      incomingStatus();
      if (restoreButtonFocus && document.activeElement === document.body && !button.disabled)
        button.focus({ preventScroll: true });
    }
  }
}
el('worklist-refresh').addEventListener('click', () => caseId ? renderIncomingBoard() : initialize());

const CERTAINTY_PLAIN = {
  reported: 'reported', pending: 'still pending', indeterminate: 'not certain yet',
  conflicting: 'different reports disagree', 'not-reported': 'not reported',
  'not-assessed': 'not assessed',
};
function renderPatientView() {
  clear('patient-timeline'); clear('patient-findings'); clear('patient-questions'); clear('patient-uncertainty');
  if (!active) return;
  const groups = groupedTimeline(active.sources).slice().reverse();
  if (!groups.length) empty(el('patient-timeline'), 'No records yet in this fictional case.');
  for (const group of groups) {
    const item = node('div', null, 'question');
    const amended = group.versions.length > 1;
    item.append(node('p', 'On ' + group.eventDate + ', a ' + group.kind + ' report (' + group.documentId + ') was recorded.' +
      (amended ? ' This report was later corrected; the latest version is the one shown in the workspace, and older versions are kept.' : '')));
    el('patient-timeline').append(item);
  }
  if (!active.assertions.length) empty(el('patient-findings'), 'No reported findings yet in this fictional case.');
  for (const assertion of active.assertions) {
    const card = node('div', null, 'finding');
    card.append(node('strong', 'Source says'), node('p', assertion.quote, 'quoted'),
      node('span', 'How certain the source is: ' + (CERTAINTY_PLAIN[assertion.certainty] || assertion.certainty) +
        ' · Exact source version #' + assertion.source_version_id + ', line ' + assertion.source_line, 'ref'));
    const source = active.sources.find(item => Number(item.id) === Number(assertion.source_version_id));
    const inspect = node('button', source ? 'Read the original source' : 'Original source unavailable', 'button secondary minor source-jump');
    inspect.type = 'button';
    inspect.disabled = !source;
    if (source) inspect.addEventListener('click', () => openSource(source, Number(assertion.source_line)));
    card.append(inspect);
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
  const notes = [];
  if (stale) notes.push(stale + ' earlier draft(s) retain their original text after a source changed. Current questions and review status show what still needs attention.');
  if (superseded) notes.push(superseded + ' older report version(s) have been replaced by a newer version; the older versions are still kept and can be inspected.');
  if (!notes.length) notes.push('Nothing in this fictional case is currently flagged as changed or needing another look.');
  for (const text of notes) {
    const row = node('div', null, 'question');
    row.append(node('p', text));
    el('patient-uncertainty').append(row);
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
    projectIncomingCase(response);
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
  // Source-dependent review is CURRENT work only while its question is reopened.
  // Keep superseded snapshots stale in history even after the replacement is acknowledged.
  const reopenedQuestionIds = new Set(stale
    .filter(snapshot => active.questions.some(q =>
      Number(q.id) === Number(snapshot.question_id) && q.state === 'open'))
    .map(snapshot => Number(snapshot.question_id)));
  const reviewRequired = reopenedQuestionIds.size;
  el('metrics').append(
    metric(latest.length, 'Current source documents'), metric(active.assertions.length, 'Reported statements'),
    metric(active.questions.filter(q => q.state === 'open').length, 'Open questions'), metric(reviewRequired, 'Review required'));
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
    el('assertion-list').append(card);
  }
  renderBiologicalAssets();
  clear('question-list'); clear('question-choice');
  if (!active.questions.length) empty(el('question-list'), 'Add an unresolved question to begin.');
  for (const question of active.questions) {
    const row = node('div', null, 'question');
    row.append(node('p', question.question), pill(question.state, question.state === 'open' ? 'pill-warn' : ''));
    el('question-list').append(row);
    const opt = node('option', 'Q' + question.id + ', ' + question.question.slice(0, 62));
    opt.value = question.id; el('question-choice').append(opt);
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
  if (!active.snapshots.length) empty(el('snapshot-list'), 'No investigation drafts yet.');
  for (const snapshot of active.snapshots) {
    const box = node('div', null, 'snapshot'); const top = node('div', null, 'topline');
    box.id = 'snapshot-' + snapshot.id;
    top.append(node('strong', 'Investigation #' + snapshot.id), pill(snapshot.state,
      snapshot.state === 'stale' ? 'pill-alert' : snapshot.state === 'draft' ? 'pill-warn' : ''));
    const origin = snapshot.investigation_origin;
    const description = node(origin ? 'div' : 'p', origin ? null : snapshot.summary);
    if (origin) {
      // Preserve report structure as literal text; model output never becomes HTML.
      for (const line of snapshot.summary.split('\n')) description.append(node('div', line || '\u00a0'));
    }
    const meta = node('p', 'Sources: ' + snapshot.source_ids.map(x => '#' + x).join(', ') + ', ' + snapshot.created_at, 'snapshot-meta');
    const actions = node('div', null, 'actions');
    const exportButton = node('button', 'Export with sources', 'button secondary minor'); exportButton.type = 'button';
    exportButton.addEventListener('click', () => downloadSnapshot(snapshot.id)); actions.append(exportButton);
    if (snapshot.state === 'draft') {
      const button = node('button', 'Demo review acknowledgment', 'button minor'); button.type = 'button';
      button.dataset.presentation = 'clinician';
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
    if (origin) {
      box.append(node('p', 'Prepared from model investigation #' + origin.investigation_id +
        ' · ' + origin.mode + ' · ' + origin.model + ' · ' + origin.template, 'snapshot-meta'));
      appendReviewCitations(box, origin.citations || [], caseId, refreshSequence);
    }
    if (snapshot.state === 'stale') box.append(node('p', origin
      ? 'Source or evidence inputs changed. This historical report and its review record are preserved; a new run and report are required.'
      : 'Source or evidence inputs changed. This historical draft and its review record are preserved; prepare a new draft for review.', 'muted'));
    el('snapshot-list').append(box);
  }
  clear('model-investigation-question');
  for (const question of active.questions) {
    const opt = node('option', question.question);
    opt.value = question.id; el('model-investigation-question').append(opt);
  }
  loadModelInvestigations();
  loadChangesSinceReview();
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
  renderOptions();
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
el('dialog-close').addEventListener('click', () => { cancelSourceRead(); el('source-dialog').close(); });
el('compare-close').addEventListener('click', () => { cancelSourceRead(); el('compare-dialog').close(); });
// Native Escape dispatches cancel before closing. Avoid a close-event handler:
// queued programmatic close events must not cancel a newer read intent.
for (const id of ['source-dialog', 'compare-dialog'])
  el(id).addEventListener('cancel', cancelSourceRead);
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
    notice('Draft #' + created.snapshot_id + ' saved with exact source versions.', false, requestedCase);
    const reportLink = node('a', 'View saved report', 'notice-action');
    reportLink.href = '#snapshot-' + created.snapshot_id;
    el('notice').append(' ', reportLink);
    await refresh();
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
    await renderIncomingBoard(); // Shared evidence can invalidate more than the selected case.
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
    await renderIncomingBoard();
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


function renderOptions() {
  el('option-disclaimer').textContent = active.option_disclaimer || '';
  const options = active.options || [];
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
  fill('option-snapshot-choice', active.snapshots, s => 'Investigation #' + s.id + ' · ' + s.state);
  fill('review-snapshot-choice', active.snapshots, s => 'Investigation #' + s.id + ' · ' + s.state, true);
  const optionLabel = o => 'Option #' + o.id + ' · ' + o.label + ' (' + o.display_operational_status + ')';
  fill('dependency-option-choice', options, optionLabel);
  fill('task-option-choice', options, optionLabel);
  fill('threat-option-choice', options, optionLabel);
  fill('review-option-choice', options, optionLabel);
  fill('dependency-option-target-choice', options, optionLabel, true);
  fill('dependency-source-choice', active.sources, s => s.document_id + '@' + s.version + ' · ' + s.state, true);
  fill('dependency-assessment-choice', active.evidence_assessments || [],
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
    box.append(top, node('p', option.description),
      node('p', 'Based on investigation #' + option.snapshot_id + ' (' + option.snapshot_state + ') · ' +
        option.potential_discussion_deadline.label, 'snapshot-meta'));
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
        (t.lead_time_days !== null && t.lead_time_days !== undefined ? ' · lead ' + t.lead_time_days + 'd' : '')).join('; '), 'snapshot-meta'));
    }
    if (option.threats.length) {
      box.append(node('p', 'Optionality threats: ' + option.threats.map(t =>
        t.kind + ': ' + t.description +
        (t.threat_date ? ' · ' + t.threat_date + ' (' + t.threat_basis + ')' : ' · date unknown')).join(' ; '), 'snapshot-meta'));
    }
    if (option.review_events.length) {
      box.append(node('p', 'Review history: ' + option.review_events.map(e =>
        e.action + ' by ' + e.reviewer_label + ' · scope: ' + e.scope).join(' ; '), 'snapshot-meta'));
    }
    el('option-list').append(box);
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
function modelViewIsCurrent(requestedCase, sequence) {
  return requestedCase === caseId && sequence === refreshSequence &&
    renderedCaseId === requestedCase && active?.case?.case_id === requestedCase;
}
async function prepareModelReviewDraft(detail, requestedCase, sequence, button) {
  if (button.disabled || !modelViewIsCurrent(requestedCase, sequence)) return;
  try {
    if (readyCase() !== requestedCase || detail.case_id !== requestedCase || detail.stale ||
        !Number.isSafeInteger(detail.id) || detail.id < 1 ||
        !Number.isSafeInteger(detail.question_id) || detail.question_id < 1 ||
        !detail.context_fingerprint || !['completed', 'abstained'].includes(detail.status) || detail.review_draft)
      throw Error('A current investigation with captured inputs is required. Run a new investigation if needed.');
    button.disabled = true;
    button.textContent = 'Preparing…';
    const result = await api('/api/cases/' + requestedCase + '/investigations/' + detail.id + '/review-draft',
      {question_id: detail.question_id});
    if (!modelViewIsCurrent(requestedCase, sequence)) return;
    notice('Review draft #' + result.snapshot_id + ' is available in Reports. Human review remains a separate action.');
    await refresh();
  } catch (err) {
    if (modelViewIsCurrent(requestedCase, sequence)) notice(err.message, true);
  } finally {
    if (modelViewIsCurrent(requestedCase, sequence)) {
      button.disabled = false;
      button.textContent = 'Prepare review draft';
    }
  }
}
function appendReviewCitations(container, citations, requestedCase, sequence) {
  if (!citations.length) return;
  const actions = node('div', null, 'actions');
  for (const citation of citations) {
    const button = node('button', 'Read ' + citation.label, 'button secondary minor');
    button.type = 'button';
    button.addEventListener('click', async () => {
      if (!modelViewIsCurrent(requestedCase, sequence)) return;
      if (citation.type === 'source') {
        const source = active.sources.find(item => item.id === citation.id);
        if (source) await openSource(source); // The model contract has no exact line anchor.
      } else if (citation.type === 'assessment') {
        const evidence = (active.evidence || []).find(item => item.id === citation.evidence_version_id);
        if (evidence) await openEvidence(evidence);
      }
    });
    actions.append(button);
  }
  container.append(actions);
}
let modelInvestigationSequence = 0;
async function loadModelInvestigations() {
  const requested = caseId;
  const sequence = refreshSequence;
  const loadSequence = ++modelInvestigationSequence;
  const current = () => loadSequence === modelInvestigationSequence && modelViewIsCurrent(requested, sequence);
  try {
    const data = await api('/api/cases/' + requested + '/investigations');
    if (!current()) return;
    clear('model-investigation-list');
    const items = data.investigations || [];
    if (!items.length) { empty(el('model-investigation-list'), 'No model investigations yet.'); return; }
    for (const item of items) {
      const detail = await api('/api/cases/' + requested + '/investigations/' + item.id);
      if (!current()) return;
      if (detail.case_id !== requested) continue;
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
      if (detail.review_draft) {
        const link = node('a', 'Review draft #' + detail.review_draft.snapshot_id + ' · ' + detail.review_draft.state);
        link.href = '#snapshot-' + detail.review_draft.snapshot_id;
        box.append(link);
      } else if (!detail.stale && detail.context_fingerprint && ['completed', 'abstained'].includes(detail.status)) {
        const button = node('button', 'Prepare review draft', 'button minor');
        button.type = 'button';
        button.addEventListener('click', () => prepareModelReviewDraft(detail, requested, sequence, button));
        box.append(button);
      } else if (!detail.context_fingerprint) {
        box.append(node('p', 'This older run has no captured input context. Run a new investigation to prepare a draft.', 'muted'));
      }
      if (detail.stale) box.append(node('p', 'Sources or evidence changed. Run a new investigation before preparing a review draft.', 'muted'));
      box.append(node('p', detail.disclaimer || 'Research demonstration only.', 'muted'));
      el('model-investigation-list').append(box);
    }
  } catch (err) {
    if (current()) notice(err.message, true);
  }
}
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
      ? 'Reported findings: ' + findings.map(entry => entry.finding_key + ' (' + entry.reported_state + ')').join('; ')
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
          : cause.cause === 'investigation_context_change'
            ? 'Stale because sources or assessments in the model input context changed (event #' + cause.event_id +
              ' at ' + cause.occurred_at + '). A new run and report are required.'
          : 'Stale (' + (cause.cause || 'unknown cause') + ', event #' + cause.event_id +
            ' at ' + cause.occurred_at + ').';
      box.append(node('p', causeText, 'muted'));
    }
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
document.addEventListener('oi:composer-open-source', event => {
  const detail = event.detail || {};
  if (!active || detail.caseId !== caseId ||
      !Number.isSafeInteger(detail.sourceId) || !Number.isSafeInteger(detail.line)) return;
  const source = active.sources.find(x => x.id === detail.sourceId);
  if (!source) return;
  // The existing inspector expects an active-case source record, NOT a
  // numeric identifier; it rechecks membership before fetching raw bytes.
  void openSource(source, detail.line);
});

el('model-investigation-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const requestedCase = readyCase();
    const contextFingerprint = el('composer-context-fingerprint').value;
    if (!/^[a-f0-9]{64}$/.test(contextFingerprint)) {
      throw Error('Preview and verify the current Composer source context before running.');
    }
    await api('/api/cases/' + requestedCase + '/investigations', {
      question_id: Number(el('model-investigation-question').value),
      template: el('model-investigation-template').value,
      mode: el('model-investigation-mode').value,
      context_fingerprint: contextFingerprint,
    });
    if (requestedCase !== caseId) return;
    notice('Model investigation stored as a hypothesis pending review.');
    await refresh();
  } catch (err) {
    // A legitimate source amendment can race an in-progress task. Never leave
    // the user with a visually reusable old fingerprint after the server
    // rejects the task; update both chart and Composer from canonical state.
    if (String(err.message).includes('stale Composer context')) {
      try { await refresh(); } catch (_) { /* notice below owns error feedback */ }
      document.dispatchEvent(new Event('oi:composer-refresh'));
    }
    notice(err.message, true);
  }
});
// Begin workspace navigation model.
// Presentation routes only. They never grant permissions or own case data.
const WORKSPACE_ROUTES = {
  'incoming-board': { title: 'Patients', group: 'patients', scope: 'global', clinical: true },
  'patient-home': { title: 'Your health overview', group: 'home', scope: 'case' },
  overview: { title: 'Patient overview', group: 'overview', scope: 'case', clinical: true },
  'patient-view': { title: 'My record', group: 'record', scope: 'case' },
  assertions: { title: 'Reported findings', group: 'record', scope: 'case' },
  timeline: { title: 'Record timeline', group: 'record', scope: 'case' },
  'patient-mission': { title: 'Record and review status', group: 'record', scope: 'case' },
  'biological-assets': { title: 'Samples and provenance', group: 'record', scope: 'case' },
  sources: { title: 'Documents', group: 'documents', scope: 'case' },
  'source-intake': { title: 'Add original records', group: 'documents', scope: 'case', clinical: true },
  import: { title: 'Structured import', group: 'documents', scope: 'case', clinical: true },
  questions: { title: 'Questions', group: 'investigations', scope: 'case' },
  investigations: { title: 'Prepare a draft', group: 'investigations', scope: 'case', clinical: true },
  'model-investigation-heading': { title: 'Model investigation', group: 'investigations', scope: 'case', clinical: true },
  reports: { title: 'Reports', group: 'investigations', scope: 'case' },
  evidence: { title: 'Evidence review', group: 'evidence', scope: 'case', clinical: true },
  options: { title: 'Options and dependencies', group: 'evidence', scope: 'case', clinical: true },
  'changes-since-review': { title: 'Updates since review', group: 'review', scope: 'case' },
  activity: { title: 'Recent activity', group: 'review', scope: 'case' },
  bibliography: { title: 'Research library', group: 'research', scope: 'global' },
  'workspace-start': { title: 'Workspace setup', group: 'setup', scope: 'global', clinical: true },
};
function resolveWorkspaceRoute(hash, audience) {
  let mode = audience === 'patient' ? 'patient' : 'clinician';
  const target = String(hash || '').replace(/^#/, '');
  const aliases = { 'world-model-detail': 'patient-mission',
    'investigation-history-heading': 'reports', 'question-pane-heading': 'questions',
    'draft-pane-heading': 'investigations', 'new-case-panel': 'workspace-start' };
  const alias = Object.hasOwn(aliases, target) ? aliases[target] : null;
  let id = Object.hasOwn(WORKSPACE_ROUTES, target) ? target : alias;
  if (/^snapshot-[1-9]\d*$/.test(target)) id = 'reports';
  if (!id) id = mode === 'patient' ? 'patient-home' : 'incoming-board';
  const route = WORKSPACE_ROUTES[id];
  if (route.clinical) mode = 'clinician';
  if (id === 'patient-home') mode = 'patient';
  return { ...route, id, target: id === target || alias || /^snapshot-[1-9]\d*$/.test(target)
    ? target : id, audience: mode };
}
// End workspace navigation model.

const workspacePresentation = (() => {
  const views = new Map();
  const main = el('main-content');
  const host = el('view-host');
  const rail = el('workspace-rail');
  const mobile = window.matchMedia('(max-width: 760px)');
  const groups = [
    ['overview', 'Overview', ['overview']],
    ['record', 'Record', ['assertions', 'timeline', 'patient-view', 'patient-mission', 'biological-assets']],
    ['documents', 'Documents', ['sources', 'source-intake', 'import']],
    ['investigations', 'Investigations', ['questions', 'investigations', 'model-investigation-heading', 'reports']],
    ['evidence', 'Evidence', ['evidence', 'options']],
    ['review', 'Review', ['changes-since-review', 'activity']],
  ];
  const descriptions = {
    'incoming-board': 'Find a case and open its dedicated chart. Listed by the most recent source event.',
    'patient-home': 'Your records, open questions and recent updates, together in one place.',
    overview: 'Start with the available source record and its review status.',
    'patient-view': 'Read the original statements in plain language, with uncertainty kept visible.',
    sources: 'Inspect original documents, exact source lines and earlier versions.',
    questions: 'Keep a durable record of the questions you want to explore.',
    reports: 'Read saved drafts, inspect their sources and export a dated copy.',
    bibliography: 'Explore public citation metadata. This library is separate from every patient chart.',
    'workspace-start': 'Create a fictional case and continue with its original records.',
  };
  let current;
  let pendingTarget = null;
  let syncQueued = false;
  let navigationCase = null;

  function register(id, content) {
    if (!content) return;
    const view = node('div', null, 'workspace-view');
    view.dataset.workspaceView = id;
    view.hidden = true;
    view.append(content);
    host.append(view);
    views.set(id, view);
  }
  function link(id, label, className = '') {
    const item = node('a', label || WORKSPACE_ROUTES[id].title, className);
    item.href = '#' + id;
    if (current?.id === id) item.setAttribute('aria-current', 'page');
    return item;
  }
  function removeSubheadBefore(item) {
    if (item.previousElementSibling?.classList.contains('subhead')) item.previousElementSibling.remove();
  }

  // Move the existing, live elements. Form listeners, values and observer targets
  // survive navigation; there is still only one canonical record and workflow.
  el('case-heading-slot').append(el('case-heading'));
  const pickerLabel = document.querySelector('label[for="case-picker"]');
  pickerLabel.textContent = 'Selected case';
  el('case-select-slot').append(pickerLabel, el('case-picker'));
  el('workspace-header').after(el('notice'));
  const sectionMenu = document.querySelector('.section-menu');
  sectionMenu.open = true;
  const help = node('details', null, 'workspace-help');
  help.append(node('summary', 'About this workspace'));
  const originalNote = rail.querySelector(':scope > p.muted');
  if (originalNote) help.append(originalNote);
  const originalHelp = rail.querySelector('.side-bottom');
  if (originalHelp) help.append(originalHelp);
  rail.append(help);
  if (el('new-workspace-button')) {
    el('new-workspace-button').dataset.presentation = 'clinician';
    el('workspace-primary-action').before(el('new-workspace-button'));
  }

  const questionPane = document.querySelector('.question-pane');
  questionPane.classList.add('panel');
  register('questions', questionPane);
  const reportPane = document.querySelector('.investigation-history');
  reportPane.classList.add('panel');
  register('reports', reportPane);
  const modelPane = document.querySelector('.model-investigation');
  modelPane.classList.add('panel');
  register('model-investigation-heading', modelPane);
  for (const id of Object.keys(WORKSPACE_ROUTES)) {
    if (!views.has(id)) register(id, el(id));
  }
  for (const [source, destination] of [
    ['patient-questions', 'home-questions-slot'], ['patient-uncertainty', 'home-updates-slot'],
  ]) {
    removeSubheadBefore(el(source));
    el(destination).append(el(source));
  }
  const patientHistory = node('details', null, 'input-disclosure patient-history');
  patientHistory.append(node('summary', 'Previous record events'));
  removeSubheadBefore(el('patient-timeline'));
  patientHistory.append(el('patient-timeline'));
  el('patient-view').append(patientHistory);

  const overview = el('overview');
  overview.querySelector('.hero-copy').remove();
  const overviewMetrics = node('div', null, 'overview-metrics-slot');
  overviewMetrics.append(el('metrics'));
  overview.prepend(overviewMetrics);
  const overviewRecord = node('div', null, 'overview-record-slot summary-preview');
  overview.append(overviewRecord, link('assertions', 'View the complete source record', 'record-more'),
    el('review-attention'), overview.querySelector('.hero-actions'));
  const guide = document.querySelector('.glance-guide');
  if (guide) overview.append(guide);
  // Only empty legacy layout shells are removed; their live sections are above.
  for (const shell of [...main.children].filter(item => item.matches('.glance-layout, .workspace'))) shell.remove();
  for (const [id, title] of [
    ['option-form', 'Propose an option for discussion'],
    ['option-dependency-form', 'Add a dependency'],
    ['option-task-form', 'Add a preparation task'],
    ['option-threat-form', 'Add an optionality threat'],
    ['option-review-form', 'Record a reviewer action'],
    ['evidence-assessment-form', 'Record an evidence assessment'],
  ]) {
    const form = el(id);
    removeSubheadBefore(form);
    const disclosure = node('details', null, 'input-disclosure contextual-form');
    disclosure.append(node('summary', title));
    form.before(disclosure);
    disclosure.append(form);
  }

  function setMenu(open, returnFocus = false) {
    const expanded = mobile.matches && open;
    rail.hidden = mobile.matches && !expanded;
    document.body.dataset.navOpen = String(expanded);
    el('menu-toggle').setAttribute('aria-expanded', String(expanded));
    if (returnFocus && mobile.matches) el('menu-toggle').focus();
  }
  function renderNavigation() {
    const patient = current.audience === 'patient';
    const globalNav = el('workspace-nav');
    globalNav.replaceChildren();
    const primary = node('div', null, 'nav-section');
    primary.append(node('p', patient ? 'MY HEALTH' : 'WORKSPACE', 'nav-section-label'));
    const patientLinks = [['patient-home', 'Home'], ['patient-view', 'My record'],
      ['sources', 'Documents'], ['questions', 'Questions & reports'], ['changes-since-review', 'Updates']];
    for (const [id, label] of patient ? patientLinks : [['incoming-board', 'Patients'], ['bibliography', 'Research library']]) {
      const item = link(id, label);
      if (patient && ((id === 'patient-view' && current.group === 'record') ||
        (id === 'questions' && current.group === 'investigations') ||
        (id === 'changes-since-review' && current.group === 'review'))) item.setAttribute('aria-current', 'page');
      primary.append(item);
    }
    globalNav.append(primary);
    if (!patient && caseId) {
      const context = node('div', null, 'nav-section');
      context.append(node('p', 'SELECTED CASE', 'nav-section-label'));
      const item = link('overview', 'Patient chart', 'nav-context-link');
      if (current.scope === 'case') item.setAttribute('aria-current', 'page');
      context.append(item);
      globalNav.append(context);
    }
    if (patient || views.has('workspace-start')) {
      const tools = node('div', null, 'nav-section');
      tools.append(node('p', 'TOOLS', 'nav-section-label'));
      if (patient) tools.append(link('bibliography', 'Research library'));
      if (views.has('workspace-start')) tools.append(link('workspace-start', patient ? 'Clinical workspace setup' : 'Workspace setup'));
      globalNav.append(tools);
    }
    el('rail-workspace-label').textContent = patient ? 'Patient experience' : 'Clinical workspace';
    const brand = document.querySelector('.brand');
    brand.href = patient ? '#patient-home' : '#incoming-board';
    brand.setAttribute('aria-label', 'Open Intelligence ' + (patient ? 'home' : 'patients'));

    const chart = el('chart-nav');
    chart.replaceChildren();
    chart.hidden = patient || current.scope !== 'case';
    for (const [id, label, routes] of groups) {
      const entry = link(routes.find(route => views.has(route)), label);
      if (current.group === id) entry.setAttribute('aria-current', 'page');
      chart.append(entry);
    }
    const section = el('section-nav');
    section.replaceChildren();
    let routes = groups.find(group => group[0] === current.group)?.[2] || [];
    if (patient) routes = routes.filter(id => !WORKSPACE_ROUTES[id].clinical);
    routes = routes.filter(id => views.has(id));
    section.hidden = current.scope !== 'case' || routes.length < 2;
    for (const id of routes) section.append(link(id));
    const select = el('chart-section-picker');
    select.replaceChildren();
    el('chart-section-select').hidden = patient || current.scope !== 'case';
    for (const [, label, ids] of groups) {
      const group = node('optgroup'); group.label = label;
      for (const id of ids.filter(id => views.has(id))) {
        const option = node('option', WORKSPACE_ROUTES[id].title); option.value = id;
        group.append(option);
      }
      select.append(group);
    }
    select.value = current.id;
    const crumbs = el('workspace-breadcrumb');
    crumbs.replaceChildren();
    crumbs.append(link(patient ? 'patient-home' : 'incoming-board', patient ? 'Home' : 'Patients'));
    if (current.scope === 'case' && !patient) crumbs.append(node('span', '/'), link('overview', 'Patient chart'));
    if (!['patient-home', 'incoming-board'].includes(current.id)) crumbs.append(node('span', '/'), node('span', current.title));
  }

  function filterList(inputId, listId, selector, countId, emptyId, noun, searchData) {
    const query = el(inputId).value.trim().toLocaleLowerCase();
    const rows = [...el(listId).querySelectorAll(selector)];
    let visible = 0;
    for (const row of rows) {
      row.hidden = !(searchData ? row.dataset[searchData] : row.textContent).toLocaleLowerCase().includes(query);
      if (!row.hidden) visible++;
    }
    const text = visible + ' of ' + rows.length + ' ' + noun;
    if (el(countId).textContent !== text) el(countId).textContent = text;
    el(emptyId).hidden = !query || visible > 0 || !rows.length;
  }
  function filterCases() {
    if (!caseId && !['empty', 'available'].includes(workspaceStartupPhase)) {
      el('case-search-count').textContent = '';
      el('case-search-empty').hidden = true;
      return;
    }
    filterList('case-search', 'incoming-list', '[data-case-search]', 'case-search-count', 'case-search-empty', 'cases', 'caseSearch');
  }
  function filterDocuments() {
    filterList('document-search', 'source-list', '.source-card', 'document-search-count', 'document-search-empty', 'documents');
  }
  function revealTarget() {
    if (!pendingTarget || views.get(current.id).hidden) return;
    const target = el(pendingTarget);
    if (!target || !views.get(current.id).contains(target)) return;
    for (let parent = target; parent && parent !== host; parent = parent.parentElement)
      if (parent.tagName === 'DETAILS') parent.open = true;
    target.scrollIntoView({ block: 'start' });
    if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
    target.focus({ preventScroll: true });
    pendingTarget = null;
  }
  function syncState() {
    syncQueued = false;
    if (!current) return;
    let ready = false;
    try { ready = Boolean(readyCase()); } catch (_) { /* Retain the original readiness guard. */ }
    const emptyState = document.body.dataset.workspaceState === 'empty';
    if (emptyState && views.has('workspace-start') && current.id !== 'workspace-start' && current.id !== 'bibliography') {
      navigate('workspace-start', { replace: true, focus: false });
      return;
    }
    const waiting = current.scope === 'case' && !ready;
    if (navigationCase !== caseId) { navigationCase = caseId; renderNavigation(); }
    el('case-context').hidden = current.scope !== 'case';
    el('case-heading').hidden = !ready;
    el('case-reference').textContent = ready ? 'Fictional record · ' + caseId : (caseId ? 'Loading selected case…' : 'No case selected');
    el('workspace-loading').hidden = !waiting || !caseId;
    el('workspace-loading').textContent = !el('notice').hidden && el('notice').classList.contains('error')
      ? 'The selected record is unavailable. See the message above, or choose another case.'
      : 'Loading the selected record…';
    host.setAttribute('aria-busy', String(waiting && (Boolean(caseId) || workspaceStartupPhase === 'loading')));
    for (const [id, view] of views) view.hidden = id !== current.id || waiting;
    filterCases(); filterDocuments();
    if (ready) revealTarget();
  }
  function scheduleSync() {
    if (syncQueued) return;
    syncQueued = true;
    queueMicrotask(syncState);
  }
  function apply(route, focus) {
    const previous = current;
    current = route;
    if (!views.has(current.id)) current = resolveWorkspaceRoute('', current.audience);
    document.documentElement.dataset.audience = current.audience;
    document.body.dataset.view = current.id;
    el('presentation-view').value = current.audience;
    el('workspace-title').textContent = current.title;
    el('workspace-description').textContent = descriptions[current.id] || '';
    el('workspace-description').hidden = !descriptions[current.id];
    el('workspace-eyebrow').textContent = current.audience === 'patient' ? 'YOUR HEALTH' :
      (current.scope === 'case' ? 'PATIENT CHART' : 'CLINICAL WORKSPACE');
    el('case-context-label').textContent = current.audience === 'patient' ? 'YOUR SELECTED RECORD' : 'PATIENT CHART';
    document.title = current.title + ' · Open Intelligence';
    const primary = el('workspace-primary-action');
    primary.hidden = true;
    if (el('new-workspace-button')) el('new-workspace-button').hidden = current.id !== 'incoming-board';
    // The original source statements are summarized here, then moved back to
    // their complete view; a second set of record data is never generated.
    (current.id === 'overview' ? overviewRecord : views.get('assertions')).append(el('assertions'));
    (current.audience === 'patient' ? el('patient-metrics-slot') : overviewMetrics).append(el('metrics'));
    if (current.id === 'workspace-start' || current.id === 'source-intake') el(current.id).open = true;
    renderNavigation();
    setMenu(false);
    const targetsDetail = current.target !== current.id;
    pendingTarget = targetsDetail ? current.target : null;
    syncState();
    if (focus) {
      if (targetsDetail) revealTarget();
      else {
        window.scrollTo({ top: 0, behavior: 'instant' });
        el('workspace-title').focus({ preventScroll: true });
      }
    } else if (!previous) window.scrollTo(0, 0);
  }
  function navigate(target, options = {}) {
    const route = resolveWorkspaceRoute(target, options.audience || current?.audience);
    const available = views.has(route.id) ? route : resolveWorkspaceRoute('', route.audience);
    const hash = '#' + available.target;
    const method = options.replace ? 'replaceState' : 'pushState';
    if (window.location.hash !== hash || history.state?.presentation !== available.audience)
      history[method]({ presentation: available.audience }, '', hash);
    apply(available, options.focus !== false);
  }

  document.addEventListener('click', event => {
    const anchor = event.target.closest('a[href^="#"]');
    if (!anchor || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const hash = anchor.getAttribute('href');
    if (hash === '#main-content') {
      event.preventDefault();
      main.focus({ preventScroll: true });
      main.scrollIntoView({ block: 'start' });
      return;
    }
    const id = hash.slice(1);
    // Preserve other in-panel anchors without treating arbitrary IDs as routes.
    const destination = el(id)?.closest('[data-workspace-view]')?.dataset.workspaceView;
    if (destination && !Object.hasOwn(WORKSPACE_ROUTES, id) && !/^snapshot-[1-9]\d*$/.test(id)) {
      event.preventDefault();
      navigate(destination);
      pendingTarget = id; revealTarget();
      return;
    }
    event.preventDefault(); navigate(hash);
  });
  window.addEventListener('hashchange', () => apply(resolveWorkspaceRoute(location.hash, current?.audience), true));
  window.addEventListener('popstate', event => apply(resolveWorkspaceRoute(location.hash, event.state?.presentation || current?.audience), true));
  el('presentation-view').addEventListener('change', event => {
    const audience = event.target.value;
    let id = current.id;
    if (audience === 'patient' && (current.clinical || current.scope === 'global')) id = 'patient-home';
    if (audience === 'clinician' && current.audience === 'patient') id = 'incoming-board';
    navigate(id, { audience });
  });
  el('chart-section-picker').addEventListener('change', event => navigate(event.target.value));
  el('menu-toggle').addEventListener('click', () => setMenu(rail.hidden));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && mobile.matches && !rail.hidden && !document.querySelector('dialog[open]')) setMenu(false, true);
  });
  mobile.addEventListener('change', () => setMenu(false));
  el('case-search').addEventListener('input', filterCases);
  el('document-search').addEventListener('input', filterDocuments);
  document.addEventListener('oi:case-selection-changed', scheduleSync);
  document.addEventListener('oi:workspace-startup-changed', scheduleSync);
  const observer = new MutationObserver(scheduleSync);
  for (const id of ['case-heading', 'source-list', 'question-list', 'snapshot-list', 'incoming-list', 'notice'])
    observer.observe(el(id), { childList: true, subtree: true });
  new MutationObserver(scheduleSync).observe(document.body, { attributes: true, attributeFilter: ['data-workspace-state'] });
  document.body.classList.add('ux-ready');
  const initialRoute = resolveWorkspaceRoute(location.hash, history.state?.presentation || 'clinician');
  history.replaceState({ presentation: initialRoute.audience }, '', location.hash || '#' + initialRoute.id);
  apply(initialRoute, false);
  return { navigate };
})();

initialize();
initializeBibliography();
loadModelTemplates();
