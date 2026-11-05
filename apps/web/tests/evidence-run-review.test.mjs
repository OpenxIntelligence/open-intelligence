import test from 'node:test';
import assert from 'node:assert/strict';
import {openedReviewArtifacts,decodeEvidenceRunReturn} from '../.test-dist/review-queue-view.js';

const question={patient_id:'PAT-FICTION',case_id:'CASE-FICTION',question_id:'QUESTION-'+'A'.repeat(32),
  source_id:'SRC-'+'B'.repeat(32),source_line:2,source_version:3,source_sha256:'a'.repeat(64),
  source_snapshot_sha256:'b'.repeat(64),preflight_sha256:'c'.repeat(64)};
const item={...question,queue_fingerprint:'d'.repeat(64)};
const run={questionId:question.question_id,status:{run_id:'RUN-'+'C'.repeat(32),state:'completed',result_sha256:'e'.repeat(64)},
  result:{brief:{question}}};
const report={question_id:question.question_id,report_id:'REPORT-'+'D'.repeat(32),snapshot_sha256:'f'.repeat(64),
  snapshot:{question},state:'current_unreviewed'};
test('opens a handoff only for the current inspected run, report and inbox source',()=>{
 const match=openedReviewArtifacts(item,run,report);
 assert.equal(match.result_sha256,run.status.result_sha256);
 assert.equal(match.report_snapshot_sha256,report.snapshot_sha256);
 for(const attr of Object.keys(question)){
  const other={...question,[attr]: typeof question[attr]==='number' ? 99 : 'other'};
  assert.equal(openedReviewArtifacts(item,run,{...report,snapshot:{question:other}}),null);
  assert.equal(openedReviewArtifacts(item,{...run,result:{brief:{question:other}}},report),null);
 }
 for(const stale of ['content_withheld','historical_reassessment_required']){
  assert.equal(openedReviewArtifacts(item,run,{...report,state:stale}),null);
 }
 assert.equal(openedReviewArtifacts({...item,queue_fingerprint:null},run,report),null);
 assert.equal(openedReviewArtifacts(item,{...run,result:null},report),null);
});
test('accepts only an exact receipt for the captured pair and HTTP result',()=>{
 const expected=openedReviewArtifacts(item,run,report);
 const first={...expected,receipt_id:'REVIEW-'+'E'.repeat(32),question_id:question.question_id,
   duplicate:false,clinical_approval:false,verification:'matched_current_source_and_evidence'};
 assert.equal(decodeEvidenceRunReturn(first,question.question_id,expected,201).artifacts,expected);
 assert.equal(decodeEvidenceRunReturn({...first,duplicate:true},question.question_id,expected,200).duplicate,true);
 for(const key of Object.keys(expected)){
  assert.throws(()=>decodeEvidenceRunReturn({...first,[key]:'different'},question.question_id,expected,201));
 }
 for(const changed of [{clinical_approval:true},{verification:'approved'},{duplicate:true},{unexpected:'content'}]){
  assert.throws(()=>decodeEvidenceRunReturn({...first,...changed},question.question_id,expected,201));
 }
});
