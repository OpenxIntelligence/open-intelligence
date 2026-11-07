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
