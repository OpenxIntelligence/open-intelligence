import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {ready,transportFor,response,deferred,world,question,history,patientId,caseId,
 sourceId,sourceHash,questionId,fingerprint,time,token} from './authored-evidence-fixtures.mjs';

const packetId='SECONDOP-'+'A'.repeat(32);
const record=()=>({packet_id:packetId,patient_id:patientId,case_id:caseId,
 title:'Fictional discussion packet',source_snapshot_contract:'oi.pg-source-world-model/1',
 source_snapshot_sha256:fingerprint,created_at:time,preparation_state:'current_preparation',
 sources:[{source_id:sourceId,document_id:'DOC-ONE',version:1,sha256:sourceHash,kind:'pathology',state:'current'}],
 questions:[{question_id:questionId,question:question().question,source_id:sourceId,source_line:8,
 source_context_state:'current_unreviewed_question'}],record_completeness_verified:false,
 recipient_verified:false,external_request_sent:false,clinical_approval:false});
const listing=(packets=[record()])=>({contract:'oi.pg-second-opinion-packets/1',patient_id:patientId,
 case_id:caseId,access_receipt_id:'ACCESS-'+'B'.repeat(32),packets,synthetic:true,
 recipient_verification_supported:false,external_dispatch_supported:false,clinical_approval:false});
async function open(handler=()=>response(listing())){
 const calls=[],fallback=transportFor(()=>response({}));
 const session=new RegistrySession((url,init)=>{
  if(url.endsWith('/second-opinion-packets')){calls.push({url,init});return handler(url,init);}
  return fallback(url,init);
 });
 await ready(session);
 assert.equal(typeof session.loadSecondOpinionPackets,'function','packet reads must use the canonical session');
 return {session,calls};
}
const draft=session=>session.editSecondOpinionPacket({title:'Fictional discussion packet',source_ids:[sourceId],question_ids:[questionId]});

test('packets are unchecked until an independent authenticated read; verified empty is distinct',async()=>{
 const {session,calls}=await open(()=>response(listing([])));
 assert.equal(session.snapshot().secondOpinionPhase,'idle');
 assert.equal(session.snapshot().secondOpinionPackets,null);
 await session.loadSecondOpinionPackets(caseId);
 assert.equal(session.snapshot().secondOpinionPhase,'ready');
 assert.deepEqual(session.snapshot().secondOpinionPackets.packets,[]);
 assert.equal(calls[0].init.method,'GET');
 assert.equal(calls[0].init.headers.Authorization,'Bearer '+token);
 assert.equal(calls[0].init.cache,'no-store');
 assert.equal(calls[0].init.credentials,'omit');
});

test('packet creation requires deliberate selection and confirmation; it never silently selects records',async()=>{
 const {session,calls}=await open((url,init)=>response({packet_id:packetId,duplicate:false},201));
 await session.saveSecondOpinionPacket(true);assert.equal(calls.length,0);
 assert.equal(session.editSecondOpinionPacket({title:'Fictional discussion packet'}),true);
 assert.deepEqual(session.snapshot().secondOpinionDraft.source_ids,[]);
 await session.saveSecondOpinionPacket(true);assert.equal(calls.length,0);
 draft(session);await session.saveSecondOpinionPacket(false);assert.equal(calls.length,0);
 await session.saveSecondOpinionPacket(true);
 assert.equal(calls.length,1);
 const body=JSON.parse(calls[0].init.body);
 assert.equal(body.expected_source_snapshot_sha256,fingerprint);
 assert.deepEqual(body.source_ids,[sourceId]);assert.deepEqual(body.question_ids,[questionId]);
 assert.equal(body.synthetic,true);assert.ok(body.request_key);
 assert.equal(session.snapshot().secondOpinionWritePhase,'saved');
 assert.equal(session.snapshot().secondOpinionReceipt.packet_id,packetId);
 assert.equal(session.snapshot().secondOpinionDraft,null);
});

test('lost response recovery resends the exact captured command and blocks edits and new saves',async()=>{
 let attempts=0;
 const {session,calls}=await open(()=>++attempts===1?Promise.reject(Error('lost reply')):response({packet_id:packetId,duplicate:true},200));
 draft(session);await session.saveSecondOpinionPacket(true);
 assert.equal(session.snapshot().secondOpinionWritePhase,'unknown');
 const captured=session.snapshot().secondOpinionIntent.body;
 assert.equal(session.editSecondOpinionPacket({title:'A different fictional packet'}),false);
 await session.saveSecondOpinionPacket(true);assert.equal(calls.length,1);
 await session.retrySecondOpinionPacket();
 assert.equal(calls[1].init.body,captured);
 assert.equal(session.snapshot().secondOpinionWritePhase,'saved');
 assert.equal(session.snapshot().secondOpinionReceipt.duplicate,true);
});

