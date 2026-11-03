import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {parseSourceWorldModel} from '../.test-dist/source-world-model.js';

const token='fictional_test_credential_000000000001';
const patientId='PAT-EXAMPLE-001', caseId='CASE-ALPHA', sourceId='SRC-'+'A'.repeat(32);
const response=(v,status=200)=>new Response(JSON.stringify(v),{status,headers:{'Content-Type':'application/json'}});
const patient=(id=patientId)=>({patient_id:id,origin_org:'FICT-ORG',status:'active',
  revision:1,created_at:'2026-11-02T10:00:00Z'});
const caseList=()=>({patient_id:patientId,synthetic:true,source_identity_verified:false,
  clinical_sources_linked:false,mappings:[{
    case_id:caseId,patient_id:patientId,source_organization:'ORG-FICT',
    source_system:'FICT-API',source_subject_ref:'SUBJECT-SYNTH',review_ref:'REVIEW-SYNTH',
    status:'active',revision:1,created_at:'2026-11-02T10:00:00Z',revoked_at:null,
    source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false,
  }]});
const source=()=>({
  source_id:sourceId,document_id:'DOC-ONE',version:1,sha256:'b'.repeat(64),
  kind:'pathology',event_date:'2026-01-10',issued_at:'2026-01-11',
  received_at:'2026-11-02T10:00:00Z',specimen_id:'SPECIMEN-ONE',
  state:'current',supersedes_id:null,
});
const world=()=>({
  contract:'oi.pg-source-world-model/1',patient_id:patientId,case_id:caseId,synthetic:true,
  authority:'source_report_only_unreviewed',clinical_interpretation:false,
  research_review_invalidation_integrated:false,composer_execution_authorized:false,
  snapshot_fingerprint:'c'.repeat(64),as_of_received_at:'2026-11-02T10:00:00Z',
  summary:{current_sources:1,historical_sources:0,current_observations:1,
    unresolved_observations:1,source_disagreements:0},
  current_sources:[source()],history:[],
  observations:[{
    source_id:sourceId,document_id:'DOC-ONE',document_version:1,source_sha256:'b'.repeat(64),
    source_kind:'pathology',finding_key:'marker',reported_state:'not-reported',
    source_statement:'Fictional café <script>literal</script>.',source_line:8,
    specimen_id:'SPECIMEN-ONE',event_date:'2026-01-10',issued_at:'2026-01-11',
    review_state:'not_established',clinical_meaning:null,
  }],
  unresolved_refs:[{source_id:sourceId,source_line:8}],conflicts:[],
  limitations:['Independently fictional data only; no professional review or clinical interpretation.'],
});
const clone=x=>structuredClone(x);

