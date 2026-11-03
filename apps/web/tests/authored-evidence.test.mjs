import {test} from 'node:test';
import assert from 'node:assert/strict';
import {decodeEvidencePacket,decodeEvidenceReport,decodeEvidenceOriginal,declaredPermissions,visibleLine} from '../.test-dist/authored-evidence.js';
import {packet,question,patientId,caseId,evidence,assessment,report,reportId,evidenceId,original,hash,signPacket,permissions} from './authored-evidence-fixtures.mjs';

test('fictional evidence packet preserves exact Unicode quote position and independent content permissions',async()=>{
 const got=await decodeEvidencePacket(packet(),question());
 assert.equal(got.evidence[0].content_item,'abstract');
 assert.equal(got.assessments[0].quote_start,12);
 assert.equal(got.evidence[0].permissions.full_text.display,'unknown');
 assert.equal(got.evidence[0].permissions.abstract.ml_use,'unknown');
 assert.ok(Object.isFrozen(got)&&Object.isFrozen(got.evidence)&&Object.isFrozen(got.evidence[0].permissions.abstract));
});

test('forged packet shape, digest, scope, rights or quote anchor is refused even if attacker rehashes it',async()=>{
 const mutations=[p=>p.extra=true,p=>p.patient_id='PAT-OTHER',p=>p.question.question_id='QUESTION-'+'B'.repeat(32),p=>p.question.preflight_sha256='f'.repeat(64),p=>p.model_executed=true,p=>p.evidence.push({...evidence()}),p=>p.evidence[0].permissions.abstract.display='denied',p=>p.evidence[0].rights_sha256='f'.repeat(64),p=>p.evidence[0].content_item='figures',p=>p.assessments[0].quote_start=13,p=>p.assessments[0].quote='invented excerpt',p=>p.assessments[0].evidence_id='EVIDENCE-'+'B'.repeat(32),p=>p.assessments[0].applicability='not_applicable',p=>p.assessments[0].source_snapshot_sha256='f'.repeat(64),p=>p.assessments[0].state='clinically_approved',p=>p.reports[0].question_id='QUESTION-'+'B'.repeat(32)];
 for(const mutate of mutations){const p=packet();mutate(p);await assert.rejects(()=>decodeEvidencePacket(signPacket(p),question()));}
 await assert.rejects(()=>decodeEvidencePacket({...packet(),packet_sha256:'f'.repeat(64)},question()));
});

test('withheld evidence never carries an excerpt or rationale and stale questions never promote current assessments',async()=>{
 const p=packet();p.evidence[0].state='withdrawn';p.evidence[0].title=null;p.evidence[0].statement=null;p.assessments[0].state='content_withheld';p.assessments[0].quote=null;p.assessments[0].quote_start=null;p.assessments[0].rationale=null;
 assert.equal((await decodeEvidencePacket(signPacket(p),question())).assessments[0].quote,null);
 p.assessments[0].rationale='A hidden forbidden excerpt remains here.';
 await assert.rejects(()=>decodeEvidencePacket(signPacket(p),question()));
 const stale=packet();stale.question.source_context_state='source_reassessment_required';stale.source_snapshot_sha256='e'.repeat(64);
 await assert.rejects(()=>decodeEvidencePacket(signPacket(stale),question()));
 stale.assessments[0].state='reassessment_required';stale.reports[0].state='historical_reassessment_required';
 assert.equal((await decodeEvidencePacket(signPacket(stale),question())).question.source_context_state,'source_reassessment_required');
});

test('report validates immutable question/source/evidence snapshots and body hashes independently',async()=>{
 const r=report();assert.equal((await decodeEvidenceReport(r,question(),reportId)).body,r.body);
 for(const mutate of [v=>v.body+='altered',v=>v.snapshot.selected_source.line=9,v=>v.snapshot.comparisons[0].evidence.sha256='f'.repeat(64),v=>v.snapshot.comparisons[0].assessment.quote_start=13,v=>v.snapshot.prepared_at='2026-11-04T12:00:00Z',v=>v.snapshot.comparisons[0].evidence.permissions.abstract.redistribute='denied']){
  const bad=report();mutate(bad);bad.snapshot_sha256=hash(bad.snapshot);await assert.rejects(()=>decodeEvidenceReport(bad,question(),reportId));
 }
});

test('historical reports preserve original bytes while withdrawn reports carry only history metadata',async()=>{
 const historical={...report(),state:'historical_reassessment_required'};
 const stale={...question(),source_context_state:'source_reassessment_required'};
 assert.equal((await decodeEvidenceReport(historical,stale,reportId)).body,report().body);
 const withheld={...report(),state:'content_withheld',body:null,snapshot:null};
 assert.equal((await decodeEvidenceReport(withheld,question(),reportId)).body,null);
 await assert.rejects(()=>decodeEvidenceReport({...withheld,body:report().body},question(),reportId));
});

test('exact original validates UTF-8 bytes and source-scoped identity before download',async()=>{
 const v={contract:'oi.h1-evidence-original/1',patient_id:patientId,case_id:caseId,evidence_id:evidenceId,sha256:evidence().sha256,original_text:original,access_receipt_id:'ACCESS-'+'A'.repeat(32),synthetic:true};
 assert.equal((await decodeEvidenceOriginal(v,question(),evidence())).original_text,original);
 await assert.rejects(()=>decodeEvidenceOriginal({...v,original_text:original+'changed'},question(),evidence()));
 await assert.rejects(()=>decodeEvidenceOriginal({...v,evidence_id:'EVIDENCE-'+'B'.repeat(32)},question(),evidence()));
});

test('permission defaults are explicit only for metadata and the selected human-readable content class',()=>{
 assert.deepEqual(declaredPermissions('abstract','allowed','allowed'),permissions());
 const p=declaredPermissions('api_output','unknown','denied');
 assert.equal(p.api_output.store,'allowed');assert.equal(p.api_output.display,'unknown');assert.equal(p.api_output.redistribute,'denied');assert.equal(p.api_output.ml_use,'unknown');assert.equal(p.full_text.store,'unknown');
});

test('visible rationale rejects directional and Unicode line separators without rejecting ordinary Unicode text',()=>{
 for(const text of ['Fictional\u2028rationale remains unknown.','Fictional\u2029rationale remains unknown.','Fictional\u202erationale remains unknown.','Fictional\nrationale remains unknown.'])assert.equal(visibleLine(text),false);
 assert.equal(visibleLine('Fictional café 🧪 rationale remains uncertain.'),true);
});

test('an amendment declaring abstract rights cannot permit an earlier full-text quotation',async()=>{
 const p=packet();const old=p.evidence[0];old.content_item='full_text';old.permissions=structuredClone(old.permissions);old.permissions.full_text={...old.permissions.abstract};old.rights_sha256=hash(old.permissions);old.state='superseded';p.assessments[0].state='reassessment_required';p.assessments[0].rights_sha256=old.rights_sha256;
 const latest={...evidence(),evidence_id:'EVIDENCE-'+'B'.repeat(32),version:2};p.evidence.push(latest);p.reports[0].state='historical_reassessment_required';
 await assert.rejects(()=>decodeEvidencePacket(signPacket(p),question()));
 old.title=null;old.statement=null;p.assessments[0].state='content_withheld';p.assessments[0].quote=null;p.assessments[0].quote_start=null;p.assessments[0].rationale=null;
 assert.equal((await decodeEvidencePacket(signPacket(p),question())).evidence[0].statement,null);
});
