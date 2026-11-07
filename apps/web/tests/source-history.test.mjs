import test from 'node:test';
import assert from 'node:assert/strict';
import {receiptMicros,parseSourceHistory} from '../.test-dist/source-contracts.js';

const first={source_id:'SRC-'+'A'.repeat(32),document_id:'DOC-ONE',version:1,sha256:'a'.repeat(64),kind:'pathology',
  event_date:'2026-01-01',issued_at:'2026-01-02',received_at:'2026-01-03T10:00:00.000001Z',specimen_id:null,state:'superseded',supersedes_id:null};
const second={...first,source_id:'SRC-'+'B'.repeat(32),version:2,received_at:'2026-01-03T10:00:00.000002Z',state:'current',supersedes_id:first.source_id};
const late={...first,source_id:'SRC-'+'C'.repeat(32),document_id:'DOC-LATE',received_at:'2026-01-04T00:00:00Z',state:'current'};
const index={patient_id:'PAT-FICTIONAL',case_id:'CASE-ALPHA',sources:[first,second,late]};
const omitState=({state,...source})=>source;
const snapshot={contract:'oi.synthetic-source-history/1',patient_id:index.patient_id,case_id:index.case_id,
  access_receipt_id:'ACCESS-'+'D'.repeat(32),received_through:first.received_at,cutoff_basis:'platform_received_at',
  selection:'latest_version_per_document',sources:[omitState(first)],synthetic:true,clinical_interpretation:false};
const parse=(v=snapshot,cutoff=first.received_at)=>parseSourceHistory(v,index,cutoff);

test('receipt comparisons preserve microseconds and timezone offsets',()=>{
  assert.equal(receiptMicros(second.received_at)-receiptMicros(first.received_at),1n);
  assert.equal(receiptMicros(first.received_at),receiptMicros('2026-01-03T11:00:00.000001+01:00'));
  for(const bad of ['2026-02-30T00:00:00Z','2026-01-01T24:00:00Z','2026-01-01','2026-01-01T00:00:00',
    '2026-01-01T00:00:00.0000001Z','2026-01-01T00:00:00+00:99'])assert.throws(()=>receiptMicros(bad));
});
test('earlier membership excludes amendments and later imports despite old event dates',()=>{
  assert.deepEqual(parse().sources,[omitState(first)]);
  assert.equal(parse(snapshot,'2026-01-03T11:00:00.000001+01:00').sources[0].version,1);
  const latest=parse({...snapshot,received_through:late.received_at,sources:[omitState(second),omitState(late)]},late.received_at);
  assert.deepEqual(latest.sources.map(s=>s.version),[2,1]);
  assert.equal(parse({...snapshot,received_through:'2025-01-01T00:00:00Z',sources:[]},'2025-01-01T00:00:00Z').sources.length,0);
  assert.ok(Object.isFrozen(latest)&&Object.isFrozen(latest.sources)&&Object.isFrozen(latest.sources[0]));
});
test('hindsight fields, wrong scope, missing or invented membership and altered bytes fail closed',()=>{
  for(const change of [{patient_id:'PAT-OTHER'},{case_id:'CASE-OTHER'},{received_through:second.received_at},
    {access_receipt_id:'invalid'},{cutoff_basis:'event_date'},{clinical_interpretation:true},{source_reported_assertions:[]},
    {sources:[]},{sources:[first]},{sources:[omitState(second)]},{sources:[omitState(first),omitState(first)]},
    {sources:[{...omitState(first),sha256:'e'.repeat(64)}]}])assert.throws(()=>parse({...snapshot,...change}));
});
