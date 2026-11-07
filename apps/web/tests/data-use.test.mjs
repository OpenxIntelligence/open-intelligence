import test from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
const identity={patient_id:'PAT-ONE',origin_org:'ORG-ONE',status:'active',revision:1,created_at:'2026-11-05T12:00:00Z'};
const decision={patient_id:'PAT-ONE',target_purpose:'operations',state:'restricted',revision:1,consent_established:false};
const response=body=>new Response(JSON.stringify(body),{headers:{'Content-Type':'application/json'}});
async function setup(read){const s=new RegistrySession((url,init)=>url.includes('/data-use/')?read(url,init):Promise.resolve(response(identity)));s.connect('a'.repeat(40));await s.read('PAT-ONE');return s;}
test('restriction response is scoped and never establishes consent',async()=>{
 const s=await setup(async(url,init)=>{assert.equal(init.credentials,'omit');assert.equal(init.cache,'no-store');return response(decision);});
 assert.deepEqual(await s.readDataUse('operations',new AbortController().signal),decision);
 for(const changes of [{patient_id:'PAT-OTHER'},{target_purpose:'research'},{consent_established:true},{revision:true},{state:'unrecorded'},{extra:'private'}]){
  const bad=await setup(async()=>response({...decision,...changes}));
  await assert.rejects(bad.readDataUse('operations',new AbortController().signal));
 }
});
test('late restriction response is discarded after disconnect or same-patient refresh',async()=>{
 for(const disconnect of [true,false]){
  let resolve;const pending=new Promise(r=>resolve=r);const s=await setup(()=>pending);
  const read=s.readDataUse('operations',new AbortController().signal);
  if(disconnect)s.disconnect();else await s.read('PAT-ONE');
  resolve(response(decision));await assert.rejects(read);
 }
});
test('authentication loss clears patient and credential while denied status grants do not',async()=>{
 for(const status of [401,404]){
  const s=await setup(async()=>new Response('{}',{status}));
  await assert.rejects(s.readDataUse('operations',new AbortController().signal));
  assert.equal(s.snapshot().connected,status!==401);
  assert.equal(Boolean(s.snapshot().patient),status!==401);
 }
});
const snapshot={...decision,state:'unrecorded',revision:0};
const receipt={...decision};
async function writable(write){
 const calls=[];
 const s=new RegistrySession(async(url,init)=>{calls.push({url,init});return init.method==='POST'?write(url,init):response(identity);});
 s.connect('a'.repeat(40));await s.read('PAT-ONE');return {s,calls};
}
test('data-use mutation binds explicit confirmation, patient, purpose and decision revision',async()=>{
 const {s,calls}=await writable(async()=>response(receipt));
 await s.decideDataUse(snapshot,'restricted',false);assert.equal(calls.length,1);
 await s.decideDataUse({...snapshot,patient_id:'PAT-OTHER'},'restricted',true);assert.equal(calls.length,1);
 await s.decideDataUse(snapshot,'restricted',true);
 const body=JSON.parse(calls[1].init.body);
 assert.equal(calls[1].url,'/v1/patients/PAT-ONE/data-use');
 assert.deepEqual(Object.keys(body).sort(),['expected_revision','request_key','state','synthetic','target_purpose']);
 assert.equal(body.expected_revision,0);assert.equal(body.target_purpose,'operations');assert.equal(body.state,'restricted');
 assert.equal(s.snapshot().dataUsePhase,'confirmed');assert.equal(s.snapshot().patient,null);
 assert.deepEqual(s.snapshot().dataUseReceipt,receipt);
});
test('lost response retains exact retry, blocks switching, and later refusal does not erase uncertainty',async()=>{
 let n=0;const {s,calls}=await writable(async()=>{n++;if(n===1)throw Error('lost');if(n===2)return new Response('{}',{status:404});return response(receipt);});
 await s.decideDataUse(snapshot,'restricted',true);
 assert.equal(s.snapshot().dataUsePhase,'unknown');assert.equal(s.snapshot().patient,null);
 await s.read('PAT-OTHER');await s.create('CREATE-OTHER',true);assert.equal(calls.length,2);
 await s.retryDataUse();assert.equal(s.snapshot().dataUsePhase,'unknown');
 await s.retryDataUse();assert.equal(s.snapshot().dataUsePhase,'confirmed');
 assert.equal(calls[1].init.body,calls[2].init.body);assert.equal(calls[2].init.body,calls[3].init.body);
});
test('malformed success remains recoverable and leaving does not reissue the command',async()=>{
 const {s,calls}=await writable(async()=>response({...receipt,target_purpose:'research'}));
 await s.decideDataUse(snapshot,'restricted',true);assert.equal(s.snapshot().dataUsePhase,'unknown');
 s.leaveDataUseRecovery();await s.retryDataUse();assert.equal(calls.length,2);
 await s.read('PAT-ONE');assert.equal(s.snapshot().dataUsePhase,'idle');
});
test('late success after credential switch cannot publish a decision receipt',async()=>{
 let resolve;const pending=new Promise(r=>resolve=r);const {s}=await writable(()=>pending);
 const writing=s.decideDataUse(snapshot,'restricted',true);
 assert.equal(s.snapshot().dataUsePhase,'sending');assert.equal(s.snapshot().patient,null);
 s.connect('b'.repeat(40));resolve(response(receipt));await writing;
 assert.equal(s.snapshot().dataUseReceipt,null);assert.equal(s.snapshot().dataUsePhase,'idle');
});
test('in-flight decision blocks duplicate submit and suspension, and initial conflict requires reopening',async()=>{
 let resolve;const pending=new Promise(r=>resolve=r);const {s,calls}=await writable(()=>pending);
 const first=s.decideDataUse(snapshot,'restricted',true);
 await s.decideDataUse(snapshot,'restricted',true);await s.suspendPatient(true);
 assert.equal(calls.length,2);
 resolve(new Response('{}',{status:409}));await first;
 assert.equal(s.snapshot().dataUsePhase,'rejected');assert.equal(s.snapshot().patient,null);
 await s.retryDataUse();assert.equal(calls.length,2);
 await s.read('PAT-ONE');assert.equal(s.snapshot().dataUsePhase,'idle');
});
test('data-use write authentication loss clears recovery and credentials',async()=>{
 const {s}=await writable(async()=>new Response('{}',{status:401}));
 await s.decideDataUse(snapshot,'restricted',true);
 assert.equal(s.snapshot().connected,false);assert.equal(s.snapshot().patient,null);
 assert.equal(s.snapshot().dataUseTarget,null);assert.equal(s.snapshot().dataUseReceipt,null);
});
