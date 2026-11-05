import test from 'node:test';
import assert from 'node:assert/strict';
import {parseLinkedSources, prepareSourceLink, parseLinkReceipt} from '../.test-dist/encounter-source-links.js';

const patient = 'PAT-FICTIONAL', caseId = 'CASE-EXAMPLE', visit = 3;
const source = {source_id:'SRC-'+'A'.repeat(32), version:1, sha256:'a'.repeat(64),
  state:'current', document_id:'DOC-TEST'};
const index = {patient_id:patient, case_id:caseId, sources:[source]};
const link = {id:5, encounter_id:visit, patient_id:patient, case_id:caseId, source_id:source.source_id,
  version:1, sha256:source.sha256, source_state:'current'};
const page = {patient_id:patient, encounter_id:visit, case_id:caseId, next_after_id:null,
  access_receipt_id:'ACCESS-'+'F'.repeat(32), links:[link]};
const parse = (p=page,i=index,after=0) => parseLinkedSources(p,i,visit,after);

test('encounter links resolve the exact source owner, including a superseded original', () => {
  assert.equal(parse().links[0].source.document_id, 'DOC-TEST');
  const previous = {...source,state:'superseded'};
  const history = parse({...page,links:[{...link,source_state:'superseded'}]},
                        {...index,sources:[previous,{...source,source_id:'SRC-'+'B'.repeat(32),version:2}]});
  assert.equal(history.links[0].source, previous);
});
test('foreign, stale, malformed or unresolved entries prevent disclosure of the entire page', () => {
  for (const change of [{patient_id:'PAT-OTHER'},{case_id:'CASE-OTHER'},{encounter_id:4},
        {version:2},{sha256:'b'.repeat(64)},{source_id:'SRC-'+'B'.repeat(32)},
        {source_state:'superseded'},{id:0},{reviewed:true}]) {
    assert.throws(()=>parse({...page,links:[{...link,...change}]}));
  }
  for (const change of [{patient_id:'PAT-OTHER'},{case_id:'CASE-OTHER'},{encounter_id:4},
                         {access_receipt_id:'ACCESS-wrong'},{next_after_id:8},{links:[link,link]},
                         {links:[link,{...link,id:6}]},{unexpected:true}]) {
    assert.throws(()=>parse({...page,...change}));
  }
  assert.throws(()=>parse(page,index,5));
});
test('only an independently selected current source can make a retryable link intent', () => {
  const cmd = prepareSourceLink(index,visit,source.source_id);
  const payload = JSON.parse(cmd.body);
  assert.equal(cmd.encounterId, visit);
  assert.equal(cmd.caseId, caseId);
  assert.deepEqual(payload, {synthetic:true,request_key:payload.request_key,source_id:source.source_id,
                              expected_version:1,expected_sha256:source.sha256});
  assert.match(payload.request_key,/^[A-Za-z0-9_.:-]{8,100}$/);
  assert.throws(()=>prepareSourceLink(index,0,source.source_id));
  assert.throws(()=>prepareSourceLink({...index,sources:[{...source,state:'superseded'}]},visit,source.source_id));
  assert.throws(()=>prepareSourceLink(index,visit,'SRC-'+'B'.repeat(32)));
});
test('a malformed write receipt cannot be presented as a confirmed link', () => {
  assert.deepEqual(parseLinkReceipt({id:1,duplicate:true}),{id:1,duplicate:true});
  for(const value of [{id:1,duplicate:0},{id:-1,duplicate:false},{id:'1',duplicate:false},{id:1,duplicate:true,verified:true}])
    assert.throws(()=>parseLinkReceipt(value));
});
