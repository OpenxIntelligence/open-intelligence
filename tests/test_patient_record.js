'use strict';
// Independently authored fictional state. The DOM double only supplies browser primitives;
// every rendered label, link target and asynchronous decision comes from the real component.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const filename = path.join(__dirname, '../web/patient-record.js');
const code = fs.existsSync(filename) ? fs.readFileSync(filename, 'utf8') : '';

class Element {
  constructor(tag, doc) { this.tagName = tag; this.ownerDocument = doc; this.children = []; this.attributes = {}; this.dataset = {}; this.listeners = {}; this._text = ''; }
  get textContent() { return this._text + this.children.map(item => item.textContent).join(' '); }
  set textContent(value) { this._text = String(value); this.children = []; }
  set innerHTML(_) { throw Error('Untrusted markup must never be inserted'); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this._text = ''; this.children = items; }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  addEventListener(name, action) { (this.listeners[name] ||= []).push(action); }
  click() { const event = {preventDefault() {}}; for (const action of this.listeners.click || []) action(event); }
}
function nodes(root, tag) {
  return [root, ...root.children.flatMap(child => nodes(child, tag))].filter(item => !tag || item.tagName === tag);
}
function fixture(caseId = 'FICTION-A', marker = 'Authored record') {
  const common = {kind: 'pathology', event_date: '2026-01-10', issued_at: '2026-01-11', received_at: '2026-01-12', specimen_id: 'SYNTH-SAMPLE'};
  const sources = [
    {...common, id: 1, document_id: 'SYNTH-PATH', version: 1, sha256: 'a'.repeat(64), state: 'superseded', supersedes_id: null},
    {...common, id: 2, document_id: 'SYNTH-PATH', version: 2, sha256: 'b'.repeat(64), state: 'current', supersedes_id: 1},
    {...common, id: 3, document_id: 'SYNTH-REVIEW', version: 1, sha256: 'c'.repeat(64), state: 'current', supersedes_id: null},
  ];
  const statuses = ['reported', 'negative', 'pending', 'indeterminate', 'not-reported', 'not-assessed', 'conflicting'];
  const assertions = statuses.map((certainty, index) => ({id: index + 10, source_version_id: index === 1 ? 3 : 2,
    source_line: index + 5, finding_key: index < 2 ? 'Marker A' : 'Field ' + index, certainty, quote: marker + ' ' + certainty}));
  const state = {case: {case_id: caseId}, sources, assertions,
    questions: [{id: 20, case_id: caseId, question: 'Which source needs clarification?', state: 'open'},
      {id: 21, case_id: caseId, question: 'Earlier question', state: 'addressed'}],
    snapshots: [{id: 30, case_id: caseId, question_id: 20, state: 'stale'},
      {id: 31, case_id: caseId, question_id: 20, state: 'draft'}],
    events: [{id: 8, occurred_at: '2026-01-13T10:00:00Z'}, {id: 4, occurred_at: '2026-01-12T10:00:00Z'}]};
  const sourceView = source => ({...common, source_version_id: source.id, document_id: source.document_id,
    version: source.version, source_sha256: source.sha256, state: source.state, supersedes_source_id: source.supersedes_id});
  const observations = assertions.map(assertion => {
    const source = sources.find(item => item.id === assertion.source_version_id);
    return {...common, assertion_id: assertion.id, finding_key: assertion.finding_key, reported_state: assertion.certainty,
      source_statement: assertion.quote, source_line: assertion.source_line, source_version_id: source.id,
      source_sha256: source.sha256, document_id: source.document_id, document_version: source.version,
      source_kind: source.kind, review_state: 'not_established', clinical_meaning: null};
  });
  const model = {contract: 'oi.synthetic-world-model/1', synthetic: true, case_id: caseId,
    scope: 'fictional_case_only_not_a_verified_patient', authority: 'source_report_only_unreviewed', clinical_interpretation: 'not_generated',
    as_of_ledger: {event_id: 8, recorded_at: '2026-01-13T10:00:00Z'},
    summary: {current_sources: 2, superseded_sources: 1, current_observations: 7, unresolved_observations: 5, source_disagreements: 1},
    current_sources: sources.slice(1).map(sourceView), history: [sourceView(sources[0])], observations,
    unresolved: observations.slice(2), conflicts: [{specimen_id: 'SYNTH-SAMPLE', event_date: '2026-01-10', finding_key: 'Marker A',
      status: 'unresolved_source_disagreement', reported_states: ['negative', 'reported'], clinical_interpretation: 'not_performed',
      observation_refs: [{assertion_id: 10, source_version_id: 2, source_line: 5}, {assertion_id: 11, source_version_id: 3, source_line: 6}]}],
    review_needed: {open_question_ids: [20], draft_snapshot_ids: [31], stale_snapshot_ids: [30]}, limitations: []};
  return {state, model};
}
function harness() {
  const document = {createElement: tag => new Element(tag, document)};
  const elements = Object.fromEntries(['root', 'status', 'timeline', 'findings', 'questions', 'uncertainty'].map(name => [name, document.createElement('div')]));
  const requests = [], sourceCalls = [], questionCalls = [], refreshes = [];
  const ctx = vm.createContext({document}); vm.runInContext(code, ctx);
  assert.equal(typeof ctx.OpenIntelligencePatientRecord?.create, 'function', 'patient-record component must expose create');
  const component = ctx.OpenIntelligencePatientRecord.create({elements,
    fetchModel: caseId => new Promise((resolve, reject) => requests.push({caseId, resolve, reject})),
    onOpenSource: (...args) => sourceCalls.push(args), onOpenQuestion: id => questionCalls.push(id), onRefresh: () => refreshes.push(true)});
  return {elements, requests, sourceCalls, questionCalls, refreshes, component};
}
async function render(h, input = fixture()) {
  const pending = h.component.load(input.state);
  h.requests.at(-1).resolve(input.model);
  assert.equal(await pending, true);
  return input;
}
const allText = h => Object.values(h.elements).map(node => node.textContent).join(' ');
const buttons = h => Object.values(h.elements).flatMap(element => nodes(element, 'button'));

