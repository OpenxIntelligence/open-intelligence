import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {prepareLaboratoryFile,parseLaboratoryReceipt} from '../.test-dist/laboratory-fhir.js';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {DocumentClient} from '../.test-dist/reviewed-documents.js';
const PID='PAT-LAB-001',CID='CASE-LAB',SID='SRC-'+'A'.repeat(32),TOKEN='fictional_test_credential_000000000001';
const RAW=readFileSync(new URL('../../../examples/synthetic/fictional-fhir-r4-lab-bundle.json',import.meta.url),'utf8');
const HASH=createHash('sha256').update(RAW).digest('hex');
const PAT={patient_id:PID,origin_org:'ORG-0',created_at:'2026-11-02T10:00:00Z',status:'active',revision:1};
const binding=case_id=>({case_id,patient_id:PID,source_organization:'FICT-ORG',source_system:'FICT-SYS',source_subject_ref:'FICTIONAL-PATIENT-A',review_ref:'FICT-REVIEW',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false});
const MAP={patient_id:PID,mappings:[binding(CID),binding('CASE-OTHER')],synthetic:true,source_identity_verified:false,clinical_sources_linked:false};
const META={source_id:SID,document_id:'FICTIONAL-REPORT-A',version:1,sha256:HASH,kind:'laboratory',event_date:'2026-04-03',issued_at:'2026-04-04',received_at:'2026-11-02T10:00:00Z',specimen_id:'FICTIONAL-SPECIMEN-A',state:'current',supersedes_id:null};
const INDEX={contract:'oi.synthetic-original-sources/1',patient_id:PID,case_id:CID,access_receipt_id:'ACCESS-'+'B'.repeat(32),sources:[META],source_reported_assertions:[],synthetic:true,clinical_interpretation:false,research_review_invalidation_integrated:false};
const RECEIPT={source_id:SID,version:1,duplicate:false,original_sha256:HASH,observation_count:1};
const reply=(v,status=200)=>new Response(JSON.stringify(v),{status,headers:{'Content-Type':'application/json'}});
const bytes=s=>new TextEncoder().encode(s);
const deferred=()=>{let done;return{promise:new Promise(r=>done=r),resolve:x=>done(x)}};
async function ready(operation){
 const flags={patient:200,cases:200,sources:200};const calls=[];const session=new RegistrySession(async(url,init)=>{
  calls.push([url,init]);
  if(url==='/v1/patients/'+PID)return reply(PAT,flags.patient);
  if(url.endsWith('/case-bindings'))return reply(MAP,flags.cases);
  if(init.method==='GET'&&url.endsWith('/sources'))return reply({...INDEX,case_id:url.includes('/CASE-OTHER/')?'CASE-OTHER':CID},flags.sources);
  return operation(url,init);
 });
 session.connect(TOKEN);await session.read(PID);await session.loadCases();await session.loadSources(CID);calls.length=0;
 return{session,calls,flags};
}
test('local laboratory inspection preserves decimal spelling, whitespace, Unicode and exact digest',async()=>{
 const raw=RAW.replace('Fictional plasma sample','Fictional café plasma sample')+'\r\n';
 const file=await prepareLaboratoryFile(bytes(raw),'lab.JSON');
 assert.equal(file.text,raw);assert.ok(file.text.includes('4.20'));assert.equal(file.byteCount,bytes(raw).length);
 assert.equal(file.sha256,createHash('sha256').update(raw).digest('hex'));
});
test('local laboratory selection rejects invalid UTF-8, BOM, oversize and unsupported envelopes',async()=>{
 for(const [b,name] of [[new Uint8Array([255]),'lab.json'],[bytes('\uFEFF'+RAW),'lab.json'],[bytes(RAW),'lab.txt'],
  [bytes('x'.repeat(65537)),'lab.json'],[bytes('{}'),'lab.json'],[bytes('[]'),'lab.json'],[bytes('invalid'),'lab.json']])
   await assert.rejects(()=>prepareLaboratoryFile(b,name));
});
test('laboratory receipt binds exact original hash, strict keys, bounded counts and HTTP outcome',()=>{
 assert.equal(parseLaboratoryReceipt(RECEIPT,HASH,201).source_id,SID);
 assert.equal(parseLaboratoryReceipt({...RECEIPT,duplicate:true},HASH,200).duplicate,true);
 for(const value of [{...RECEIPT,original_sha256:'f'.repeat(64)},{...RECEIPT,observation_count:0},{...RECEIPT,observation_count:17},
  {...RECEIPT,clinical_approval:true},{...RECEIPT,version:1.5},{...RECEIPT,duplicate:true}])assert.throws(()=>parseLaboratoryReceipt(value,HASH,201));
 assert.throws(()=>parseLaboratoryReceipt(RECEIPT,HASH,200));
});
test('laboratory import requires active exact case, confirmation and a current laboratory predecessor',async()=>{
 const{session,calls}=await ready(()=>reply(RECEIPT,201));
 await session.importLaboratory(CID,RAW,false);await session.importLaboratory('CASE-UNKNOWN',RAW,true);
 await session.importLaboratory(CID,RAW,true,'SRC-'+'F'.repeat(32));assert.equal(calls.length,0);
});
test('import sends exact JSON to the fixed route with explicit predecessor and refreshes sources',async()=>{
 const{session,calls}=await ready(()=>reply(RECEIPT,201));
 await session.importLaboratory(CID,RAW,true,SID);
 const write=calls.find(x=>x[1].method==='POST');const payload=JSON.parse(write[1].body);
 assert.equal(write[0],`/v1/patients/${PID}/cases/${CID}/laboratory/fhir-r4/sources`);
 assert.equal(payload.bundle_json,RAW);assert.equal(payload.expected_previous_source_id,SID);assert.equal(payload.synthetic,true);
 assert.match(payload.request_key,/^[a-f0-9-]{36}$/);assert.equal(write[1].credentials,'omit');assert.equal(write[1].redirect,'error');
 assert.equal(session.snapshot().laboratoryPhase,'saved');assert.equal(session.snapshot().laboratoryReceipt.original_sha256,HASH);
 assert.equal(session.snapshot().sourceIndex.case_id,CID);assert.equal(session.snapshot().worldModel,null);
});
test('uncertain import retains exact command across same-case metadata refresh and retries only explicitly',async()=>{
 let attempt=0;const{session,calls}=await ready(()=>{if(++attempt===1)throw Error('transport failed '+TOKEN);return reply({...RECEIPT,duplicate:true},200);});
 await session.importLaboratory(CID,RAW,true);
 assert.equal(session.snapshot().laboratoryPhase,'unknown');assert.equal(attempt,1);
 const first=calls.find(x=>x[1].method==='POST')[1].body;
 await session.importLaboratory(CID,RAW+' ',true);assert.equal(attempt,1);
 await session.loadCases();await session.loadSources(CID);assert.equal(session.snapshot().laboratoryPhase,'unknown');
 await session.retryLaboratoryImport();const posts=calls.filter(x=>x[1].method==='POST');
 assert.equal(posts.length,2);assert.equal(posts[1][1].body,first);assert.equal(session.snapshot().laboratoryReceipt.duplicate,true);
 assert.ok(!JSON.stringify(session.snapshot()).includes(TOKEN));
});
test('concurrent imports submit only once and malformed/failed success remains uncertain',async()=>{
 for(const response of [reply({},201),reply({},503),reply({...RECEIPT,original_sha256:'0'.repeat(64)},201)]){
  const hold=deferred(),started=deferred();
  const{session,calls}=await ready(()=>{started.resolve();return hold.promise;});
  const first=session.importLaboratory(CID,RAW,true);
  await Promise.race([started.promise,first.then(()=>{throw Error('First import ended before transport');})]);
  await session.importLaboratory(CID,RAW,true);assert.equal(calls.filter(x=>x[1].method==='POST').length,1);
  hold.resolve(response);await first;assert.equal(session.snapshot().laboratoryPhase,'unknown');
 }
});
test('credential or case denial clears original and pending import even with non-JSON body',async()=>{
 for(const status of [401,403,404]){
  const{session}=await ready(()=>new Response('Denied',{status,headers:{'Content-Type':'text/html'}}));
  await session.importLaboratory(CID,RAW,true);assert.equal(session.snapshot().laboratoryIntent,null);
  assert.equal(session.snapshot().sourceIndex,null);assert.equal(session.snapshot().laboratoryReceipt,null);
 }
});
test('profile rejection is distinct from an unknown outcome and permits a corrected explicit command',async()=>{
 const{session}=await ready(()=>reply({},422));await session.importLaboratory(CID,RAW,true);
 assert.equal(session.snapshot().laboratoryPhase,'error');assert.equal(session.snapshot().laboratoryIntent,null);
 assert.equal(session.snapshot().sourceIndex.case_id,CID);
});
test('different case and disconnect clear pending original and prevent late resurrection',async()=>{
 for(const change of [s=>s.loadSources('CASE-OTHER'),s=>s.disconnect()]){
  const sent=deferred(), hold=deferred();
  const{session}=await ready(()=>{sent.resolve();return hold.promise;});
  const pending=session.importLaboratory(CID,RAW,true);await sent.promise;
  await change(session);hold.resolve(reply(RECEIPT,201));await pending;
  assert.equal(session.snapshot().laboratoryReceipt,null);assert.equal(session.snapshot().laboratoryIntent,null);
 }
});
test('a same-case refresh during sending retains unknown command and suppresses old success',async()=>{
 const sent=deferred(), hold=deferred();
 const{session}=await ready(()=>{sent.resolve(); return hold.promise;});
 const pending=session.importLaboratory(CID,RAW,true);await sent.promise;
 await session.loadSources(CID);assert.equal(session.snapshot().laboratoryPhase,'unknown');
 hold.resolve(reply(RECEIPT,201));await pending;assert.equal(session.snapshot().laboratoryPhase,'unknown');
 assert.equal(session.snapshot().laboratoryReceipt,null);assert.ok(session.snapshot().laboratoryIntent);
});
test('document denial clears uncertain laboratory original through the same shared scope owner',async()=>{
 const{session}=await ready(url=>url.endsWith('/documents')?reply({},404):Promise.reject(Error('lost reply')));
 await session.importLaboratory(CID,RAW,true);assert.equal(session.snapshot().laboratoryPhase,'unknown');
 const documents=new DocumentClient((path,body)=>session.documentRequest(CID,path,body));await documents.load();
 assert.equal(session.snapshot().laboratoryIntent,null);assert.equal(session.snapshot().sourceIndex,null);
});
test('unpaired Unicode is refused before import rather than silently rewriting original bytes',async()=>{
 const{session,calls}=await ready(()=>reply(RECEIPT,201));await session.importLaboratory(CID,RAW+'\ud800',true);
 assert.equal(calls.length,0);assert.equal(session.snapshot().laboratoryPhase,'error');
});

