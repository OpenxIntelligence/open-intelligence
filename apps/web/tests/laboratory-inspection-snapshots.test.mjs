import assert from 'node:assert/strict';
import test from 'node:test';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {snapshotHistory,snapshotReceipt,reopenedSnapshot} from '../.test-dist/laboratory-inspection-snapshots.js';
import {caseId,patient,projection} from './laboratory-projection-fixture.mjs';

const model=projection(),obs=model.laboratory_observations[0],qid='QUESTION-'+'A'.repeat(32),snapshotId='LAB-SNAPSHOT-'+'C'.repeat(32);
const digest='b'.repeat(64),grant='ACCESS-'+'D'.repeat(32),state='current_unreviewed_question';
const anchor={source_id:obs.source_id,source_version:obs.document_version,source_sha256:obs.source_sha256,
  observation_reference:obs.observation_reference,source_snapshot_sha256:model.snapshot_fingerprint,preflight_sha256:'e'.repeat(64)};
const q={...anchor,question_id:qid,question:'What did the fictional original report?',source_context_state:state};
const citations={patient_id:patient,case_id:caseId,question_id:qid,question_anchor:anchor,source_context_state:state,
  source_access_receipt_id:grant,synthetic:true,model_executed:false,content_appraised:false,clinical_approval:false,
  contract:'oi.pg-question-evidence-links/1',links:[]};
const result={source_id:obs.source_id,sha256:obs.source_sha256,version:obs.document_version,document_id:obs.document_id,
  resource_reference:obs.observation_reference,report_reference:obs.report_reference,specimen_reference:obs.specimen_reference,
  specimen_type_text:obs.specimen_type_text,specimen_collected_at:obs.specimen_collected_at,effective_at:obs.effective_at,
  issued_at:obs.issued_at,loinc_code:obs.loinc_code,status:obs.status,value_text:obs.value_text,unit_code:obs.unit_code,
  absent_reason:obs.absent_reason,source_reported:true,clinical_review:'not_performed',review_state:'not_established',anchor_kind:'fhir_observation',kind:'laboratory'};
const report={contract:'oi.laboratory-source-citation-inspection/2',report_sha256:digest,question:q.question,
  reported_result:result,citations,clinical_review:'not_performed',claim_appraisal:'not_performed'};
const row={snapshot_id:snapshotId,captured_report_sha256:digest,captured_at:'2026-04-10T10:00:00.123456+00:00',
  citation_count:0,captured_source_context_state:state};
