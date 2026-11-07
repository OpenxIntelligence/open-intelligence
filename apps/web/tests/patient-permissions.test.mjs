import test from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {readPermissionPage} from '../.test-dist/patient-permissions.js';
const token='a'.repeat(40),id='PAT-FICTIONAL',gid='GRANT-'+'A'.repeat(32);
const response=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json'}});
const page=()=>({patient_id:id,grants:[],next_after:null,enforcement:'persisted_grants',available_actions:['patient_read'],operator_expires_at:'2099-01-01T00:00:00Z'});
const receipt=()=>({patient_id:id,grant_id:gid,duplicate:false});
const identity=()=>({patient_id:id,origin_org:'ORG-ONE',status:'active',revision:1,created_at:'2026-11-05T12:00:00Z'});
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve}};
const command=()=>({synthetic:true,request_key:'KEY-ONE',actor:'ACTOR-ONE',purpose:'operations',actions:['patient_read'],authority_ref:'REF-ONE',relationship:'patient',expires_at:'2099-01-01T00:00:00Z'});

test('opening management clears patient records and never sends an implicit request',async()=>{
  const calls=[];const s=new RegistrySession(async(url,init)=>{calls.push([url,init]);return response(identity());});
  s.connect(token);await s.read(id);assert.equal(s.snapshot().patient.patient_id,id);
  s.managePatientPermissions(id);assert.equal(calls.length,1);assert.equal(s.snapshot().patient,null);
  assert.equal(s.snapshot().cases,null);assert.equal(s.currentPermissions().scope.patientId,id);
});

test('lost response retains exact intent across console reacquisition and prevents patient switching',async()=>{
  const calls=[];let attempt=0;
  const s=new RegistrySession(async(url,init)=>{calls.push([url,init]);if(++attempt===1)throw Error('PRIVATE '+token);return response(receipt());});
  s.connect(token);s.managePatientPermissions(id);const c=s.currentPermissions();
  await c.command(command());assert.ok(c.pending);assert.match(c.message,/unknown/);
  await s.read('PAT-OTHER');await s.create('CREATE-OTHER',true);s.managePatientPermissions('PAT-OTHER');
  assert.equal(calls.length,1);assert.equal(s.currentPermissions(),c);
  await s.currentPermissions().retry();assert.equal(c.pending,null);
  assert.equal(calls[0][1].body,calls[1][1].body);assert.ok(!c.message.includes(token));
});

test('duplicate clicks cannot create a second command while the first is pending',async()=>{
  const wait=deferred();let calls=0;
  const s=new RegistrySession(async()=>{calls++;return wait.promise});s.connect(token);s.managePatientPermissions(id);
  const c=s.currentPermissions(),pending=c.command(command());
  await c.command({...command(),request_key:'OTHER-KEY'});await c.retry();assert.equal(calls,1);
  wait.resolve(response(receipt()));await pending;assert.equal(c.pending,null);
});

test('late permission response cannot reappear after credential replacement',async()=>{
  const wait=deferred();const s=new RegistrySession(async()=>wait.promise);s.connect(token);s.managePatientPermissions(id);
  const c=s.currentPermissions(),reading=c.read();s.connect('b'.repeat(40));
  wait.resolve(response(page()));await reading;assert.equal(c.page,null);assert.equal(s.currentPermissions(),null);
});

test('opening a patient retires permission history and stale callbacks',async()=>{
  const s=new RegistrySession(async(url)=>response(url.endsWith('/permissions')?page():identity()));
  s.connect(token);s.managePatientPermissions(id);const c=s.currentPermissions();await c.read();assert.ok(c.page);
  await s.read(id);assert.equal(s.currentPermissions(),null);assert.equal(c.page,null);
  assert.equal(c.scope.active(),false);assert.equal(s.snapshot().patient.patient_id,id);
});

test('contradictory receipt remains unknown while definite refusal clears the pending command',async()=>{
  for(const status of [200,409,404]){
    const s=new RegistrySession(async()=>response({...receipt(),patient_id:'PAT-OTHER'},status));
    s.connect(token);s.managePatientPermissions(id);const c=s.currentPermissions();await c.command(command());
    assert.equal(Boolean(c.pending),status===200);assert.equal(c.page,null);
  }
});

test('a permission page cannot switch patients or invent administrative delegation',()=>{
  for(const delta of [{patient_id:'PAT-OTHER'},{available_actions:['patient_permissions_manage']},{enforcement:'unknown'},{next_after:'unbounded'}])
    assert.throws(()=>readPermissionPage({...page(),...delta},id));
});

test('a refused retry cannot settle an earlier unknown permission outcome',async()=>{
  for(const status of [403,404,409,413,422]){
    let attempt=0;const bodies=[];
    const s=new RegistrySession(async(url,init)=>{
      bodies.push(init.body);if(++attempt===1)throw Error('lost committed response');
      return attempt===2?response({},status):response({...receipt(),duplicate:true});
    });
    s.connect(token);s.managePatientPermissions(id);const c=s.currentPermissions();
    await c.command(command());await c.retry();
    assert.ok(c.pending);assert.match(c.message,/unknown/);
    await s.read('PAT-OTHER');assert.equal(bodies.length,2);
    await c.retry();assert.equal(c.pending,null);
    assert.deepEqual(bodies,[bodies[0],bodies[0],bodies[0]]);
  }
});
