import {before,test} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'vite';
import {projection} from './laboratory-projection-fixture.mjs';
import {parseSourceWorldModel} from '../.test-dist/source-world-model.js';

let LaboratoryResultPage,LaboratoryResultRow;
before(async()=>{
  const outDir='.test-dist/laboratory-result-browser-ui';
  await build({configFile:false,logLevel:'silent',build:{ssr:resolve('src/laboratory-result-browser.tsx'),
    outDir,emptyOutDir:true,rollupOptions:{output:{entryFileNames:'browser.mjs'}}}});
  ({LaboratoryResultPage,LaboratoryResultRow}=await import(pathToFileURL(resolve(outDir,'browser.mjs')).href));
});

// These independent fictional originals deliberately reuse their local Observation
// and Specimen references. The same test can occur with different literal units.
function results(large=false){
  const wire=projection(),a=wire.current_sources[0];
  const b={...a,source_id:'SRC-'+'B'.repeat(32),document_id:'FICTIONAL-REPORT-B',sha256:'c'.repeat(64)};
  wire.current_sources.push(b);
  const rows=wire.laboratory_observations;
  rows[1]={...rows[1],loinc_code:'718-7'};
  rows.push({...rows[0],source_id:b.source_id,source_sha256:b.sha256,document_id:b.document_id,
    report_reference:'DiagnosticReport/FICTIONAL-REPORT-B',value_text:'0.00',unit_code:'mg/L'});
  if(large){
    const aRow=rows[0],bRow=rows[3];
    for(let i=0;i<22;i++)rows.push({...((i%2===0)?aRow:bRow),observation_reference:'Observation/FICTIONAL-PAGE-'+i});
  }
  wire.laboratory_timeline=[...rows].reverse().map(o=>({
    source_id:o.source_id,observation_reference:o.observation_reference,loinc_code:o.loinc_code,
    effective_at:o.effective_at,issued_at:o.issued_at,specimen_reference:o.specimen_reference,
    status:o.status,clinical_interpretation:'not_performed'}));
  Object.assign(wire.summary,{current_sources:2,current_observations:rows.length,current_laboratory_observations:rows.length});
  const model=parseSourceWorldModel(wire,wire.patient_id,wire.case_id);
  const key=r=>r.source_id+':'+r.observation_reference,byKey=new Map(model.laboratory_observations.map(r=>[key(r),r]));
  return model.laboratory_timeline.map(t=>byKey.get(key(t)));
}
const page=(results,filters={},n=0)=>renderToStaticMarkup(createElement(LaboratoryResultPage,{
  filters:{code:'',context:'',status:'',...filters},page:n,change(){},setPage(){},
},results.map(result=>createElement(LaboratoryResultRow,{result,key:result.source_id+':'+result.observation_reference}))));
const rows=html=>html.match(/<li data-testid="world-laboratory-observation">[\s\S]*?<\/li>/g)??[];

test('an exact test filter preserves chronology, literal units and the reason for an absent result',()=>{
  const r=rows(page(results(),{code:'777-3'}));
  assert.equal(r.length,3);
  assert.match(r[0],/FICTIONAL-REPORT-B/);assert.match(r[0],/<strong>0\.00<\/strong> <code>mg\/L<\/code>/);
  assert.match(r[1],/Result absent · source reason: <strong>not-performed<\/strong>/);
  assert.match(r[2],/<strong>0<\/strong> <code>10\*9\/L<\/code>/);
  assert.deepEqual(rows(page(results(),{code:'777'})),[],'partial codes must not match');
  assert.equal(rows(page(results(),{code:'777-3',status:'reported_value'})).length,2);
});

test('selecting an original excludes a reused bundle-local specimen and observation from another original',()=>{
  const data=results(),html=page(data);
  const choices=[...html.matchAll(/<option value="([^"]+)">(FICTIONAL-REPORT-[AB] v1 · Specimen\/FICTIONAL-SPECIMEN-A)<\/option>/g)];
  assert.equal(choices.length,2);
  const value=choices.find(([, ,label])=>label.startsWith('FICTIONAL-REPORT-B'))[1].replaceAll('&quot;','"');
  const filtered=rows(page(data,{code:'777-3',context:value}));
  assert.equal(filtered.length,1);
  assert.match(filtered[0],/FICTIONAL-REPORT-B/);assert.match(filtered[0],/Observation\/FICTIONAL-OBS-0/);
  assert.ok(filtered[0].includes('c'.repeat(64)));assert.ok(!filtered[0].includes('b'.repeat(64)));
  const empty=page(data,{code:'777-3',context:value,status:'reported_absent'});
  assert.match(empty,/No results match these filters/);assert.match(empty,/Clear laboratory filters/);
  assert.deepEqual(rows(empty),[]);
});

test('a large timeline renders bounded pages without dropping or duplicating any source locator',()=>{
  const data=results(true),first=page(data),second=page(data,{},1);
  assert.match(first,/Showing 1–25 of 26/);assert.match(second,/Showing 26–26 of 26/);
  const shown=[...rows(first),...rows(second)];assert.equal(shown.length,data.length);
  data.forEach((entry,i)=>{assert.ok(shown[i].includes(entry.observation_reference));assert.ok(shown[i].includes(entry.source_id));});
});

test('coded status filtering spans pages without mixing test codes or bundle-local source identities',()=>{
  const original=results(true),data=[...original,...original.slice(0,3)].map((o,i)=>i<27?
    {...o,observation_reference:'Observation/Literal-'+i,status:'reported_coded',value_text:null,unit_code:null,absent_reason:null,
      coded_result:{system:'urn:oi:synthetic:lab-results',code:'FIXTURE-'+i}}:o);
  const filter={status:'reported_coded'},first=page(data,filter),last=page(data,filter,1);
  assert.match(first,/<option value="reported_coded" selected="">Coded result<\/option>/);
  assert.match(first,/Showing 1–25 of 27/);assert.match(last,/Showing 26–27 of 27/);
  const shown=[...rows(first),...rows(last)];assert.equal(shown.length,27);
  shown.forEach((row,i)=>{assert.ok(row.includes('Coded result: FIXTURE-'+i+'<'));assert.ok(row.includes(data[i].source_id));});
  const b=data[0],criteria={...filter,context:JSON.stringify([b.source_id,b.specimen_reference]),code:b.loinc_code};
  const scoped=rows(page(data,criteria));
  assert.equal(scoped.length,data.filter(r=>r.status===filter.status&&r.source_id===b.source_id&&r.loinc_code===b.loinc_code).length);
  assert.ok(scoped.every(row=>row.includes(b.source_sha256)&&row.includes('LOINC '+b.loinc_code)));
});