test('source findings retain distinct uncertainty states, exact anchors and inspectable history', async () => {
  const h = harness(); await render(h);
  assert.equal(h.requests[0].caseId, 'FICTION-A');
  for (const label of ['Reported', 'Negative', 'Pending', 'Indeterminate', 'Not reported', 'Not assessed', 'Conflicting'])
    assert.ok(nodes(h.elements.findings, 'span').some(node => node.textContent === label), label);
  nodes(h.elements.findings, 'button')[0].click();
  assert.deepEqual(h.sourceCalls, [[2, 5]]);
  const history = nodes(h.elements.timeline, 'details')[0];
  assert.match(history.textContent, /SYNTH-PATH/);
  nodes(history, 'button')[0].click();
  assert.deepEqual(h.sourceCalls[1], [1, null]);
  assert.match(h.elements.uncertainty.textContent, /SYNTH-SAMPLE/);
  assert.match(h.elements.uncertainty.textContent, /disagree/i);
  assert.match(h.elements.uncertainty.textContent, /not resolved/i);
  nodes(h.elements.questions, 'button')[0].click();
  assert.deepEqual(h.questionCalls, [20]);
  assert.equal(nodes(h.elements.questions, 'button').length, 1);
  assert.equal(nodes(h.elements.questions, 'a')[0].href, '#investigations');
  assert.match(h.elements.questions.textContent, /1.*draft/i);
  assert.match(h.elements.questions.textContent, /1.*reassessment/i);
});

