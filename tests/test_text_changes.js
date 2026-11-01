'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const file = path.join(__dirname, '../web/text-changes.js');
const api = fs.existsSync(file) ? require(file) : {};
function diff(before, after) {
  assert.equal(typeof api.compareLines, 'function', 'source line comparison has not been implemented');
  return api.compareLines(before, after);
}
function restore(result, side) {
  return result.operations.filter(x => side === 'before' ? x.kind !== 'added' : x.kind !== 'removed')
    .map(x => x.text).join('');
}
function faithful(before, after) {
  const result = diff(before, after);
  assert.equal(result.status, 'compared');
  assert.equal(restore(result, 'before'), before);
  assert.equal(restore(result, 'after'), after);
  let left = 1, right = 1;
  for (const op of result.operations) {
    assert.equal(op.beforeLine, op.kind === 'added' ? null : left++);
    assert.equal(op.afterLine, op.kind === 'removed' ? null : right++);
  }
  return result;
}
test('identical source remains exactly reconstructable with no changes', () => {
  const result = faithful('A\nB\n', 'A\nB\n');
  assert.equal(result.added, 0); assert.equal(result.removed, 0);
});
test('empty originals are equal without inventing a blank source line', () => {
  const result = faithful('', ''); assert.deepEqual(result.operations, []);
});
test('a replaced finding preserves both texts and their actual line numbers', () => {
  const r = faithful('Header\nNot tested\nTail\n', 'Header\nNegative\nTail\n');
  assert.deepEqual(r.operations.filter(x => x.kind !== 'equal'), [
    {kind:'removed', text:'Not tested\n', beforeLine:2, afterLine:null},
    {kind:'added', text:'Negative\n', beforeLine:null, afterLine:2}
  ]);
});
test('an inserted line does not mark later unchanged lines as different', () => {
  const r = faithful('A\nB\n', 'A\nNew\nB\n');
  assert.equal(r.added, 1); assert.equal(r.removed, 0);
  assert.equal(r.operations.at(-1).beforeLine, 2); assert.equal(r.operations.at(-1).afterLine, 3);
});
test('deletion retains an old-only original line anchor', () => {
  const r = faithful('A\nOld\nB\n', 'A\nB\n');
  assert.equal(r.removed, 1); assert.equal(r.added, 0);
});
test('all-added and all-removed documents are supported', () => {
  assert.equal(faithful('', 'A\nB').added, 2);
  assert.equal(faithful('A\nB', '').removed, 2);
});
test('repeated lines use a stable alignment without dropping occurrences', () => {
  const r = faithful('A\nA\nB\nA\n', 'A\nB\nA\nA\n');
  assert.deepEqual(diff('A\nA\nB\nA\n', 'A\nB\nA\nA\n'), r);
});
test('a final newline-only change is not hidden', () => {
  const r = faithful('A', 'A\n'); assert.equal(r.added, 1); assert.equal(r.removed, 1);
});
test('CRLF and LF differences preserve the actual original endings', () => {
  const r = faithful('A\r\nB\r\n', 'A\nB\n'); assert.equal(r.removed, 2);
});
test('blank lines and whitespace-only changes are not normalized away', () => {
  const r = faithful(' \n\nA\n', '\t\nA\n'); assert.ok(r.removed > 0);
});
test('Unicode and combining marks are preserved without normalization', () => {
  const r = faithful('É\n🧬\n', 'E\u0301\n🧬\n'); assert.equal(r.removed, 1);
});
test('markup-like original content remains a plain string', () => {
  const r = faithful('<script>throw 1</script>\n', '<img src=x onerror=alert(1)>\n');
  assert.equal(r.operations[1].text, '<img src=x onerror=alert(1)>\n');
});
test('invalid input is rejected rather than coerced to a source document', () => {
  assert.throws(() => diff(null, 'A'), TypeError);
  assert.throws(() => diff('A', {text:'B'}), TypeError);
});
test('character limit yields an explicit unavailable result without partial rows', () => {
  const r = diff('x'.repeat(65537), 'y');
  assert.equal(r.status, 'limited'); assert.deepEqual(r.operations, []);
  assert.equal(r.added, undefined); assert.equal(r.removed, undefined);
});
test('line count limit also applies to identical originals', () => {
  assert.equal(diff('\n'.repeat(2001), '\n'.repeat(2001)).status, 'limited');
});
test('alignment work limit prevents large unrelated line matrices', () => {
  const a = Array.from({length:600}, (_,i)=>'before'+i+'\n').join('');
  const b = Array.from({length:600}, (_,i)=>'after'+i+'\n').join('');
  const r = diff(a,b); assert.equal(r.status, 'limited'); assert.deepEqual(r.operations, []);
});
test('large shared context is trimmed before allocating alignment work', () => {
  const prefix = 'same\n'.repeat(700), suffix = 'end\n'.repeat(700);
  const r = faithful(prefix+'Old\n'+suffix, prefix+'New\n'+suffix);
  assert.equal(r.added, 1); assert.equal(r.removed, 1);
});
test('bounded generated examples reconstruct both originals and line anchors', () => {
  let state = 17;
  const next = () => (state = (state * 48271) % 2147483647);
  const tokens = ['A\n','B\r\n','\n',' 🧬\n','<p>\n'];
  for (let i=0;i<150;i++) {
    const a = Array.from({length:next()%14},()=>tokens[next()%tokens.length]).join('');
    const b = Array.from({length:next()%14},()=>tokens[next()%tokens.length]).join('');
    faithful(a,b);
  }
});