test('strict source-world contract preserves original anchors without assigning clinical meaning',()=>{
  const m=parseSourceWorldModel(world(),patientId,caseId);
  assert.equal(m.patient_id,patientId);
  assert.equal(m.observations[0].source_id,sourceId);
  assert.equal(m.observations[0].source_line,8);
  assert.equal(m.observations[0].source_statement,'Fictional café <script>literal</script>.');
  assert.equal(m.observations[0].clinical_meaning,null);
  assert.equal(m.composer_execution_authorized,false);
  assert.equal(m.summary.unresolved_observations,1);
  assert.ok(Object.isFrozen(m));
});
test('cross-patient, forged clinical authority, hash/source mismatch and count fraud fail closed',()=>{
  for(const mutate of [
    m=>{m.patient_id='PAT-OTHER';},
    m=>{m.case_id='CASE-OTHER';},
    m=>{m.clinical_interpretation=true;},
    m=>{m.composer_execution_authorized=true;},
    m=>{m.research_review_invalidation_integrated=true;},
    m=>{m.authority='clinician_approved';},
    m=>{m.snapshot_fingerprint='not-a-fingerprint';},
    m=>{m.observations[0].source_id='SRC-'+'D'.repeat(32);},
    m=>{m.observations[0].source_sha256='f'.repeat(64);},
    m=>{m.observations[0].review_state='approved';},
    m=>{m.observations[0].clinical_meaning='diagnosis';},
    m=>{m.current_sources[0].state='superseded';},
    m=>{m.summary.unresolved_observations=0;},
    m=>{m.unresolved_refs=[];},
    m=>{m.observations[0].reported_state='negative';},
    m=>{m.conflicts=[{status:'unresolved_source_disagreement',
      specimen_id:'SPECIMEN-ONE',event_date:'2026-01-10',finding_key:'marker',
      reported_states:['reported','negative'],source_refs:[{source_id:sourceId,source_line:8}],
      clinical_interpretation:'not_performed'}];},
  ]){
    const v=world();mutate(v);
    assert.throws(()=>parseSourceWorldModel(v,patientId,caseId));
  }
});
test('known same-specimen same-date contradiction is never promoted to assessment',()=>{
  const w=world();const other='SRC-'+'B'.repeat(32);
  w.current_sources.push({...source(),source_id:other,document_id:'DOC-TWO',
    sha256:'d'.repeat(64)});
  w.observations.push({...w.observations[0],source_id:other,document_id:'DOC-TWO',
    source_sha256:'d'.repeat(64),reported_state:'negative',source_statement:'Fictional negative'});
  w.conflicts=[{status:'unresolved_source_disagreement',specimen_id:'SPECIMEN-ONE',
    event_date:'2026-01-10',finding_key:'marker',reported_states:['negative','not-reported','reported'],
    source_refs:[{source_id:sourceId,source_line:8},{source_id:other,source_line:8}],
    clinical_interpretation:'not_performed'}];
  w.summary={current_sources:2,historical_sources:0,current_observations:2,
    unresolved_observations:1,source_disagreements:1};
  // There is no "reported" observation: fake source disagreement cannot pass.
  assert.throws(()=>parseSourceWorldModel(w,patientId,caseId));
  assert.equal(Object.isFrozen(w.observations[0]),false,
    'Parser must not freeze untrusted source data after a failed response');
  w.observations[0].reported_state='reported';
  w.unresolved_refs=[];
  w.conflicts[0].reported_states=['negative','reported'];
  w.summary.unresolved_observations=0;
  const checked=parseSourceWorldModel(w,patientId,caseId);
  assert.equal(checked.conflicts.length,1);
  assert.equal(checked.conflicts[0].clinical_interpretation,'not_performed');
});
test('session retrieves only the exact authorized patient/case source World Model',async()=>{
  const urls=[];
  const s=new RegistrySession(async (url,init)=>{
    urls.push([url,init]);
    if(url.endsWith('/case-bindings'))return response(caseList());
    if(url.endsWith('/world-model'))return response(world());
    return response(patient());
  });
  s.connect(token);await s.read(patientId);await s.loadCases();
  await s.loadWorldModel(caseId);
  const state=s.snapshot();
  assert.equal(state.worldPhase,'ready');
  assert.equal(state.worldModel.observations[0].source_line,8);
  assert.equal(urls.at(-1)[0],'/v1/patients/PAT-EXAMPLE-001/cases/CASE-ALPHA/world-model');
  assert.equal(urls.at(-1)[1].method,'GET');
  assert.equal(urls.at(-1)[1].credentials,'omit');
  assert.equal(urls.at(-1)[1].redirect,'error');
  assert.equal(JSON.stringify(state).includes(token),false);
});
test('unknown/revoked source case never sends World Model request',async()=>{
  let count=0;const s=new RegistrySession(async url=>{
    count++;return response(url.endsWith('/case-bindings')?caseList():patient());
  });
  s.connect(token);await s.read(patientId);await s.loadCases();
  const initial=count;
  await s.loadWorldModel('CASE-FOREIGN');
  await s.loadWorldModel('https://attacker.invalid');
  assert.equal(count,initial);
  assert.equal(s.snapshot().worldModel,null);
  assert.equal(s.snapshot().worldPhase,'error');
});
test('permission denial clears prior world view while preserving independent identity',async()=>{
  let calls=0;
  const s=new RegistrySession(async url=>{
    if(url.endsWith('/case-bindings'))return response(caseList());
    if(url.endsWith('/world-model'))return ++calls===1?response(world()):response({detail:'private'},404);
    return response(patient());
  });
  s.connect(token);await s.read(patientId);await s.loadCases();
  await s.loadWorldModel(caseId);assert.ok(s.snapshot().worldModel);
  await s.loadWorldModel(caseId);
  assert.equal(s.snapshot().worldModel,null);
  assert.equal(s.snapshot().worldPhase,'error');
  assert.equal(s.snapshot().patient.patient_id,patientId);
  assert.ok(!JSON.stringify(s.snapshot()).includes('private'));
});
test('stale world response cannot restore after patient switch, disconnect, or source refresh',async()=>{
  const deferred=()=>{let resolve;return {promise:new Promise(r=>resolve=r),resolve};};
  const slow=deferred();
  const s=new RegistrySession(async url=>{
    if(url.endsWith('/case-bindings'))return response(caseList());
    if(url.endsWith('/world-model'))return slow.promise;
    if(url.endsWith('/PAT-OTHER'))return response(patient('PAT-OTHER'));
    return response(patient());
  });
  s.connect(token);await s.read(patientId);await s.loadCases();
  const waiting=s.loadWorldModel(caseId);
  await s.read('PAT-OTHER');
  slow.resolve(response(world()));await waiting;
  assert.equal(s.snapshot().patient.patient_id,'PAT-OTHER');
  assert.equal(s.snapshot().worldModel,null);

  const ok=new RegistrySession(async url=>{
    if(url.endsWith('/case-bindings'))return response(caseList());
    if(url.endsWith('/world-model'))return response(world());
    if(url.endsWith('/sources'))return response({},404);
    return response(patient());
  });
  ok.connect(token);await ok.read(patientId);await ok.loadCases();
  await ok.loadWorldModel(caseId);assert.ok(ok.snapshot().worldModel);
  await ok.loadSources(caseId);assert.equal(ok.snapshot().worldModel,null);
  ok.disconnect();assert.equal(ok.snapshot().worldModel,null);
});
test('malformed and expired World Model response never retains prior context',async()=>{
  const s=new RegistrySession(async url=>{
    if(url.endsWith('/case-bindings'))return response(caseList());
    if(url.endsWith('/world-model'))return response({...world(),clinical_interpretation:true});
    return response(patient());
  });
  s.connect(token);await s.read(patientId);await s.loadCases();await s.loadWorldModel(caseId);
  assert.equal(s.snapshot().worldModel,null);
  assert.equal(s.snapshot().worldPhase,'error');

  const e=new RegistrySession(async url=>{
    if(url.endsWith('/case-bindings'))return response(caseList());
    if(url.endsWith('/world-model'))return response({},401);
    return response(patient());
  });
  e.connect(token);await e.read(patientId);await e.loadCases();await e.loadWorldModel(caseId);
  assert.equal(e.snapshot().connected,false);
  assert.equal(e.snapshot().worldModel,null);
});