for (const [name, change] of [
  ['case', model => { model.case_id = 'OTHER'; }],
  ['contract', model => { model.contract = 'unknown'; }],
  ['synthetic flag', model => { model.synthetic = false; }],
  ['scope', model => { model.scope = 'verified_patient'; }],
  ['cutoff', model => { model.as_of_ledger.event_id = 7; }],
  ['source membership', model => { model.current_sources[0].source_version_id = 999; }],
  ['source integrity', model => { model.current_sources[0].source_sha256 = 'd'.repeat(64); }],
  ['omitted source', model => { model.history = []; }],
  ['observation source', model => { model.observations[0].source_version_id = 999; }],
  ['observation anchor', model => { model.observations[0].source_line = 99; }],
  ['observation statement', model => { model.observations[0].source_statement = 'Unsupported claim'; }],
  ['question membership', model => { model.review_needed.open_question_ids = [999]; }],
  ['conflict membership', model => { model.conflicts[0].observation_refs[0].source_version_id = 999; }],
]) {
  test(`mismatched ${name} clears old state and all source/question actions before retry`, async () => {
    const h = harness(); await render(h);
    const old = nodes(h.elements.findings, 'button')[0];
    const input = fixture(); change(input.model);
    const pending = h.component.load(input.state);
    assert.equal(h.elements.findings.textContent, '');
    h.requests.at(-1).resolve(input.model);
    assert.equal(await pending, false);
    old.click(); assert.equal(h.sourceCalls.length, 0);
    assert.equal(h.elements.questions.textContent, '');
    assert.match(h.elements.status.textContent, /refresh|load/i);
    assert.equal(buttons(h).length, 1);
    buttons(h)[0].click(); assert.equal(h.refreshes.length, 1);
  });
}

test('A to B to A and same-case reload cannot revive an older response', async () => {
  const h = harness();
  const a1 = fixture('FICTION-A', 'obsolete A'), b = fixture('FICTION-B', 'obsolete B');
  const a2 = fixture('FICTION-A', 'current A'), a3 = fixture('FICTION-A', 'latest A');
  const first = h.component.load(a1.state), second = h.component.load(b.state), third = h.component.load(a2.state);
  h.requests[2].resolve(a2.model); assert.equal(await third, true);
  h.requests[0].resolve(a1.model); h.requests[1].resolve(b.model);
  assert.equal(await first, false); assert.equal(await second, false);
  assert.match(allText(h), /current A/); assert.doesNotMatch(allText(h), /obsolete/);
  const fourth = h.component.load(a2.state), fifth = h.component.load(a3.state);
  h.requests[4].resolve(a3.model); await fifth;
  h.requests[3].resolve(a2.model); await fourth;
  assert.match(allText(h), /latest A/); assert.doesNotMatch(allText(h), /current A/);
});

test('clear invalidates in-flight loads and detached source, question and retry actions', async () => {
  const h = harness(); await render(h);
  const source = nodes(h.elements.findings, 'button')[0], question = nodes(h.elements.questions, 'button')[0];
  const next = fixture(), pending = h.component.load(next.state);
  h.component.clear('Choose a case.'); h.requests.at(-1).resolve(next.model);
  assert.equal(await pending, false); source.click(); question.click();
  assert.equal(h.sourceCalls.length, 0); assert.equal(h.questionCalls.length, 0);
  assert.equal(h.elements.status.textContent, 'Choose a case.');
  assert.equal(buttons(h).length, 0);
  const failed = h.component.load(next.state); h.requests.at(-1).reject(Error('unavailable')); await failed;
  const retry = buttons(h)[0]; h.component.clear(); retry.click();
  assert.equal(h.refreshes.length, 0);
});