const list={patient_id:patient,case_id:caseId,question_id:qid,source_access_receipt_id:grant,snapshots:[row]};
const receipt=duplicate=>({snapshot_id:snapshotId,captured_report_sha256:digest,duplicate});
const sig=()=>new AbortController().signal;
const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});
const urlBase='/v1/patients/'+patient+'/cases/'+caseId+'/composer/laboratory-questions/'+qid+'/source-citation-report';
async function setup(handle){
  const binding={case_id:caseId,patient_id:patient,source_organization:'ORG-A',source_system:'SYS-A',source_subject_ref:'SUBJECT-A',
    review_ref:'REVIEW-A',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false};
  const s=new RegistrySession((url,init)=>{
    if(url.endsWith('/versioned'))return reply(report);
    if(url.startsWith(urlBase+'/snapshots'))return handle(url.slice(urlBase.length),init);
    if(url.endsWith('/composer/laboratory-questions'))return reply({patient_id:patient,case_id:caseId,access_receipt_id:grant,questions:[q]});
    if(url.endsWith('/evidence-links'))return reply(citations);
    if(url.endsWith('/world-model'))return reply(model);
    if(url.endsWith('/case-bindings'))return reply({patient_id:patient,mappings:[binding],synthetic:true,source_identity_verified:false,clinical_sources_linked:false});
    return reply({patient_id:patient,origin_org:'ORG-A',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z'});
  });
  s.connect('fictional_snapshot_recovery_token_00000000001');
  await reauthorize(s);
  return s;
}
async function reauthorize(s){await s.read(patient);await s.loadCases();await s.loadWorldModel(caseId);await s.loadLabQuestions(s.snapshot().worldModel);}
test('capture needs the actual current live report; history reopens only its selected receipt',async()=>{
  let posts=0,gets=0;
  const s=await setup((path,i)=>{
    if(i.method==='POST'){
      posts++;assert.equal(path,'/snapshots');const {request_key,...cmd}=JSON.parse(i.body);
      assert.match(request_key,/^[a-f0-9-]{36}$/);assert.deepEqual(cmd,{synthetic:true,expected_report_sha256:digest});
      return reply(receipt(false),201);
    }
    gets++;return path==='/snapshots'?reply(list):reply({snapshot:row,inspection:report});
  });
  const live=await s.readLaboratoryCitationReport(qid,sig());
  await assert.rejects(s.captureLaboratorySnapshot(qid,{...live.report},sig()));assert.equal(posts,0);
  const saved=await s.captureLaboratorySnapshot(qid,live.report,sig());
  assert.equal(saved.receipt.snapshot_id,snapshotId);assert.equal(s.laboratorySnapshotWritePhase(qid),'idle');
  const records=await s.listLaboratorySnapshots(qid,sig()),selected=records.snapshots[0];
  await assert.rejects(s.reopenLaboratorySnapshot(qid,{...selected},sig()));
  assert.equal(gets,1);
  const reopened=await s.reopenLaboratorySnapshot(qid,selected,sig());
  assert.equal(reopened.snapshot.snapshot_id,snapshotId);assert.equal(reopened.report.result.value_text,'0');
  await assert.rejects(s.captureLaboratorySnapshot(qid,reopened.report,sig()));
  assert.equal(posts,1);assert.equal(gets,2);
});
test('lost and in-flight saves recover the exact command after a same-patient authority recheck',async()=>{
  for(const mode of ['lost','in-flight']){
    let release;const writes=[];
    const s=await setup((_path,i)=>{
      writes.push(i.body);if(writes.length===1){if(mode==='lost')return reply({},503);return new Promise(r=>release=r);}
      return reply(receipt(true));
    });
    const live=await s.readLaboratoryCitationReport(qid,sig());
    const original=s.captureLaboratorySnapshot(qid,live.report,sig());
    if(mode==='lost')await assert.rejects(original);
    assert.equal(s.laboratorySnapshotWritePhase(qid),mode==='lost'?'unknown':'saving');
    await reauthorize(s);assert.equal(s.laboratorySnapshotWritePhase(qid),'unknown');
    const recovered=await s.captureLaboratorySnapshot(qid,null,sig());
    assert.equal(recovered.receipt.duplicate,true);assert.deepEqual(writes,[writes[0],writes[0]]);
    if(release){release(reply({},404));await assert.rejects(original);assert.equal(s.snapshot().patient.patient_id,patient);}
    assert.equal(s.laboratorySnapshotWritePhase(qid),'idle');
  }
});
test('a later fresh read invalidates earlier selections and late errors without clearing the new scope',async()=>{
  let release;const s=await setup(path=>path==='/snapshots'?reply(list):new Promise(r=>release=r));
  const {snapshots:[selected]}=await s.listLaboratorySnapshots(qid,sig());
  const open=s.reopenLaboratorySnapshot(qid,selected,sig());
  const fresh=await s.readLaboratoryCitationReport(qid,sig());release(reply({},404));await assert.rejects(open);
  assert.equal(s.snapshot().patient.patient_id,patient);assert.equal(fresh.generation,s.snapshot().evidenceGeneration);
  await assert.rejects(s.reopenLaboratorySnapshot(qid,selected,sig()));
});
test('changed report rejects capture; explicit denial purges its scope and pending retry',async()=>{
  for(const code of [409,404]){
    let posts=0;const s=await setup(()=>{posts++;return reply({},posts===1?503:code);});
    const {report:live}=await s.readLaboratoryCitationReport(qid,sig());
    await assert.rejects(s.captureLaboratorySnapshot(qid,live,sig()));
    await assert.rejects(s.captureLaboratorySnapshot(qid,null,sig()));
    assert.equal(s.laboratorySnapshotWritePhase(qid),'idle');
    if(code===404)assert.equal(s.snapshot().patient,null);
    await assert.rejects(s.captureLaboratorySnapshot(qid,null,sig()));assert.equal(posts,2);
  }
});
test('history refuses duplicate identifiers, wrong scope, unsupported states and inconsistent receipt identity',()=>{
  for(const bad of [{...list,patient_id:'other'},{...list,case_id:'other'},{...list,question_id:'other'},
    {...list,snapshots:[row,row]},{...list,snapshots:[{...row,citation_count:-1}]},
    {...list,snapshots:[{...row,captured_source_context_state:'approved'}]},
    {...list,snapshots:[{...row,captured_report_sha256:digest+'\n'}]}])assert.throws(()=>snapshotHistory(bad,model,q));
  assert.throws(()=>snapshotReceipt(receipt(false),digest,200));assert.throws(()=>snapshotReceipt(receipt(true),'a'.repeat(64),200));
});

test('an amended source and withdrawn display rights retain the captured identity without restoring its old citation title',()=>{
  const historical={...model,current_sources:[],laboratory_observations:[],history:[{...model.current_sources[0],state:'superseded'}]};
  const saved={...q,source_context_state:'source_reassessment_required'},summary={...row,citation_count:1};
  const link={link_id:'EVIDENCE-LINK-'+'F'.repeat(32),citation:'FICT-LAB-RECORD@1',metadata_sha256:'a'.repeat(64),
    actor_label:'ACTOR-SYNTHETIC',created_at:'2026-04-10T10:00:00Z',status:'rights_restricted',record:null};
  const inspection={...report,report_sha256:'1'.repeat(64),citations:{...citations,source_context_state:saved.source_context_state,links:[link]}};
  const wire={snapshot:summary,inspection};
  const reopened=reopenedSnapshot(wire,summary,historical,saved);
  assert.equal(reopened.snapshot.captured_report_sha256,digest);
  assert.equal(reopened.report.report_sha256,inspection.report_sha256);
  assert.equal(reopened.report.result.value_text,'0');
  assert.equal(reopened.report.citations.links[0].record,null);
  const disclosed={...inspection,citations:{...inspection.citations,links:[{...link,record:{title:'Previously visible'}}]}};
  for(const forged of [{...wire,inspection:disclosed},{...wire,snapshot:{...summary,citation_count:2}},
      {...wire,snapshot:{...summary,captured_report_sha256:'1'.repeat(64)}}])assert.throws(()=>reopenedSnapshot(forged,summary,historical,saved));
});

const fingerprint='f'.repeat(64),rid='REVIEW-'+'1'.repeat(32);
const reviewQueue={contract:'oi.laboratory-inspection-review-returns/1',patient_id:patient,case_id:caseId,question_id:qid,
 snapshot_id:snapshotId,captured_report_sha256:digest,current_report_sha256:digest,source_context_state:state,
 queue_fingerprint:fingerprint,source_access_receipt_id:grant,review_state:'awaiting_independent_verification',
 current_return_receipt_id:null,return_count:0,prior_return_count:0,receipts:[],synthetic:true,clinical_approval:false,
 reviewer_identity_verified:false,external_notification_sent:false};
const returned=duplicate=>({receipt_id:rid,question_id:qid,snapshot_id:snapshotId,duplicate});
const reason='Please independently verify this fictional laboratory report.';
async function reviewSetup(handle){return setup((path,init)=>path.endsWith('/review-returns')?handle(path,init):
 reply(path==='/snapshots'?list:{snapshot:row,inspection:report}));}
async function openReview(s){const {snapshots:[selected]}=await s.listLaboratorySnapshots(qid,sig());
 const opened=await s.reopenLaboratorySnapshot(qid,selected,sig());
 return s.readLaboratoryReviewReturns(qid,opened,sig());}
test('inspection verification return requires actually reopened scope and current checked history',async()=>{
 const writes=[];const s=await reviewSetup((_path,init)=>{if(init.method!=='POST')return reply(reviewQueue);
 writes.push(init.body);return reply(returned(false),201);});
 const {snapshots:[selected]}=await s.listLaboratorySnapshots(qid,sig());
 const opened=await s.reopenLaboratorySnapshot(qid,selected,sig());
 await assert.rejects(s.readLaboratoryReviewReturns(qid,{...opened},sig()));
 const checked=await s.readLaboratoryReviewReturns(qid,opened,sig());
 assert.equal(checked.generation,s.snapshot().evidenceGeneration);
 await assert.rejects(s.returnLaboratoryInspection(qid,{...checked},reason,sig()));
 await assert.rejects(s.returnLaboratoryInspection(qid,checked,'short',sig()));
 const result=await s.returnLaboratoryInspection(qid,checked,reason,sig());
 assert.equal(result.receipt.receipt_id,rid);assert.equal(s.laboratoryReviewWritePhase(qid),'idle');
 const {request_key,...body}=JSON.parse(writes[0]);assert.match(request_key,/^[a-f0-9-]{36}$/);
 assert.deepEqual(body,{synthetic:true,expected_queue_fingerprint:fingerprint,
 expected_captured_report_sha256:digest,expected_report_sha256:digest,reason});
});
test('ambiguous review return retries exact intent after reauthorization and discards late scope errors',async()=>{
 for(const mode of ['lost','in-flight']){
  let release;const writes=[];const s=await reviewSetup((_p,i)=>{
   if(i.method!=='POST')return reply(reviewQueue);writes.push(i.body);
   if(writes.length===1)return mode==='lost'?reply({},503):new Promise(r=>release=r);
   return reply(returned(true));
  });
  const checked=await openReview(s),original=s.returnLaboratoryInspection(qid,checked,reason,sig());
  if(mode==='lost')await assert.rejects(original);
  assert.equal(s.laboratoryReviewWritePhase(qid),mode==='lost'?'unknown':'saving');
  await reauthorize(s);assert.equal(s.laboratoryReviewWritePhase(qid),'unknown');
  const recovered=await s.returnLaboratoryInspection(qid,null,'',sig());
  assert.equal(recovered.receipt.duplicate,true);assert.deepEqual(writes,[writes[0],writes[0]]);
  if(release){release(reply({},404));await assert.rejects(original);assert.equal(s.snapshot().patient.patient_id,patient);}
  assert.equal(s.laboratoryReviewWritePhase(qid),'idle');
 }
});
test('changed opened digest and contradictory return history never authorize a return',async()=>{
 for(const bad of [{...reviewQueue,current_report_sha256:'a'.repeat(64)},
  {...reviewQueue,snapshot_id:'LAB-SNAPSHOT-'+'2'.repeat(32)},
  {...reviewQueue,clinical_approval:true},{...reviewQueue,return_count:1},
  {...reviewQueue,review_state:'returned_for_independent_verification'},
  {...reviewQueue,current_return_receipt_id:rid}]){
   const s=await reviewSetup(()=>reply(bad));await assert.rejects(openReview(s));
 }
});
test('review denials clear pending intent, and disconnect cannot recover it',async()=>{
 for(const code of [403,409]){
  let count=0;const s=await reviewSetup((_p,i)=>i.method!=='POST'?reply(reviewQueue):reply({},++count===1?503:code));
  const opened=await openReview(s);await assert.rejects(s.returnLaboratoryInspection(qid,opened,reason,sig()));
  await assert.rejects(s.returnLaboratoryInspection(qid,null,'',sig()));
  assert.equal(s.laboratoryReviewWritePhase(qid),'idle');
  await assert.rejects(s.returnLaboratoryInspection(qid,null,'',sig()));assert.equal(count,2);
 }
 const s=await reviewSetup((_p,i)=>reply(i.method==='POST'?{}:reviewQueue,i.method==='POST'?503:200));
 const checked=await openReview(s);await assert.rejects(s.returnLaboratoryInspection(qid,checked,reason,sig()));
 s.disconnect();s.connect('fictional_snapshot_recovery_token_00000000001');await reauthorize(s);
 await assert.rejects(s.returnLaboratoryInspection(qid,null,'',sig()));
});

test('earlier and current requests keep captured and reopened hashes separate without clearing reassessment',async()=>{
 const {inspectionReview}=await import('../.test-dist/laboratory-review-returns.js');
 const old={receipt_id:rid,question_id:qid,snapshot_id:snapshotId,captured_report_sha256:digest,report_sha256:digest,
  source_context_state:state,queue_fingerprint:fingerprint,actor_label:'ACTOR-FICTIONAL',action:'returned',reason,
  created_at:row.captured_at,clinical_approval:false,reviewer_identity_verified:false,external_notification_sent:false};
 const newer={...old,receipt_id:'REVIEW-'+'2'.repeat(32),report_sha256:'1'.repeat(64),
  source_context_state:'source_reassessment_required',queue_fingerprint:'2'.repeat(64)};
 const opened={snapshot:row,report:{report_sha256:newer.report_sha256,citations:{...citations,source_context_state:newer.source_context_state}},generation:1};
 const wire={...reviewQueue,current_report_sha256:newer.report_sha256,source_context_state:newer.source_context_state,
  queue_fingerprint:newer.queue_fingerprint,review_state:'source_reassessment_required',current_return_receipt_id:newer.receipt_id,
  return_count:1,prior_return_count:1,receipts:[old,newer]};
 const parsed=inspectionReview(wire,opened);assert.equal(parsed.review_state,'source_reassessment_required');
 assert.equal(parsed.receipts[0].report_sha256,digest);assert.equal(parsed.receipts[1].report_sha256,newer.report_sha256);
 for(const bad of [{...wire,review_state:'returned_for_independent_verification'},
  {...wire,receipts:[old,{...newer,report_sha256:digest}]},
  {...wire,receipts:[old,{...newer,clinical_approval:true}]},
  {...wire,receipts:[old,{...newer,reason:'unsafe\u202etext'}]},
  {...wire,current_return_receipt_id:old.receipt_id},
  {...wire,receipts:[old,old,newer],prior_return_count:2}])assert.throws(()=>inspectionReview(bad,opened));
});
test('fresh inspection reads invalidate previous checked return context and late replies',async()=>{
 let release;let reads=0;const s=await reviewSetup(()=>++reads===1?reply(reviewQueue):new Promise(r=>release=r));
 const checked=await openReview(s);await s.readLaboratoryCitationReport(qid,sig());
 await assert.rejects(s.returnLaboratoryInspection(qid,checked,reason,sig()));
 const pending=openReview(s);await new Promise(r=>setImmediate(r));
 const fresh=await s.readLaboratoryCitationReport(qid,sig());release(reply({},404));
 await assert.rejects(pending);assert.equal(s.snapshot().patient.patient_id,patient);
 assert.equal(fresh.generation,s.snapshot().evidenceGeneration);
});
