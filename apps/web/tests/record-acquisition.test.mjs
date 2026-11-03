import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RecordAcquisition,decodeRequests,decodeReceipt,eligibleSources,receiptLabel} from '../.test-dist/record-acquisition.js';
const PID='PAT-EXAMPLE-001',CID='CASE-ALPHA',RID='RECORD-'+'A'.repeat(32),SID='SRC-'+'B'.repeat(32);
const draft={kind:'pathology',record_label:'Fictional pathology report',source_organization:'Fictional laboratory'};
const source={source_id:SID,case_id:CID,document_id:'DOC-ONE',version:1,sha256:'a'.repeat(64),kind:'pathology',state:'current'};
const row=(change={})=>({request_id:RID,patient_id:PID,...draft,status:'requested',revision:1,created_at:'2026-11-03T09:00:00Z',updated_at:'2026-11-03T09:00:00Z',receipt_status:'not_received',source_reference:null,external_request_sent:false,...change});
const packet=(rows=[row()])=>({patient_id:PID,requests:rows,synthetic:true,external_request_sent:false,source_receipts_enabled:true});
const response=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});
const defer=()=>{let resolve;return {promise:new Promise(r=>resolve=r),resolve:x=>resolve(x)}};
function harness(handler=async()=>response(packet())){
 let ctx={scope:'session:1',patientId:PID,ready:true,sourceIndex:{patient_id:PID,case_id:CID,sources:[source]},cases:[{patient_id:PID,case_id:CID,status:'active'}],sourceBusy:false};
 const calls=[];let expired=0;
 const client=new RecordAcquisition({context:()=>ctx,send:async(...args)=>{calls.push(args);return handler(...args)},expired:()=>{expired++;ctx={...ctx,ready:false}}});
 return {client,calls,set:v=>{ctx={...ctx,...v}},expired:()=>expired};
}
test('request decoder preserves absence versus empty list and exact unreviewed receipt states',()=>{
 const received=row({status:'received',revision:2,receipt_status:'source_current_unreviewed',source_reference:{case_id:CID,source_id:SID,version:1,sha256:'a'.repeat(64)}});
 assert.equal(decodeRequests(packet([received]),PID)[0].receipt_status,'source_current_unreviewed');
 assert.deepEqual(decodeRequests(packet([]),PID),[]);
 assert.equal(receiptLabel(received),'Original linked · not clinically reviewed');
 assert.equal(receiptLabel({...received,receipt_status:'source_superseded_reconciliation_required'}),'Original amended · reassessment needed');
 assert.equal(receiptLabel({...received,receipt_status:'binding_revoked_not_usable',source_reference:null}),'Case access revoked · source withheld');
});
test('reject wrong patient, duplicate rows, invented external delivery and inconsistent receipt state',()=>{
 for(const value of [packet([row({patient_id:'PAT-OTHER'})]),packet([row(),row()]),{...packet(),external_request_sent:true},packet([row({receipt_status:'source_current_unreviewed'})]),packet([row({status:'received',revision:2})]),packet([row({status:'cancelled',revision:2,source_reference:{case_id:CID,source_id:SID,version:1,sha256:'a'.repeat(64)}})])])assert.throws(()=>decodeRequests(value,PID));
});
test('receipt source identifiers stay redacted without source permission',()=>{
 const value=decodeRequests(packet([row({status:'received',revision:2,receipt_status:'source_current_unreviewed'})]),PID)[0];
 assert.equal(value.source_reference,null);assert.equal(value.status,'received');
});
test('copy and freeze accepted payload; caller cannot change displayed status or source',()=>{
 const raw=packet();const result=decodeRequests(raw,PID);raw.requests[0].status='received';
 assert.equal(result[0].status,'requested');assert.ok(Object.isFrozen(result));assert.ok(Object.isFrozen(result[0]));
});
test('source eligibility does not join other patient, case, category or historical version',()=>{
 const rows=[source,{...source,source_id:'SRC-'+'C'.repeat(32),kind:'imaging'},{...source,source_id:'SRC-'+'D'.repeat(32),state:'superseded'}];
 assert.deepEqual(eligibleSources(row(),PID,{patient_id:PID,case_id:CID,sources:rows},[{patient_id:PID,case_id:CID,status:'active'}]).map(x=>x.source_id),[SID]);
 assert.deepEqual(eligibleSources(row({patient_id:'PAT-OTHER'}),PID,{patient_id:PID,case_id:CID,sources:rows},[{patient_id:PID,case_id:CID,status:'active'}]),[]);
 assert.deepEqual(eligibleSources(row(),PID,{patient_id:PID,case_id:CID,sources:rows},[{patient_id:PID,case_id:CID,status:'revoked'}]),[]);
});
test('mutation receipt must match exact intended request, source and version',()=>{
 const intent={operation:'receive',patientId:PID,requestId:RID,sourceId:SID,version:1,body:{synthetic:true,case_id:CID,source_id:SID}};
 assert.equal(decodeReceipt({request_id:RID,source_id:SID,version:1,duplicate:false},intent).source_id,SID);
 for(const delta of [{request_id:'RECORD-'+'C'.repeat(32)},{version:2},{source_id:'SRC-'+'D'.repeat(32)},{clinical_approval:true}])assert.throws(()=>decodeReceipt({request_id:RID,source_id:SID,version:1,duplicate:false,...delta},intent));
});
test('does not issue requests without active patient context',async()=>{const h=harness();h.set({ready:false});await h.client.load();h.client.setDraft(draft);await h.client.create(true);assert.equal(h.calls.length,0)});
test('load uses bounded existing endpoint and a failed refresh is unknown, not empty',async()=>{
 let fail=false;const h=harness(async()=>fail?response({},403):response(packet()));await h.client.load();assert.equal(h.client.snapshot().requests.length,1);
 assert.equal(h.calls[0][0].operation,'list');assert.equal(h.calls[0][0].patientId,PID);
 fail=true;await h.client.load();assert.equal(h.client.snapshot().requests,null);assert.equal(h.client.snapshot().phase,'error');
});
test('late read cannot restore records after patient switch or explicit clear',async()=>{const d=defer(),h=harness(()=>d.promise);const work=h.client.load();h.set({patientId:'PAT-OTHER',scope:'session:2'});h.client.clear();d.resolve(response(packet()));await work;assert.equal(h.client.snapshot().requests,null)});
test('newer response wins; older empty results cannot erase an accepted list',async()=>{const a=defer(),b=defer();let n=0;const h=harness(()=>++n===1?a.promise:b.promise);const first=h.client.load(),last=h.client.load();b.resolve(response(packet()));await last;a.resolve(response(packet([])));await first;assert.equal(h.client.snapshot().requests.length,1)});
test('draft persists inside current controller, trims on submit, and clears on patient reset',async()=>{
 const h=harness(async c=>c.operation==='create'?response({request_id:RID,duplicate:false},201):response(packet()));h.client.setDraft({...draft,record_label:'  Fictional report  '});await h.client.create(true);
 assert.equal(h.calls[0][0].body.record_label,'Fictional report');assert.equal(h.calls[0][0].body.synthetic,true);assert.ok(h.calls[0][0].body.request_key);assert.equal(h.client.snapshot().writePhase,'confirmed');h.client.clear();assert.equal(h.client.snapshot().draft.record_label,'');
});
test('creation requires explicit fictional confirmation and bounded nonempty labels',async()=>{const h=harness();h.client.setDraft(draft);await h.client.create(false);h.client.setDraft({...draft,record_label:' '});await h.client.create(true);h.client.setDraft({...draft,source_organization:'a'.repeat(101)});await h.client.create(true);assert.equal(h.calls.length,0)});
test('lost write response retains exact intent/key; no automatic or changed-intent retry',async()=>{
 const commands=[];let attempt=0;const h=harness(async c=>{commands.push(c);if(c.operation==='list')return response(packet());if(++attempt===1)throw Error('network');return response({request_id:RID,duplicate:true},200)});
 h.client.setDraft(draft);await h.client.create(true);assert.equal(h.client.snapshot().writePhase,'unknown');assert.equal(commands.length,1);
 const first=structuredClone(commands[0]);h.client.setDraft({...draft,record_label:'Changed'});await h.client.create(true);assert.equal(commands.length,1);
 await h.client.retry();assert.deepEqual(commands[1],first);assert.equal(h.client.snapshot().writePhase,'confirmed');assert.equal(h.client.snapshot().receipt.duplicate,true);
});
test('malformed success or server failure leaves uncertain intent; no false success',async()=>{
 for(const output of [response({request_id:RID,duplicate:false,clinical_approval:true},201),response({},503)]){const h=harness(async()=>output);h.client.setDraft(draft);await h.client.create(true);assert.equal(h.client.snapshot().writePhase,'unknown');assert.equal(h.client.snapshot().receipt,null)}
});
test('confirmed write survives history refresh failure without claiming loaded history',async()=>{const h=harness(async c=>c.operation==='create'?response({request_id:RID,duplicate:false},201):response({},503));h.client.setDraft(draft);await h.client.create(true);assert.equal(h.client.snapshot().writePhase,'confirmed');assert.equal(h.client.snapshot().receipt.request_id,RID);assert.equal(h.client.snapshot().requests,null)});
test('record permission denial withholds list and does not claim mutation success',async()=>{const h=harness(async()=>response({},404));h.client.setDraft(draft);await h.client.create(true);assert.equal(h.client.snapshot().writePhase,'rejected');assert.equal(h.client.snapshot().requests,null);assert.equal(h.client.snapshot().receipt,null)});
test('credential expiry clears acquisition and calls shared session expiry',async()=>{const h=harness(async()=>response({},401));await h.client.load();assert.equal(h.expired(),1);assert.equal(h.client.snapshot().requests,null)});
test('attach original uses exact current source and request category without copying bytes',async()=>{const h=harness(async c=>c.operation==='receive'?response({request_id:RID,source_id:SID,version:1,duplicate:false},201):response(packet()));await h.client.load();await h.client.receive(RID,SID,true);const c=h.calls.find(x=>x[0].operation==='receive')[0];assert.deepEqual(c.body,{synthetic:true,case_id:CID,source_id:SID});assert.equal(h.client.snapshot().writePhase,'confirmed')});
test('cannot attach an absent, mismatched or superseded source or unconfirmed selection',async()=>{const h=harness();await h.client.load();await h.client.receive(RID,SID,false);h.set({sourceIndex:{patient_id:PID,case_id:CID,sources:[{...source,state:'superseded'}]}});await h.client.receive(RID,SID,true);assert.equal(h.calls.length,1)});
test('cancel requires open request and reason; received records cannot be cancelled',async()=>{
 const h=harness(async c=>c.operation==='cancel'?response({request_id:RID,duplicate:false}):response(packet()));await h.client.load();await h.client.cancel(RID,' ',true);assert.equal(h.calls.length,1);await h.client.cancel(RID,'Fictional duplicate request',true);assert.equal(h.calls[1][0].operation,'cancel');assert.equal(h.client.snapshot().writePhase,'confirmed');
 const r=harness(async()=>response(packet([row({status:'received',revision:2,receipt_status:'source_current_unreviewed'})])));await r.client.load();await r.client.cancel(RID,'Reason',true);assert.equal(r.calls.length,1);
});
test('source refresh invalidates receipt statuses, preserving uncertain exact retry',async()=>{let write=false;const h=harness(async c=>{if(c.operation==='list')return response(packet());write=true;throw Error('lost')});await h.client.load();await h.client.receive(RID,SID,true);const intent=h.client.snapshot().intent;h.client.invalidate();assert.equal(h.client.snapshot().requests,null);assert.deepEqual(h.client.snapshot().intent,intent);assert.equal(h.client.snapshot().writePhase,'unknown');assert.equal(write,true)});
test('late successful mutation never returns old patient data after reset',async()=>{const d=defer(),h=harness(()=>d.promise);h.client.setDraft(draft);const saving=h.client.create(true);h.client.clear();h.set({patientId:'PAT-OTHER',scope:'session:2'});d.resolve(response({request_id:RID,duplicate:false},201));await saving;assert.equal(h.client.snapshot().receipt,null);assert.equal(h.client.snapshot().writePhase,'idle')});
test('double submission dispatches one write while its outcome is pending',async()=>{const d=defer(),h=harness(c=>c.operation==='list'?Promise.resolve(response(packet())):d.promise);h.client.setDraft(draft);const first=h.client.create(true);await h.client.create(true);assert.equal(h.calls.length,1);d.resolve(response({request_id:RID,duplicate:false},201));await first;assert.equal(h.client.snapshot().writePhase,'confirmed')});