test('same-patient recheck preserves the exact uncertain amendment key through transient read failures',async()=>{
 let attempt=0;const{session,calls,flags}=await ready(()=>{if(++attempt===1)throw Error('lost committed reply');return reply({...RECEIPT,version:2,duplicate:true},200);});
 await session.importLaboratory(CID,RAW,true,SID);const original=session.snapshot().laboratoryIntent.body;
 flags.patient=503;await session.read(PID);assert.equal(session.snapshot().laboratoryPhase,'unknown');
 assert.equal(session.snapshot().laboratoryIntent.body,original);
 flags.patient=200;await session.read(PID);flags.cases=503;await session.loadCases();
 assert.equal(session.snapshot().laboratoryIntent.body,original);
 flags.cases=200;await session.loadCases();flags.sources=503;await session.loadSources(CID);
 assert.equal(session.snapshot().laboratoryIntent.body,original);
 flags.sources=200;await session.loadCases();await session.loadSources(CID);await session.retryLaboratoryImport();
 const posts=calls.filter(x=>x[1].method==='POST');assert.equal(posts.length,2);assert.equal(posts[1][1].body,original);
 assert.equal(JSON.parse(posts[1][1].body).expected_previous_source_id,SID);assert.equal(session.snapshot().laboratoryReceipt.version,2);
});
test('explicit patient, source or case denial clears uncertain laboratory custody recovery',async()=>{
 for(const denied of ['patient','cases','sources']){
  const{session,flags}=await ready(()=>Promise.reject(Error('lost reply')));await session.importLaboratory(CID,RAW,true);
  flags[denied]=404;
  if(denied==='patient')await session.read(PID);else if(denied==='cases')await session.loadCases();else await session.loadSources(CID);
  assert.equal(session.snapshot().laboratoryIntent,null);assert.equal(session.snapshot().laboratoryReceipt,null);
 }
});
test('same-patient recheck during sending retains unknown request and late old reply cannot overwrite recovered success',async()=>{
 const sent=deferred(), hold=deferred();let attempt=0;
 const{session,calls}=await ready(()=>{
  if(++attempt===1){sent.resolve();return hold.promise;}
  return reply({...RECEIPT,duplicate:true},200);
 });
 const old=session.importLaboratory(CID,RAW,true);await sent.promise;
 const original=session.snapshot().laboratoryIntent.body;
 await session.read(PID);await session.loadCases();await session.loadSources(CID);
 assert.equal(session.snapshot().laboratoryPhase,'unknown');await session.retryLaboratoryImport();
 hold.resolve(reply({},503));await old;
 assert.equal(session.snapshot().laboratoryPhase,'saved');assert.equal(session.snapshot().laboratoryReceipt.duplicate,true);
 assert.equal(calls.filter(x=>x[1].method==='POST')[1][1].body,original);
});

