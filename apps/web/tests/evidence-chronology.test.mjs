import {test} from 'node:test';
import assert from 'node:assert/strict';
import {decodeEvidencePacket,decodeEvidenceReport} from '../.test-dist/authored-evidence.js';
import {decodeQuestionEvidenceLinks} from '../.test-dist/question-evidence-view.js';
import {packet,question,report,reportId,hash,signPacket,patientId,caseId,questionId} from './authored-evidence-fixtures.mjs';

// Calendar and clock expectations are hand-authored, independent of Date.parse.
const invalid=[
 '2026-02-30T12:00:00Z','2026-02-29T12:00:00Z','1900-02-29T12:00:00Z',
 '2026-04-31T12:00:00Z','0000-01-01T00:00:00Z','2026-00-10T12:00:00Z',
 '2026-13-01T12:00:00Z','2026-11-00T12:00:00Z',
 '2026-11-03T24:00:00Z','2026-11-03T23:60:00Z','2026-11-03T23:59:60Z',
 '2026-11-03T12:00:00+24:00','2026-11-03T12:00:00+05:99',
 '2026-11-03T12:00:00Z\n','2026-11-03\u202812:00:00Z',
 '2026-11-03t12:00:00Z','2026-11-03T12:00:00z','2026-11-03T12:00:00',
];
const valid=[
 '2026-11-03T12:00:00Z','2024-02-29T23:59:59.123456+05:30',
 '2000-02-29T00:00:00-04:00','0001-01-01T00:00:00+23:59',
 '0099-12-31T23:59:59-23:59','9999-12-31T23:59:59.000001Z',
];
const authoredOnly=['2026-11-03T12:00Z','2026-11-03T12:00:00.1234567Z'];
const links=created_at=>({
 contract:'oi.pg-question-evidence-links/1',patient_id:patientId,case_id:caseId,question_id:questionId,
 source_context_state:'current_unreviewed_question',source_access_receipt_id:'ACCESS-'+'F'.repeat(32),
 synthetic:true,model_executed:false,content_appraised:false,clinical_approval:false,
 links:[{link_id:'EVIDENCE-LINK-'+'E'.repeat(32),citation:'FICT-HISTORY@1',metadata_sha256:'d'.repeat(64),
  created_at,actor_label:'FICT-AUTHOR',status:'rights_restricted',record:null}],
});

for(const [name,change] of [
 ['evidence creation',(p,t)=>{p.evidence[0].created_at=t;}],
 ['comparison creation',(p,t)=>{p.assessments[0].created_at=t;}],
 ['report preparation',(p,t)=>{p.reports[0].prepared_at=t;}],
]){
 test(`${name} rejects impossible chronology even with a recomputed packet digest`,async()=>{
  for(const time of invalid){
   const p=packet();change(p,time);
   await assert.rejects(()=>decodeEvidencePacket(signPacket(p),question()),undefined,time);
  }
 });
}

test('report and withheld history reject invalid preparation times without relying on a cached summary',async()=>{
 for(const time of invalid){
  const r=report();r.prepared_at=time;r.snapshot.prepared_at=time;r.snapshot_sha256=hash(r.snapshot);
  await assert.rejects(()=>decodeEvidenceReport(r,question(),reportId),undefined,time);
  await assert.rejects(()=>decodeEvidenceReport({...r,state:'content_withheld',body:null,snapshot:null},question(),reportId),undefined,time);
 }
});

test('frozen report comparisons validate their own evidence and assessment timestamps',async()=>{
 for(const field of ['evidence','assessment'])for(const time of invalid){
  const r=report();r.snapshot.comparisons[0][field].created_at=time;r.snapshot_sha256=hash(r.snapshot);
  await assert.rejects(()=>decodeEvidenceReport(r,question(),reportId),undefined,field+': '+time);
 }
});

test('citation chronology matches its stricter API format even when content is withheld',()=>{
 for(const time of [...invalid,...authoredOnly]){
  assert.throws(()=>decodeQuestionEvidenceLinks(links(time),patientId,caseId,questionId),undefined,time);
 }
});

test('valid calendar dates, fractional precision and offsets survive decoding verbatim',async()=>{
 for(const time of [...valid,...authoredOnly]){
  const p=packet();p.evidence[0].created_at=time;p.assessments[0].created_at=time;p.reports[0].prepared_at=time;
  const got=await decodeEvidencePacket(signPacket(p),question());
  assert.equal(got.evidence[0].created_at,time);assert.equal(got.assessments[0].created_at,time);assert.equal(got.reports[0].prepared_at,time);
  const r=report();r.prepared_at=time;r.snapshot.prepared_at=time;r.snapshot_sha256=hash(r.snapshot);
  const decoded=await decodeEvidenceReport(r,question(),reportId);
  assert.equal(decoded.prepared_at,time);assert.equal(decoded.snapshot.prepared_at,time);
  assert.equal(decoded.body,r.body);assert.equal(decoded.snapshot_sha256,r.snapshot_sha256);
 }
 for(const time of valid)assert.equal(decodeQuestionEvidenceLinks(links(time),patientId,caseId,questionId).links[0].created_at,time);
});

test('packet and frozen-report questions reject impossible dates even when their expected identity matches',async()=>{
 for(const time of invalid){
  const expected={...question(),created_at:time},p=packet();p.question=expected;
  await assert.rejects(()=>decodeEvidencePacket(signPacket(p),expected),undefined,time);
  const r=report();r.snapshot.question=expected;r.snapshot_sha256=hash(r.snapshot);
  await assert.rejects(()=>decodeEvidenceReport(r,expected,reportId),undefined,time);
 }
});

test('evidence issue and selected-source dates reject year zero as well as calendar rollover',async()=>{
 for(const day of ['0000-01-01','2026-02-30']){
  const p=packet();p.evidence[0].issued_at=day;
  await assert.rejects(()=>decodeEvidencePacket(signPacket(p),question()),undefined,day);
  for(const change of [
   r=>{r.snapshot.comparisons[0].evidence.issued_at=day;},
   r=>{r.snapshot.selected_source.issued_at=day;},
   r=>{r.snapshot.selected_source.event_date=day;},
  ]){
   const r=report();change(r);r.snapshot_sha256=hash(r.snapshot);
   await assert.rejects(()=>decodeEvidenceReport(r,question(),reportId),undefined,day);
  }
 }
});