for(const [status,duplicate] of [[200,false],[201,true],[202,false]]){
 test(`contradictory packet receipt ${status}/${duplicate} remains outcome unknown`,async()=>{
  const {session}=await open(()=>response({packet_id:packetId,duplicate},status));
  draft(session);await session.saveSecondOpinionPacket(true);
  assert.equal(session.snapshot().secondOpinionWritePhase,'unknown');
  assert.equal(session.snapshot().secondOpinionReceipt,null);
  assert.ok(session.snapshot().secondOpinionIntent);
 });
}

test('pending create is single-flight and disconnect rejects its delayed receipt',async()=>{
 const held=deferred();const {session,calls}=await open(()=>held.promise);
 draft(session);const write=session.saveSecondOpinionPacket(true);
 try{
  await session.saveSecondOpinionPacket(true);assert.equal(calls.length,1);
  session.disconnect();
 }finally{held.resolve(response({packet_id:packetId,duplicate:false},201));await write;}
 assert.equal(session.snapshot().secondOpinionReceipt,null);
 assert.equal(session.snapshot().secondOpinionIntent,null);
});

test('refresh clears previously disclosed packets before the response and denial preserves independent questions',async()=>{
 const held=deferred();let repeat=false;
 const {session}=await open(()=>repeat?held.promise:response(listing()));
 await session.loadSecondOpinionPackets(caseId);repeat=true;
 const read=session.loadSecondOpinionPackets(caseId);
 assert.equal(session.snapshot().secondOpinionPackets,null);
 assert.equal(session.snapshot().secondOpinionPhase,'loading');
 held.resolve(response({detail:'Denied'},404));await read;
 assert.equal(session.snapshot().secondOpinionPhase,'error');
 assert.equal(session.snapshot().secondOpinionPackets,null);
 assert.equal(session.snapshot().questions[0].question_id,questionId);
});

test('late packet read cannot restore after A/B/A case navigation',async()=>{
 const held=deferred();const {session}=await open(()=>held.promise);
 const read=session.loadSecondOpinionPackets(caseId);
 await session.loadWorldModel('CASE-BETA');await session.loadWorldModel(caseId);await session.loadSavedQuestions(caseId);
 held.resolve(response(listing()));await read;
 assert.equal(session.snapshot().secondOpinionPackets,null);
});

test('same-case source refresh retains an uncertain command but not an earlier packet read',async()=>{
 let fail=true;const {session,calls}=await open((url,init)=>init.method==='GET'?response(listing()):
  fail?Promise.reject(Error('lost')):response({packet_id:packetId,duplicate:true},200));
 await session.loadSecondOpinionPackets(caseId);draft(session);await session.saveSecondOpinionPacket(true);
 const original=session.snapshot().secondOpinionIntent.body;
 await session.loadWorldModel(caseId);await session.loadSavedQuestions(caseId);
 assert.equal(session.snapshot().secondOpinionPackets,null);
 assert.equal(session.snapshot().secondOpinionIntent.body,original);
 fail=false;await session.retrySecondOpinionPacket();
 assert.equal(calls.at(-1).init.body,original);
});

test('changed source snapshot clears unsent selection instead of retargeting it',async()=>{
 let changed=false;const fallback=transportFor(()=>response({}));
 const session=new RegistrySession((url,init)=>url.endsWith('/world-model')?
  response({...world(),snapshot_fingerprint:changed?'f'.repeat(64):fingerprint}):fallback(url,init));
 await ready(session);assert.equal(typeof session.editSecondOpinionPacket,'function');draft(session);
 changed=true;await session.loadWorldModel(caseId);await session.loadSavedQuestions(caseId);
 assert.equal(session.snapshot().secondOpinionDraft,null);
});

for(const [name,mutate] of [
 ['wrong patient',v=>v.patient_id='PAT-OTHER'],
 ['duplicate packet',v=>v.packets.push(structuredClone(v.packets[0]))],
 ['duplicate source',v=>v.packets[0].sources.push(structuredClone(v.packets[0].sources[0]))],
 ['question without selected source',v=>v.packets[0].questions[0].source_id='SRC-'+'F'.repeat(32)],
 ['forged dispatch',v=>v.packets[0].external_request_sent=true],
 ['impossible date',v=>v.packets[0].created_at='2026-02-30T10:00:00Z'],
 ['fresh label with superseded source',v=>v.packets[0].sources[0].state='superseded'],
 ['fresh label with stale question',v=>v.packets[0].questions[0].source_context_state='source_reassessment_required'],
 ['numeric false',v=>v.clinical_approval=0],
 ['unknown field',v=>v.undocumented='field'],
]){
 test(`invalid packet projection fails closed: ${name}`,async()=>{
  const bad=listing();mutate(bad);
  const {session}=await open(()=>response(bad));await session.loadSecondOpinionPackets(caseId);
  assert.equal(session.snapshot().secondOpinionPhase,'error');assert.equal(session.snapshot().secondOpinionPackets,null);
 });
}