test('a failed current fetch clears prior content, but a stale failure cannot replace newer content', async () => {
  const h = harness(); await render(h);
  const input = fixture(), failed = h.component.load(input.state);
  h.requests.at(-1).reject(Error('<sensitive server error>')); assert.equal(await failed, false);
  assert.doesNotMatch(allText(h), /Authored record|sensitive server error/);
  assert.equal(h.elements.root.attributes['aria-busy'], 'false');
  assert.equal(h.elements.status.attributes['aria-live'], 'polite');
  const older = h.component.load(input.state), newer = h.component.load(input.state);
  h.requests.at(-1).resolve(input.model); await newer;
  h.requests.at(-2).reject(Error('late')); await older;
  assert.match(allText(h), /Authored record/); assert.equal(buttons(h).filter(button => /retry/i.test(button.textContent)).length, 0);
});

test('source text is literal and an empty record does not invent observations or review actions', async () => {
  const h = harness(); await render(h, fixture('FICTION-A', '<script>not markup</script>'));
  assert.match(h.elements.findings.textContent, /<script>not markup<\/script>/);
  assert.equal(nodes(h.elements.findings, 'script').length, 0);
  const input = fixture();
  for (const key of ['sources', 'assertions', 'questions', 'snapshots', 'events']) input.state[key] = [];
  for (const key of ['current_sources', 'history', 'observations', 'unresolved', 'conflicts']) input.model[key] = [];
  input.model.as_of_ledger = {event_id: null, recorded_at: null};
  input.model.summary = {current_sources: 0, superseded_sources: 0, current_observations: 0, unresolved_observations: 0, source_disagreements: 0};
  input.model.review_needed = {open_question_ids: [], draft_snapshot_ids: [], stale_snapshot_ids: []};
  await render(h, input);
  assert.match(h.elements.findings.textContent, /no.*findings/i);
  assert.match(h.elements.timeline.textContent, /no.*records/i);
  assert.equal(buttons(h).length, 0);
});

test('acknowledged replacement retains stale history without claiming another review is pending', async () => {
  const h = harness(), input = fixture();
  input.state.questions[0].state = 'addressed';
  input.state.snapshots[1].state = 'reviewed_in_demo';
  input.model.review_needed.open_question_ids = [];
  input.model.review_needed.draft_snapshot_ids = [];
  await render(h, input);
  assert.match(h.elements.questions.textContent, /0 earlier reports need reassessment/);
  assert.match(h.elements.questions.textContent, /1 historical stale version/);
  assert.equal(nodes(h.elements.questions, 'button').length, 0);
  assert.equal(nodes(h.elements.questions, 'a')[0].href, '#investigations');
});

function manualFixture(pdf = true) {
  const input = fixture();
  const provenance = {
    classification_origin: 'user_selected',
    annotation_method: pdf ? 'manual-exact-extraction-line-selection' : 'manual-exact-line-selection',
    clinical_review: 'not_performed', transcription_review_sha256: 'd'.repeat(64),
    ...(pdf ? {text_origin: 'pdf_extraction', extraction_sha256: 'e'.repeat(64)} : {}),
  };
  const receipt = {
    filename: pdf ? 'fictional-report.pdf' : 'fictional-report.txt',
    media_type: pdf ? 'application/pdf' : 'text/plain; charset=utf-8',
    extraction_method: pdf ? 'pypdf-text-v1' : 'utf8-plain-text-v1',
    annotation_method: provenance.annotation_method, manual_transcription_confirmed: true,
    clinical_review: 'not_performed', review_sha256: 'd'.repeat(64),
    ...(pdf ? {extraction_sha256: 'e'.repeat(64)} : {}),
  };
  for (const source of input.state.sources.filter(row => row.id !== 3))
    Object.assign(source, provenance, {document_intake: structuredClone(receipt)});
  for (const source of [...input.model.current_sources, ...input.model.history].filter(row => row.source_version_id !== 3))
    Object.assign(source, provenance, {document_intake: structuredClone(receipt)});
  for (const assertion of input.state.assertions.filter(row => row.source_version_id === 2)) {
    const anchor = pdf ? {source_page: 2, page_line: assertion.source_line - 4, page_text_sha256: 'f'.repeat(64)} : {};
    Object.assign(assertion, provenance, anchor);
    Object.assign(input.model.observations.find(row => row.assertion_id === assertion.id), provenance, anchor);
  }
  for (const conflict of input.model.conflicts) for (const ref of conflict.observation_refs) {
    const observation = input.model.observations.find(row => row.assertion_id === ref.assertion_id);
    if (observation.classification_origin) {
      Object.assign(ref, provenance, {source_sha256: observation.source_sha256},
        pdf ? {source_page: observation.source_page, page_line: observation.page_line, page_text_sha256: 'f'.repeat(64)} : {});
    }
  }
  return input;
}

