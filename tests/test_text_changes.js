'use strict';
// Supplementary invariants for the SAME comparison implementation as
// test_source_line_diff.js. No second renderer, diff engine or dependency.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
function load() {
  const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
  const start = app.indexOf('// Begin source text comparison.');
  const end = app.indexOf('// End source text comparison.');
  assert.ok(start >= 0 && end > start, 'canonical source-line comparison is not implemented');
  class TextNode { constructor(text='') { this.textContent=String(text); } }
  class Element {
    constructor(tag='div') { this.tagName=tag; this.children=[]; this.dataset={}; }
    append(...items) { this.children.push(...items); }
    replaceChildren(...items) { this.children=items; }
    set textContent(text) { this.children=[new TextNode(text)]; }
    get textContent() { return this.children.map(x=>x.textContent).join(''); }
  }
  const elements = new Map(['compare-before','compare-after','compare-context'].map(id=>[id,new Element()]));
  const sandbox = {document:{createTextNode:text=>new TextNode(text)}, el:id=>elements.get(id),
    node:(tag,text,cls)=>{const e=new Element(tag);e.textContent=text;e.className=cls;return e;}};
  vm.createContext(sandbox); vm.runInContext(app.slice(start,end),sandbox);
  return {compare:(a,b)=>JSON.parse(JSON.stringify(sandbox.compareReportLines(a,b))),
    render:(a,b)=>sandbox.renderReportLineComparison(a,b),elements};
}
const lines = text => text.match(/[^\n]*\n|[^\n]+$/g) || [];
function check(h,a,b) {
  const r=h.compare(a,b), left=lines(a),right=lines(b);
  assert.ok(['compared','identical'].includes(r.status));
  for (const [indices,source] of [[r.beforeLines,left],[r.afterLines,right]]) {
    assert.deepEqual([...new Set(indices)].sort((x,y)=>x-y),indices);
    assert.ok(indices.every(i=>Number.isInteger(i)&&i>=1&&i<=source.length));
  }
  assert.deepEqual(left.filter((_,i)=>!r.beforeLines.includes(i+1)),
                   right.filter((_,i)=>!r.afterLines.includes(i+1)),
                   'unhighlighted original lines must match exactly in order');
  h.render(a,b);
  assert.equal(h.elements.get('compare-before').textContent,a);
  assert.equal(h.elements.get('compare-after').textContent,b);
  return r;
}
function lcsBySubsets(a,b) {
  let best=0;
  for(let mask=0;mask<(1<<a.length);mask++) {
    const subsequence=a.filter((_,i)=>(mask&(1<<i))!==0);
    let j=0;
    for(const token of b) if(token===subsequence[j])j++;
    if(j===subsequence.length)best=Math.max(best,j);
  }
  return best;
}
test('400 generated source pairs preserve originals and align untouched lines',()=>{
  const h=load(); let seed=23;
  const next=()=>seed=(seed*48271)%2147483647;
  const tokens=['A\n','B\r\n','\n',' 🧬\n','<mark>\n','é\n','e\u0301\n'];
  for(let i=0;i<400;i++) {
    const a=Array.from({length:next()%14},()=>tokens[next()%tokens.length]).join('');
    const b=Array.from({length:next()%14},()=>tokens[next()%tokens.length]).join('');
    check(h,a,b);
  }
});
test('small repeated-line comparisons agree with independent subsequence oracle',()=>{
  const h=load();
  const inputs=['','A\n','B\n','A\nA\n','A\nB\nA\n','B\nA\nB\n','\nA\n','A\nB\nB\nA\n'];
  for(const a of inputs)for(const b of inputs){
    const r=check(h,a,b),left=lines(a),right=lines(b);
    assert.equal(r.beforeLines.length+r.afterLines.length,left.length+right.length-2*lcsBySubsets(left,right));
  }
});
test('reversing comparison swaps edit counts without fabricating equal content',()=>{
  const h=load(),a='A\nA\nB\n\n🧬\n',b='B\nA\n🧬\nC\n';
  const x=check(h,a,b),y=check(h,b,a);
  assert.equal(x.beforeLines.length,y.afterLines.length);
  assert.equal(x.afterLines.length,y.beforeLines.length);
});
test('markup-looking source content never produces source-named elements',()=>{
  const h=load();
  check(h,'A\n</mark><script>run()</script>\n','A\n<img id=bad onerror=run()>\n');
  for(const id of ['compare-before','compare-after']) {
    const children=h.elements.get(id).children;
    assert.ok(children.filter(x=>x.tagName).every(x=>x.tagName==='mark'));
  }
});
test('blank final lines retain real line anchors at the supported boundary',()=>{
  const h=load(),a='A\n'.repeat(510)+'\nB',b='A\n'.repeat(510)+'\nB\n';
  const r=check(h,a,b);assert.deepEqual(r.beforeLines,[512]);assert.deepEqual(r.afterLines,[512]);
});
test('Unicode normalization is not silently treated as equality',()=>{
  const r=check(load(),'é\n🧬\n','e\u0301\n🧬\n');
  assert.deepEqual(r.beforeLines,[1]); assert.deepEqual(r.afterLines,[1]);
});
test('fallback clears a previous result and preserves complete oversized source',()=>{
  const h=load();h.render('old\n','new\n');
  const a='x'.repeat(65537);h.render(a,'y');
  assert.equal(h.elements.get('compare-before').textContent,a);
  assert.equal(h.elements.get('compare-after').textContent,'y');
  for(const id of ['compare-before','compare-after'])
    assert.equal(h.elements.get(id).children.filter(x=>x.tagName==='mark').length,0);
  assert.match(h.elements.get('compare-context').textContent,/skipped/i);
});
test('successive different comparisons do not retain earlier highlighted line numbers',()=>{
  const h=load();check(h,'A\nold\n','A\nnew\n');check(h,'left\nA\n','right\nA\n');
  for(const id of ['compare-before','compare-after'])
    assert.deepEqual(h.elements.get(id).children.filter(x=>x.tagName==='mark').map(x=>x.dataset.line),['1']);
});
