'use strict';
// Focused node:test checks for the A11Y-002 dialog focus return and the
// A11Y-031 per-field error association in the actual web/app.js. They slice the
// marked implementation blocks into a vm sandbox with minimal DOM fakes, the
// same convention as test_source_dialogs.js; no third-party packages.
// A11Y-004 is intentionally NOT covered here: the Tab reroute is kept under a
// recorded decision (see the comment above focusOverviewFromCasePicker in
// web/app.js), and tests/browser_journey.py already pins its behavior.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');

class FakeElement {
  constructor() {this.listeners = {}; this.open = false; this.isConnected = true; this.focusCount = 0;}
  addEventListener(type, fn) {(this.listeners[type] = this.listeners[type] || []).push(fn);}
  showModal() {this.open = true;}
  close() {this.open = false; for (const fn of this.listeners.close || []) fn();}
  focus() {this.focusCount++;}
}
class FakeHTMLElement extends FakeElement {}

function loadDialogFocus() {
  const start = app.indexOf('function showSourceView(dialogId) {');
  const endMarker = '// End dialog focus return (A11Y-002).';
  const end = app.indexOf(endMarker);
  assert.ok(start >= 0 && end > start, 'dialog focus-return block is not implemented in app.js');
  const dialogs = new Map([
    ['source-dialog', new FakeElement()],
    ['compare-dialog', new FakeElement()],
  ]);
  const opener = new FakeHTMLElement();
  const sandbox = {
    el: id => dialogs.get(id),
    document: {activeElement: opener},
    HTMLElement: FakeHTMLElement,
  };
  vm.createContext(sandbox);
  vm.runInContext(app.slice(start, end + endMarker.length), sandbox);
  sandbox.watchDialogFocusReturn();
  return {sandbox, dialogs, opener};
}

test('closing the source dialog returns focus to its opener', () => {
  const h = loadDialogFocus();
  h.sandbox.showSourceView('source-dialog');
  assert.equal(h.dialogs.get('source-dialog').open, true);
  h.dialogs.get('source-dialog').close();
  assert.equal(h.opener.focusCount, 1);
});

test('closing the compare dialog returns focus to its opener', () => {
  const h = loadDialogFocus();
  h.sandbox.showSourceView('compare-dialog');
  assert.equal(h.dialogs.get('compare-dialog').open, true);
  h.dialogs.get('compare-dialog').close();
  assert.equal(h.opener.focusCount, 1);
});

test('the opener is captured when the dialog opens, not earlier', () => {
  const h = loadDialogFocus();
  const first = h.opener;
  const second = new FakeHTMLElement();
  h.sandbox.document.activeElement = second;
  h.sandbox.showSourceView('source-dialog');
  h.dialogs.get('source-dialog').close();
  assert.equal(first.focusCount, 0);
  assert.equal(second.focusCount, 1);
});

test('a detached or unfocusable opener is skipped without throwing', () => {
  const h = loadDialogFocus();
  h.opener.isConnected = false;
  h.sandbox.showSourceView('source-dialog');
  h.dialogs.get('source-dialog').close();
  assert.equal(h.opener.focusCount, 0);
  const h2 = loadDialogFocus();
  h2.opener.focus = null;
  h2.sandbox.showSourceView('compare-dialog');
  h2.dialogs.get('compare-dialog').close();
  assert.equal(h2.opener.focusCount, 0);
});

test('case-switch close closes dialogs without stealing focus', () => {
  const h = loadDialogFocus();
  h.sandbox.showSourceView('source-dialog');
  h.sandbox.closeSourceViewsWithoutFocusReturn();
  assert.equal(h.dialogs.get('source-dialog').open, false);
  assert.equal(h.opener.focusCount, 0);
  // The next normal open/close cycle still restores focus.
  h.sandbox.showSourceView('source-dialog');
  h.dialogs.get('source-dialog').close();
  assert.equal(h.opener.focusCount, 1);
});

test('dialog focus return is wired into the app (not only defined)', () => {
  assert.ok(app.includes('watchDialogFocusReturn();'),
    'watchDialogFocusReturn() is never called in app.js');
  assert.ok(app.includes('closeSourceViewsWithoutFocusReturn();'),
    'closeSourceViewsWithoutFocusReturn() is never called in app.js');
});

class FieldElement {
  constructor(id) {this.id = id; this.attrs = {}; this.textContent = ''; this.hidden = false;}
  setAttribute(key, value) {this.attrs[key] = String(value);}
  getAttribute(key) {return this.attrs[key] === undefined ? null : this.attrs[key];}
  removeAttribute(key) {delete this.attrs[key];}
}

function loadFieldErrors() {
  const startMarker = '// Begin per-field error association (A11Y-031).';
  const endMarker = '// End per-field error association (A11Y-031).';
  const start = app.indexOf(startMarker);
  const end = app.indexOf(endMarker);
  assert.ok(start >= 0 && end > start, 'per-field error helpers are not implemented in app.js');
  const nodes = new Map([
    ['demo-field', new FieldElement('demo-field')],
    ['demo-field-error', new FieldElement('demo-field-error')],
  ]);
  nodes.get('demo-field-error').hidden = true;
  const sandbox = {el: id => nodes.get(id)};
  vm.createContext(sandbox);
  vm.runInContext(app.slice(start, end + endMarker.length), sandbox);
  return {sandbox, nodes};
}

test('setFieldError exposes the message and describes the field by it', () => {
  const h = loadFieldErrors();
  h.sandbox.setFieldError('demo-field', 'Add reported observations before saving.');
  const field = h.nodes.get('demo-field');
  const error = h.nodes.get('demo-field-error');
  assert.equal(error.textContent, 'Add reported observations before saving.');
  assert.equal(error.hidden, false);
  assert.equal(field.getAttribute('aria-invalid'), 'true');
  assert.equal(field.getAttribute('aria-describedby'), 'demo-field-error');
});

test('clearFieldError hides the message and removes the association', () => {
  const h = loadFieldErrors();
  h.sandbox.setFieldError('demo-field', 'Add reported observations before saving.');
  h.sandbox.clearFieldError('demo-field');
  const field = h.nodes.get('demo-field');
  const error = h.nodes.get('demo-field-error');
  assert.equal(error.textContent, '');
  assert.equal(error.hidden, true);
  assert.equal(field.getAttribute('aria-invalid'), null);
  assert.equal(field.getAttribute('aria-describedby'), null);
});

test('field-error helpers tolerate a field with no error element', () => {
  const h = loadFieldErrors();
  assert.doesNotThrow(() => {
    h.sandbox.setFieldError('missing-field', 'message');
    h.sandbox.clearFieldError('missing-field');
  });
});

test('draft observations field owns a per-field error element in the page', () => {
  assert.ok(html.includes('id="draft-observations-error"'),
    'index.html lacks the draft-observations-error element');
  assert.ok(html.includes('class="field-error"'),
    'index.html lacks the field-error styling hook');
  assert.ok(app.includes("setFieldError('draft-observations'"),
    'draft submit never sets the per-field error in app.js');
  assert.ok(app.includes("clearFieldError('draft-observations')"),
    'draft submit never clears the per-field error in app.js');
});