test('PDF selections keep manual status, physical page anchors and the original source action', async () => {
  const h = harness(); await render(h, manualFixture());
  const card = nodes(h.elements.findings, 'article')[0];
  assert.match(card.textContent, /User-selected status: Reported/);
  assert.match(card.textContent, /Clinical review not performed/);
  assert.match(card.textContent, /page 2.*extraction line 5/i);
  const action = nodes(card, 'button')[0];
  assert.equal(action.attributes['data-source-id'], '2');
  assert.equal(action.attributes['data-source-line'], '5');
  assert.equal(action.attributes['data-source-page'], '2');
  action.click(); assert.deepEqual(h.sourceCalls, [[2, 5]]);
  assert.match(h.elements.timeline.textContent, /PDF.*manually selected/i);
  assert.match(h.elements.uncertainty.textContent, /selected statuses differ/i);
  assert.doesNotMatch(h.elements.uncertainty.textContent, /Sources disagree:/);
  const conflict = nodes(h.elements.uncertainty, 'article').find(item => /selected statuses differ/i.test(item.textContent));
  assert.match(conflict.textContent, /Clinical review not performed/);
  nodes(nodes(h.elements.timeline, 'details')[0], 'button')[0].click();
  assert.deepEqual(h.sourceCalls[1], [1, null]);
  const authored = nodes(h.elements.findings, 'article')[1];
  assert.doesNotMatch(authored.textContent, /User-selected status/);
});

test('ordinary text manual selections stay distinct without inventing PDF page references', async () => {
  const h = harness(); await render(h, manualFixture(false));
  const card = nodes(h.elements.findings, 'article')[0];
  assert.match(card.textContent, /User-selected status: Reported/);
  assert.match(card.textContent, /Clinical review not performed/);
  assert.doesNotMatch(card.textContent, /page|extraction line/i);
  nodes(card, 'button')[0].click(); assert.deepEqual(h.sourceCalls, [[2, 5]]);
});