test('wrong-patient source index cannot offer a received pointer',()=>{assert.deepEqual(eligibleSources(row(),PID,{patient_id:'PAT-OTHER',case_id:CID,sources:[source]},[{patient_id:PID,case_id:CID,status:'active'}]),[])});
test('refused recovery preserves original uncertain create key rather than allowing duplicates',async()=>{let i=0;const h=harness(async()=>{if(i++===0)throw Error('lost');return response({},403)});h.client.setDraft(draft);await h.client.create(true);const intent=h.client.snapshot().intent;await h.client.retry();assert.equal(h.client.snapshot().writePhase,'unknown');assert.deepEqual(h.client.snapshot().intent,intent);await h.client.create(true);assert.equal(h.calls.length,2)});

// Exercise the actual shared credential/session owner, not a second auth store.
test('registry delegates only scoped acquisition routes and clears them with patient/session',async()=>{
 const {RegistrySession}=await import('../.test-dist/registry-client.js');const calls=[];
 const session=new RegistrySession(async(url,init)=>{calls.push({url,init});if(url.endsWith('/record-requests'))return response(packet());return response({patient_id:PID,origin_org:'FICT-ORG',created_at:'2026-11-03T09:00:00Z',status:'active',revision:1})});
 session.connect('fictional_test_credential_000000000001');await session.read(PID);await session.acquisition.load();
 assert.equal(calls[1].url,'/v1/patients/'+PID+'/record-requests');assert.equal(calls[1].init.headers.Authorization,'Bearer fictional_test_credential_000000000001');
 assert.equal(calls[1].init.credentials,'omit');assert.equal(calls[1].init.redirect,'error');assert.equal(calls[1].init.cache,'no-store');
 assert.equal(session.acquisition.snapshot().requests.length,1);assert.ok(!JSON.stringify(session.acquisition.snapshot()).includes('credential_'));
 await session.read('PAT-OTHER');assert.equal(session.acquisition.snapshot().requests,null);session.disconnect();assert.equal(session.acquisition.snapshot().draft.record_label,'');
});

test('patient recheck does not silently discard uncertain acquisition intent',async()=>{const {RegistrySession}=await import('../.test-dist/registry-client.js');let reads=0;const s=new RegistrySession(async(url)=>{if(url.endsWith('/record-requests'))throw Error('lost');reads++;return response({patient_id:PID,origin_org:'FICT-ORG',created_at:'2026-11-03T09:00:00Z',status:'active',revision:1})});s.connect('fictional_test_credential_000000000001');await s.read(PID);s.acquisition.setDraft(draft);await s.acquisition.create(true);const original=s.acquisition.snapshot().intent;await s.read(PID);assert.equal(reads,1);assert.deepEqual(s.acquisition.snapshot().intent,original);assert.equal(s.acquisition.snapshot().writePhase,'unknown')});