test('historical packets retain pinned identities and explicit reassessment',async()=>{
 const old=listing();old.packets[0].preparation_state='source_reassessment_required';
 old.packets[0].sources[0].state='superseded';old.packets[0].questions[0].source_context_state='source_reassessment_required';
 const {session}=await open(()=>response(old));await session.loadSecondOpinionPackets(caseId);
 assert.equal(session.snapshot().secondOpinionPhase,'ready');
 assert.equal(session.snapshot().secondOpinionPackets.packets[0].sources[0].source_id,sourceId);
 assert.equal(session.snapshot().secondOpinionPackets.packets[0].preparation_state,'source_reassessment_required');
});

test('same-patient access recheck preserves uncertain receipt recovery without exposing old records',async()=>{
 const {session}=await open(()=>Promise.reject(Error('lost')));draft(session);await session.saveSecondOpinionPacket(true);
 const captured=session.snapshot().secondOpinionIntent.body;
 await session.read(patientId);
 assert.equal(session.snapshot().secondOpinionIntent?.body,captured);
 assert.equal(session.snapshot().secondOpinionPackets,null);
 await session.loadCases();await session.loadWorldModel(caseId);await session.loadSavedQuestions(caseId);
 assert.equal(session.snapshot().secondOpinionIntent?.body,captured);
});

test('question refresh during a packet write marks it uncertain rather than leaving saving stuck',async()=>{
 const held=deferred();const {session}=await open(()=>held.promise);
 draft(session);const write=session.saveSecondOpinionPacket(true);
 await session.loadSavedQuestions(caseId);
 assert.equal(session.snapshot().secondOpinionWritePhase,'unknown');
 held.resolve(response({packet_id:packetId,duplicate:false},201));await write;
 assert.equal(session.snapshot().secondOpinionWritePhase,'unknown');
 assert.equal(session.snapshot().secondOpinionReceipt,null);
});

test('question refresh during a packet read removes loading and rejects the old result',async()=>{
 const held=deferred();const {session}=await open(()=>held.promise);
 const read=session.loadSecondOpinionPackets(caseId);
 await session.loadSavedQuestions(caseId);
 held.resolve(response(listing()));await read;
 assert.equal(session.snapshot().secondOpinionPackets,null);
 assert.equal(session.snapshot().secondOpinionPhase,'idle');
});

test('source-selection mismatch prevents create and ordinary editing sends no request',async()=>{
 const {session,calls}=await open();
 assert.equal(session.editSecondOpinionPacket({title:'Fictional discussion packet',question_ids:[questionId]}),true);
 await session.saveSecondOpinionPacket(true);assert.equal(calls.length,0);
 assert.equal(session.editSecondOpinionPacket({source_ids:['SRC-'+'F'.repeat(32)]}),false);
 assert.equal(session.editSecondOpinionPacket({question_ids:[questionId,questionId]}),false);
 assert.equal(session.editSecondOpinionPacket({title:'   Fictional packet'}),true);
 session.editSecondOpinionPacket({source_ids:[sourceId]});await session.saveSecondOpinionPacket(true);
 assert.equal(calls.length,0);
});

test('unauthorized packet response expires the shared session and all packet data',async()=>{
 const {session}=await open(()=>response({detail:'expired'},401));
 draft(session);await session.loadSecondOpinionPackets(caseId);
 assert.equal(session.snapshot().connected,false);assert.equal(session.snapshot().secondOpinionDraft,null);
 assert.equal(session.snapshot().secondOpinionIntent,null);
});

test('abandoning uncertain recovery sends no cancellation and does not claim the packet was undone',async()=>{
 const {session,calls}=await open(()=>Promise.reject(Error('lost')));draft(session);await session.saveSecondOpinionPacket(true);
 assert.equal(session.abandonSecondOpinionPacket(),true);assert.equal(calls.length,1);
 assert.equal(session.snapshot().secondOpinionIntent,null);
 assert.match(session.snapshot().secondOpinionWriteMessage,/does not undo/);
});

for(const status of [403,404,409,422]){
 test(`refused retry ${status} cannot erase uncertainty about the earlier committed command`,async()=>{
  let first=true;const {session,calls}=await open(()=>first?(first=false,Promise.reject(Error('lost'))):response({detail:'refused'},status));
  draft(session);await session.saveSecondOpinionPacket(true);const captured=session.snapshot().secondOpinionIntent.body;
  await session.retrySecondOpinionPacket();
  assert.equal(session.snapshot().secondOpinionWritePhase,'unknown');
  assert.equal(session.snapshot().secondOpinionIntent?.body,captured);
  await session.saveSecondOpinionPacket(true);assert.equal(calls.length,2);
 });
}