for (const [name, change] of [
  ['source manual origin omitted', m => { delete m.current_sources[0].classification_origin; }],
  ['source original receipt omitted', m => { delete m.current_sources[0].document_intake; }],
  ['source original receipt forged', m => { m.current_sources[0].document_intake.review_sha256 = '0'.repeat(64); }],
  ['source extraction digest changed', m => { m.current_sources[0].extraction_sha256 = '0'.repeat(64); }],
  ['historical source downgraded', m => { delete m.history[0].clinical_review; }],
  ['authored source given invented manual origin', m => { m.current_sources[1].classification_origin = 'user_selected'; }],
  ['observation origin omitted', m => { delete m.observations[0].classification_origin; }],
  ['observation method changed', m => { m.observations[0].annotation_method = 'automatic'; }],
  ['observation review falsely approved', m => { m.observations[0].clinical_review = 'approved'; }],
  ['observation original receipt changed', m => { m.observations[0].transcription_review_sha256 = '0'.repeat(64); }],
  ['observation PDF origin downgraded', m => { m.observations[0].text_origin = 'original'; }],
  ['observation extraction digest omitted', m => { delete m.observations[0].extraction_sha256; }],
  ['observation page omitted', m => { delete m.observations[0].source_page; }],
  ['observation page changed', m => { m.observations[0].source_page = 1; }],
  ['observation page line changed', m => { m.observations[0].page_line = 99; }],
  ['observation page digest changed', m => { m.observations[0].page_text_sha256 = '0'.repeat(64); }],
  ['authored observation given invented PDF anchor', m => { m.observations[1].source_page = 9; }],
  ['unresolved payload downgraded', m => { m.unresolved = structuredClone(m.unresolved); delete m.unresolved[0].classification_origin; }],
  ['unresolved page forged', m => { m.unresolved = structuredClone(m.unresolved); m.unresolved[0].source_page = 1; }],
  ['conflict provenance omitted', m => { delete m.conflicts[0].observation_refs[0].annotation_method; }],
  ['conflict original digest changed', m => { m.conflicts[0].observation_refs[0].source_sha256 = '0'.repeat(64); }],
  ['conflict page line changed', m => { m.conflicts[0].observation_refs[0].page_line = 88; }],
]) {
  test(`manual/PDF ${name} clears all actions instead of downgrading provenance`, async () => {
    const h = harness(); await render(h);
    const oldSource = nodes(h.elements.findings, 'button')[0], oldQuestion = nodes(h.elements.questions, 'button')[0];
    const input = manualFixture(); change(input.model);
    const pending = h.component.load(input.state); h.requests.at(-1).resolve(input.model);
    assert.equal(await pending, false);
    oldSource.click(); oldQuestion.click();
    assert.equal(h.sourceCalls.length, 0); assert.equal(h.questionCalls.length, 0);
    assert.equal(h.elements.findings.textContent, '');
    assert.equal(h.elements.questions.textContent, '');
    assert.equal(h.elements.root.dataset.state, 'unavailable');
    assert.equal(buttons(h).length, 1);
  });
}

test('partial manual provenance in the case snapshot is rejected even if copied by the response', async () => {
  const h = harness(), input = manualFixture();
  delete input.state.assertions[0].page_text_sha256;
  delete input.model.observations[0].page_text_sha256;
  const pending = h.component.load(input.state); h.requests.at(-1).resolve(input.model);
  assert.equal(await pending, false);
  assert.equal(h.elements.root.dataset.state, 'unavailable');
});

test('omitting a known same-specimen disagreement cannot produce an all-clear uncertainty view', async () => {
  const h = harness(), input = fixture();
  input.state.assertions = input.state.assertions.slice(0, 2);
  input.model.observations = input.model.observations.slice(0, 2);
  input.model.unresolved = [];
  input.model.conflicts = [];
  input.model.summary.source_disagreements = 0;
  const pending = h.component.load(input.state); h.requests.at(-1).resolve(input.model);
  assert.equal(await pending, false);
  assert.equal(h.elements.root.dataset.state, 'unavailable');
  assert.doesNotMatch(h.elements.uncertainty.textContent, /No unresolved source findings/);
  assert.equal(h.elements.findings.textContent, '');
});

test('duplicating one disagreement cannot stand in for a different omitted conflict group', async () => {
  const h = harness(), input = fixture();
  for (let i = 0; i < 2; i++) {
    input.state.assertions.push({...input.state.assertions[i], id: 90 + i, finding_key: 'Marker B', source_line: 20 + i});
    input.model.observations.push({...input.model.observations[i], assertion_id: 90 + i, finding_key: 'Marker B', source_line: 20 + i});
  }
  input.model.conflicts.push(structuredClone(input.model.conflicts[0]));
  input.model.summary.source_disagreements = 2;
  const pending = h.component.load(input.state); h.requests.at(-1).resolve(input.model);
  assert.equal(await pending, false);
  assert.equal(h.elements.root.dataset.state, 'unavailable');
  assert.equal(h.elements.findings.textContent, '');
});

