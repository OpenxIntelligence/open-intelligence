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
const page=(results,filters={},n=0,layout='cards')=>renderToStaticMarkup(createElement(LaboratoryResultPage,{
  filters:{code:'',context:'',status:'',...filters},page:n,change(){},setPage(){},layout,setLayout(){},
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


const tableRows=html=>html.match(/<tr data-testid="world-laboratory-observation">[\s\S]*?<\/tr>/g)??[];

test('compact table preserves the same chronological originals, literal values and absence reasons as cards',()=>{
  const data=results(),html=page(data,{},0,'table'),shown=tableRows(html);
  assert.equal(shown.length,data.length);
  data.forEach((entry,i)=>{
    assert.ok(shown[i].includes(entry.observation_reference));
    assert.ok(shown[i].includes(entry.source_id));
    assert.ok(shown[i].includes(entry.source_sha256));
  });
  assert.match(shown[0],/<strong>0\.00<\/strong> <code>mg\/L<\/code>/);
  assert.match(html,/Result absent · source reason: <strong>not-performed<\/strong>/);
  assert.ok(!html.includes('<script>plasma</script>'));
  assert.ok(html.includes('&lt;script&gt;plasma&lt;/script&gt;'));
});

test('table exposes a caption, scoped headers, named scroll region and explicit pressed layout',()=>{
  const html=page(results(),{},0,'table');
  assert.match(html,/<caption>Current source-reported laboratory results · not clinically reviewed<\/caption>/);
  assert.equal((html.match(/scope="col"/g)??[]).length,5);
  assert.equal((html.match(/scope="row"/g)??[]).length,4);
  assert.match(html,/role="region" aria-label="Laboratory results table" aria-describedby="laboratory-table-help" tabindex="0"/);
  assert.match(html,/aria-pressed="true">Table<\/button>/);
});

test('empty table matches show the existing filter reset and do not render a misleading empty table',()=>{
  const html=page(results(),{code:'777'},0,'table');
  assert.match(html,/No results match these filters/);
  assert.match(html,/Clear laboratory filters/);
  assert.equal(tableRows(html).length,0);
  assert.ok(!html.includes('<table'));
});

test('both layouts clamp a stale page after results shrink',()=>{
  const data=results();
  assert.equal(rows(page(data,{},8)).length,4);
  assert.equal(tableRows(page(data,{},8,'table')).length,4);
  assert.match(page(data,{},8,'table'),/Showing 1–4 of 4/);
});
