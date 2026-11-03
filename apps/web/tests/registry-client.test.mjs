import {createHash} from 'node:crypto';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
const token='fictional_test_credential_000000000001';
const token2='fictional_test_credential_000000000002';
const patient=(id='PAT-EXAMPLE-001')=>({patient_id:id,origin_org:'FICT-ORG',created_at:'2026-11-02T10:00:00Z',status:'active',revision:1});
const response=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
const deferred=()=>{let resolve;return {promise:new Promise(r=>{resolve=r}),resolve:(x)=>resolve(x)}};
test('default session has no authority and does not call transport',async()=>{let calls=0;const s=new RegistrySession(async()=>{calls++;return response(patient())});await s.read('PAT-EXAMPLE-001');assert.equal(calls,0);assert.equal(s.snapshot().connected,false);assert.equal(s.snapshot().patient,null)});
test('credential is absent from public state; session replacement clears patient',async()=>{const s=new RegistrySession(async()=>response(patient()));s.connect(token);await s.read('PAT-EXAMPLE-001');assert.ok(s.snapshot().patient);assert.ok(!JSON.stringify(s.snapshot()).includes(token));s.connect(token2);assert.equal(s.snapshot().patient,null);s.disconnect();assert.equal(s.snapshot().connected,false)});
test('create is explicit synthetic and does not auto-read or grant patient access',async()=>{const calls=[];const s=new RegistrySession(async(url,options)=>{calls.push([url,options]);return response({patient_id:'PAT-EXAMPLE-001',duplicate:false},201)});s.connect(token);await s.create('REQUEST-ONE',true);assert.equal(calls.length,1);assert.equal(calls[0][0],'/v1/patients');assert.deepEqual(JSON.parse(calls[0][1].body),{synthetic:true,request_key:'REQUEST-ONE'});assert.equal(s.snapshot().patient,null);assert.equal(s.snapshot().created.patient_id,'PAT-EXAMPLE-001')});
test('unconfirmed and malformed request keys never reach backend',async()=>{let calls=0;const s=new RegistrySession(async()=>{calls++;return response({})});s.connect(token);for(const key of ['','a','bad key','../other'])await s.create(key,true);await s.create('REQUEST-ONE',false);assert.equal(calls,0)});
test('fetch sends credential only to fixed same-origin API with no cookies or redirects',async()=>{let call;const s=new RegistrySession(async(...args)=>{call=args;return response(patient())});s.connect(token);await s.read('PAT-EXAMPLE-001');assert.equal(call[0],'/v1/patients/PAT-EXAMPLE-001');assert.equal(call[1].headers.Authorization,'Bearer '+token);assert.equal(call[1].credentials,'omit');assert.equal(call[1].redirect,'error');assert.equal(call[1].cache,'no-store');await s.read('https://attacker.invalid');assert.equal(call[0],'/v1/patients/PAT-EXAMPLE-001');assert.equal(s.snapshot().patient,null)});
test('HTTP 404 clears prior patient without exposing server detail',async()=>{let n=0;const s=new RegistrySession(async()=>++n===1?response(patient()):response({detail:'secret identity detail'},404));s.connect(token);await s.read('PAT-EXAMPLE-001');await s.read('PAT-EXAMPLE-002');assert.equal(s.snapshot().patient,null);assert.ok(!JSON.stringify(s.snapshot()).includes('secret'));assert.equal(s.snapshot().connected,true)});
test('HTTP 401 expires session and removes old patient and creation receipt',async()=>{let n=0;const s=new RegistrySession(async()=>++n===1?response(patient()):response({},401));s.connect(token);await s.read('PAT-EXAMPLE-001');await s.read('PAT-EXAMPLE-001');assert.equal(s.snapshot().connected,false);assert.equal(s.snapshot().patient,null);assert.equal(s.snapshot().created,null)});
test('late old patient response cannot replace a newer selection',async()=>{const a=deferred(),b=deferred();let n=0;const s=new RegistrySession(()=>++n===1?a.promise:b.promise);s.connect(token);const pa=s.read('PAT-EXAMPLE-001'),pb=s.read('PAT-EXAMPLE-002');b.resolve(response(patient('PAT-EXAMPLE-002')));await pb;a.resolve(response(patient()));await pa;assert.equal(s.snapshot().patient.patient_id,'PAT-EXAMPLE-002')});
test('old response after disconnect/reconnect is discarded even for same patient',async()=>{const a=deferred();const s=new RegistrySession(()=>a.promise);s.connect(token);const p=s.read('PAT-EXAMPLE-001');s.disconnect();s.connect(token);a.resolve(response(patient()));await p;assert.equal(s.snapshot().patient,null)});
test('mismatched or extra response fields and malformed values are withheld',async()=>{for(const value of [patient('PAT-WRONG'),{...patient(),secret:'raw-text'},{...patient(),revision:0},{...patient(),status:'approved'},{...patient(),created_at:'unknown'}]){const s=new RegistrySession(async()=>response(value));s.connect(token);await s.read('PAT-EXAMPLE-001');assert.equal(s.snapshot().patient,null);assert.equal(s.snapshot().phase,'error')}});
test('explicit retry uses same request key; no hidden automatic retry',async()=>{const requests=[];const s=new RegistrySession(async(url,options)=>{requests.push(options.body);if(requests.length===1)throw Error('network token '+token);return response({patient_id:'PAT-EXAMPLE-001',duplicate:true})});s.connect(token);await s.create('REQUEST-SAME',true);assert.equal(requests.length,1);assert.ok(!JSON.stringify(s.snapshot()).includes(token));await s.create('REQUEST-SAME',true);assert.equal(requests[0],requests[1]);assert.equal(s.snapshot().created.duplicate,true)});
test('concurrent create clicks do not produce extra network calls',async()=>{const d=deferred();let count=0;const s=new RegistrySession(()=>{count++;return d.promise});s.connect(token);const p=s.create('REQUEST-ONE',true);await s.create('REQUEST-TWO',true);assert.equal(count,1);d.resolve(response({patient_id:'PAT-EXAMPLE-001',duplicate:false},201));await p});
test('response after read grant failure cannot restore stale content',async()=>{const d=deferred();let n=0;const s=new RegistrySession(()=>++n===1?d.promise:Promise.resolve(response({},404)));s.connect(token);const p=s.read('PAT-EXAMPLE-001');await s.read('PAT-EXAMPLE-002');d.resolve(response(patient()));await p;assert.equal(s.snapshot().patient,null)});
test('oversized or non-JSON data is rejected without retaining content',async()=>{for(const r of [new Response('x'.repeat(65537),{headers:{'content-type':'application/json'}}),new Response('<html>secret</html>',{headers:{'content-type':'text/html'}})]){const s=new RegistrySession(async()=>r);s.connect(token);await s.read('PAT-EXAMPLE-001');assert.equal(s.snapshot().patient,null);assert.equal(s.snapshot().phase,'error')}});
test('invalid replacement credential clears any earlier session',async()=>{const s=new RegistrySession(async()=>response(patient()));s.connect(token);await s.read('PAT-EXAMPLE-001');s.connect('not valid');assert.equal(s.snapshot().connected,false);assert.equal(s.snapshot().patient,null)});
test('terminal newline cannot pass opaque identifier or credential validation',async()=>{let calls=0;const s=new RegistrySession(async()=>{calls++;return response(patient())});s.connect(token+'\n');assert.equal(s.snapshot().connected,false);s.connect(token);await s.read('PAT-EXAMPLE-001\n');assert.equal(calls,0)});
test('creating a different identity clears prior selection and invalidates an older pending read',async()=>{const d=deferred();const s=new RegistrySession((url)=>url==='/v1/patients'?Promise.resolve(response({patient_id:'PAT-NEW-001',duplicate:false},201)):d.promise);s.connect(token);const old=s.read('PAT-EXAMPLE-001');await s.create('REQUEST-NEW',true);d.resolve(response(patient()));await old;assert.equal(s.snapshot().patient,null);assert.equal(s.snapshot().created.patient_id,'PAT-NEW-001')});


