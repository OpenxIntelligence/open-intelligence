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
  const hold=deferred();const{session,calls}=await ready(()=>hold.promise);
  const first=session.importLaboratory(CID,RAW,true);await new Promise(r=>setTimeout(r,10));
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
  const hold=deferred();const{session}=await ready(()=>hold.promise);
  const pending=session.importLaboratory(CID,RAW,true);await new Promise(r=>setTimeout(r,10));
  await change(session);hold.resolve(reply(RECEIPT,201));await pending;
  assert.equal(session.snapshot().laboratoryReceipt,null);assert.equal(session.snapshot().laboratoryIntent,null);
 }
});
test('a same-case refresh during sending retains unknown command and suppresses old success',async()=>{
 const hold=deferred();const{session}=await ready(()=>hold.promise);
 const pending=session.importLaboratory(CID,RAW,true);await new Promise(r=>setTimeout(r,10));
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
 const hold=deferred();let attempt=0;
 const{session,calls}=await ready(()=>++attempt===1?hold.promise:reply({...RECEIPT,duplicate:true},200));
 const old=session.importLaboratory(CID,RAW,true);await new Promise(r=>setTimeout(r,10));
 const original=session.snapshot().laboratoryIntent.body;
 await session.read(PID);await session.loadCases();await session.loadSources(CID);
 assert.equal(session.snapshot().laboratoryPhase,'unknown');await session.retryLaboratoryImport();
 hold.resolve(reply({},503));await old;
 assert.equal(session.snapshot().laboratoryPhase,'saved');assert.equal(session.snapshot().laboratoryReceipt.duplicate,true);
 assert.equal(calls.filter(x=>x[1].method==='POST')[1][1].body,original);
});

test('a blocked World Model read cannot strand an in-flight import without receipt or recovery',async()=>{
 const hold=deferred();const{session}=await ready(()=>hold.promise);
 const pending=session.importLaboratory(CID,RAW,true);await new Promise(r=>setTimeout(r,10));
 await session.loadWorldModel(CID);hold.resolve(reply(RECEIPT,201));await pending;
 assert.equal(session.snapshot().laboratoryPhase,'saved');assert.equal(session.snapshot().laboratoryReceipt.source_id,SID);
});
