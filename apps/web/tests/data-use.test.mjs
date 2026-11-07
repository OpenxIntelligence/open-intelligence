import test from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
const identity={patient_id:'PAT-ONE',origin_org:'ORG-ONE',status:'active',revision:1,created_at:'2026-11-05T12:00:00Z'};
const decision={patient_id:'PAT-ONE',target_purpose:'operations',state:'restricted',revision:1,consent_established:false};
const response=body=>new Response(JSON.stringify(body),{headers:{'Content-Type':'application/json'}});
async function setup(read){const s=new RegistrySession((url,init)=>url.includes('/data-use/')?read(url,init):Promise.resolve(response(identity)));s.connect('a'.repeat(40));await s.read('PAT-ONE');return s;}
test('restriction response is scoped and never establishes consent',async()=>{
 const s=await setup(async(url,init)=>{assert.equal(init.credentials,'omit');assert.equal(init.cache,'no-store');return response(decision);});
 assert.deepEqual(await s.readDataUse('operations',new AbortController().signal),{state:'restricted',revision:1});
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
