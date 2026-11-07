import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseSourceWorldModel} from '../.test-dist/source-world-model.js';
import {parseSourceSemantics} from '../.test-dist/source-semantics.js';
const fixture=JSON.parse(readFileSync(new URL('./fixtures/source-semantics.json',import.meta.url)));
const world=parseSourceWorldModel(fixture.world,'PAT-SYNTH','CASE-ALPHA');
test('Python/TypeScript semantic contract retains all original statuses',()=>{
  const value=parseSourceSemantics(fixture.semantics,world);
  assert.deepEqual(value.records.map(r=>r.original_state),world.observations.map(o=>o.reported_state));
  assert.equal(value.records[4].evidence_status,'missing');
  assert.equal(value.records[1].evidence_status,'negative');
  assert.ok(Object.isFrozen(value.records[0]));
});
test('wrong scope, stale source, fabricated meaning and incomplete coverage fail closed',()=>{
  for(const mutate of [x=>x.patient_id='PAT-OTHER',x=>x.case_id='CASE-OTHER',
    x=>x.source_snapshot_sha256='b'.repeat(64),x=>x.records[0].source_sha256='b'.repeat(64),
    x=>x.records[0].concept_version=2,x=>x.records[0].concept_version=true,
    x=>x.records[0].knowledge_kind='inferred',x=>x.records[4].evidence_status='negative',
    x=>x.records[4].original_state='not-assessed',x=>x.records[0].owner='other',
    x=>x.records.pop(),x=>x.records.push(x.records[0]),x=>x.records[1]=x.records[0],
    x=>x.records[0].clinical_meaning='normal',x=>x.clinical_interpretation=true]){
    const raw=structuredClone(fixture.semantics);mutate(raw);
    assert.throws(()=>parseSourceSemantics(raw,world));
  }
});

test('historical semantics binds the exact microsecond cutoff and past source snapshot',async()=>{
  const {parseHistoricalSourceSemantics}=await import('../.test-dist/source-semantics.js');
  const history={contract:'oi.pg-source-history/1',received_through:'2026-01-02T00:00:00.000001Z',
    selection_basis:'received_at_inclusive',current_authority_required:true,historical_only:true,world_model:world};
  const raw={contract:'oi.source-semantics-history/1',received_through:history.received_through,
    selection_basis:history.selection_basis,current_authority_required:true,historical_only:true,semantics:fixture.semantics};
  assert.equal(parseHistoricalSourceSemantics(raw,history).records[4].evidence_status,'missing');
  for(const mutate of [x=>x.received_through='2026-01-02T00:00:00.000002Z',
    x=>x.current_authority_required=false,x=>x.historical_only=false,
    x=>x.semantics.source_snapshot_sha256='b'.repeat(64),x=>x.semantics.records[4].evidence_status='negative']){
    const value=structuredClone(raw);mutate(value);assert.throws(()=>parseHistoricalSourceSemantics(value,history));
  }
});
