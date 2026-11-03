'use strict';
// Route decisions from the real shell; DOM retention and interactions are
// exercised separately by workspace_navigation_browser_journey.py.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const start = source.indexOf('/* Workspace navigation shell');
const context = vm.createContext({});
if (start >= 0) vm.runInContext(source.slice(start), context);
function route(hash, audience = 'clinician') {
  assert.equal(typeof context.workspaceRoute, 'function', 'The connected navigation shell must resolve destinations');
  return JSON.parse(JSON.stringify(context.workspaceRoute(hash, audience)));
}
test('patient and clinician open distinct landing pages', () => {
  assert.equal(route('', 'patient').page, 'home');
  assert.equal(route('', 'clinician').page, 'workspace');
});
test('the patient chart is distinct from the global patient directory', () => {
  assert.equal(route('#incoming-board').page, 'patients');
  assert.equal(route('#overview').page, 'overview');
  assert.equal(route('#assertions').page, 'overview');
});
test('legacy patient reading anchors remain accessible in the patient experience', () => {
  assert.equal(route('#patient-view').page, 'records');
  assert.equal(route('#patient-view').audience, 'patient');
  for (const hash of ['#patient-mission', '#world-model-detail']) {
    assert.equal(route(hash, 'patient').page, 'records');
    assert.equal(route(hash, 'patient').audience, 'patient');
    assert.equal(route(hash, 'clinician').page, 'overview');
    assert.equal(route(hash, 'clinician').audience, 'clinician');
  }
});
test('source intake, history and pasted import resolve to the same document destination', () => {
  for (const hash of ['#sources', '#source-intake', '#import', '#biological-assets'])
    assert.equal(route(hash).page, 'documents');
});
test('late saved-report fragments reveal the correct report history for each preview', () => {
  assert.equal(route('#snapshot-37', 'patient').page, 'questions');
  assert.equal(route('#snapshot-37', 'clinician').page, 'investigations');
  assert.equal(route('#snapshot-37').anchor, 'snapshot-37');
});
test('research discovery stays separate from case-linked evidence assessment', () => {
  assert.equal(route('#bibliography').page, 'research');
  assert.equal(route('#evidence').page, 'evidence');
});
test('update and setup legacy links remain reachable', () => {
  assert.equal(route('#changes-since-review').page, 'updates');
  assert.equal(route('#activity').page, 'updates');
  assert.equal(route('#workspace-start').page, 'setup');
  assert.equal(route('#new-case-panel').page, 'setup');
});
test('a direct clinical-authoring link clearly selects the clinician preview', () => {
  const result = route('#model-investigation-heading', 'patient');
  assert.equal(result.page, 'investigations');
  assert.equal(result.audience, 'clinician');
});
test('unknown or malformed fragments fall back without interpreting markup', () => {
  for (const hash of ['#missing', '#%ZZ', '#<script>', '#snapshot-nope', '#__proto__']) {
    assert.equal(route(hash, 'patient').page, 'home');
    assert.equal(route(hash, 'clinician').page, 'workspace');
  }
});
