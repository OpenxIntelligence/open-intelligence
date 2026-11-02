'use strict';
// Run the entire actual literature script with a DOM/fetch boundary, without packages.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function element(tag='div') {
  return {tag, children:[], events:{}, value:'', checked:false, disabled:false, _text:'',
    get textContent(){return this._text+this.children.map(x=>x.textContent).join('');},
    set textContent(value){this._text=String(value);this.children=[];},
    set innerHTML(value){throw Error('HTML rendering is forbidden');},
    append(...items){this.children.push(...items);},
    replaceChildren(...items){this._text='';this.children=[...items];},
    addEventListener(name,handler){this.events[name]=handler;},
    focus(){},
    async fire(name){if(this.events[name]) await this.events[name]({preventDefault(){}});}};
}
function harness() {
  const nodes=new Map(), requests=[];
  for(const id of ['literature-search-form','literature-terms','literature-public-attestation',
    'literature-live-button','literature-clear-button','literature-mode','literature-feedback','literature-results']) {
    nodes.set(id,element());
  }
  const el=id=>{assert.ok(nodes.has(id),'Literature UI must not read case controls: '+id);return nodes.get(id);};
  el('literature-terms').value='RESTORED PRIVATE TEXT MUST BE CLEARED';
  el('literature-public-attestation').checked=true;
  const globals={document:{getElementById:el,createElement:element},
    fetch:(url,options)=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}))};
  for(const name of ['active','caseId','localStorage','sessionStorage']) {
    Object.defineProperty(globals,name,{get(){throw Error('Patient context or persistence must not be accessed');}});
  }
  const ctx=vm.createContext(globals);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/literature.js'),'utf8'),ctx);
  return {el,requests};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function response(body,status=200) {return {ok:status>=200&&status<300,status,json:async()=>body};}
async function ready(h,enabled=true) {
  assert.equal(h.requests[0].url,'/api/literature/status');
  h.requests[0].resolve(response({live_enabled:enabled})); await settle();
}
async function enter(h,terms='public oncology review') {
  h.el('literature-terms').value=terms; await h.el('literature-terms').fire('input');
  h.el('literature-public-attestation').checked=true; await h.el('literature-public-attestation').fire('change');
}
function result(changes={}) {
  return {provider:'europe_pmc',provider_hit_count:12,returned_record_count:2,
    excluded_counts:{unsupported_source:1},metadata_only:true,clinical_evidence_appraised:false,
    rights_status:'not_assessed',retrieved_at:'2026-11-02T12:00:00Z',
    citations:[{source_database:'MED',source_record_id:'12345678',title:'<img src=x onerror=alert(1)> literal title',
      authors:'Invented A',journal:'Fictional bibliography journal',publication_year:2026,
      record_url:'https://europepmc.org/article/MED/12345678',
      integrity:{status:'unknown',markers:[]},metadata_only:true,clinical_evidence_appraised:false,
      rights_status:'not_assessed'}],...changes};
}
function descendants(item,tag) {return [...(item.tag===tag?[item]:[]),...item.children.flatMap(x=>descendants(x,tag))];}

