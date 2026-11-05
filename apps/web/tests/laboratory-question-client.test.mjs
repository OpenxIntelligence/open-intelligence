import test from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {readLabPreparation} from '../.test-dist/laboratory-question.js';
import {patient,caseId,projection} from './laboratory-projection-fixture.mjs';

const question='What does this source report about the specimen?', token='fictional_lab_preparation_token_00000000001';
const access='ACCESS-'+'D'.repeat(32);
const reply=(value,code=200)=>new Response(JSON.stringify(value),{status:code,headers:{'Content-Type':'application/json'}});
function prepared(w,o){
  return {contract:'oi.synthetic-laboratory-question-preflight/1',patient_id:patient,case_id:caseId,question,
    source_snapshot_contract:w.contract,source_snapshot_sha256:w.snapshot_fingerprint,synthetic:true,source_context_only:true,
    durable_question_created:false,durable_review_connected:false,biomedical_evidence_rights_verified:false,model_execution_authorized:false,
    clinical_approval:false,clinical_interpretation:'not_performed',terminology_validation:'not_performed',
    reassessment_policy:'revalidate_source_and_authority_before_any_future_write',access_receipt_id:access,preflight_sha256:'f'.repeat(64),
    selected_source:{anchor_kind:'fhir_observation',source_id:o.source_id,document_id:o.document_id,version:o.document_version,sha256:o.source_sha256,
      kind:'laboratory',resource_reference:o.observation_reference,specimen_reference:o.specimen_reference,specimen_type_text:o.specimen_type_text,
      specimen_collected_at:o.specimen_collected_at,report_reference:o.report_reference,loinc_code:o.loinc_code,effective_at:o.effective_at,
      issued_at:o.issued_at,status:o.status,value_text:o.value_text,unit_code:o.unit_code,absent_reason:o.absent_reason,
      source_reported:true,review_state:'not_established',clinical_review:'not_performed'}};
}
async function ready(onPost){
  const binding={case_id:caseId,patient_id:patient,source_organization:'ORG-A',source_system:'SYS-A',source_subject_ref:'SUBJECT-A',review_ref:'REVIEW-A',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false};
  const session=new RegistrySession(async(url,init)=>{
    if(init.method==='POST')return onPost(url,JSON.parse(init.body));
    if(url.endsWith('/world-model'))return reply(projection());
    if(url.endsWith('/case-bindings'))return reply({patient_id:patient,mappings:[binding],synthetic:true,source_identity_verified:false,clinical_sources_linked:false});
    return reply({patient_id:patient,origin_org:'ORG-A',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z'});
  });
  session.connect(token);await session.read(patient);await session.loadCases();await session.loadWorldModel(caseId);
  const world=session.snapshot().worldModel;assert.ok(world,session.snapshot().worldMessage);
  const item=world.laboratory_observations[0];
  return {session,world,item,send:(signal=new AbortController().signal)=>session.prepareLabQuestion(world,item.source_id,item.observation_reference,question,signal)};
}
test('submission sends only the selected source and local Observation; absent results require the exact original reason',async()=>{
  let count=0;
  const f=await ready((url,payload)=>{
    count++;assert.ok(url.endsWith('/composer/laboratory-preflight'));
    assert.deepEqual(payload,{synthetic:true,source_id:f.item.source_id,observation_reference:f.item.observation_reference,question,expected_source_snapshot_sha256:f.world.snapshot_fingerprint});
    return reply(prepared(f.world,f.item));
  });
  assert.equal(count,0);assert.equal((await f.send()).receipt,access);assert.equal(count,1);
  const absent=f.world.laboratory_observations.find(o=>o.value_text===null),p=prepared(f.world,absent);
  assert.equal(readLabPreparation(p,f.world,absent,question).receipt,access);
  for(const partial of [{absent_reason:'unknown'},{value_text:'0'},{specimen_reference:'Specimen/Other'},{resource_reference:f.item.observation_reference},{line:1}]){
    assert.throws(()=>readLabPreparation({...p,selected_source:{...p.selected_source,...partial}},f.world,absent,question));
  }
});
test('denied, changed-source and contradictory receipts withhold the preview and clear the current world',async()=>{
  for(const mode of ['deny','stale','claim','wrong patient','changed value']){
    const f=await ready(()=>{const p=prepared(f.world,f.item);
      if(mode==='claim')p.clinical_approval=true;
      if(mode==='wrong patient')p.patient_id='PAT-OTHER';
      if(mode==='changed value')p.selected_source.value_text='1';
      return reply(p,mode==='deny'?404:mode==='stale'?409:200);});
    assert.equal(await f.send(),null,mode);assert.equal(f.session.snapshot().worldModel,null,mode);
  }
});
test('late success or denial cannot cross a draft edit, disconnect, or fresh read of the same case',async()=>{
  for(const action of ['edit','disconnect','refresh'])for(const status of [200,404]){
    let release;const wait=new Promise(r=>{release=r;});
    const f=await ready(()=>wait);const control=new AbortController();const pending=f.send(control.signal);
    if(action==='edit')control.abort();else if(action==='disconnect')f.session.disconnect();else await f.session.loadWorldModel(caseId);
    const after=f.session.snapshot().worldModel;
    release(reply(prepared(f.world,f.item),status));assert.equal(await pending,null,action);
    assert.equal(f.session.snapshot().worldModel,after,action);
  }
});
test('world datetime and preflight string use equivalent UTC spellings without losing microseconds or date roles',()=>{
  const w=projection(), o={...w.laboratory_observations[0],effective_at:'2026-04-03T13:05:00.123456Z',
    specimen_collected_at:'2026-04-03T13:05:00.123455Z'}, p=prepared(w,o);
  for(const k of ['issued_at','effective_at','specimen_collected_at'])p.selected_source[k]=o[k].replace(/Z$/,'+00:00');
  assert.equal(readLabPreparation(p,w,o,question).receipt,access);
  for(const fields of [{issued_at:o.issued_at.replace(/Z$/,'-00:00')},{effective_at:p.selected_source.specimen_collected_at},
    {specimen_collected_at:p.selected_source.effective_at},{effective_at:o.effective_at.replace(/Z$/,'+01:00')}]){
    assert.throws(()=>readLabPreparation({...p,selected_source:{...p.selected_source,...fields}},w,o,question));
  }
});
