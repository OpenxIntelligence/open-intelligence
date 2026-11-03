import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {prepareSource,parseImportReceipt,verifyOriginal} from '../.test-dist/source-intake.js';
import {RegistrySession} from '../.test-dist/registry-client.js';
const PID='PAT-EXAMPLE-001', CID='CASE-INTAKE', SID='SRC-'+ 'A'.repeat(32), TOKEN='fictional_test_credential_000000000001';
const RAW=`OI-SYNTHETIC-REPORT/1\nPatient: ${CID}\nDocument: INTAKE-PATH\nType: pathology\nEvent-Date: 2026-01-01\nIssued-At: 2026-01-02\nSpecimen: INTAKE-SPEC\nFinding: marker|not-reported|Fictional café <script>literal</script>.\n`;
const HASH=createHash('sha256').update(RAW).digest('hex');
const PAT={patient_id:PID,origin_org:'ORG-0',created_at:'2026-11-02T10:00:00Z',status:'active',revision:1};
const MAP={patient_id:PID,mappings:[{case_id:CID,patient_id:PID,source_organization:'FICT-ORG',source_system:'FICT-SYS',source_subject_ref:'FICT-SUB',review_ref:'FICT-REVIEW',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false}],synthetic:true,source_identity_verified:false,clinical_sources_linked:false};
const META={source_id:SID,document_id:'INTAKE-PATH',version:1,sha256:HASH,kind:'pathology',event_date:'2026-01-01',issued_at:'2026-01-02',received_at:'2026-11-02T10:00:00Z',specimen_id:'INTAKE-SPEC',state:'current',supersedes_id:null};
const INDEX={contract:'oi.synthetic-original-sources/1',patient_id:PID,case_id:CID,sources:[META],source_reported_assertions:[],synthetic:true,clinical_interpretation:false,research_review_invalidation_integrated:false};
const ORIGINAL={source_id:SID,case_id:CID,document_id:'INTAKE-PATH',version:1,state:'current',sha256:HASH,original_text:RAW,synthetic:true,clinical_review_state:'not_established'};
const reply=(v,status=200)=>new Response(JSON.stringify(v),{status,headers:{'Content-Type':'application/json'}});
const bytes=s=>new TextEncoder().encode(s);
const deferred=()=>{let done;return{promise:new Promise(r=>done=r),resolve:x=>done(x)}};
async function ready(operation){
 const calls=[];const session=new RegistrySession(async(url,init)=>{
  calls.push([url,init]);
  if(url==='/v1/patients/'+PID)return reply(PAT);
  if(url.endsWith('/case-bindings'))return reply(MAP);
  if(init.method==='GET'&&url.endsWith('/sources'))return reply(INDEX);
  return operation(url,init);
 });
 session.connect(TOKEN);await session.read(PID);await session.loadCases();await session.loadSources(CID);calls.length=0;
 return{session,calls};
}
test('preflight keeps exact source bytes, Unicode and declared identity',()=>{const p=prepareSource(bytes(RAW),'original.txt');assert.equal(p.text,RAW);assert.deepEqual(bytes(p.text),bytes(RAW));assert.equal(p.declaredCase,CID);assert.equal(p.byteLength,bytes(RAW).length)});
test('invalid encoding, BOM, CRLF, NUL, oversize and unsupported extension fail before network',()=>{
 for(const [b,n] of [[new Uint8Array([255]),'x.txt'],[bytes('\uFEFF'+RAW),'x.txt'],[bytes(RAW.replaceAll('\n','\r\n')),'x.txt'],[bytes(RAW+'\0'),'x.txt'],[bytes('x'.repeat(65537)),'x.txt'],[bytes(RAW),'x.pdf'],[bytes(''),'x.txt']])assert.throws(()=>prepareSource(b,n));
});
test('ambiguous patient headers rejected; foreign case is preserved, not repaired',()=>{
 assert.throws(()=>prepareSource(bytes(RAW.replace('Document:',`Patient: ${CID}\nDocument:`)),'x.txt'));
 assert.equal(prepareSource(bytes(RAW.replace(CID,'CASE-FOREIGN')),'x.txt').declaredCase,'CASE-FOREIGN');
});
test('receipt accepts only coherent exact import, duplicate and quarantine contracts',()=>{
 assert.equal(parseImportReceipt({result:'imported',duplicate:false,source_id:SID,version:1}).result,'imported');
 assert.equal(parseImportReceipt({result:'quarantined',duplicate:true,source_id:null,version:null}).result,'quarantined');
 for(const r of [{result:'duplicate',duplicate:false,source_id:SID,version:1},{result:'imported',duplicate:false,source_id:null,version:null},{result:'quarantined',duplicate:false,source_id:SID,version:1},{result:'imported',duplicate:false,source_id:SID,version:1,approved:true}])assert.throws(()=>parseImportReceipt(r));
});
test('original read verifies byte hash and exact selected source/version/case',async()=>{
 assert.equal((await verifyOriginal(ORIGINAL,CID,META)).original_text,RAW);
 for(const v of [{...ORIGINAL,original_text:RAW+'changed'},{...ORIGINAL,case_id:'CASE-FOREIGN'},{...ORIGINAL,version:2},{...ORIGINAL,clinical_review_state:'approved'},{...ORIGINAL,state:'superseded'}])await assert.rejects(()=>verifyOriginal(v,CID,META));
});
test('source import requires an active opened patient/case and explicit confirmation',async()=>{
 let calls=0;const s=new RegistrySession(async()=>{calls++;return reply({})});s.connect(TOKEN);await s.importSource(CID,RAW,true);assert.equal(calls,0);
 const {session,calls:seen}=await ready(()=>reply({}));await session.importSource(CID,RAW,false);assert.equal(seen.length,0);
 await session.importSource('CASE-FOREIGN',RAW,true);assert.equal(seen.length,0);
});
test('import sends original text unchanged through fixed authorized route and refreshes metadata',async()=>{
 const{session,calls}=await ready(()=>reply({result:'imported',duplicate:false,source_id:SID,version:1},201));
 await session.importSource(CID,RAW,true);
 const write=calls.find(c=>c[1].method==='POST');assert.equal(write[0],`/v1/patients/${PID}/cases/${CID}/sources`);
 assert.deepEqual(JSON.parse(write[1].body),{synthetic:true,original_text:RAW});assert.equal(write[1].credentials,'omit');assert.equal(write[1].redirect,'error');
 assert.equal(session.snapshot().importReceipt.result,'imported');assert.equal(session.snapshot().sourceIndex.case_id,CID);
});
test('wrong-case source produces quarantine not a success or rewritten identity',async()=>{
 const{session,calls}=await ready(()=>reply({result:'quarantined',duplicate:false,source_id:null,version:null}));
 await session.importSource(CID,RAW.replace(CID,'CASE-FOREIGN'),true);
 assert.equal(session.snapshot().importReceipt.result,'quarantined');assert.ok(JSON.parse(calls[0][1].body).original_text.includes('CASE-FOREIGN'));
});
test('lost import reply is unknown and never automatically retried',async()=>{
 const{session,calls}=await ready(()=>{throw Error('private token '+TOKEN)});await session.importSource(CID,RAW,true);
 assert.equal(calls.length,1);assert.equal(session.snapshot().importOutcome,'unknown');assert.equal(session.snapshot().importReceipt,null);assert.ok(!JSON.stringify(session.snapshot()).includes(TOKEN));
});
test('malformed success and HTTP 5xx are ambiguous, not a false rollback',async()=>{
 for(const r of [reply({wrong:true}),reply({},503)]){const{session,calls}=await ready(()=>r);await session.importSource(CID,RAW,true);assert.equal(session.snapshot().importOutcome,'unknown');assert.equal(calls.length,1);}
});
test('confirmed denial clears clinical source view and does not treat upload as committed',async()=>{
 const{session}=await ready(()=>reply({},404));await session.importSource(CID,RAW,true);assert.equal(session.snapshot().sourceIndex,null);assert.equal(session.snapshot().original,null);assert.equal(session.snapshot().importOutcome,'rejected');
});
test('two import submissions cause one write while first is unresolved',async()=>{
 const d=deferred();const{session,calls}=await ready(()=>d.promise);const first=session.importSource(CID,RAW,true);await session.importSource(CID,RAW,true);assert.equal(calls.length,1);d.resolve(reply({result:'duplicate',duplicate:true,source_id:SID,version:1}));await first;
});
test('late upload result after disconnect cannot restore any record or receipt',async()=>{
 const d=deferred();const{session}=await ready(()=>d.promise);const pending=session.importSource(CID,RAW,true);session.disconnect();session.connect(TOKEN);d.resolve(reply({result:'imported',duplicate:false,source_id:SID,version:1},201));await pending;assert.equal(session.snapshot().sourceIndex,null);assert.equal(session.snapshot().importReceipt,null);
});
test('original read uses separate endpoint and grant; refusal clears prior original',async()=>{
 let n=0;const{session,calls}=await ready(()=>++n===1?reply(ORIGINAL):reply({},404));await session.loadOriginal(SID);assert.equal(session.snapshot().original.original_text,RAW);assert.ok(calls[0][0].endsWith('/sources/'+SID));await session.loadOriginal(SID);assert.equal(session.snapshot().original,null);
});
test('late original after patient recheck cannot restore older raw content',async()=>{
 const d=deferred();const{session}=await ready(()=>d.promise);const p=session.loadOriginal(SID);await session.read(PID);d.resolve(reply(ORIGINAL));await p;assert.equal(session.snapshot().original,null);
});
test('new metadata refresh dismisses previously authorized original',async()=>{
 const{session}=await ready(()=>reply(ORIGINAL));await session.loadOriginal(SID);assert.ok(session.snapshot().original);await session.loadSources(CID);assert.equal(session.snapshot().original,null);
});
test('unpaired Unicode surrogate is rejected rather than silently changed by encoding',async()=>{
 const{session,calls}=await ready(()=>reply({}));await session.importSource(CID,RAW+'\ud800',true);assert.equal(calls.length,0);assert.equal(session.snapshot().importOutcome,'rejected');
});
test('JSON envelope bound is checked before submission without altering source bytes',async()=>{
 const large=RAW+'\\'.repeat(40000);const{session,calls}=await ready(()=>reply({}));await session.importSource(CID,large,true);assert.equal(calls.length,0);assert.equal(session.snapshot().importOutcome,'rejected');
});
