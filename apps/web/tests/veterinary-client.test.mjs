import assert from 'node:assert/strict';
import test from 'node:test';
import {requestVeterinary, VeterinaryRequestError} from '../.test-dist/veterinary-client.js';

const animal = 'ANM-' + 'A'.repeat(32);
const caseId = 'VCASE-' + 'B'.repeat(32);
const record = {animal_id: animal, case_id: caseId, species: 'cat', origin_org: 'ORG-ALPHA',
  created_at: '2026-05-01T10:00:00Z'};
const intent = {kind: 'read', animal, caseId};
const signal = new AbortController().signal;
const read = (output, status=200) => requestVeterinary('fixture', intent, signal, async () => Response.json(output, {status}));

test('a veterinary case reads only its exact animal and case under the same origin', async () => {
  const result = await requestVeterinary('fixture', intent, signal, async (url, init) => {
    assert.equal(url, '/v1/veterinary/animals/' + animal + '/cases/' + caseId);
    assert.equal(init.headers.Authorization, 'Bearer fixture');
    assert.deepEqual([init.credentials, init.redirect, init.cache, init.mode], ['omit','error','no-store','same-origin']);
    return Response.json(record);
  });
  assert.equal(result.species, 'cat');
  for (const change of [{animal_id: 'ANM-'+'C'.repeat(32)}, {case_id: 'VCASE-'+'D'.repeat(32)}, {species:'human'}])
    await assert.rejects(read({...record,...change}));
  await assert.rejects(read({},404), e => e instanceof VeterinaryRequestError && e.status === 404);
  await assert.rejects(requestVeterinary('fixture', {...intent, animal: '../patients'}, signal,
    () => assert.fail('Invalid identity must not reach transport')));
});

test('case creation sends an exact retry key and validates the returned receipt', async () => {
  const create = {kind: 'open', animal, key: 'SYN-CASE-1'};
  const run = (duplicate, status) => requestVeterinary('fixture', create, signal, async (url, init) => {
    assert.equal(url, '/v1/veterinary/animals/' + animal + '/cases');
    assert.deepEqual(JSON.parse(init.body), {synthetic:true,request_key:create.key});
    return Response.json({case_id:caseId, animal_id:animal, duplicate}, {status});
  });
  assert.equal((await run(false,201)).duplicate,false);
  assert.equal((await run(true,200)).duplicate,true);
  await assert.rejects(run(false,200));
});
