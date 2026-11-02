'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');

function load() {
  const start = app.indexOf('// Begin source text comparison.');
  const end = app.indexOf('// End source text comparison.');
  assert.ok(start >= 0 && end > start, 'bounded source-line comparison is not implemented');
  class TextNode {
    constructor(text = '') { this.textContent = String(text); }
  }
  class Element {
    constructor(tag = 'div') { this.tagName = tag; this.children = []; this.dataset = {}; }
    append(...items) { this.children.push(...items); }
    replaceChildren(...items) { this.children = items; }
    set textContent(text) { this.children = [new TextNode(text)]; }
    get textContent() { return this.children.map(x => x.textContent).join(''); }
  }
  const elements = new Map(['compare-before', 'compare-after', 'compare-context'].map(id => [id, new Element()]));
  const sandbox = {document: {createTextNode: text => new TextNode(text)},
    el: id => elements.get(id), node: (tag, text, className) => {
      const element = new Element(tag); element.textContent = text; element.className = className; return element;
    }};
  vm.createContext(sandbox);
  vm.runInContext(app.slice(start, end), sandbox);
  return {compare: (a, b) => JSON.parse(JSON.stringify(sandbox.compareReportLines(a, b))),
    render: (a, b) => sandbox.renderReportLineComparison(a, b), elements};
}

function check(a, b, oldLines, newLines, status = 'compared') {
  const result = load().compare(a, b);
  assert.equal(result.status, status);
  assert.deepEqual(result.beforeLines, oldLines);
  assert.deepEqual(result.afterLines, newLines);
}

test('identical text is not described as a clinical conclusion', () => {
  check('Marker: not tested\n', 'Marker: not tested\n', [], [], 'identical');
  const h = load(); h.render('same\n', 'same\n');
  assert.match(h.elements.get('compare-context').textContent, /clinical/i);
});
test('inserting one line does not mark the shifted matching lines', () => {
  check('A\nC\n', 'A\nB\nC\n', [], [2]);
});
test('a deletion retains the original one-based source line', () => {
  check('A\nB\nC\n', 'A\nC\n', [2], []);
});
test('changed missingness wording is a text replacement only', () => {
  check('Marker: not tested\n', 'Marker: negative\n', [1], [1]);
});
test('repeated lines align deterministically without changing counts', () => {
  check('A\nA\nB\n', 'A\nB\n', [2], []);
  const h = load(); assert.deepEqual(h.compare('A\nB\nA\n', 'A\nA\nB\n'), h.compare('A\nB\nA\n', 'A\nA\nB\n'));
});
test('whitespace-only edits are not normalized away', () => {
  check('A \n', 'A\n', [1], [1]);
});
test('CRLF and LF are distinct exact source characters', () => {
  check('A\r\nB\r\n', 'A\nB\n', [1, 2], [1, 2]);
});
test('a changed final newline is visible rather than silently equal', () => {
  check('A\n', 'A', [1], [1]);
});
test('blank lines and empty documents retain honest counts', () => {
  check('', '', [], [], 'identical'); check('', '\n', [], [1]);
  check('A\n\nB\n', 'A\nB\n', [2], []);
});
test('Unicode and markup-like content survive rendering exactly as inert text', () => {
  const h = load(), a = 'α 🧬\n<script>bad()</script>\n', b = 'α 🧬\n<img src=x onerror=bad()>\n';
  h.render(a, b);
  assert.equal(h.elements.get('compare-before').textContent, a);
  assert.equal(h.elements.get('compare-after').textContent, b);
  assert.deepEqual(h.elements.get('compare-before').children.filter(x => x.tagName).map(x => x.tagName), ['mark']);
  const mark = h.elements.get('compare-after').children.find(x => x.tagName === 'mark');
  assert.equal(mark.dataset.line, '2');
  assert.match(h.elements.get('compare-context').textContent, /text.only/i);
});
test('long input falls back explicitly with both originals preserved', () => {
  const h = load(), a = 'x'.repeat(65537), b = 'y';
  assert.equal(h.compare(a, b).status, 'limited');
  h.render(a, b);
  assert.equal(h.elements.get('compare-before').textContent, a);
  assert.equal(h.elements.get('compare-after').textContent, b);
  assert.match(h.elements.get('compare-context').textContent, /skipped/i);
  assert.equal(h.elements.get('compare-before').children.filter(x => x.tagName === 'mark').length, 0);
});
test('line count is bounded even for small-character inputs', () => {
  check('a\n'.repeat(513), 'a\n', [], [], 'limited');
});
test('maximum supported line count is accepted', () => {
  const a = 'a\n'.repeat(511) + 'old\n', b = 'a\n'.repeat(511) + 'new\n';
  check(a, b, [512], [512]);
});
test('invalid or absent source text is rejected, never coerced to empty', () => {
  for (const value of [null, undefined, {}, 7]) assert.throws(() => load().compare(value, 'ok'), /source text/i);
});
test('a second rendering clears previous highlights and counts', () => {
  const h = load(); h.render('old\n', 'new\n'); h.render('same\n', 'same\n');
  assert.equal(h.elements.get('compare-before').children.filter(x => x.tagName === 'mark').length, 0);
  assert.equal(h.elements.get('compare-before').textContent, 'same\n');
  assert.match(h.elements.get('compare-context').textContent, /identical/i);
});
