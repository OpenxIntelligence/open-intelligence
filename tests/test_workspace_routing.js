'use strict';
// Navigation contracts: legacy/deep links must reveal their real workspace.
// The DOM integration journey separately proves controls retain their state.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const start = app.indexOf('// Begin workspace navigation model.');
const end = app.indexOf('// End workspace navigation model.', start);
const context = vm.createContext({});
if (start >= 0 && end > start) vm.runInContext(app.slice(start, end), context);
function route(hash, audience) {
  assert.equal(typeof context.resolveWorkspaceRoute, 'function', 'Workspace navigation has not been implemented');
  return context.resolveWorkspaceRoute(hash, audience);
}

test('clinician entry opens the case worklist and patient entry opens personal home', () => {
  assert.equal(route('', 'clinician').id, 'incoming-board');
  assert.equal(route('', 'patient').id, 'patient-home');
});
test('generated report links reveal saved reports and retain the exact target', () => {
  const result = route('#snapshot-27', 'patient');
  assert.equal(result.id, 'reports');
  assert.equal(result.target, 'snapshot-27');
  assert.equal(result.audience, 'patient');
});
test('source provenance deep link reveals its parent workspace', () => {
  const result = route('#world-model-detail', 'clinician');
  assert.equal(result.id, 'patient-mission');
  assert.equal(result.target, 'world-model-detail');
  assert.equal(result.group, 'record');
});
test('professional authoring is explicitly a clinical presentation', () => {
  for (const hash of ['#investigations', '#model-investigation-heading', '#evidence', '#options']) {
    const result = route(hash, 'patient');
    assert.equal(result.audience, 'clinician', hash);
    assert.equal(result.scope, 'case', hash);
  }
});
test('all original sidebar destinations and omitted biological assets remain routable', () => {
  const ids = ['overview', 'incoming-board', 'patient-view', 'patient-mission', 'assertions',
    'timeline', 'investigations', 'sources', 'evidence', 'bibliography', 'import',
    'activity', 'changes-since-review', 'options', 'biological-assets', 'source-intake', 'workspace-start'];
  for (const id of ids) assert.equal(route('#' + id, 'clinician').id, id);
});
test('shared record and export destinations retain the current presentation', () => {
  for (const id of ['sources', 'timeline', 'assertions', 'questions', 'reports', 'changes-since-review']) {
    assert.equal(route('#' + id, 'patient').audience, 'patient');
    assert.equal(route('#' + id, 'clinician').audience, 'clinician');
  }
});
test('application destinations do not masquerade as sections of a patient chart', () => {
  for (const id of ['incoming-board', 'bibliography', 'workspace-start'])
    assert.equal(route('#' + id, 'clinician').scope, 'global');
  assert.equal(route('#sources', 'clinician').scope, 'case');
});
test('invalid and unknown targets recover to an accessible entry view', () => {
  for (const hash of ['#does-not-exist', '#snapshot-0', '#snapshot-abc', '#<script>', '#snapshot-27/other', '#__proto__', '#constructor']) {
    assert.equal(route(hash, 'patient').id, 'patient-home');
    assert.equal(route(hash, 'clinician').id, 'incoming-board');
  }
});
test('unknown audience never creates an authenticated or privileged role', () => {
  const result = route('#sources', 'administrator');
  assert.equal(result.audience, 'clinician');
  assert.equal(Object.hasOwn(result, 'permissions'), false);
  assert.equal(Object.hasOwn(result, 'authorization'), false);
});
