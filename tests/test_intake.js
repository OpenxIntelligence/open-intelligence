'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const intake=require('../web/intake.js');
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
