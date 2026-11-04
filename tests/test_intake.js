'use strict';
const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const {readReportFile, importReportFiles, validateCaseInput} = require('../web/intake.js');
const original = fs.readFileSync(path.join(__dirname, '../examples/synthetic/alpha-pathology-original.txt'));
function file(name = 'report.txt', bytes = original) {
  return {name, size: bytes.byteLength, arrayBuffer: async () => Uint8Array.from(bytes).buffer};
}
const imported = {status: 200, body: {result: 'imported', source_id: 12, version: 1, invalidated_snapshots: []}};
test('original UTF-8 bytes and source patient are never rewritten', async () => {
  const bytes = Buffer.concat([original, Buffer.from('\nNote: Original Unicode α β\n')]);
  assert.deepEqual(Buffer.from(await readReportFile(file('source.txt', bytes)), 'utf8'), bytes);
  const calls = [];
  await importReportFiles([file()], {caseId: 'CASE-OTHER', send: async (id,text) => { calls.push({id,text}); return imported; }});
  assert.equal(calls[0].id, 'CASE-OTHER');
  assert.equal(calls[0].text, original.toString('utf8'));
  assert.match(calls[0].text, /Patient: CASE-ALPHA/);
});
test('refuses unsupported and oversized inputs before reading', async () => {
  let reads = 0;
  for (const f of [file('x.pdf'), {...file(), size: 65537}, {...file(), size: 0}]) {
    f.arrayBuffer = async () => { reads++; throw Error('must not read'); };
    await assert.rejects(readReportFile(f));
  }
  assert.equal(reads, 0);
});
test('refuses non-UTF8, BOM and non-contract text without normalizing', async () => {
  for (const b of [Buffer.from([0xff]), Buffer.concat([Buffer.from([0xef,0xbb,0xbf]),original]), Buffer.from('ordinary unknown report'), Buffer.from('')]) {
    await assert.rejects(readReportFile(file('report.txt', b)));
  }
});
test('refuses size mismatch between metadata and actual bytes', async () => {
  await assert.rejects(readReportFile({...file(), size: original.length - 1}));
});
test('case input validates rather than silently changing identity', () => {
  assert.deepEqual(validateCaseInput('CASE-NEW', 'Example'), {case_id:'CASE-NEW',label:'Fictional case Example'});
  for (const id of ['', 'case-new', ' CASE-NEW', '../X', 'CASE-NEW\n', 'C'.repeat(41)]) assert.throws(() => validateCaseInput(id, 'Example'));
  for (const label of ['', ' ', 'X'.repeat(67)]) assert.throws(() => validateCaseInput('CASE-NEW', label));
});
test('batch retains order and distinguishes imported duplicate quarantine and rejection', async () => {
  const results = [imported, {status:200,body:{result:'duplicate',source_id:12,version:1}},
    {status:200,body:{result:'quarantined',quarantine_id:3,reason:'patient_mismatch'}}, {status:422,body:{error:'Changed document requires explicit amendment'}}];
  const seen=[]; const receipts=[];
  const out=await importReportFiles([1,2,3,4].map(n=>file(n+'.txt')), {caseId:'CASE-ALPHA',send:async(id,text)=>{seen.push(id);return results.shift();},onReceipt:r=>receipts.push(r)});
  assert.deepEqual(out.map(x=>x.status), ['imported','duplicate','quarantined','rejected']);
  assert.equal(out[2].quarantineId,3); assert.equal(out[0].sourceId,12);
  assert.deepEqual(seen,Array(4).fill('CASE-ALPHA')); assert.deepEqual(receipts,out);
});
test('local invalid file does not prevent a later supported file', async () => {
  let calls=0;
  const out=await importReportFiles([file('bad.pdf'),file()],{caseId:'CASE-ALPHA',send:async()=>{calls++;return imported;}});
  assert.deepEqual(out.map(x=>x.status),['rejected','imported']); assert.equal(calls,1);
});
test('network ambiguity stops subsequent writes and never claims rollback', async () => {
  let calls=0;
  const out=await importReportFiles([file('a.txt'),file('b.txt')],{caseId:'CASE-ALPHA',send:async()=>{calls++;throw Error('connection lost');}});
  assert.deepEqual(out.map(x=>x.status),['unknown','not_attempted']); assert.equal(calls,1);
  assert.match(out[0].message,/may have been saved/i);
});
test('malformed success or server failure is unknown, not imported or rejected', async () => {
  for (const response of [{status:200,body:{result:'imported'}},{status:200,body:{result:'new'}},{status:500,body:{error:'failure'}},null]) {
    let calls=0;
    const out=await importReportFiles([file('a.txt'),file('b.txt')], {caseId:'CASE-ALPHA',send:async()=>{calls++;return response;}});
    assert.deepEqual(out.map(x=>x.status),['unknown','not_attempted']); assert.equal(calls,1);
  }
});
test('case changes during file read stop before any write', async () => {
  let current=true, calls=0; const f=file();
  f.arrayBuffer=async()=>{current=false;return Uint8Array.from(original).buffer;};
  const out=await importReportFiles([f,file()],{caseId:'CASE-ALPHA',isCurrent:()=>current,send:async()=>{calls++;return imported;}});
  assert.deepEqual(out.map(x=>x.status),['not_attempted','not_attempted']); assert.equal(calls,0);
});
test('case changes after committed request retain original-case receipt but stop next file', async () => {
  let current=true,calls=0;
  const out=await importReportFiles([file(),file()],{caseId:'CASE-ALPHA',isCurrent:()=>current,send:async()=>{calls++;current=false;return imported;}});
  assert.deepEqual(out.map(x=>x.status),['imported','not_attempted']); assert.equal(out[0].caseId,'CASE-ALPHA'); assert.equal(calls,1);
});
test('empty oversized count and aggregate batches fail before IO',async()=>{
  let calls=0;
  for (const batch of [[],Array.from({length:21},()=>file()),Array.from({length:17},()=>({...file(),size:65536}))]) {
    await assert.rejects(importReportFiles(batch,{caseId:'CASE-ALPHA',send:async()=>{calls++;return imported;}}));
  }
  assert.equal(calls,0);
});
