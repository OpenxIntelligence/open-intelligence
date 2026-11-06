import test from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';

const token='a'.repeat(40);
const identity=(id='PAT-FICTIONAL')=>({patient_id:id,origin_org:'ORG-FICTIONAL',
  status:'active',revision:1,created_at:'2026-11-05T12:00:00Z'});
const receipt=(patch={})=>({patient_id:'PAT-FICTIONAL',revision:2,status:'suspended',...patch});
const response=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json'}});
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve}};
async function opened(write){
  const calls=[];
  const session=new RegistrySession(async(url,init)=>{
    calls.push({url,init});return init.method==='POST'?write(url,init):response(identity(url.split('/').at(-1)));
  });
  session.connect(token);await session.read('PAT-FICTIONAL');return {session,calls};
}

test('suspension requires explicit confirmation and exact active patient revision',async()=>{
  const {session,calls}=await opened(async()=>response(receipt()));
  await session.suspendPatient(false);assert.equal(calls.length,1);
  await session.suspendPatient(true);
  const {url,init}=calls[1],body=JSON.parse(init.body);
  assert.equal(url,'/v1/patients/PAT-FICTIONAL/suspensions');
  assert.deepEqual(Object.keys(body).sort(),['expected_revision','request_key','synthetic']);
  assert.equal(body.expected_revision,1);assert.equal(body.synthetic,true);assert.ok(body.request_key);
  assert.equal(init.credentials,'omit');assert.equal(init.redirect,'error');assert.equal(init.cache,'no-store');
  assert.equal(session.snapshot().patient.status,'suspended');
  assert.equal(session.snapshot().suspensionPhase,'confirmed');
  await session.suspendPatient(true);assert.equal(calls.length,2);
});

test('patient content is cleared before waiting and duplicate clicks or new identity reads are blocked',async()=>{
  const wait=deferred();const {session,calls}=await opened(()=>wait.promise);
  const pending=session.suspendPatient(true);
  assert.equal(session.snapshot().patient,null);assert.equal(session.snapshot().worldModel,null);
  assert.equal(session.snapshot().sourceIndex,null);assert.equal(session.snapshot().cases,null);
  assert.equal(session.snapshot().suspensionPhase,'sending');
  await session.suspendPatient(true);await session.read('PAT-CONTROL');await session.create('NEW-IDENTITY',true);
  assert.equal(calls.length,2);
  wait.resolve(response(receipt()));await pending;
});

test('lost response retains byte-identical recovery and blocks changed intent after refusal',async()=>{
  let attempt=0;
  const {session,calls}=await opened(async()=>{
    if(++attempt===1)throw Error('transport detail '+token);
    return attempt===2?response({detail:'private refusal'},404):response(receipt());
  });
  await session.suspendPatient(true);assert.equal(session.snapshot().suspensionPhase,'unknown');
  assert.ok(!JSON.stringify(session.snapshot()).includes(token));
  await session.read('PAT-CONTROL');await session.create('NEW-IDENTITY',true);
  assert.equal(calls.length,2);
  await session.retryPatientSuspension();assert.equal(session.snapshot().suspensionPhase,'unknown');
  assert.ok(!JSON.stringify(session.snapshot()).includes('private refusal'));
  await session.retryPatientSuspension();assert.equal(session.snapshot().suspensionPhase,'confirmed');
  assert.equal(calls[1].init.body,calls[2].init.body);assert.equal(calls[2].init.body,calls[3].init.body);
});

test('initial denied, stale and invalid requests clear content without inventing a receipt',async()=>{
  for(const code of [403,404,409,422]){
    const {session}=await opened(async()=>response({detail:'private backend detail'},code));
    await session.suspendPatient(true);
    assert.equal(session.snapshot().suspensionPhase,'rejected');
    assert.equal(session.snapshot().patient,null);assert.equal(session.snapshot().suspensionReceipt,null);
    assert.ok(!JSON.stringify(session.snapshot()).includes('private backend detail'));
    await session.read('PAT-CONTROL');assert.equal(session.snapshot().patient.patient_id,'PAT-CONTROL');
  }
});

test('wrong patient, status, revision, extra fields and non-JSON success remain uncertain',async()=>{
  for(const malformed of [receipt({patient_id:'PAT-OTHER'}),receipt({status:'active'}),
    receipt({revision:3}),receipt({revision:'2'}),receipt({secret:'should not appear'})]){
    const {session}=await opened(async()=>response(malformed));await session.suspendPatient(true);
    assert.equal(session.snapshot().suspensionPhase,'unknown');assert.equal(session.snapshot().patient,null);
    assert.equal(session.snapshot().suspensionReceipt,null);
    assert.ok(!JSON.stringify(session.snapshot()).includes('should not appear'));
  }
  const {session}=await opened(async()=>new Response('private html',{headers:{'content-type':'text/html'}}));
  await session.suspendPatient(true);assert.equal(session.snapshot().suspensionPhase,'unknown');
});

test('server errors and unexpected successful status do not imply suspension failed',async()=>{
  for(const status of [201,408,429,500,503]){
    const {session}=await opened(async()=>response(receipt(),status));await session.suspendPatient(true);
    assert.equal(session.snapshot().suspensionPhase,'unknown');assert.equal(session.snapshot().patient,null);
  }
});

test('expired credential clears receipt and recovery intent',async()=>{
  const {session,calls}=await opened(async()=>response({},401));await session.suspendPatient(true);
  assert.equal(session.snapshot().connected,false);assert.equal(session.snapshot().suspensionTarget,null);
  session.connect(token);await session.retryPatientSuspension();assert.equal(calls.length,2);
});

test('late suspension response after disconnect cannot restore patient or receipt',async()=>{
  const wait=deferred();const {session}=await opened(()=>wait.promise);
  const pending=session.suspendPatient(true);session.disconnect();session.connect(token);
  await session.read('PAT-CONTROL');wait.resolve(response(receipt()));await pending;
  assert.equal(session.snapshot().patient.patient_id,'PAT-CONTROL');
  assert.equal(session.snapshot().suspensionReceipt,null);
});

test('leaving uncertain recovery does not retry or claim to reverse suspension',async()=>{
  const {session,calls}=await opened(async()=>{throw Error('lost')});await session.suspendPatient(true);
  session.leaveSuspensionRecovery();await session.retryPatientSuspension();
  assert.equal(calls.length,2);assert.equal(session.snapshot().patient,null);
  assert.match(session.snapshot().message,/does not reverse or cancel/);
  await session.read('PAT-CONTROL');assert.equal(session.snapshot().patient.patient_id,'PAT-CONTROL');
});

test('late old case read is fenced when suspension begins',async()=>{
  const delayed=deferred();let calls=0;
  const session=new RegistrySession(async(url,init)=>{
    calls++;if(url.endsWith('/case-bindings'))return delayed.promise;
    return response(init.method==='POST'?receipt():identity());
  });
  session.connect(token);await session.read('PAT-FICTIONAL');const read=session.loadCases();
  await session.suspendPatient(true);
  delayed.resolve(response({patient_id:'PAT-FICTIONAL',mappings:[],synthetic:true,
    source_identity_verified:false,clinical_sources_linked:false}));await read;
  assert.equal(calls,3);assert.equal(session.snapshot().cases,null);
  assert.equal(session.snapshot().patient.status,'suspended');
});
