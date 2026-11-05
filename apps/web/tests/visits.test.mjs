import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {VisitClient} from '../.test-dist/visits.js';

const patient='PAT-EXAMPLE-001', key='NOTE-ONE', receipt='ACCESS-'+'A'.repeat(32);
const at='2026-11-05T12:00:00+00:00';
const hash=text=>createHash('sha256').update(text).digest('hex');
const visit={id:3,patient_id:patient,external_key:'VISIT-ONE',kind:'outpatient',service_date:'2026-11-05',
  status:'in_progress',revision:2,created_at:at,updated_at:at};
const page={patient_id:patient,access_receipt_id:receipt,encounters:[visit],next_after_id:null};
const version={id:7,version:1,status:'draft',body:'Fictional note.',sha256:hash('Fictional note.'),
  authored_by:'ACTOR-ONE',created_at:at,supersedes_id:null,amendment_reason:null,facility_id:null,department_id:null,note_kind:'progress'};
const history={patient_id:patient,encounter_id:3,note_key:key,versions:[version],next_after_version:null};
const client=value=>new VisitClient(patient,async()=>({access_receipt_id:receipt,...value}));
test('visit pages require the selected patient, valid cursor and unique ordered rows',async()=>{
  assert.equal((await client(page).list(0)).items[0].id,3);
  for(const bad of [{patient_id:'OTHER'},{access_receipt_id:''},{encounters:[{...visit,patient_id:'OTHER'}]},
    {encounters:[visit,visit]},{next_after_id:4},{encounters:[{...visit,status:'approved'}]}]){
    await assert.rejects(client({...page,...bad}).list(0));
  }
  await assert.rejects(client(page).list(3));
});
test('notes and literal versions bind to the requested encounter, key, version and digest',async()=>{
  assert.equal((await client(history).version(3,key,1)).body,version.body);
  for(const bad of [{encounter_id:4},{note_key:'NOTE-ELSE'},{versions:[]},
    {versions:[{...version,body:'Different'}]},{versions:[{...version,version:2}]}]){
    await assert.rejects(client({...history,...bad}).version(3,key,1));
  }
  await assert.rejects(client({patient_id:patient,encounter_id:4,notes:[],next_after_id:null}).notes(3,0));
});
test('write receipts bind to the submitted note bytes, key and expected version or encounter revision',async()=>{
  const command={type:'save',visitId:3,noteKey:key,expected:0,body:version.body,kind:'progress',requestKey:'retry-key-001'};
  const ok={note_id:4,note_key:key,version:1,sha256:hash(command.body),status:'draft'};
  let requests=[];
  const c=new VisitClient(patient,async(path,body)=>{requests.push([path,body]);return ok;});
  await c.submit(command);await c.submit(command);
  assert.deepEqual(requests[0],requests[1]);
  assert.equal(JSON.parse(requests[0][1]).expected_version,0);
  for(const bad of [{...ok,note_key:'NOTE-ELSE'},{...ok,version:2},{...ok,sha256:'3'.repeat(64)}]){
    await assert.rejects(new VisitClient(patient,async()=>bad).submit(command));
  }
  await assert.rejects(new VisitClient(patient,async()=>({encounter_id:4,revision:3,status:'completed'}))
    .submit({type:'move',visitId:3,expected:2,target:'completed',requestKey:'retry-key-002'}));
});
test('visit transport rejects a late response after patient recheck and clears an expired credential',async()=>{
  let release,expire=false;
  const response=value=>new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
  const s=new RegistrySession(async url=>url.includes('/encounters')
    ?expire?new Response('',{status:401}):new Promise(resolve=>{release=()=>resolve(response(page));})
    :response({patient_id:patient,origin_org:'ORG-ONE',created_at:at,status:'active',revision:1}));
  s.connect('fictional_test_credential_000000000001');await s.read(patient);
  const c=s.visitClient(s.snapshot().patient),pending=c.list(0);
  await s.read(patient);release();await assert.rejects(pending);
  await assert.rejects(c.list(0));
  expire=true;await assert.rejects(s.visitClient(s.snapshot().patient).list(0));
  assert.equal(s.snapshot().connected,false);
});
