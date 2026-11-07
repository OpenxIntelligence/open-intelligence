import test from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {readConsentPage} from '../.test-dist/patient-consent.js';
const token='a'.repeat(40),id='PAT-FICTIONAL';
const response=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json'}});
const command=()=>({synthetic:true,request_key:'CONSENT-ONE',expected_revision:0,actor:'ACTOR-ONE',target_purpose:'operations',state:'granted',actions:['patient_read'],decision_maker:'PERSON-ONE',basis:'self',authority_ref:'DECLARATION-ONE',valid_from:'2026-01-01T00:00:00Z',expires_at:'2099-01-01T00:00:00Z'});
const receipt=()=>({patient_id:id,event_id:1,revision:1,actor:'ACTOR-ONE',target_purpose:'operations',state:'granted',request_key:'CONSENT-ONE',duplicate:false});
const page=()=>({patient_id:id,decisions:[],next_before:null,available_actions:['patient_read'],operator_expires_at:'2099-01-01T00:00:00Z',enforcement:'required',authority_verified:false,data_scope:'patient_record'});

test('consent recovery survives refused retry and blocks switching to permission management',async()=>{
  let attempt=0;const calls=[];
  const s=new RegistrySession(async(url,init)=>{calls.push([url,init.body]);if(++attempt===1)throw Error('lost');return attempt===2?response({},404):response({...receipt(),duplicate:true});});
  s.connect(token);s.managePatientConsent(id);const c=s.currentConsent();
  await c.command(command());assert.match(c.message,/unknown/);await c.retry();assert.ok(c.pending);
  s.managePatientPermissions('PAT-OTHER');await s.read('PAT-OTHER');await s.create('CREATE-OTHER',true);
  assert.equal(calls.length,2);assert.equal(s.currentConsent(),c);
  await c.retry();assert.equal(c.pending,null);assert.equal(new Set(calls.map(x=>x[1])).size,1);
});

test('late consent history cannot survive a credential change',async()=>{
  let resolve;const wait=new Promise(r=>resolve=r);const s=new RegistrySession(async()=>wait);
  s.connect(token);s.managePatientConsent(id);const c=s.currentConsent(),pending=c.read();s.connect('b'.repeat(40));
  resolve(response(page()));await pending;assert.equal(c.page,null);assert.equal(s.currentConsent(),null);
});

test('consent receipt must match recipient purpose request and revision',async()=>{
  for(const delta of [{actor:'ACTOR-OTHER'},{target_purpose:'research'},{revision:2},{request_key:'OTHER-KEY'},{state:'withdrawn'}]){
    const s=new RegistrySession(async()=>response({...receipt(),...delta}));s.connect(token);s.managePatientConsent(id);
    await s.currentConsent().command(command());assert.ok(s.currentConsent().pending);
  }
});

test('consent history cannot invent proofing, delegation or invalid chronology',()=>{
  for(const change of [{authority_verified:true},{data_scope:'all_people'},{available_actions:['consent_manage']},{enforcement:'optional'},{next_before:-1}])
    assert.throws(()=>readConsentPage({...page(),...change},id));
  const row={...command(),event_id:2,revision:1,status:'active',recorded_at:'2026-01-01T00:00:00Z',recorded_by:'ACTOR-ONE'};
  for(const change of [{expires_at:'2026-02-31T00:00:00Z'},{valid_from:row.expires_at},{status:'withdrawn'},{revision:0}])
    assert.throws(()=>readConsentPage({...page(),decisions:[{...row,...change}]},id));
});

test('duplicate clicks and initial definitive refusal have distinct outcomes',async()=>{
  let resolve,calls=0;const wait=new Promise(r=>resolve=r);const s=new RegistrySession(async()=>{calls++;return wait});
  s.connect(token);s.managePatientConsent(id);const c=s.currentConsent();const first=c.command(command());
  await c.command(command());await c.retry();assert.equal(calls,1);resolve(response({},409));await first;
  assert.equal(c.pending,null);assert.match(c.message,/refused/);
});


test('unknown purpose decisions survive attempts to open consent or permission administration',async()=>{
  for(const open of ['managePatientConsent','managePatientPermissions']){
    const bodies=[];
    const s=new RegistrySession(async(url,init)=>{
      if(init.method==='POST'){bodies.push(init.body);throw Error('lost response');}
      return response({patient_id:id,origin_org:'ORG-ONE',status:'active',revision:1,created_at:'2026-01-01T00:00:00Z'});
    });
    s.connect(token);await s.read(id);
    await s.decideDataUse({patient_id:id,target_purpose:'operations',state:'unrecorded',revision:0,consent_established:false},'restricted',true);
    assert.equal(s.snapshot().dataUsePhase,'unknown');
    s[open](id);
    assert.equal(s.snapshot().dataUsePhase,'unknown');
    assert.equal(s.currentConsent(),null);assert.equal(s.currentPermissions(),null);
    await s.retryDataUse();assert.equal(bodies.length,2);assert.equal(bodies[0],bodies[1]);
  }
});