test('a blocked World Model read cannot strand an in-flight import without receipt or recovery',async()=>{
 const sent=deferred(), hold=deferred();
 const{session}=await ready(()=>{sent.resolve(); return hold.promise;});
 const pending=session.importLaboratory(CID,RAW,true);await sent.promise;
 await session.loadWorldModel(CID);hold.resolve(reply(RECEIPT,201));await pending;
 assert.equal(session.snapshot().laboratoryPhase,'saved');assert.equal(session.snapshot().laboratoryReceipt.source_id,SID);
});
test('an overlapping text import cannot leave the laboratory preflight mutex stuck',async()=>{
 const digest=crypto.subtle.digest,hold=deferred(),textReply=deferred();
 const raw=`OI-SYNTHETIC-REPORT/1\nPatient: ${CID}\nDocument: FICTIONAL-TEXT\nType: clinical\nEvent-Date: 2026-01-01\nIssued-At: 2026-01-02\nFinding: note|reported|Fictional text.\n`;
 const{session,calls}=await ready(url=>url.endsWith('/laboratory/fhir-r4/sources')?reply(RECEIPT,201):textReply.promise);
 try{
  crypto.subtle.digest=()=>hold.promise;
  const preparing=session.importLaboratory(CID,RAW,true);
  const textImport=session.importSource(CID,raw,true);
  crypto.subtle.digest=digest;
  hold.resolve(await digest.call(crypto.subtle,'SHA-256',bytes(RAW)));await preparing;
  assert.equal(session.snapshot().importOutcome,'sending');
  textReply.resolve(reply({result:'imported',duplicate:false,source_id:SID,version:1},201));await textImport;
  await session.importLaboratory(CID,RAW,true);
  assert.equal(session.snapshot().laboratoryPhase,'saved');
  assert.equal(calls.filter(x=>x[0].endsWith('/laboratory/fhir-r4/sources')).length,1);
 }finally{crypto.subtle.digest=digest;}
});