function questionHandoff() {
  const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
  const start = app.indexOf('function focusPatientQuestion('), end = app.indexOf('async function refresh()', start);
  assert.ok(start >= 0 && end > start, 'The patient view needs a connected question handoff');
  const ids = ['question-choice', 'evidence-question-choice', 'model-investigation-question'];
  const elements = Object.fromEntries([...ids, 'draft-observations', 'draft-summary', 'draft-assumptions', 'evidence-rationale'].map(id => [id,
    {value: ids.includes(id) ? '20' : '', options: [{value: '20'}, {value: '22'}], changes: [],
      dispatchEvent(event) { this.changes.push({type: event.type, value: this.value}); }, focus() { this.focused = true; }}]));
  const messages = [], window = {location: {hash: ''}};
  const ctx = vm.createContext({active: {questions: [{id: 20, state: 'open'}, {id: 22, state: 'open'}]},
    readyCase: () => 'FICTION-A', el: id => elements[id], window,
    Event: class {constructor(type) {this.type = type;}}, notice: (message, error) => messages.push({message, error})});
  vm.runInContext(app.slice(start, end), ctx);
  return {elements, messages, window, open: id => ctx.focusPatientQuestion(id)};
}

test('patient question handoff selects one durable question and refreshes Composer context', () => {
  const h = questionHandoff(); h.open(22);
  for (const id of ['question-choice', 'evidence-question-choice', 'model-investigation-question'])
    assert.equal(h.elements[id].value, '22');
  assert.deepEqual(h.elements['model-investigation-question'].changes, [{type: 'change', value: '22'}]);
  assert.equal(h.window.location.hash, 'investigations');
  assert.equal(h.elements['model-investigation-question'].focused, true);
});

test('patient question handoff cannot move an unfinished report to another question', () => {
  const h = questionHandoff(); h.elements['draft-summary'].value = 'Independent fictional draft in progress';
  h.open(22);
  for (const id of ['question-choice', 'evidence-question-choice', 'model-investigation-question'])
    assert.equal(h.elements[id].value, '20');
  assert.equal(h.elements['model-investigation-question'].changes.length, 0);
  assert.equal(h.messages.at(-1).error, true);
  assert.equal(h.window.location.hash, '');
});

test('host refresh refuses a misbound case snapshot before rendering or fetching its projection', async () => {
  const h = harness(), wrong = fixture('FICTION-B');
  const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
  const start = app.indexOf('async function refresh()'), end = app.indexOf('function readyCase()', start);
  assert.ok(start >= 0 && end > start);
  const document = h.elements.root.ownerDocument;
  const hostElements = {'case-heading': document.createElement('h2'), 'model-investigation-list': document.createElement('div')};
  const requests = [], rendered = [], notices = [];
  const ctx = vm.createContext({caseId: 'FICTION-A', active: fixture().state, refreshSequence: 0,
    patientRecord: h.component, api: route => new Promise(resolve => requests.push({route, resolve})),
    clear: id => hostElements[id].replaceChildren(), el: id => hostElements[id],
    empty: (target, message) => {target.textContent = message;},
    render: () => rendered.push(ctx.active.case.case_id), notice: message => notices.push(message)});
  vm.runInContext(app.slice(start, end), ctx);
  const pending = ctx.refresh();
  assert.equal(h.elements.root.dataset.state, 'loading');
  assert.equal(requests[0].route, '/api/cases/FICTION-A/state');
  requests[0].resolve(wrong.state);
  await new Promise(setImmediate);
  // Let the old, unguarded implementation finish rather than hanging the test.
  for (const request of h.requests) request.resolve(wrong.model);
  await pending;
  assert.deepEqual(rendered, []);
  assert.equal(h.requests.length, 0, 'A wrong-case world-model endpoint was fetched');
  assert.equal(ctx.active, null);
  assert.equal(h.elements.root.dataset.state, 'unavailable');
  assert.equal(h.elements.findings.textContent, '');
  assert.equal(h.elements.questions.textContent, '');
  assert.ok(notices.some(message => /selected case|match/i.test(message)));
});
