'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const intake=require('../web/intake.js');
const {prepareBatch, importPreparedBatch}=intake;
const raw='OI-SYNTHETIC-REPORT/1\nPatient: CASE-NEW\nDocument: REPORT-ONE\nType: clinical\nEvent-Date: 2026-01-01\nIssued-At: 2026-01-02\nFinding: context|reported|Fictional café <b>literal</b>.\n';
const bytes=text=>new TextEncoder().encode(text);
test('case creation uses existing contract and explicit fictional-data confirmation',()=>{
 assert.deepEqual(intake.casePayload('CASE-NEW','Example',true),{case_id:'CASE-NEW',label:'Fictional case Example'});
 for(const yes of [false,null,'true',1]) assert.throws(()=>intake.casePayload('CASE-NEW','Example',yes));
});
test('invalid identifiers or labels rejected rather than silently normalizing identity',()=>{
 for(const id of ['case-new','CASE SPACE','CASE-É','A','A'.repeat(41),'CASE-NEW\n']) assert.throws(()=>intake.casePayload(id,'Example',true));
 for(const label of ['', ' ', 'X'.repeat(70),'test\nforged']) assert.throws(()=>intake.casePayload('CASE-NEW',label,true));
});
test('uploaded text preserves LF, Unicode and markup byte-for-byte',()=>{
 const result=intake.decodeSource(bytes(raw),'report.txt');
 assert.equal(result.text,raw); assert.deepEqual(bytes(result.text),bytes(raw));
 assert.equal(result.declaredCase,'CASE-NEW');assert.equal(result.byteLength,bytes(raw).length);
});
test('unsupported format, binary, oversize and empty uploads rejected',()=>{
 for(const [data,name] of [[bytes(raw),'report.pdf'],[new Uint8Array([255,254]),'bad.txt'],[bytes(''), 'empty.txt'],[bytes('x'.repeat(65537)),'large.txt'],[bytes('not a report'),'bad.txt'],[bytes('\uFEFF'+raw),'bom.txt']]) assert.throws(()=>intake.decodeSource(data,name));
});
test('ambiguous patient header rejected and wrong-case identity is preserved for server quarantine',()=>{
 assert.throws(()=>intake.decodeSource(bytes(raw.replace('Document:','Patient: CASE-OTHER\nDocument:')),'report.txt'));
 assert.equal(intake.decodeSource(bytes(raw.replace('CASE-NEW','CASE-OTHER')),'other.txt').declaredCase,'CASE-OTHER');
});
test('empty workspace has next steps but never implies completed care',()=>{
 const steps=intake.journey(null);assert.equal(steps.length,5);assert.equal(steps[0].status,'Start here');
 assert.ok(steps.every(s=>!s.detail.includes('clinically approved')));
});
test('workflow steps use source and review status rather than treating generation as review',()=>{
 const state={case:{case_id:'CASE-NEW'},sources:[{state:'current'}],questions:[{id:1,state:'open'}],snapshots:[{question_id:1,state:'draft'}]};
 assert.equal(intake.journey(state)[4].status,'Review pending');
 state.snapshots[0].state='stale';assert.equal(intake.journey(state)[4].status,'Update needs review');
 state.questions[0].state='addressed';state.snapshots.push({question_id:1,state:'reviewed_in_demo'});
 assert.equal(intake.journey(state)[4].status,'Demo review recorded');
});

test('CRLF is rejected rather than silently normalized against the LF-only source contract',()=>{assert.throws(()=>intake.decodeSource(bytes(raw.replace(/\n/g,'\r\n')),'windows.txt'), /line endings/);});

