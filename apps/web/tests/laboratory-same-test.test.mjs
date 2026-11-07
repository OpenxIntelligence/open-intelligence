import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseSourceWorldModel} from '../.test-dist/source-world-model.js';
import {projection} from './laboratory-projection-fixture.mjs';
import {twoReports} from './laboratory-same-test-fixture.mjs';

async function reader(){
 const m=await import('../.test-dist/laboratory-same-test.js').catch(()=>({}));
 assert.equal(typeof m.sameTestReportGroups,'function','The same-test grouping projection has not been implemented');
 return m.sameTestReportGroups;
}
const parsed=raw=>parseSourceWorldModel(raw,raw.patient_id,raw.case_id);

test('groups exact same test codes across two current originals without converting units or inferring clinical trends',async()=>{
 const group=(await reader())(parsed(twoReports()));
 assert.equal(group.group_count,1);
 assert.equal(group.excluded_reference_count,0);
 assert.equal(group.hidden_group_count,0);
 const g=group.groups[0];
 assert.equal(g.loinc_code,'777-3');assert.equal(g.source_count,2);assert.equal(g.result_count,4);
 assert.equal(g.rows[0].document_id,'FICTIONAL-REPORT-B');
 assert.equal(g.rows[0].value_text,'4.20');assert.equal(g.rows[0].unit_code,'mg/L');
 assert.equal(g.rows[0].specimen_reference,'Specimen/FICTIONAL-SPECIMEN-B');
 assert.equal(g.rows[0].source_sha256,'c'.repeat(64));
 assert.equal(g.rows[1].value_text,null);assert.equal(g.rows[1].absent_reason,'not-performed');
 assert.equal(g.rows.at(-1).value_text,'0');assert.equal(g.rows.at(-1).unit_code,'10*9/L');
 assert.ok(!JSON.stringify(group).includes('trend_value'));
});

test('a single report does not become a falsely longitudinal same-test group',async()=>{
 const result=(await reader())(parsed(projection()));
 assert.equal(result.group_count,0);assert.equal(result.groups.length,0);
});

test('legacy source labels remain in the original results list but cannot enter same-test comparison',async()=>{
 const raw=twoReports();
 for(const field of ['observation_reference','report_reference','specimen_reference']){
   const wire=structuredClone(raw),item=wire.laboratory_observations.at(-1),old=item.observation_reference;
   item[field]=field==='observation_reference'?'Observation/Legacy/_history/2':field==='report_reference'?
     'Legacy report locator':'Legacy specimen locator';
   const timeline=wire.laboratory_timeline.find(t=>t.source_id===item.source_id&&t.observation_reference===old);
   if(field==='observation_reference')timeline.observation_reference=item.observation_reference;
   if(field==='specimen_reference')timeline.specimen_reference=item.specimen_reference;
   const source=parsed(wire),view=(await reader())(source);
   assert.equal(source.laboratory_observations.length,4,'Legacy results must remain browsable');
   assert.equal(view.group_count,0);
   assert.equal(view.excluded_reference_count,1);
 }
});

test('different LOINC identifiers are not grouped despite matching specimen or value',async()=>{
 const wire=twoReports(),item=wire.laboratory_observations.at(-1);
 item.loinc_code='718-7';
 wire.laboratory_timeline[0].loinc_code='718-7';
 const groups=(await reader())(parsed(wire));
 assert.equal(groups.group_count,0);
 assert.equal(groups.excluded_reference_count,0);
});

test('a coded response remains its original literal code, not a coerced quantity',async()=>{
 const wire=twoReports(true), groups=(await reader())(parsed(wire));
 assert.equal(groups.groups[0].rows[0].status,'reported_coded');
 assert.deepEqual(groups.groups[0].rows[0].coded_result,{system:'urn:oi:synthetic:lab-results',code:'FIC.a-01_2',
   version:'V1.0-fixture',display:'Literal  <img src=x> & "label"'});
 assert.equal(groups.groups[0].rows[0].unit_code,null);
});

