import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {downloadEvidenceReport} from '../.test-dist/authored-evidence.js';
import {ready,transportFor,response,packet,questionId,patientId,caseId,reportId,report,digest,deferred} from './authored-evidence-fixtures.mjs';

const bodySeparator='--- BEGIN PRESERVED REPORT BODY ---\n';

async function captureDownload(run){
 const savedDocument=globalThis.document,savedCreate=URL.createObjectURL,savedRevoke=URL.revokeObjectURL;
 const blobs=[],links=[];
 globalThis.document={body:{append(){}},createElement(){const link={click(){links.push({name:this.download,href:this.href});},remove(){}};return link;}};
 URL.createObjectURL=blob=>{blobs.push(blob);return 'blob:fictional-report';};
 URL.revokeObjectURL=()=>{};
 try{await run();return {blobs,links};}
 finally{globalThis.document=savedDocument;URL.createObjectURL=savedCreate;URL.revokeObjectURL=savedRevoke;}
}

for(const status of ['current_unreviewed','historical_reassessment_required']){
 test(`download carries fresh ${status} status and receipt while preserving original Unicode body`,async()=>{
  const original=report();original.body+='Literal café 🧪 quotation.\n';original.body_sha256=digest(original.body);
  const inspected=packet();inspected.reports[0].body_sha256=original.body_sha256;
  const fresh={...original,state:status,access_receipt_id:'ACCESS-'+'B'.repeat(32)};
  let reads=0;
  const s=new RegistrySession(transportFor(url=>response(url.includes('/evidence-reports/')?(++reads===1?original:fresh):inspected)));
  await ready(s);await s.loadQuestionEvidence(questionId);await s.readEvidenceReport(questionId,reportId);
  const {blobs,links}=await captureDownload(()=>downloadEvidenceReport(s,questionId,reportId));
  assert.equal(reads,2,'download must authorize a fresh read');assert.equal(blobs.length,1);assert.equal(links.length,1);
  const text=await blobs[0].text();
  assert.ok(text.startsWith('OPEN INTELLIGENCE — EVIDENCE REPORT DOWNLOAD\n'));
  const split=text.indexOf(bodySeparator);assert.ok(split>0);const cover=text.slice(0,split),body=text.slice(split+bodySeparator.length);
  assert.ok(cover.includes(status==='current_unreviewed'?'CURRENT — UNREVIEWED':'HISTORICAL — REASSESSMENT REQUIRED'));
  for(const value of [patientId,caseId,questionId,reportId,fresh.prepared_at,fresh.access_receipt_id,original.body_sha256,original.snapshot_sha256])assert.ok(cover.includes(value),value);
  assert.ok(!cover.includes(original.access_receipt_id),'cached receipt cannot label the fresh export');
  assert.ok(cover.includes(`Original body UTF-8 bytes: ${Buffer.byteLength(original.body)}`));
  assert.equal(body,original.body);assert.equal(digest(body),original.body_sha256);
  assert.equal(s.snapshot().evidenceReport.body,original.body,'download does not rewrite stored/decoded report');
 });
}

test('fresh withholding and export denial never turn a cached report into a downloadable cover or body',async()=>{
 for(const denied of [response({...report(),state:'content_withheld',body:null,snapshot:null}),response({detail:'unavailable'},403),response({detail:'unavailable'},404)]){
  let reads=0;
  const s=new RegistrySession(transportFor(url=>url.includes('/evidence-reports/')?(++reads===1?response(report()):denied):response(packet())));
  await ready(s);await s.loadQuestionEvidence(questionId);await s.readEvidenceReport(questionId,reportId);
  const {blobs,links}=await captureDownload(()=>downloadEvidenceReport(s,questionId,reportId));
  assert.equal(reads,2);assert.equal(blobs.length,0);assert.equal(links.length,0);
 }
});

test('patient change during fresh report read discards the download and its status',async()=>{
 const waiting=deferred();const s=new RegistrySession(transportFor(url=>url.includes('/evidence-reports/')?waiting.promise:response(packet())));
 await ready(s);await s.loadQuestionEvidence(questionId);
 const {blobs,links}=await captureDownload(async()=>{
  const downloading=downloadEvidenceReport(s,questionId,reportId);
  await s.read('PAT-EXAMPLE-002');waiting.resolve(response(report()));await downloading;
 });
 assert.equal(blobs.length,0);assert.equal(links.length,0);assert.equal(s.snapshot().evidenceReport,null);
});