const file=(name='original.txt', text=raw)=>({
 name, size:bytes(text).byteLength, arrayBuffer:async()=>bytes(text).buffer,
});
test('one original intake owner preflights a bounded inspected batch without changing bytes',async()=>{
 const foreign=raw.replace('CASE-NEW','CASE-OTHER');
 const batch=await prepareBatch([file('a.txt'),file('foreign.txt',foreign)],'CASE-NEW');
 assert.equal(batch.length,2);
 assert.deepEqual(batch.map(x=>x.declaredCase),['CASE-NEW','CASE-OTHER']);
 assert.equal(batch[0].text,raw);
 assert.equal(batch[1].text,foreign);
 assert.equal(batch[0].caseId,'CASE-NEW');
});
test('oversized or unsupported batch preflight fails before it may import anything',async()=>{
 let reads=0;
 const make=(size,name='test.txt')=>({name,size,arrayBuffer:async()=>{reads++;return bytes(raw).buffer;}});
 for(const inputs of [[],Array.from({length:21},()=>make(1)),
   Array.from({length:17},()=>make(65536)),
   [make(65537)], [make(0)], [make(12,'test.pdf')]]) {
   await assert.rejects(prepareBatch(inputs,'CASE-NEW'));
 }
 assert.equal(reads,0);
 await assert.rejects(prepareBatch([{...file(),size:bytes(raw).length-1}],'CASE-NEW'),/changed/);
});
test('sequential original import has honest imported, duplicate, quarantine and rejected receipts',async()=>{
 const batch=await prepareBatch([file('1.txt'),file('2.txt'),file('3.txt'),file('4.txt')],'CASE-NEW');
 const replies=[
  {status:200,body:{result:'imported',source_id:8,version:1,invalidated_snapshots:[]}},
  {status:200,body:{result:'duplicate',source_id:8,version:1}},
  {status:200,body:{result:'quarantined',quarantine_id:3}},
  {status:422,body:{error:'Synthetic original rejected'}},
 ];
 const calls=[],receipts=[];
 const results=await importPreparedBatch(batch,{caseId:'CASE-NEW',
  send:async(id,text)=>{calls.push({id,text});return replies.shift();},
  onReceipt:x=>receipts.push(x)});
 assert.deepEqual(results.map(x=>x.status),['imported','duplicate','quarantined','rejected']);
 assert.equal(results[0].sourceId,8);assert.equal(results[2].quarantineId,3);
 assert.deepEqual(results,receipts);
 assert.equal(calls.length,4);
 assert.ok(calls.every(c=>c.id==='CASE-NEW'&&c.text===raw));
});
test('unknown server or connection outcome stops later writes and never invents rollback',async()=>{
 const batch=await prepareBatch([file('1.txt'),file('2.txt')],'CASE-NEW');
 for(const reply of [null,{status:200,body:{result:'imported'}},{status:500,body:{error:'down'}}]) {
  let calls=0;
  const outcome=await importPreparedBatch(batch,{caseId:'CASE-NEW',
   send:async()=>{calls++;return reply;}});
  assert.deepEqual(outcome.map(x=>x.status),['unknown','not_attempted']);
  assert.equal(calls,1);
  assert.match(outcome[0].message,/may have been saved/i);
 }
 let calls=0;
 const rejected=await importPreparedBatch(batch,{caseId:'CASE-NEW',send:async()=>{
  calls++;throw Error('PRIVATE QUERY AND URL');
 }});
 assert.equal(calls,1);assert.deepEqual(rejected.map(x=>x.status),['unknown','not_attempted']);
 assert.doesNotMatch(JSON.stringify(rejected),/PRIVATE/);
});
test('source case changes between accepted batch entries stop further writes',async()=>{
 const batch=await prepareBatch([file('1.txt'),file('2.txt')],'CASE-NEW');
 let selected='CASE-NEW',calls=0;
 const results=await importPreparedBatch(batch,{caseId:'CASE-NEW',
   isCurrent:()=>selected==='CASE-NEW',
   send:async()=>{calls++;selected='CASE-OTHER';
     return {status:200,body:{result:'imported',source_id:4,version:1}};}});
 assert.equal(calls,1);
 assert.deepEqual(results.map(x=>x.status),['imported','not_attempted']);
 assert.ok(results.every(x=>x.caseId==='CASE-NEW'));
});