const receiptPatient='PAT-EXAMPLE-001';
const receiptCase='CASE-ALPHA';
const receiptSource='SRC-'+ 'A'.repeat(32);
const originalText='OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: DOC-ONE\nType: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-11\nSpecimen: SPECIMEN-ONE\nFinding: marker|not-reported|Independently fictional example.\n';
const sha256=createHash('sha256').update(originalText,'utf8').digest('hex');
const receiptRef={case_id:receiptCase,source_id:receiptSource,version:1,sha256};
const fixtureRequest=(ref=receiptRef,status='received',receipt='source_current_unreviewed')=>({
 request_id:'RECORD-EXAMPLE-001',patient_id:receiptPatient,kind:'pathology',
 record_label:'Fictional pathology report',source_organization:'Example institution',
 status,revision:status==='received'?2:1,created_at:'2026-11-02T10:00:00Z',
 updated_at:'2026-11-02T10:05:00Z',receipt_status:receipt,
 source_reference:ref,external_request_sent:false
});
const fixtureRecords=(requests=[fixtureRequest()])=>({
 patient_id:receiptPatient,requests,synthetic:true,external_request_sent:false,source_receipts_enabled:true
});
const fixtureOriginal=()=>({
 source_id:receiptSource,case_id:receiptCase,document_id:'DOC-ONE',version:1,
 state:'current',sha256,original_text:originalText,synthetic:true,clinical_review_state:'not_established'
});
test('record requests require an already authorized selected patient',async()=>{
 let called=0;const s=new RegistrySession(async()=>{called++;return response(fixtureRecords())});
 s.connect(token);await s.loadRecords();
 assert.equal(called,0);assert.equal(s.snapshot().records,null);
 assert.equal(s.snapshot().recordsPhase,'error');
});
test('received source requires an explicit second original-text read and SHA match',async()=>{
 const paths=[],methods=[];const s=new RegistrySession(async(url,init)=>{
   paths.push(url);methods.push(init);
   if(url==='/v1/patients/'+receiptPatient)return response(patient());
   if(url.endsWith('/record-requests'))return response(fixtureRecords());
   if(url.endsWith('/sources/'+receiptSource))return response(fixtureOriginal());
   throw Error('unexpected URL');
 });
 s.connect(token);await s.read(receiptPatient);await s.loadRecords();
 assert.equal(s.snapshot().records[0].status,'received');
 assert.equal(s.snapshot().original,null);
 await s.openOriginal(receiptCase,receiptSource);
 assert.equal(s.snapshot().original?.original_text,originalText);
 assert.equal(s.snapshot().originalPhase,'ready');
 assert.equal(paths[2],'/v1/patients/'+receiptPatient+'/cases/'+receiptCase+'/sources/'+receiptSource);
 assert.equal(methods[2].headers.Authorization,'Bearer '+token);
 assert.equal(methods[2].credentials,'omit');
 assert.equal(methods[2].redirect,'error');
 assert.equal(methods[2].cache,'no-store');
 assert.ok(!JSON.stringify(s.snapshot()).includes(token));
});
test('a receipt status without source-read disclosure cannot open original text',async()=>{
 let calls=0;const s=new RegistrySession(async(url)=>{
   calls++;
   if(url.endsWith('/record-requests'))return response(fixtureRecords([fixtureRequest(null)]));
   return response(patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadRecords();
 assert.equal(s.snapshot().records[0].status,'received');
 assert.equal(s.snapshot().records[0].source_reference,null);
 await s.openOriginal(receiptCase,receiptSource);
 assert.equal(calls,2);assert.equal(s.snapshot().original,null);
});
test('record grant denial clears previously displayed source and record metadata',async()=>{
 let denied=false;const s=new RegistrySession(async(url)=>{
   if(url.endsWith('/record-requests'))return denied?response({detail:'forbidden details'},404):response(fixtureRecords());
   if(url.endsWith('/sources/'+receiptSource))return response(fixtureOriginal());
   return response(patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadRecords();
 await s.openOriginal(receiptCase,receiptSource);
 assert.ok(s.snapshot().original);
 denied=true;await s.loadRecords();
 assert.equal(s.snapshot().records,null);assert.equal(s.snapshot().original,null);
 assert.equal(s.snapshot().recordsPhase,'error');
 assert.ok(!JSON.stringify(s.snapshot()).includes('forbidden details'));
});
test('original-text refusal never leaks prior content or changes receipt state',async()=>{
 let denied=false;const s=new RegistrySession(async(url)=>{
   if(url.endsWith('/record-requests'))return response(fixtureRecords());
   if(url.endsWith('/sources/'+receiptSource))return denied?response({detail:'private'},404):response(fixtureOriginal());
   return response(patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadRecords();
 await s.openOriginal(receiptCase,receiptSource);assert.ok(s.snapshot().original);
 denied=true;await s.openOriginal(receiptCase,receiptSource);
 assert.equal(s.snapshot().original,null);assert.equal(s.snapshot().originalPhase,'error');
 assert.equal(s.snapshot().records[0].status,'received');
});
test('cross-patient and changed-original fingerprints fail closed without disclosed text',async()=>{
 for(const bad of [
   {...fixtureRecords(),patient_id:'PAT-OTHER-001'},
   {...fixtureRecords(),requests:[{...fixtureRequest(),patient_id:'PAT-OTHER-001'}]},
   {...fixtureRecords(),requests:[{...fixtureRequest(),source_reference:{...receiptRef,sha256:'0'.repeat(64)}}]},
 ]){
   const s=new RegistrySession(async(url)=>url.endsWith('/record-requests')?response(bad):response(patient()));
   s.connect(token);await s.read(receiptPatient);await s.loadRecords();
   // The third case is a valid reference shape; its incorrect hash must
   // still block original text if the returned bytes do not match.
   if(bad.requests?.[0]?.source_reference?.sha256==='0'.repeat(64)){
     assert.equal(s.snapshot().recordsPhase,'ready');
   }else{assert.equal(s.snapshot().records,null);assert.equal(s.snapshot().recordsPhase,'error');}
 }
 const s=new RegistrySession(async(url)=>
   url.endsWith('/record-requests')?response({...fixtureRecords(),requests:[
     {...fixtureRequest(),source_reference:{...receiptRef,sha256:'0'.repeat(64)}}]}):
   url.endsWith('/sources/'+receiptSource)?response(fixtureOriginal()):response(patient()));
 s.connect(token);await s.read(receiptPatient);await s.loadRecords();
 await s.openOriginal(receiptCase,receiptSource);
 assert.equal(s.snapshot().original,null);assert.equal(s.snapshot().originalPhase,'error');
});
test('patient switching or disconnect invalidates pending record and source responses',async()=>{
 const delayed=deferred();let calls=0;
 const s=new RegistrySession(async(url)=>{
   calls++;
   if(url.endsWith('/record-requests'))return delayed.promise;
   return response(patient(url.endsWith('/PAT-EXAMPLE-002')?'PAT-EXAMPLE-002':receiptPatient));
 });
 s.connect(token);await s.read(receiptPatient);
 const request=s.loadRecords();
 await s.read('PAT-EXAMPLE-002');
 delayed.resolve(response(fixtureRecords()));await request;
 assert.equal(s.snapshot().records,null);
 assert.equal(s.snapshot().patient?.patient_id,'PAT-EXAMPLE-002');
 const late=deferred();
 const t=new RegistrySession(async(url)=>
   url.endsWith('/record-requests')?response(fixtureRecords()):
   url.includes('/sources/')?late.promise:response(patient()));
 t.connect(token);await t.read(receiptPatient);await t.loadRecords();
 const original=t.openOriginal(receiptCase,receiptSource);t.disconnect();
 late.resolve(response(fixtureOriginal()));await original;
 assert.equal(t.snapshot().original,null);assert.equal(t.snapshot().records,null);
});
test('historical receipts remain explicit and cannot be silently promoted',async()=>{
 const s=new RegistrySession(async(url)=>
   url.endsWith('/record-requests')?response(fixtureRecords([fixtureRequest(
     receiptRef,'received','source_superseded_reconciliation_required')])):response(patient()));
 s.connect(token);await s.read(receiptPatient);await s.loadRecords();
 assert.equal(s.snapshot().records[0].receipt_status,'source_superseded_reconciliation_required');
 assert.equal(s.snapshot().original,null);
});


const worldSource=()=>({
 source_version_id:receiptSource,document_id:'DOC-ONE',version:1,
 source_sha256:sha256,kind:'pathology',specimen_id:'SPECIMEN-ONE',
 event_date:'2026-01-10',issued_at:'2026-01-11',
 received_at:'2026-11-02T11:00:00Z',state:'current',supersedes_source_id:null
});
const worldObservation=()=>({
 assertion_id:1,finding_key:'marker',reported_state:'not-reported',
 source_statement:'Independently fictional example.',source_line:8,
 source_version_id:receiptSource,document_id:'DOC-ONE',document_version:1,
 source_sha256:sha256,source_kind:'pathology',specimen_id:'SPECIMEN-ONE',
 event_date:'2026-01-10',issued_at:'2026-01-11',
 received_at:'2026-11-02T11:00:00Z',review_state:'not_established',clinical_meaning:null
});
const worldFixture=()=>{
 const observation=worldObservation();
 return {
 contract:'oi.synthetic-postgres-world-model-sources/1',synthetic:true,
 patient_id:receiptPatient,case_id:receiptCase,source_snapshot_sha256:'a'.repeat(64),
 authority:'source_report_only_unreviewed',clinical_interpretation:'not_generated',
 clinical_approval:false,review_workflow_connected:false,
 summary:{current_sources:1,superseded_sources:0,current_observations:1,
  unresolved_observations:1,source_disagreements:0},
 current_sources:[worldSource()],history:[],observations:[observation],
 unresolved:[observation],conflicts:[],
 limitations:['Synthetic authored observations only; not medical evidence.']
 };
};
test('source World Model read requires authorized selected patient and exact case ID',async()=>{
 const paths=[];
 const s=new RegistrySession(async(url)=>{paths.push(url);return response(patient())});
 s.connect(token);await s.loadWorldModel(receiptCase);assert.equal(paths.length,0);
 await s.read(receiptPatient);await s.loadWorldModel('../other');assert.equal(paths.length,1);
 assert.equal(s.snapshot().worldModel,null);
 assert.equal(s.snapshot().worldPhase,'error');
});
test('source World Model is read only, scoped and anchored to original source UUIDs',async()=>{
 const paths=[],options=[];
 const s=new RegistrySession(async(url,opts)=>{
  paths.push(url);options.push(opts);
  return response(url.endsWith('/world-model')?worldFixture():patient());
 });
 s.connect(token);await s.read(receiptPatient);
 await s.loadWorldModel(receiptCase);
 assert.equal(s.snapshot().worldPhase,'ready');
 assert.equal(s.snapshot().worldModel.observations[0].source_version_id,receiptSource);
 assert.equal(s.snapshot().worldModel.summary.unresolved_observations,1);
 assert.equal(s.snapshot().worldModel.review_workflow_connected,false);
 assert.equal(s.snapshot().original,null);
 assert.equal(paths[1],'/v1/patients/'+receiptPatient+'/cases/'+receiptCase+'/world-model');
 assert.equal(options[1].method,'GET');assert.equal(options[1].credentials,'omit');
 assert.equal(options[1].headers.Authorization,'Bearer '+token);
});
test('mismatched patient, case, source hash and fabricated model authority fail closed',async()=>{
 const bad=[
 {...worldFixture(),patient_id:'PAT-OTHER-999'},
 {...worldFixture(),case_id:'CASE-BETA'},
 {...worldFixture(),clinical_approval:true},
 {...worldFixture(),observations:[{...worldObservation(),source_sha256:'0'.repeat(64)}]},
 {...worldFixture(),observations:[{...worldObservation(),source_version_id:'SRC-'+'B'.repeat(32)}]},
 {...worldFixture(),summary:{...worldFixture().summary,current_observations:2}},
 ];
 for(const fixture of bad){
  const s=new RegistrySession(async(url)=>response(url.endsWith('/world-model')?fixture:patient()));
  s.connect(token);await s.read(receiptPatient);await s.loadWorldModel(receiptCase);
  assert.equal(s.snapshot().worldModel,null);
  assert.equal(s.snapshot().worldPhase,'error');
 }
});
test('world model permission denial clears prior observations and does not echo provider details',async()=>{
 let deny=false;
 const s=new RegistrySession(async(url)=>url.endsWith('/world-model')?
  deny?response({detail:'sensitive model content'},404):response(worldFixture()):
  response(patient()));
 s.connect(token);await s.read(receiptPatient);await s.loadWorldModel(receiptCase);
 assert.ok(s.snapshot().worldModel);
 deny=true;await s.loadWorldModel(receiptCase);
 assert.equal(s.snapshot().worldModel,null);
 assert.equal(s.snapshot().worldPhase,'error');
 assert.ok(!JSON.stringify(s.snapshot()).includes('sensitive model content'));
});
test('source correction refresh changes fingerprint, never silently promotes old observation',async()=>{
 let corrected=false;
 const correctedId='SRC-'+'C'.repeat(32);
 const base=worldFixture();
 const replacement={
  ...base,source_snapshot_sha256:'b'.repeat(64),
  summary:{...base.summary,superseded_sources:1,unresolved_observations:0},
  current_sources:[{...worldSource(),source_version_id:correctedId,version:2,
                   supersedes_source_id:receiptSource}],
  history:[{...worldSource(),state:'superseded'}],
  observations:[{...worldObservation(),source_version_id:correctedId,
    document_version:2,reported_state:'negative',assertion_id:2}],
  unresolved:[],
 };
 const s=new RegistrySession(async(url)=>url.endsWith('/world-model')?
  response(corrected?replacement:base):response(patient()));
 s.connect(token);await s.read(receiptPatient);await s.loadWorldModel(receiptCase);
 assert.equal(s.snapshot().worldModel.observations[0].source_version_id,receiptSource);
 corrected=true;await s.loadWorldModel(receiptCase);
 assert.equal(s.snapshot().worldModel.source_snapshot_sha256,'b'.repeat(64));
 assert.equal(s.snapshot().worldModel.observations[0].source_version_id,correctedId);
 assert.equal(s.snapshot().worldModel.history[0].source_version_id,receiptSource);
});
test('late world model response cannot restore another patient after selection or disconnect',async()=>{
 const a=deferred();let calls=0;
 const s=new RegistrySession(async(url)=>{
  calls++;return url.endsWith('/world-model')?a.promise:
    response(patient(url.endsWith('PAT-EXAMPLE-002')?'PAT-EXAMPLE-002':receiptPatient));
 });
 s.connect(token);await s.read(receiptPatient);
 const pending=s.loadWorldModel(receiptCase);
 await s.read('PAT-EXAMPLE-002');
 a.resolve(response(worldFixture()));await pending;
 assert.equal(s.snapshot().worldModel,null);
 assert.equal(s.snapshot().patient.patient_id,'PAT-EXAMPLE-002');
 const b=deferred();
 const t=new RegistrySession(async(url)=>url.endsWith('/world-model')?b.promise:response(patient()));
 t.connect(token);await t.read(receiptPatient);const old=t.loadWorldModel(receiptCase);
 t.disconnect();b.resolve(response(worldFixture()));await old;
 assert.equal(t.snapshot().worldModel,null);
});

// A deterministic standard question exercises context verification only;
// it is not a stored patient question, clinical decision or AI prompt run.
const composerQuestion='What source provenance and reported uncertainty require independent verification?';
const composerFixture=()=>({
 contract:'oi.synthetic-source-composer-preflight/1',
 patient_id:receiptPatient,case_id:receiptCase,question:composerQuestion,
 source_snapshot_sha256:'a'.repeat(64),
 selected_source:{
  source_id:receiptSource,document_id:'DOC-ONE',version:1,sha256,line:8,
  finding_key:'marker',reported_state:'not-reported',
  statement:'Independently fictional example.',kind:'pathology',
  event_date:'2026-01-10',issued_at:'2026-01-11',specimen_id:'SPECIMEN-ONE'
 },
 source_context_only:true,biomedical_evidence_rights_verified:false,
 model_execution_authorized:false,durable_question_created:false,
 durable_review_connected:false,clinical_approval:false,
 clinical_interpretation:'not_performed',
 reassessment_policy:'revalidate_source_and_authority_before_any_future_write',
 limitations:'Fictional source text only. No model, clinician review, real consent or medical conclusion.',
 preflight_sha256:'b'.repeat(64),
});
const sourcePreflightPath='/v1/patients/'+receiptPatient+'/cases/'+receiptCase+
 '/composer/source-preflight';
test('Composer source preflight is a read-only bounded POST with independent grant semantics',async()=>{
 const requests=[];
 const s=new RegistrySession(async(url,opts)=>{
  requests.push([url,opts]);
  if(url===sourcePreflightPath)return response(composerFixture());
  if(url.endsWith('/world-model'))return response(worldFixture());
  return response(patient());
 });
 s.connect(token);
 await s.read(receiptPatient);await s.loadWorldModel(receiptCase);
 assert.equal(s.snapshot().composerPreview,null);
 await s.prepareSourceContext(receiptSource,8,composerQuestion);
 assert.equal(s.snapshot().composerPhase,'ready');
 assert.equal(s.snapshot().composerPreview?.selected_source.source_id,receiptSource);
 assert.equal(s.snapshot().composerPreview?.model_execution_authorized,false);
 assert.equal(s.snapshot().composerPreview?.durable_review_connected,false);
 assert.equal(s.snapshot().composerPreview?.durable_question_created,false);
 assert.equal(s.snapshot().composerPreview?.clinical_approval,false);
 assert.equal(requests.length,3);
 assert.equal(requests[2][0],sourcePreflightPath);
 assert.equal(requests[2][1].method,'POST');
 assert.equal(requests[2][1].credentials,'omit');
 assert.equal(requests[2][1].redirect,'error');
 assert.equal(requests[2][1].cache,'no-store');
 assert.deepEqual(JSON.parse(requests[2][1].body),{
  synthetic:true,expected_source_snapshot_sha256:'a'.repeat(64),
  source_id:receiptSource,source_line:8,question:composerQuestion
 });
});
test('Composer preflight cannot be started without selected current source observation',async()=>{
 let calls=0;
 const s=new RegistrySession(async(url)=>{
  calls++;return response(url.endsWith('/world-model')?worldFixture():patient());
 });
 s.connect(token);await s.prepareSourceContext(receiptSource,8);
 assert.equal(calls,0);
 await s.read(receiptPatient);await s.prepareSourceContext(receiptSource,8);
 assert.equal(calls,1);
 await s.loadWorldModel(receiptCase);
 await s.prepareSourceContext(receiptSource,9);
 assert.equal(calls,2);assert.equal(s.snapshot().composerPreview,null);
});
test('Composer preflight permission denial clears previously read World Model context',async()=>{
 let reject=false;
 const s=new RegistrySession(async(url)=>{
  if(url===sourcePreflightPath)return reject?response({detail:'private'},404):response(composerFixture());
  return response(url.endsWith('/world-model')?worldFixture():patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadWorldModel(receiptCase);
 await s.prepareSourceContext(receiptSource,8);
 assert.ok(s.snapshot().composerPreview);
 reject=true;await s.prepareSourceContext(receiptSource,8);
 assert.equal(s.snapshot().composerPreview,null);
 assert.equal(s.snapshot().worldModel,null);
 assert.equal(s.snapshot().composerPhase,'error');
 assert.ok(!JSON.stringify(s.snapshot()).includes('private'));
});
test('stale source snapshot demands refresh and cannot be used for an old preflight',async()=>{
 let stale=false;
 const s=new RegistrySession(async(url)=>{
  if(url===sourcePreflightPath)return stale?response({detail:'stale source'},409):response(composerFixture());
  return response(url.endsWith('/world-model')?worldFixture():patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadWorldModel(receiptCase);
 await s.prepareSourceContext(receiptSource,8);assert.ok(s.snapshot().composerPreview);
 stale=true;await s.prepareSourceContext(receiptSource,8);
 assert.equal(s.snapshot().worldModel,null);
 assert.equal(s.snapshot().composerPreview,null);
 assert.ok(s.snapshot().composerMessage.includes('Refresh Investigations'));
});
test('forged Composer authority, source line, patient or source statement is rejected',async()=>{
 const wrong=[
  {...composerFixture(),model_execution_authorized:true},
  {...composerFixture(),clinical_approval:true},
  {...composerFixture(),durable_review_connected:true},
  {...composerFixture(),selected_source:{...composerFixture().selected_source,line:9}},
  {...composerFixture(),selected_source:{...composerFixture().selected_source,statement:'fabricated'}},
  {...composerFixture(),patient_id:'PAT-OTHER-001'},
  {...composerFixture(),source_snapshot_sha256:'0'.repeat(64)},
 ];
 for(const forged of wrong){
  const s=new RegistrySession(async(url)=>
   response(url===sourcePreflightPath?forged:url.endsWith('/world-model')?worldFixture():patient()));
  s.connect(token);await s.read(receiptPatient);await s.loadWorldModel(receiptCase);
  await s.prepareSourceContext(receiptSource,8);
  assert.equal(s.snapshot().composerPreview,null);
  assert.equal(s.snapshot().composerPhase,'error');
 }
});
test('source refresh, patient switch and disconnect invalidate pending Composer preflight',async()=>{
 const delayed=deferred();
 const s=new RegistrySession(async(url)=>{
  if(url===sourcePreflightPath)return delayed.promise;
  if(url.endsWith('/world-model'))return response(worldFixture());
  return response(patient(url.endsWith('PAT-EXAMPLE-002')?'PAT-EXAMPLE-002':receiptPatient));
 });
 s.connect(token);await s.read(receiptPatient);await s.loadWorldModel(receiptCase);
 const pending=s.prepareSourceContext(receiptSource,8);
 await s.read('PAT-EXAMPLE-002');
 delayed.resolve(response(composerFixture()));await pending;
 assert.equal(s.snapshot().composerPreview,null);
 assert.equal(s.snapshot().worldModel,null);
 const t=new RegistrySession(async(url)=>
  response(url===sourcePreflightPath?composerFixture():url.endsWith('/world-model')?worldFixture():patient()));
 t.connect(token);await t.read(receiptPatient);await t.loadWorldModel(receiptCase);
 await t.prepareSourceContext(receiptSource,8);
 assert.ok(t.snapshot().composerPreview);
 await t.loadWorldModel(receiptCase);
 assert.equal(t.snapshot().composerPreview,null);
 t.disconnect();assert.equal(t.snapshot().composerPreview,null);
});


const savedQuestionId='QUESTION-'+'A'.repeat(32);
const sourceQuestion=(
 state='current_unreviewed_question',overrides={}
)=>({
 question_id:savedQuestionId,patient_id:receiptPatient,case_id:receiptCase,
 question:composerQuestion,source_id:receiptSource,source_line:8,
 source_sha256:sha256,source_version:1,
 source_snapshot_sha256:'a'.repeat(64),preflight_sha256:'b'.repeat(64),
 created_at:'2026-11-02T12:00:00Z',source_context_state:state,
 human_review_state:'not_submitted',clinical_approval:false,
 model_executed:false,...overrides,
});
const sourceQuestions=(questions=[sourceQuestion()])=>({
 patient_id:receiptPatient,case_id:receiptCase,questions,
 synthetic:true,clinical_review_connected:false,clinical_approval:false,
});
const questionsPath='/v1/patients/'+receiptPatient+'/cases/'+receiptCase+'/questions';
test('source questions persist only after explicit source preflight and idempotent POST',async()=>{
 const calls=[];
 let n=0;
 const s=new RegistrySession(async(url,init)=>{
  calls.push([url,init]);
  if(url===sourcePreflightPath)return response(composerFixture());
  if(url===questionsPath)return response({question_id:savedQuestionId,duplicate:++n>1},n>1?200:201);
  if(url.endsWith('/world-model'))return response(worldFixture());
  return response(patient());
 });
 s.connect(token);
 await s.savePreparedQuestion();
 assert.equal(s.snapshot().savedQuestion,null);
 assert.equal(calls.length,0);
 await s.read(receiptPatient);await s.loadWorldModel(receiptCase);
 await s.prepareSourceContext(receiptSource,8,composerQuestion);
 assert.equal(s.snapshot().savedQuestion,null);
 await s.savePreparedQuestion();
 assert.equal(s.snapshot().savedQuestion.question_id,savedQuestionId);
 assert.equal(s.snapshot().questionSavePhase,'saved');
 assert.equal(s.snapshot().composerPreview.clinical_approval,false);
 assert.equal(s.snapshot().composerPreview.durable_review_connected,false);
 assert.equal(calls[3][0],questionsPath);
 assert.equal(calls[3][1].method,'POST');
 assert.equal(calls[3][1].credentials,'omit');
 assert.equal(calls[3][1].redirect,'error');
 assert.equal(calls[3][1].cache,'no-store');
 const body=JSON.parse(calls[3][1].body);
 assert.equal(body.synthetic,true);
 assert.equal(body.source_id,receiptSource);
 assert.equal(body.source_line,8);
 assert.equal(body.expected_source_snapshot_sha256,'a'.repeat(64));
 assert.equal(body.expected_preflight_sha256,'b'.repeat(64));
 assert.ok(typeof body.request_key==='string'&&body.request_key.length>=3);
 await s.savePreparedQuestion();
 assert.deepEqual(JSON.parse(calls[4][1].body),body);
 assert.equal(s.snapshot().savedQuestion.duplicate,true);
});
test('network uncertainty retries with one stable question-intent key',async()=>{
 const posts=[];
 const s=new RegistrySession(async(url,init)=>{
  if(url===questionsPath){
   posts.push(init.body);
   if(posts.length===1)throw Error('network may have saved the request');
   return response({question_id:savedQuestionId,duplicate:true},200);
  }
  return response(url===sourcePreflightPath?composerFixture():url.endsWith('/world-model')?worldFixture():patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadWorldModel(receiptCase);
 await s.prepareSourceContext(receiptSource,8,composerQuestion);
 await s.savePreparedQuestion();
 assert.equal(s.snapshot().savedQuestion,null);
 assert.ok(s.snapshot().questionSaveMessage.includes('outcome unknown'));
 await s.savePreparedQuestion();
 assert.equal(posts.length,2);
 assert.equal(posts[0],posts[1]);
 assert.equal(s.snapshot().savedQuestion.duplicate,true);
});
test('saved questions read current versus reassessment states, never clinician approval',async()=>{
 let changed=false;
 const s=new RegistrySession(async url=>{
  if(url===questionsPath)return response(sourceQuestions([
    sourceQuestion(changed?'source_reassessment_required':'current_unreviewed_question')
  ]));
  return response(patient());
 });
 s.connect(token);await s.read(receiptPatient);
 await s.loadSavedQuestions(receiptCase);
 assert.equal(s.snapshot().questions[0].source_context_state,'current_unreviewed_question');
 assert.equal(s.snapshot().questions[0].human_review_state,'not_submitted');
 assert.equal(s.snapshot().questions[0].clinical_approval,false);
 changed=true;await s.loadSavedQuestions(receiptCase);
 assert.equal(s.snapshot().questions[0].source_context_state,'source_reassessment_required');
 assert.equal(s.snapshot().questions[0].source_id,receiptSource);
});
test('cross-patient question list, forged review status and bad source references fail closed',async()=>{
 const forged=[
  {...sourceQuestions(),patient_id:'PAT-OTHER-001'},
  {...sourceQuestions(),case_id:'CASE-BETA'},
  {...sourceQuestions(),clinical_review_connected:true},
  sourceQuestions([sourceQuestion('current_unreviewed_question',{clinical_approval:true})]),
  sourceQuestions([sourceQuestion('current_unreviewed_question',{human_review_state:'approved'})]),
  sourceQuestions([sourceQuestion('current_unreviewed_question',{source_id:'SRC-'+'F'.repeat(31)})]),
 ];
 for(const responseBody of forged){
  const s=new RegistrySession(async url=>response(url===questionsPath?responseBody:patient()));
  s.connect(token);await s.read(receiptPatient);await s.loadSavedQuestions(receiptCase);
  assert.equal(s.snapshot().questions,null);
  assert.equal(s.snapshot().questionListPhase,'error');
 }
});
test('question read revocation removes an earlier visible history',async()=>{
 let revoked=false;
 const s=new RegistrySession(async url=>response(url===questionsPath?
  revoked?{detail:'private review data'}:sourceQuestions():patient(),revoked&&url===questionsPath?404:200));
 s.connect(token);await s.read(receiptPatient);await s.loadSavedQuestions(receiptCase);
 assert.equal(s.snapshot().questions.length,1);
 revoked=true;await s.loadSavedQuestions(receiptCase);
 assert.equal(s.snapshot().questions,null);
 assert.equal(s.snapshot().questionListPhase,'error');
 assert.ok(!JSON.stringify(s.snapshot()).includes('private review data'));
});
test('changed source before question save rejects and clears obsolete preflight',async()=>{
 let stale=false;
 const s=new RegistrySession(async url=>{
  if(url===questionsPath)return stale?response({detail:'source changed'},409):
    response({question_id:savedQuestionId,duplicate:false},201);
  return response(url===sourcePreflightPath?composerFixture():
    url.endsWith('/world-model')?worldFixture():patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadWorldModel(receiptCase);
 await s.prepareSourceContext(receiptSource,8,composerQuestion);
 stale=true;await s.savePreparedQuestion();
 assert.equal(s.snapshot().worldModel,null);
 assert.equal(s.snapshot().composerPreview,null);
 assert.equal(s.snapshot().savedQuestion,null);
 assert.equal(s.snapshot().questionSavePhase,'error');
});
test('patient switching, navigation reset and disconnect invalidate durable question UI responses',async()=>{
 const late=deferred();
 const s=new RegistrySession(async url=>{
  if(url===questionsPath)return late.promise;
  return response(patient(url.endsWith('PAT-EXAMPLE-002')?'PAT-EXAMPLE-002':receiptPatient));
 });
 s.connect(token);await s.read(receiptPatient);
 const pending=s.loadSavedQuestions(receiptCase);
 await s.read('PAT-EXAMPLE-002');
 late.resolve(response(sourceQuestions()));await pending;
 assert.equal(s.snapshot().questions,null);
 const t=new RegistrySession(async url=>response(
  url===questionsPath?sourceQuestions():
  url===sourcePreflightPath?composerFixture():
  url.endsWith('/world-model')?worldFixture():patient()
 ));
 t.connect(token);await t.read(receiptPatient);await t.loadSavedQuestions(receiptCase);
 assert.equal(t.snapshot().questions.length,1);
 t.clearWorldModel();
 assert.equal(t.snapshot().questions,null);
 await t.loadWorldModel(receiptCase);await t.prepareSourceContext(receiptSource,8,composerQuestion);
 await t.savePreparedQuestion();
 t.disconnect();assert.equal(t.snapshot().questions,null);
 assert.equal(t.snapshot().savedQuestion,null);
});


const reviewReceiptId='REVIEW-'+'D'.repeat(32);
const reviewFingerprint='c'.repeat(64);
const reviewItem=(overrides={})=>({
 question_id:savedQuestionId,patient_id:receiptPatient,case_id:receiptCase,
 question:composerQuestion,source_id:receiptSource,source_line:8,source_sha256:sha256,
 source_version:1,source_snapshot_sha256:'a'.repeat(64),
 preflight_sha256:'b'.repeat(64),created_at:'2026-11-02T11:30:00Z',
 kind:'source-question',queue_fingerprint:reviewFingerprint,
 source_context_state:'current_unreviewed_question',
 review_state:'awaiting_independent_verification',
 current_return_receipt_id:null,return_count:0,prior_return_count:0,
 clinical_approval:false,reviewer_identity_verified:false,...overrides
});
const reviewReceipt=()=>({
 receipt_id:reviewReceiptId,question_id:savedQuestionId,
 queue_fingerprint:reviewFingerprint,source_snapshot_sha256:'a'.repeat(64),
 actor_label:'ACTOR-FICTIONAL',action:'returned',
 reason:'Please independently verify this fictional source quotation and uncertainty.',
 created_at:'2026-11-02T11:32:00Z',reviewer_identity_verified:false,
 external_notification_sent:false,clinical_approval:false
});
const reviewQueue=(items=[reviewItem()],receipts=[])=>({
 contract:'oi.synthetic-question-review-return-queue/1',
 patient_id:receiptPatient,case_id:receiptCase,synthetic:true,items,receipts,
 external_notification_sent:false,reviewer_identity_verified:false,
 clinical_approval:false,review_completion_supported:false
});
const reviewPath='/v1/patients/'+receiptPatient+'/cases/'+receiptCase+'/review-queue';
const reviewReturnPath='/v1/patients/'+receiptPatient+'/cases/'+receiptCase+
 '/questions/'+savedQuestionId+'/return-for-verification';
test('review queue stays unavailable without authorized patient and case context',async()=>{
 let calls=0;const s=new RegistrySession(async()=>{calls++;return response(patient())});
 s.connect(token);await s.loadReviewQueue(receiptCase);
 assert.equal(calls,0);assert.equal(s.snapshot().reviewQueue,null);
 await s.read(receiptPatient);await s.loadReviewQueue('../OTHER');
 assert.equal(calls,1);assert.equal(s.snapshot().reviewPhase,'error');
});
test('review return is a distinct nonterminal authorization action and never calls model',async()=>{
 const requests=[];
 const s=new RegistrySession(async(url,opts)=>{
  requests.push([url,opts]);
  if(url===reviewPath)return response(reviewQueue());
  if(url===reviewReturnPath)return response({
   receipt_id:reviewReceiptId,question_id:savedQuestionId,duplicate:false
  },201);
  return response(patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadReviewQueue(receiptCase);
 assert.equal(s.snapshot().reviewPhase,'ready');
 assert.equal(s.snapshot().reviewQueue.items[0].review_state,'awaiting_independent_verification');
 assert.equal(s.snapshot().reviewReturn,null);
 assert.equal(requests.length,2);
 await s.returnReviewQuestion(savedQuestionId,reviewFingerprint,
   'Please independently verify this fictional source quotation and uncertainty.');
 assert.equal(s.snapshot().reviewReturn?.receipt_id,reviewReceiptId);
 assert.equal(s.snapshot().reviewReturnPhase,'saved');
 assert.equal(requests.length,3);
 assert.equal(requests[2][0],reviewReturnPath);
 assert.equal(requests[2][1].method,'POST');
 assert.equal(requests[2][1].credentials,'omit');
 assert.equal(requests[2][1].redirect,'error');
 const sent=JSON.parse(requests[2][1].body);
 assert.equal(sent.synthetic,true);
 assert.equal(sent.expected_queue_fingerprint,reviewFingerprint);
 assert.equal(sent.reason,'Please independently verify this fictional source quotation and uncertainty.');
 assert.equal(typeof sent.request_key,'string');
 assert.equal(s.snapshot().reviewQueue.clinical_approval,false);
 assert.equal(s.snapshot().reviewQueue.review_completion_supported,false);
});
test('uncertain network return can retry with exact same durable request key',async()=>{
 const requests=[];let attempts=0;
 const s=new RegistrySession(async(url,opts)=>{
  if(url===reviewPath)return response(reviewQueue());
  if(url===reviewReturnPath){
   requests.push(JSON.parse(opts.body));attempts++;
   if(attempts===1)throw Error('response lost after commit');
   return response({receipt_id:reviewReceiptId,question_id:savedQuestionId,duplicate:true});
  }
  return response(patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadReviewQueue(receiptCase);
 await s.returnReviewQuestion(savedQuestionId,reviewFingerprint);
 assert.equal(s.snapshot().reviewReturn,null);
 assert.equal(s.snapshot().reviewReturnPhase,'error');
 await s.returnReviewQuestion(savedQuestionId,reviewFingerprint);
 assert.equal(s.snapshot().reviewReturn?.duplicate,true);
 assert.equal(requests.length,2);
 assert.equal(requests[0].request_key,requests[1].request_key);
 assert.deepEqual(requests[0],requests[1]);
});
test('review return is blocked for historical source and forged clinical approval',async()=>{
 let calls=0;
 const historical=reviewItem({
  source_context_state:'source_reassessment_required',
  review_state:'source_reassessment_required',queue_fingerprint:null,
  prior_return_count:1
 });
 const s=new RegistrySession(async(url)=>{
  calls++;
  return response(url===reviewPath?reviewQueue([historical],[reviewReceipt()]):patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadReviewQueue(receiptCase);
 assert.equal(s.snapshot().reviewQueue.items[0].review_state,'source_reassessment_required');
 await s.returnReviewQuestion(savedQuestionId,reviewFingerprint);
 assert.equal(calls,2);assert.equal(s.snapshot().reviewReturn,null);
 for(const bad of [
  {...reviewQueue(),review_completion_supported:true},
  {...reviewQueue(),clinical_approval:true},
  {...reviewQueue(),patient_id:'PAT-OTHER-001'},
  {...reviewQueue(),items:[reviewItem({clinical_approval:true})]},
  {...reviewQueue(),items:[reviewItem({source_id:'SRC-'+'E'.repeat(31)})]},
  {...reviewQueue(),items:[reviewItem({return_count:1})]},
  {...reviewQueue(),items:[reviewItem({queue_fingerprint:null})]},
 ]){
  const t=new RegistrySession(async(url)=>response(url===reviewPath?bad:patient()));
  t.connect(token);await t.read(receiptPatient);await t.loadReviewQueue(receiptCase);
  assert.equal(t.snapshot().reviewQueue,null);assert.equal(t.snapshot().reviewPhase,'error');
 }
});
test('review grant denial clears prior queue and opaque source references',async()=>{
 let rejected=false;
 const s=new RegistrySession(async(url)=>
  response(url===reviewPath?rejected?{detail:'private source notes'}:reviewQueue():patient(),
           rejected&&url===reviewPath?404:200));
 s.connect(token);await s.read(receiptPatient);await s.loadReviewQueue(receiptCase);
 assert.equal(s.snapshot().reviewQueue.items.length,1);
 rejected=true;await s.loadReviewQueue(receiptCase);
 assert.equal(s.snapshot().reviewQueue,null);
 assert.equal(s.snapshot().reviewPhase,'error');
 assert.ok(!JSON.stringify(s.snapshot()).includes('private source notes'));
});
test('patient switch and navigation reset block stale review queue or return responses',async()=>{
 const late=deferred();
 const s=new RegistrySession(async(url)=>{
  if(url===reviewPath)return late.promise;
  return response(patient(url.endsWith('PAT-EXAMPLE-002')?'PAT-EXAMPLE-002':receiptPatient));
 });
 s.connect(token);await s.read(receiptPatient);
 const pending=s.loadReviewQueue(receiptCase);
 await s.read('PAT-EXAMPLE-002');late.resolve(response(reviewQueue()));await pending;
 assert.equal(s.snapshot().reviewQueue,null);
 const t=new RegistrySession(async(url)=>response(url===reviewPath?reviewQueue():patient()));
 t.connect(token);await t.read(receiptPatient);await t.loadReviewQueue(receiptCase);
 assert.ok(t.snapshot().reviewQueue);
 t.clearWorldModel();assert.equal(t.snapshot().reviewQueue,null);
 t.disconnect();assert.equal(t.snapshot().reviewReturn,null);
});
test('returned receipt can be read as immutable history, never as a clinical decision',async()=>{
 const received=reviewReceipt();
 const item=reviewItem({
  review_state:'returned_for_independent_verification',
  current_return_receipt_id:reviewReceiptId,return_count:1
 });
 const s=new RegistrySession(async(url)=>
  response(url===reviewPath?reviewQueue([item],[received]):patient()));
 s.connect(token);await s.read(receiptPatient);await s.loadReviewQueue(receiptCase);
 assert.equal(s.snapshot().reviewQueue.receipts.length,1);
 assert.equal(s.snapshot().reviewQueue.items[0].review_state,'returned_for_independent_verification');
 assert.equal(s.snapshot().reviewQueue.receipts[0].action,'returned');
 assert.equal(s.snapshot().reviewQueue.receipts[0].clinical_approval,false);
});
