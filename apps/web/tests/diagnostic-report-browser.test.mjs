import {test} from 'node:test';
import assert from 'node:assert/strict';
import {browseDiagnosticReports} from '../.test-dist/diagnostic-report-browser.js';
import {sourceIndex} from './source-images-fixtures.mjs';

export function diagnosticIndex(kind='pathology', count=2) {
  const index=sourceIndex();
  index.sources=Array.from({length:count},(_,i)=>({...index.sources[0],
    source_id:'SRC-'+String(i+1).padStart(32,'0'),document_id:'REPORT-'+(i+1),kind,
    specimen_id:i===0?null:'SPECIMEN-'+i}));
  index.source_reported_assertions=index.sources.flatMap((source,i)=>[
    {source_id:source.source_id,finding_key:'marker',reported_state:'negative',
      source_statement:'Fictional marker was negative.',source_line:8,clinical_review_state:'not_established'},
    {source_id:source.source_id,finding_key:'second-marker',reported_state:i?'indeterminate':'pending',
      source_statement:'A fictional second marker awaits review.',source_line:9,clinical_review_state:'not_established'},
  ]);
  return index;
}
const all={query:'',versionState:'all'};
const browse=(index,filters=all,page=1)=>browseDiagnosticReports(index,'pathology',filters,page);

test('searches literal statements without losing exact original or line identity',()=>{
  const index=diagnosticIndex();const result=browse(index,{...all,query:'  AwAiTs ReViEw  '});
  assert.equal(result.matchedReports,2);
  assert.equal(result.rows[0].source,index.sources[0]);
  assert.deepEqual(result.rows[0].findings,[index.source_reported_assertions[1]]);
  assert.equal(result.rows[0].totalFindings,2);
  assert.equal(result.rows[0].findings[0].source_line,9);
});
test('query and state must match the same statement, not different lines in a report',()=>{
  assert.equal(browse(diagnosticIndex(),{...all,query:'awaits',reportedState:'negative'}).matchedReports,0);
});
test('negative, pending, indeterminate and not-reported stay separate literal states',()=>{
  const index=diagnosticIndex();
  index.source_reported_assertions.push({...index.source_reported_assertions[0],reported_state:'not-reported',source_line:10});
  const result=browse(index);
  assert.deepEqual(result.reportedStates,['indeterminate','negative','not-reported','pending']);
  for(const state of result.reportedStates) {
    const rows=browse(index,{...all,reportedState:state}).rows;
    assert.ok(rows.length>0);assert.ok(rows.every(row=>row.findings.every(f=>f.reported_state===state)));
  }
});
test('same document label across domains does not mix sources, states or specimens',()=>{
  const index=diagnosticIndex();
  index.sources.push({...index.sources[0],source_id:'OTHER',kind:'molecular',specimen_id:'SECRET-SPECIMEN'});
  index.source_reported_assertions.push({...index.source_reported_assertions[0],source_id:'OTHER',reported_state:'other-state'});
  const result=browse(index);
  assert.equal(result.totalReports,2);assert.equal(result.totalStatements,4);
  assert.ok(!result.specimens.includes('SECRET-SPECIMEN'));assert.ok(!result.reportedStates.includes('other-state'));
});
test('unrecorded specimen is distinct from a literal label and filters exact identifiers',()=>{
  const index=diagnosticIndex();index.sources[1].specimen_id='none';
  assert.equal(browse(index,{...all,specimen:null}).rows[0].source.source_id,index.sources[0].source_id);
  assert.equal(browse(index,{...all,specimen:'none'}).rows[0].source.source_id,index.sources[1].source_id);
  assert.equal(browse(index,{...all,specimen:'no'}).matchedReports,0);
});
test('historical versions keep original metadata but cannot acquire current quotations or state',()=>{
  const index=diagnosticIndex();index.sources[0].state='superseded';
  const history=browse(index,{...all,versionState:'superseded'});
  assert.equal(history.rows[0].source,index.sources[0]);assert.deepEqual(history.rows[0].findings,[]);
  assert.equal(browse(index,{...all,versionState:'superseded',reportedState:'negative'}).matchedReports,0);
  assert.equal(browse(index,{...all,query:index.sources[0].source_id}).rows[0].source,index.sources[0]);
});
test('reports without quoted statements remain inspectable without manufacturing results',()=>{
  const index=diagnosticIndex();index.source_reported_assertions=[];
  assert.equal(browse(index).matchedReports,2);assert.deepEqual(browse(index).reportedStates,[]);
  assert.equal(browse(index,{...all,reportedState:'negative'}).matchedReports,0);
});
test('pagination has no duplication or lost source across page boundaries',()=>{
  const index=diagnosticIndex('pathology',27);
  const pages=[1,2,3].map(page=>browse(index,all,page));
  assert.deepEqual(pages.map(p=>p.rows.length),[12,12,3]);
  assert.deepEqual(pages.flatMap(p=>p.rows.map(row=>row.source.source_id)),index.sources.map(s=>s.source_id));
  assert.equal(pages[2].start,25);assert.equal(pages[2].end,27);
});
test('outdated and invalid pages clamp, including a shrinking result set',()=>{
  const index=diagnosticIndex('pathology',27);
  assert.equal(browse(index,all,99).page,3);
  for(const page of [0,-1,NaN,Infinity,1.5])assert.equal(browse(index,all,page).page,1);
  const shrunk=browse(index,{...all,specimen:'SPECIMEN-25'},3);
  assert.equal(shrunk.page,1);assert.equal(shrunk.rows[0].source,index.sources[25]);
});
test('empty results describe loaded scope and carry no source from another receipt',()=>{
  const first=diagnosticIndex();const second=diagnosticIndex('molecular');
  assert.equal(browse(first).totalReports,2);
  assert.deepEqual(browse(second).rows,[]);assert.equal(browse(second).start,0);assert.equal(browse(second).end,0);
});
test('projection does not change source order, source objects, or assertions',()=>{
  const index=diagnosticIndex();index.sources[0].state='superseded';
  const before=JSON.stringify(index);const result=browse(index);
  assert.equal(result.rows[0].source,index.sources[1]);assert.equal(JSON.stringify(index),before);
  assert.ok(Object.isFrozen(result.rows));assert.ok(Object.isFrozen(result.rows[0].findings));
});
