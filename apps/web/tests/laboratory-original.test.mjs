import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {verifyOriginal} from '../.test-dist/source-intake.js';

const caseId='CASE-FICTIONAL-LAB',subject='Patient/FICTIONAL-PATIENT-A';
const sourceId='SRC-'+'A'.repeat(32),specimen='Specimen/FICTIONAL-SPECIMEN-A';
const category=[{coding:[{system:'http://terminology.hl7.org/CodeSystem/observation-category',code:'laboratory'}]}];
const coding=code=>({coding:[{system:'http://loinc.org',code}]});
function fixture(){
 const resources=[{resourceType:'Patient',id:'FICTIONAL-PATIENT-A'},
  {resourceType:'Specimen',id:'FICTIONAL-SPECIMEN-A',subject:{reference:subject},type:{text:'Fictional plasma sample'},collection:{collectedDateTime:'2026-04-03T09:05:00-04:00'}},
  {resourceType:'Observation',id:'FICTIONAL-OBS-A',status:'final',category,code:coding('777-3'),subject:{reference:subject},specimen:{reference:specimen},effectiveDateTime:'2026-04-03T09:05:00-04:00',issued:'2026-04-04T12:00:00Z',valueQuantity:{value:4.2,system:'http://unitsofmeasure.org',code:'10*9/L'}},
  {resourceType:'DiagnosticReport',id:'FICTIONAL-REPORT-A',status:'final',category,code:coding('58410-2'),subject:{reference:subject},specimen:[{reference:specimen}],result:[{reference:'Observation/FICTIONAL-OBS-A'}],effectiveDateTime:'2026-04-03T09:05:00-04:00',issued:'2026-04-04T12:00:00Z'}];
 return {resourceType:'Bundle',type:'collection',entry:resources.map((resource,i)=>({fullUrl:'urn:uuid:00000000-0000-4000-8000-'+String(i+1).padStart(12,'0'),resource}))};
}
function original(text=JSON.stringify(fixture(),null,2).replace('4.2,','4.20,')){
 const hash=createHash('sha256').update(text).digest('hex');
 const source={source_id:sourceId,document_id:'FICTIONAL-REPORT-A',version:1,sha256:hash,kind:'laboratory',event_date:'2026-04-03',issued_at:'2026-04-04',received_at:'2026-11-04T10:00:00Z',specimen_id:'FICTIONAL-SPECIMEN-A',state:'current',supersedes_id:null};
 const value={source_id:sourceId,case_id:caseId,access_receipt_id:'ACCESS-'+'B'.repeat(32),document_id:source.document_id,version:source.version,state:source.state,sha256:hash,original_text:text,synthetic:true,clinical_review_state:'not_established'};
 return {source,value};
}
test('laboratory original retains exact whitespace, numeric token and source-bound bytes',async()=>{
 const {source,value}=original();
 const checked=await verifyOriginal(value,caseId,source,subject);
 assert.equal(checked.original_text,value.original_text);assert.match(checked.original_text,/4\.20,/);
 assert.equal(checked.sha256,source.sha256);
});
test('laboratory original requires the active mapped subject and laboratory modality',async()=>{
 const {source,value}=original();
 for(const mapped of [undefined,'Patient/OTHER','https://example.invalid/Patient/FICTIONAL-PATIENT-A'])await assert.rejects(()=>verifyOriginal(value,caseId,source,mapped));
 await assert.rejects(()=>verifyOriginal(value,caseId,{...source,kind:'pathology'},subject));
});
test('tampered bytes, case, source version or review assertions cannot open an original',async()=>{
 const {source,value}=original();
 for(const bad of [{...value,original_text:value.original_text+' '},{...value,case_id:'CASE-OTHER'},
  {...value,version:2},{...value,source_id:'SRC-'+'C'.repeat(32)},
  {...value,clinical_review_state:'approved'},{...value,state:'superseded'}])await assert.rejects(()=>verifyOriginal(bad,caseId,source,subject));
});
test('arbitrary JSON and incoherent FHIR source locators fail even with matching input hash',async()=>{
 const mutations=[b=>{b.resourceType='Observation'},b=>{b.type='transaction'},
  b=>{b.entry[3].resource.id='OTHER-REPORT'},b=>{b.entry[1].resource.id='OTHER-SPECIMEN'},
  b=>{b.entry[2].resource.subject.reference='Patient/OTHER'},b=>{b.entry[3].resource.status='preliminary'},
  b=>{b.entry[3].resource.effectiveDateTime='2026-04-02T09:05:00-04:00'},
  b=>{b.entry[3].resource.issued='2026-04-05T12:00:00Z'},
  b=>{b.entry[3].resource.result[0].reference='Observation/MISSING'},
  b=>{b.entry.push(structuredClone(b.entry[2]))},b=>{b.entry[1].resource.subject.reference='Patient/OTHER'}];
 for(const mutate of mutations){const b=fixture();mutate(b);const{source,value}=original(JSON.stringify(b));await assert.rejects(()=>verifyOriginal(value,caseId,source,subject));}
 const{source,value}=original('{}');await assert.rejects(()=>verifyOriginal(value,caseId,source,subject));
});
test('text reports keep the existing exact case and newline validation, including laboratory reports',async()=>{
 const text='OI-SYNTHETIC-REPORT/1\nPatient: '+caseId+'\nDocument: FICTIONAL-REPORT-A\nType: laboratory\nEvent-Date: 2026-04-03\nIssued-At: 2026-04-04\n';
 const {source,value}=original(text);assert.equal((await verifyOriginal(value,caseId,source)).original_text,text);
 for(const invalid of [text.replaceAll('\n','\r\n'),text.replace(caseId,'CASE-OTHER'),'\uFEFF'+text]){
  const{source,value}=original(invalid);await assert.rejects(()=>verifyOriginal(value,caseId,source,subject));
 }
});
