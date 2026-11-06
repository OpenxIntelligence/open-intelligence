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
