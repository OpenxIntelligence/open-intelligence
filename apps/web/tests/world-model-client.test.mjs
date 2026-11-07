import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {receiptMicros} from '../.test-dist/source-contracts.js';
import {parseSourceWorldModel,parseSourceHistory} from '../.test-dist/source-world-model.js';

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
  contract:'oi.pg-source-world-model/1',patient_id:patientId,case_id:caseId,access_receipt_id:'ACCESS-'+'A'.repeat(32),synthetic:true,
  authority:'source_report_only_unreviewed',clinical_interpretation:false,
  research_review_invalidation_integrated:false,composer_execution_authorized:false,
  snapshot_fingerprint:'c'.repeat(64),as_of_received_at:'2026-11-02T10:00:00Z',
  summary:{current_sources:1,historical_sources:0,current_observations:1,
    current_laboratory_observations:0,unresolved_observations:1,source_disagreements:0},
  current_sources:[source()],history:[],
  observations:[{
    source_id:sourceId,document_id:'DOC-ONE',document_version:1,source_sha256:'b'.repeat(64),
    source_kind:'pathology',finding_key:'marker',reported_state:'not-reported',
    source_statement:'Fictional café <script>literal</script>.',source_line:8,
    specimen_id:'SPECIMEN-ONE',event_date:'2026-01-10',issued_at:'2026-01-11',
    review_state:'not_established',clinical_meaning:null,
  }],
  laboratory_observations:[],laboratory_timeline:[],
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
test('strict typed laboratory projection stays source-reported and rejects fabricated interpretation',()=>{
  const w=world(),labSource='SRC-'+'C'.repeat(32);
  w.current_sources.push({...source(),source_id:labSource,document_id:'FICTIONAL-REPORT-A',
    sha256:'e'.repeat(64),kind:'laboratory',event_date:'2026-04-03',issued_at:'2026-04-04',
    specimen_id:'FICTIONAL-SPECIMEN-A'});
  const lab={source_id:labSource,document_id:'FICTIONAL-REPORT-A',document_version:1,
    source_sha256:'e'.repeat(64),observation_reference:'Observation/FICTIONAL-OBS-A',
    loinc_code:'777-3',effective_at:'2026-04-03T09:05:00-04:00',
    issued_at:'2026-04-04T12:00:00Z',specimen_reference:'Specimen/FICTIONAL-SPECIMEN-A',
    specimen_type_text:'Fictional plasma sample',
    specimen_collected_at:'2026-04-03T09:05:00-04:00',
    report_reference:'DiagnosticReport/FICTIONAL-REPORT-A',status:'reported_value',
    value_text:'4.20',unit_code:'10*9/L',absent_reason:null,source_reported:true,
    review_state:'not_established',clinical_review:'not_performed',clinical_meaning:null};
  w.laboratory_observations=[lab];
  w.laboratory_timeline=[{source_id:labSource,observation_reference:lab.observation_reference,
    loinc_code:'777-3',effective_at:lab.effective_at,issued_at:lab.issued_at,
    specimen_reference:lab.specimen_reference,status:'reported_value',
    clinical_interpretation:'not_performed'}];
  w.summary.current_sources=2;w.summary.current_observations=2;
  w.summary.current_laboratory_observations=1;
  const checked=parseSourceWorldModel(w,patientId,caseId);
  assert.equal(checked.laboratory_observations[0].clinical_meaning,null);
  assert.equal(checked.laboratory_timeline[0].clinical_interpretation,'not_performed');
  for(const mutate of [
    x=>{x.laboratory_observations[0].clinical_review='approved';},
    x=>{x.laboratory_observations[0].source_sha256='f'.repeat(64);},
    x=>{x.laboratory_observations[0].status='reported_absent';},
    x=>{x.laboratory_timeline[0].loinc_code='9999-9';},
    x=>{x.summary.current_laboratory_observations=0;},
  ]){
    const bad=structuredClone(w);mutate(bad);
    assert.throws(()=>parseSourceWorldModel(bad,patientId,caseId));
  }
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
    current_laboratory_observations:0,unresolved_observations:1,source_disagreements:1};
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

for(const action of ['opening','closing']){
  test(`${action} an original releases a pending World Model and allows an explicit retry`,async()=>{
    const originalText=`OI-SYNTHETIC-REPORT/1\nPatient: ${caseId}\nDocument: DOC-ONE\nType: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-11\nSpecimen: SPECIMEN-ONE\nFinding: marker|not-reported|Independently fictional original.\n`;
    const hash=createHash('sha256').update(originalText).digest('hex');
    const metadata={...source(),sha256:hash};
    const index={contract:'oi.synthetic-original-sources/1',patient_id:patientId,
      case_id:caseId,access_receipt_id:'ACCESS-'+'A'.repeat(32),sources:[metadata],
      source_reported_assertions:[{source_id:sourceId,finding_key:'marker',reported_state:'not-reported',
        source_statement:'Independently fictional original.',source_line:8,clinical_review_state:'not_established'}],
      synthetic:true,clinical_interpretation:false,
      research_review_invalidation_integrated:false};
    const original={source_id:sourceId,case_id:caseId,access_receipt_id:'ACCESS-'+'B'.repeat(32),
      document_id:metadata.document_id,version:metadata.version,state:metadata.state,
      sha256:hash,original_text:originalText,synthetic:true,clinical_review_state:'not_established'};
    const snapshot=world();
    snapshot.current_sources[0].sha256=hash;
    snapshot.observations[0].source_sha256=hash;
    snapshot.observations[0].source_statement='Independently fictional original.';
    let release,worldReads=0;
    const slow=new Promise(resolve=>{release=resolve;});
    const retryReceipt='ACCESS-'+'C'.repeat(32);
    const s=new RegistrySession(async url=>{
      if(url.endsWith('/case-bindings'))return response(caseList());
      if(url.endsWith('/sources'))return response(index);
      if(url.endsWith('/sources/'+sourceId))return response(original);
      if(url.endsWith('/world-model'))return ++worldReads===1?slow:
        response({...snapshot,access_receipt_id:retryReceipt});
      return response(patient());
    });
    s.connect(token);await s.read(patientId);await s.loadCases();await s.loadSources(caseId);
    if(action==='closing')await s.loadOriginal(sourceId);
    const waiting=s.loadWorldModel(caseId);
    try{
      assert.equal(s.snapshot().worldPhase,'loading');
      if(action==='opening')await s.loadOriginal(sourceId);else s.dismissOriginal();
      assert.equal(s.snapshot().worldPhase,'idle');
      assert.equal(s.snapshot().worldModel,null);
      assert.equal(s.snapshot().recordsPhase,'ready');
      assert.equal(s.snapshot().original?.original_text??null,action==='opening'?originalText:null);
      assert.equal(worldReads,1,'Original actions must not retry World Model reads automatically');

      release(response(snapshot));await waiting;
      assert.equal(s.snapshot().worldPhase,'idle');
      assert.equal(s.snapshot().worldModel,null,'The discarded response must not restore a snapshot');
      await s.loadWorldModel(caseId);
      assert.equal(worldReads,2);
      assert.equal(s.snapshot().worldPhase,'ready');
      assert.equal(s.snapshot().worldModel.access_receipt_id,retryReceipt);

      const completed=s.snapshot().worldModel;
      await s.loadOriginal(sourceId);
      assert.equal(s.snapshot().worldModel,completed,'Opening an original preserves a completed World Model');
      s.dismissOriginal();
      assert.equal(s.snapshot().worldModel,completed,'Closing an original preserves a completed World Model');
      assert.equal(s.snapshot().worldPhase,'ready');
    }finally{
      release(response(snapshot));await waiting;s.disconnect();
    }
  });
}

const history=(cutoff=source().received_at)=>({contract:'oi.pg-source-history/1',received_through:cutoff,
 selection_basis:'received_at_inclusive',current_authority_required:true,historical_only:true,world_model:world()});
test('historical wrapper requires exact cutoff, current authority and no post-cutoff sources',()=>{
 const cutoff=source().received_at;
 assert.equal(parseSourceHistory(history(),patientId,caseId,cutoff).world_model.observations[0].reported_state,'not-reported');
 for(const mutate of [x=>x.historical_only=false,x=>x.current_authority_required=false,
  x=>x.received_through='2026-11-02T10:00:00.000001Z',
  x=>x.world_model.current_sources[0].received_at='2026-11-02T10:00:00.000001Z',
  x=>x.world_model.patient_id='PAT-FOREIGN']){
  const value=history();mutate(value);assert.throws(()=>parseSourceHistory(value,patientId,caseId,cutoff));
 }
});
async function historySession(historyRead){
 const session=new RegistrySession(async url=>{
  if(url.includes('/world-model/history?'))return historyRead(url);
  if(url.endsWith('/case-bindings'))return response(caseList());
  if(url.endsWith('/world-model'))return response(world());
  return response(patient());
 });
 session.connect(token);await session.read(patientId);await session.loadCases();await session.loadWorldModel(caseId);return session;
}
test('history stays separate from the current model and cannot select unknown cutoffs',async()=>{
 let calls=0;
 const session=await historySession(url=>{calls++;assert.ok(url.endsWith(encodeURIComponent(source().received_at)));return response(history());});
 const current=session.snapshot().worldModel;
 await session.loadSourceHistory('2000-01-01T00:00:00Z');assert.equal(calls,0);
 await session.loadSourceHistory(source().received_at);
 assert.equal(session.snapshot().historyPhase,'ready');assert.equal(session.snapshot().worldModel,current);
 session.dismissSourceHistory();assert.equal(session.snapshot().sourceHistory,null);
});
test('history denial clears current and historical sources',async()=>{
 let denied=false;const session=await historySession(()=>response(denied?{}:history(),denied?404:200));
 await session.loadSourceHistory(source().received_at);assert.ok(session.snapshot().sourceHistory);
 denied=true;await session.loadSourceHistory(source().received_at);
 assert.equal(session.snapshot().sourceHistory,null);assert.equal(session.snapshot().worldModel,null);
});
test('late historical reply cannot restore data after current refresh or disconnect',async()=>{
 for(const invalidate of [s=>s.disconnect(),s=>s.loadWorldModel(caseId),s=>s.dismissSourceHistory()]){
  let resolve;const session=await historySession(()=>new Promise(r=>resolve=r));
  const pending=session.loadSourceHistory(source().received_at);await invalidate(session);
  resolve(response(history()));await pending;
  assert.equal(session.snapshot().sourceHistory,null);assert.notEqual(session.snapshot().historyPhase,'loading');
 }
});
test('invalid history clears earlier results and provides retry state',async()=>{
 let valid=true;const session=await historySession(()=>response(valid?history():{...history(),historical_only:false}));
 await session.loadSourceHistory(source().received_at);valid=false;
 await session.loadSourceHistory(source().received_at);
 assert.equal(session.snapshot().historyPhase,'error');assert.equal(session.snapshot().sourceHistory,null);
});


test('receipt boundaries preserve microseconds and reject normalized or overprecise dates',()=>{
 assert.equal(receiptMicros('2026-01-03T10:00:00.000002Z')-receiptMicros('2026-01-03T10:00:00.000001Z'),1n);
 assert.equal(receiptMicros('2026-01-03T10:00:00.000001Z'),receiptMicros('2026-01-03T11:00:00.000001+01:00'));
 for(const bad of ['2026-02-30T00:00:00Z','2026-01-01T24:00:00Z','2026-01-01','2026-01-01T00:00:00',
  '2026-01-01T00:00:00.0000001Z','2026-01-01T00:00:00+00:99']){
  assert.throws(()=>receiptMicros(bad));
  const w=world();w.current_sources[0].received_at=bad;
  assert.throws(()=>parseSourceWorldModel(w,patientId,caseId));
 }
});
function unifiedHistoryFixture(){
 const text=`OI-SYNTHETIC-REPORT/1\nPatient: ${caseId}\nDocument: DOC-ONE\nType: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-11\nSpecimen: SPECIMEN-ONE\nFinding: marker|not-reported|Independently fictional original.\n`.replaceAll('\\n','\n');
 const hash=createHash('sha256').update(text).digest('hex');
 const first={...source(),sha256:hash},second={...first,source_id:'SRC-'+'B'.repeat(32),version:2,
  sha256:'d'.repeat(64),received_at:'2026-11-02T10:00:00.000001Z',supersedes_id:sourceId};
 const past=world();past.current_sources=[first];past.observations[0].source_sha256=hash;
 past.observations[0].source_statement='Independently fictional original.';
 const current=clone(past);current.current_sources=[second];current.history=[{...first,state:'superseded'}];
 current.as_of_received_at=second.received_at;current.summary.historical_sources=1;
 Object.assign(current.observations[0],{source_id:second.source_id,document_version:2,source_sha256:second.sha256});
 current.unresolved_refs[0].source_id=second.source_id;
 const index={contract:'oi.synthetic-original-sources/1',patient_id:patientId,case_id:caseId,
  access_receipt_id:'ACCESS-'+'A'.repeat(32),sources:[{...first,state:'superseded'},second],
  source_reported_assertions:[{source_id:second.source_id,finding_key:'marker',reported_state:'not-reported',
   source_statement:'Independently fictional original.',source_line:8,clinical_review_state:'not_established'}],
  synthetic:true,clinical_interpretation:false,research_review_invalidation_integrated:false};
 const original={source_id:sourceId,case_id:caseId,access_receipt_id:'ACCESS-'+'B'.repeat(32),
  document_id:first.document_id,version:1,state:'superseded',sha256:hash,original_text:text,
  synthetic:true,clinical_review_state:'not_established'};
 return {first,second,index,original,current,historical:{...history(),world_model:past}};
}
async function unifiedHistorySession(basis,overrides={}){
 const f=unifiedHistoryFixture(),calls=[];
 const s=new RegistrySession(async(url,init)=>{
  calls.push(url);
  if(url.includes('/world-model/history?'))return overrides.history?overrides.history(url,init):response(f.historical);
  if(url.endsWith('/world-model'))return response(f.current);
  if(url.endsWith('/sources'))return overrides.index?overrides.index(url,init):response(f.index);
  if(url.endsWith('/sources/'+sourceId))return overrides.original?overrides.original(url,init):response(f.original);
  if(url.endsWith('/case-bindings'))return response(caseList());
  return response(patient());
 });
 s.connect(token);await s.read(patientId);await s.loadCases();
 if(basis==='world')await s.loadWorldModel(caseId);else await s.loadSources(caseId);
 return {s,f,calls};
}
test('history requires complete exact membership from the loaded source snapshot',()=>{
 const f=unifiedHistoryFixture(),cutoff=f.first.received_at;
 const parse=(value,known=f.index.sources)=>parseSourceHistory(value,patientId,caseId,cutoff,known);
 assert.equal(parse(f.historical).world_model.current_sources[0].state,'current');
 for(const field of ['sha256','kind','document_id','received_at','specimen_id']){
  const known=clone(f.index.sources);
  known[0][field]=field==='sha256'?'e'.repeat(64):field==='kind'?'laboratory':field==='received_at'?'2026-11-01T10:00:00Z':'DIFFERENT';
  assert.throws(()=>parse(f.historical,known),field);
 }
 assert.throws(()=>parse(f.historical,[]));
 assert.throws(()=>parse(f.historical,[...f.index.sources,{...f.first,source_id:'SRC-'+'C'.repeat(32),document_id:'DOC-MISSING'}]));
 assert.throws(()=>parseSourceHistory(f.historical,patientId,caseId,f.second.received_at,f.index.sources));
});
for(const basis of ['records','world']){
 test(`${basis} historical selection opens the exact superseded original with fresh authorization`,async()=>{
  const {s,f,calls}=await unifiedHistorySession(basis);
  await s.loadSourceHistory(f.first.received_at,basis);
  assert.equal(s.snapshot().historyPhase,'ready');
  assert.equal(s.snapshot().historyBasis,basis);
  const start=calls.length;await s.openHistoricalOriginal(sourceId);
  assert.equal(s.snapshot().original?.original_text,f.original.original_text);
  assert.equal(s.snapshot().original?.state,'superseded');
  assert.equal(s.snapshot().original?.version,1);
  assert.deepEqual(calls.slice(start).map(u=>u.split('/').at(-1)),basis==='world'?['sources',sourceId]:[sourceId]);
  s.disconnect();
 });
}
test('Records history grants no original authority and permits a fresh authorized retry',async()=>{
 const f=unifiedHistoryFixture();let allowed=false,reads=0;
 const {s}=await unifiedHistorySession('records',{original:()=>{reads++;return response(allowed?f.original:{},allowed?200:404);}});
 await s.loadSourceHistory(f.first.received_at,'records');await s.openHistoricalOriginal(sourceId);
 assert.equal(s.snapshot().original,null);assert.equal(s.snapshot().recordsPhase,'error');
 assert.ok(s.snapshot().sourceHistory);allowed=true;await s.openHistoricalOriginal(sourceId);
 assert.equal(reads,2);assert.equal(s.snapshot().original?.version,1);s.disconnect();
});
for(const invalidate of ['refresh','dismiss','disconnect','patient']){
 test(`late Records history cannot return after ${invalidate}`,async()=>{
  let release,signal;const {s,f}=await unifiedHistorySession('records',{
   history:(_,init)=>{signal=init.signal;return new Promise(r=>release=r);}});
  const pending=s.loadSourceHistory(f.first.received_at,'records');
  if(invalidate==='refresh')await s.loadSources(caseId);
  else if(invalidate==='dismiss')s.dismissSourceHistory();
  else if(invalidate==='disconnect')s.disconnect();
  else await s.read(patientId);
  assert.equal(signal.aborted,true);release(response(f.historical));await pending;
  assert.equal(s.snapshot().sourceHistory,null);assert.notEqual(s.snapshot().historyPhase,'loading');s.disconnect();
 });
}
test('a superseded history response cannot replace the most recent receipt selection',async()=>{
 let release,calls=0;const f=unifiedHistoryFixture();
 const {s}=await unifiedHistorySession('records',{history:()=>++calls===1?new Promise(r=>release=r):response({...history(f.second.received_at),world_model:f.current})});
 const old=s.loadSourceHistory(f.first.received_at,'records');await s.loadSourceHistory(f.second.received_at,'records');
 release(response(f.historical));await old;
 assert.equal(s.snapshot().sourceHistory.received_through,f.second.received_at);s.disconnect();
});
test('Journey handoff withholds originals if the refreshed source identity changed',async()=>{
 const f=unifiedHistoryFixture();const changed=clone(f.index);changed.sources[0].sha256='e'.repeat(64);
 const {s,calls}=await unifiedHistorySession('world',{index:()=>response(changed)});
 await s.loadSourceHistory(f.first.received_at);await s.openHistoricalOriginal(sourceId);
 assert.equal(s.snapshot().original,null);assert.equal(s.snapshot().recordsPhase,'error');
 assert.equal(calls.some(u=>u.endsWith('/sources/'+sourceId)),false);s.disconnect();
});
for(const invalidate of ['dismiss','disconnect','refresh']){
 test(`Journey original handoff cannot finish after ${invalidate}`,async()=>{
  let release;const {s,f,calls}=await unifiedHistorySession('world',{index:()=>new Promise(r=>release=r)});
  await s.loadSourceHistory(f.first.received_at);const pending=s.openHistoricalOriginal(sourceId);
  if(invalidate==='dismiss')s.dismissOriginal();else if(invalidate==='disconnect')s.disconnect();else await s.read(patientId);
  release(response(f.index));await pending;
  assert.equal(s.snapshot().original,null);assert.equal(calls.some(u=>u.endsWith('/sources/'+sourceId)),false);s.disconnect();
 });
}


test('Records history denial clears source metadata, original text and history',async()=>{
 let allowed=true;const f=unifiedHistoryFixture();
 const {s}=await unifiedHistorySession('records',{history:()=>response(allowed?f.historical:{},allowed?200:404)});
 await s.loadSourceHistory(f.first.received_at,'records');await s.openHistoricalOriginal(sourceId);
 assert.ok(s.snapshot().original);allowed=false;await s.loadSourceHistory(f.first.received_at,'records');
 assert.equal(s.snapshot().sourceHistory,null);assert.equal(s.snapshot().sourceIndex,null);
 assert.equal(s.snapshot().original,null);s.disconnect();
});


test('original denial does not disable independently authorized Records history browsing',async()=>{
 const f=unifiedHistoryFixture();
 const {s}=await unifiedHistorySession('records',{original:()=>response({},404),history:url=>
  response(url.endsWith(encodeURIComponent(f.first.received_at))?f.historical:{...history(f.second.received_at),world_model:f.current})});
 await s.loadSourceHistory(f.first.received_at,'records');await s.openHistoricalOriginal(sourceId);
 assert.equal(s.snapshot().recordsPhase,'error');
 await s.loadSourceHistory(f.second.received_at,'records');
 assert.equal(s.snapshot().historyPhase,'ready');assert.equal(s.snapshot().sourceHistory.received_through,f.second.received_at);
 assert.equal(s.snapshot().original,null);s.disconnect();
});