test('bounded display keeps full totals rather than claiming to show every source report',async()=>{
 const model=structuredClone(parsed(twoReports()));
 for(let i=0;i<31;i++){
   const row={...model.laboratory_observations.at(-1),observation_reference:'Observation/SYNTHETIC-'+i};
   model.laboratory_observations.push(row);
   model.laboratory_timeline.push({source_id:row.source_id,observation_reference:row.observation_reference,
     loinc_code:row.loinc_code,effective_at:row.effective_at,issued_at:row.issued_at,
     specimen_reference:row.specimen_reference,status:row.status,clinical_interpretation:'not_performed'});
 }
 const group=(await reader())(model).groups[0];
 assert.equal(group.result_count,35);
 assert.ok(group.rows.length<=20);
 assert.equal(group.hidden_result_count,group.result_count-group.rows.length);
});

test('same-code source groups explicitly distinguish source context differences, not clinical comparability',async()=>{
 const g=(await reader())(parsed(twoReports())).groups[0];
 assert.deepEqual(g.context_differences,[
   'specimen_descriptions','result_kinds','numeric_units',
 ]);
 assert.ok(Object.isFrozen(g.context_differences));
 assert.ok(!JSON.stringify(g).includes('comparable'));
 assert.ok(!JSON.stringify(g).includes('trend_value'));
});

test('no reported source-field difference never becomes a claim of clinical comparability',async()=>{
 const model=structuredClone(parsed(twoReports()));
 const specimen=model.laboratory_observations[0].specimen_type_text;
 for(const row of model.laboratory_observations){
   row.specimen_type_text=specimen;
   row.status='reported_value';row.value_text='1.00';
   row.unit_code='10*9/L';row.absent_reason=null;
 }
 const result=(await reader())(model);
 assert.deepEqual(result.groups[0].context_differences,[]);
 assert.ok(!Object.hasOwn(result.groups[0],'clinically_comparable'));
});

test('differences hidden past the displayed row cap still appear in the context inventory',async()=>{
 const model=structuredClone(parsed(twoReports()));
 const specimen=model.laboratory_observations[0].specimen_type_text;
 for(const row of model.laboratory_observations){
   row.specimen_type_text=specimen;
   row.status='reported_value';row.value_text='1.00';
   row.unit_code='10*9/L';row.absent_reason=null;
 }
 const template=model.laboratory_observations.at(-1);
 for(let i=0;i<22;i++){
   const row={...template,observation_reference:'Observation/FICT-OVERFLOW-'+i,
     unit_code:i===21?'mg/L':'10*9/L'};
   model.laboratory_observations.push(row);
   model.laboratory_timeline.push({source_id:row.source_id,observation_reference:row.observation_reference,
     loinc_code:row.loinc_code,effective_at:row.effective_at,issued_at:row.issued_at,
     specimen_reference:row.specimen_reference,status:row.status,clinical_interpretation:'not_performed'});
 }
 const group=(await reader())(model).groups[0];
 assert.equal(group.rows.length,20);
 assert.ok(group.hidden_result_count>0);
 assert.deepEqual(group.context_differences,['numeric_units']);
});

test('coded answer and version differences remain literal rather than numeric deltas',async()=>{
 const model=structuredClone(parsed(twoReports(true)));
 const coded=model.laboratory_observations.filter(row=>row.status==='reported_coded');
 assert.equal(coded.length,2);
 coded[1].coded_result={...coded[1].coded_result,code:'FIC.b-02',version:'V2-fixture'};
 const group=(await reader())(model).groups[0];
 assert.ok(group.context_differences.includes('coded_system_versions'));
 assert.ok(group.context_differences.includes('coded_answer_codes'));
 assert.ok(!Object.hasOwn(group,'numeric_delta'));
});

test('distinct absence reasons are preserved as an explicit context difference',async()=>{
 const model=structuredClone(parsed(twoReports()));
 const absent=model.laboratory_observations.filter(row=>row.status==='reported_absent');
 assert.equal(absent.length,1);
 const original=model.laboratory_observations.at(-1);
 original.status='reported_absent';original.value_text=null;original.unit_code=null;
 original.absent_reason='masked';
 const group=(await reader())(model).groups[0];
 assert.ok(group.context_differences.includes('absence_reasons'));
 assert.ok(group.context_differences.includes('result_kinds'));
});