const previewRow = {
 reference:'Observation/FICTIONAL-OBS-A', loinc_code:'777-3',
 effective_at:'2026-04-03T09:05:00-04:00', issued_at:'2026-04-04T12:00:00Z',
 source_reported:true, clinical_review:'not_performed', status:'reported_value',
 value_text:'4.20', unit_code:'10*9/L', absent_reason:null,
};
const previewResponse = {
 contract:'oi.fhir-r4-laboratory-preview/1', patient_id:PID, case_id:CID,
 source_organization:'FICT-ORG', source_system:'FICT-SYS', mapped_subject_reference:'Patient/FICTIONAL-PATIENT-A',
 original_sha256:HASH, original_byte_count:bytes(RAW).length, specimen_reference:'Specimen/FICTIONAL-SPECIMEN-A',
 specimen_type_text:'Fictional plasma sample', specimen_collected_at:previewRow.effective_at,
 report_reference:'DiagnosticReport/FICTIONAL-REPORT-A', observations:[previewRow],
 synthetic:true, persisted:false, clinical_review:'not_performed', verified_identity:false, source_version_created:false,
};

test('explicit structured preview sends only the original to the read-only route and preserves decimal spelling',async()=>{
 const file=await prepareLaboratoryFile(bytes(RAW),'lab.json');
 const {session,calls}=await ready(()=>reply(previewResponse));
 const result=await session.previewLaboratory(CID,file);
 assert.deepEqual(result.observations,[previewRow]);
 assert.equal(result.specimen_reference,previewResponse.specimen_reference);
 assert.equal(calls.length,1);
 const [url,request]=calls[0];
 assert.equal(url,`/v1/patients/${PID}/cases/${CID}/laboratory/fhir-r4/preview`);
 assert.equal(request.method,'POST');
 assert.deepEqual(JSON.parse(request.body),{synthetic:true,bundle_json:RAW});
 assert.equal(session.snapshot().laboratoryIntent,null);
 assert.equal(session.snapshot().laboratoryReceipt,null);
});