test('initialization clears browser-restored inputs and performs no search or case access',async()=>{
  const h=harness();
  assert.equal(h.el('literature-terms').value,'');
  assert.equal(h.el('literature-public-attestation').checked,false);
  assert.equal(h.el('literature-live-button').disabled,true);
  assert.equal(h.requests.length,1);
  await ready(h);
  assert.equal(h.el('literature-live-button').disabled,true);
});
test('both exact operator enablement and the explicit unchecked attestation are required',async()=>{
  for(const enabled of [false,'true',1]) {
    const h=harness(); await ready(h,enabled); await enter(h);
    await h.el('literature-search-form').fire('submit');
    assert.equal(h.el('literature-live-button').disabled,true); assert.equal(h.requests.length,1);
  }
  const h=harness(); await ready(h); h.el('literature-terms').value='public oncology review';
  await h.el('literature-terms').fire('input'); await h.el('literature-search-form').fire('submit');
  assert.equal(h.requests.length,1);
});
test('one deliberate submit sends only the four public fields in a POST body',async()=>{
  const h=harness(); await ready(h); await enter(h);
  const pending=h.el('literature-search-form').fire('submit');
  assert.equal(h.el('literature-live-button').disabled,true);
  await h.el('literature-search-form').fire('submit');
  assert.equal(h.requests.length,2);
  const request=h.requests[1]; assert.equal(request.url,'/api/literature/search');
  assert.equal(request.options.method,'POST');
  assert.deepEqual(JSON.parse(request.options.body),{terms:'public oncology review',human_authored:true,
    public_terms_only:true,page_size:5});
  request.resolve(response(result())); await pending;
});
test('metadata renders as literal text with canonical protected links and honest counts',async()=>{
  const h=harness(); await ready(h); await enter(h);
  const pending=h.el('literature-search-form').fire('submit');
  h.requests[1].resolve(response(result())); await pending;
  const view=h.el('literature-results'), links=descendants(view,'a');
  assert.equal(descendants(view,'img').length,0);
  assert.match(view.textContent,/<img src=x onerror=alert\(1\)> literal title/);
  assert.equal(links.length,1); assert.equal(links[0].href,'https://europepmc.org/article/MED/12345678');
  assert.equal(links[0].target,'_blank'); assert.equal(links[0].rel,'noopener noreferrer');
  for(const text of ['Provider matches: 12','Returned page records: 2','Displayed citations: 1','Excluded: 1',
    'Integrity: unknown','Rights: unassessed','not evidence for a clinical conclusion']) assert.ok(view.textContent.includes(text),text);
});
test('forged or noncanonical record URLs never become clickable links',async()=>{
  for(const url of ['javascript:alert(1)','https://europepmc.org.evil.invalid/article/MED/12345678',
    '//europepmc.org/article/MED/12345678','https://europepmc.org/article/MED/12345678?redirect=evil',
    'https://europepmc.org/article/MED/99999999']) {
    const h=harness(); await ready(h); await enter(h);
    const body=result(); body.citations[0].record_url=url;
    const pending=h.el('literature-search-form').fire('submit');
    h.requests[1].resolve(response(body)); await pending;
    assert.equal(descendants(h.el('literature-results'),'a').length,0);
  }
});
test('new submission clears older results immediately and a changed query needs a new attestation',async()=>{
  const h=harness(); await ready(h); await enter(h);
  let pending=h.el('literature-search-form').fire('submit');
  h.requests[1].resolve(response(result())); await pending;
  assert.ok(h.el('literature-results').textContent.length);
  pending=h.el('literature-search-form').fire('submit');
  assert.equal(h.el('literature-results').textContent,'');
  h.el('literature-terms').value='different public topic'; await h.el('literature-terms').fire('input');
  assert.equal(h.el('literature-public-attestation').checked,false);
  h.requests[2].resolve(response(result())); await pending;
  assert.equal(h.el('literature-results').textContent,'');
});
test('term or checkbox changes invalidate late responses even when values return to their originals',async()=>{
  for(const change of ['terms','checkbox']) {
    const h=harness(); await ready(h); await enter(h);
    const pending=h.el('literature-search-form').fire('submit');
    if(change==='terms') {await enter(h,'other public terms'); await enter(h,'public oncology review');}
    else {
      h.el('literature-public-attestation').checked=false; await h.el('literature-public-attestation').fire('change');
      h.el('literature-public-attestation').checked=true; await h.el('literature-public-attestation').fire('change');
    }
    h.requests[1].resolve(response(result())); await pending;
    assert.equal(h.el('literature-results').textContent,'');
  }
});
test('clear discards inputs and results and suppresses late failures',async()=>{
  const h=harness(); await ready(h); await enter(h);
  const pending=h.el('literature-search-form').fire('submit');
  await h.el('literature-clear-button').fire('click');
  assert.equal(h.el('literature-terms').value,''); assert.equal(h.el('literature-public-attestation').checked,false);
  const message=h.el('literature-feedback').textContent;
  h.requests[1].reject(Error('SECRET PROVIDER QUERY')); await pending;
  assert.equal(h.el('literature-results').textContent,'');
  assert.equal(h.el('literature-feedback').textContent,message);
});
test('HTTP and network failures never display raw server or exception messages',async()=>{
  for(const status of [422,429,502,403,500]) {
    const h=harness(); await ready(h); await enter(h);
    const pending=h.el('literature-search-form').fire('submit');
    h.requests[1].resolve({ok:false,status,json:async()=>{throw Error('Raw errors must not be read');}}); await pending;
    assert.ok(h.el('literature-feedback').textContent.length);
    assert.doesNotMatch(h.el('literature-feedback').textContent,/SECRET|Raw errors/);
  }
  const h=harness(); await ready(h); await enter(h);
  const pending=h.el('literature-search-form').fire('submit');
  h.requests[1].reject(Error('SECRET PROVIDER QUERY')); await pending;
  assert.doesNotMatch(h.el('literature-feedback').textContent,/SECRET/);
});
test('unexpected appraisal or rights grants and malformed results fail closed',async()=>{
  for(const body of [result({clinical_evidence_appraised:true}),result({rights_status:'approved'}),
    result({citations:{}}),result({provider_hit_count:'12'})]) {
    const h=harness(); await ready(h); await enter(h);
    const pending=h.el('literature-search-form').fire('submit');
    h.requests[1].resolve(response(body)); await pending;
    assert.equal(h.el('literature-results').textContent,'');
    assert.ok(h.el('literature-feedback').textContent.length);
  }
});
test('status failures leave search disabled without echoing server details',async()=>{
  const h=harness(); h.requests[0].reject(Error('SECRET STATUS RESPONSE')); await settle();
  await enter(h); await h.el('literature-search-form').fire('submit');
  assert.equal(h.requests.length,1); assert.equal(h.el('literature-live-button').disabled,true);
  assert.doesNotMatch(h.el('literature-mode').textContent,/SECRET/);
});
