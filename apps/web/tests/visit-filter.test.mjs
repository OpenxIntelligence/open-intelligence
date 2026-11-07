import test from 'node:test';
import assert from 'node:assert/strict';
import {matchingVisits} from '../.test-dist/visit-filter.js';
const first={id:1,external_key:'VISIT-APRIL',kind:'outpatient',service_date:'2026-04-06',status:'scheduled'};
const other={id:2,external_key:'VISIT-MAY',kind:'telephone',service_date:'2026-05-06',status:'in_progress'};
const rows=Object.freeze([Object.freeze(first),Object.freeze(other)]);
test('empty filters keep authorized visits in their supplied order',()=>{
  assert.deepEqual(matchingVisits(rows,'   ','all'),rows);
  assert.deepEqual(matchingVisits([],'APRIL','scheduled'),[]);
});
test('visit search combines all search terms with the selected status',()=>{
  assert.deepEqual(matchingVisits(rows,'2026-05   TELEphone','in_progress'),[other]);
  assert.deepEqual(matchingVisits(rows,'in progress','all'),[other]);
  assert.deepEqual(matchingVisits(rows,'VISIT-apr','scheduled'),[first]);
  assert.deepEqual(matchingVisits(rows,'APRIL','in_progress'),[]);
});