test('preview rejects mismatched source, binding, review claims and ambiguous observations',async()=>{
 const file=await prepareLaboratoryFile(bytes(RAW),'lab.json');
 for(const patch of [
  {patient_id:'PATIENT-OTHER'},{case_id:'CASE-OTHER'},{mapped_subject_reference:'Patient/other'},
  {source_organization:'OTHER'},{source_system:'OTHER'},{original_sha256:'0'.repeat(64)},
  {original_byte_count:file.byteCount+1},{persisted:true},{clinical_review:'approved'},
  {verified_identity:true},{source_version_created:true},{clinical_advice:'unrequested'},
  {specimen_reference:'Observation/A'},{specimen_collected_at:'2026-11-05T12:00:00+14:01'},{observations:[]},{observations:[previewRow,previewRow]},
  ...[{value_text:4.2},{unit_code:null},{absent_reason:'masked'},{source_reported:false},
   {reference:'Specimen/A'},{issued_at:'2026-11-05T12:00:00-15:00'},{effective_at:'2026-02-31T12:00:00Z'},{clinical_review:'approved'},
   {status:'reported_absent',value_text:null,unit_code:null,absent_reason:'unsupported'}]
   .map(change=>({observations:[{...previewRow,...change}]})),
 ]){
  const {session}=await ready(()=>reply({...previewResponse,...patch}));
  await assert.rejects(()=>session.previewLaboratory(CID,file),/preview/i);
 }
});

test('preview accepts an absent result and a missing optional diagnostic report, with no save',async()=>{
 const file=await prepareLaboratoryFile(bytes(RAW),'lab.json');
 const row={...previewRow,effective_at:'2026-04-03T09:05:00+14:00',status:'reported_absent',value_text:null,unit_code:null,absent_reason:'not-performed'};
 const {session}=await ready(()=>reply({...previewResponse,report_reference:null,observations:[row]}));
 const preview=await session.previewLaboratory(CID,file);
 assert.equal(preview.report_reference,null);
 assert.deepEqual(preview.observations,[row]);
});

test('preview rechecks case scope on return, clears denied access, and cannot submit a write',async()=>{
 const file=await prepareLaboratoryFile(bytes(RAW),'lab.json');
 for(const status of [401,403,404]){
  const {session}=await ready(()=>new Response('denied',{status}));
  await assert.rejects(()=>session.previewLaboratory(CID,file));
  assert.equal(session.snapshot().sourceIndex,null);
 }
 const hold=deferred(),{session,calls}=await ready(()=>hold.promise);
 await assert.rejects(()=>session.previewLaboratory('CASE-OTHER',file));
 assert.equal(calls.length,0);
 const pending=session.previewLaboratory(CID,file);
 await session.loadSources('CASE-OTHER');
 hold.resolve(reply(previewResponse));
 await assert.rejects(()=>pending);
 assert.equal(session.snapshot().sourceIndex.case_id,'CASE-OTHER');
 assert.equal(calls.filter(([url,init])=>url.endsWith('/sources')&&init.method==='POST').length,0);
});

test('dismissing another original cannot mask a preview denial on the same patient and case',async()=>{
 const file=await prepareLaboratoryFile(bytes(RAW),'lab.json');
 for(const status of [401,403,404]){
  const hold=deferred();
  const {session}=await ready(()=>hold.promise);
  const pending=session.previewLaboratory(CID,file);
  session.dismissOriginal();
  hold.resolve(new Response('Denied',{status}));
  await assert.rejects(()=>pending);
  assert.equal(session.snapshot().sourceIndex,null);
  if(status===401) assert.equal(session.snapshot().connected,false);
 }
});
