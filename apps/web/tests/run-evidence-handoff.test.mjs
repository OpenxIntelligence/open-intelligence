import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {reviewChoices, readVerificationReturn, verificationIntent} from '../.test-dist/background-brief.js';

const q = {patient_id:'PAT-ONE',case_id:'CASE-ALPHA',question_id:'QUESTION-'+'A'.repeat(32),
  preflight_sha256:'a'.repeat(64),source_snapshot_sha256:'b'.repeat(64)};
const run = {run_id:'RUN-'+'C'.repeat(32),result_sha256:'c'.repeat(64),state:'completed'};
const e = {evidence_id:'EVIDENCE-'+'D'.repeat(32),version:2,sha256:'d'.repeat(64),rights_sha256:'e'.repeat(64),
  statement_line:4,state:'current',title:'Fictional worksheet'};
const a = {assessment_id:'ASSESSMENT-'+'F'.repeat(32),question_id:q.question_id,evidence_id:e.evidence_id,
  evidence_sha256:e.sha256,rights_sha256:e.rights_sha256,source_snapshot_sha256:q.source_snapshot_sha256,
  preflight_sha256:q.preflight_sha256,quote:'🧪 café',quote_start:3,state:'current_unreviewed'};
const packet = {patient_id:q.patient_id,case_id:q.case_id,question:q,source_snapshot_sha256:q.source_snapshot_sha256,
  assessments:[a],evidence:[e]};
const digest = createHash('sha256').update(a.quote).digest('hex');
const common = {contract:'oi.synthetic-run-evidence-review-return/1',run_id:run.run_id,result_sha256:run.result_sha256,
  receipt_id:'REVIEW-'+'A'.repeat(32),question_id:q.question_id,duplicate:false,review_state:'returned_for_independent_verification',
  clinical_approval:false,model_executed:false};

test('authored handoff sends exact IDs and digests without forwarding the selected text; proves unicode offsets',async()=>{
  const [choice] = reviewChoices(q,null,packet);
  const intent = await verificationIntent(choice,run);
  assert.equal(intent.expected_quote_sha256,digest);
  assert.ok(!JSON.stringify(intent).includes('café'));
  const proof = {...common,verification:'exact_authored_quote',assessment_id:a.assessment_id,evidence_id:e.evidence_id,
    evidence_version:e.version,evidence_sha256:e.sha256,rights_sha256:e.rights_sha256,statement_line:4,
    quote_start:3,quote_length:6,quote_sha256:digest};
  assert.equal(readVerificationReturn(proof,201,run,q,choice,digest),proof.receipt_id);
  for(const tamper of [{quote_length:a.quote.length},{rights_sha256:'f'.repeat(64)},{quote_start:2},
    {clinical_approval:true},{evidence_version:1},{quote:'unauthorized text'},{duplicate:true}])
    assert.throws(()=>readVerificationReturn({...proof,...tamper},201,run,q,choice,digest));
  for (const p of [{...packet,patient_id:'PAT-ELSEWHERE'},{...packet,evidence:[{...e,state:'withdrawn'}]},
    {...packet,assessments:[{...a,state:'content_withheld',quote:null}]},{...packet,source_snapshot_sha256:'0'.repeat(64)}])
    assert.deepEqual(reviewChoices(q,null,p),[]);
});

test('metadata-only handoffs require the same current case, available link, exact version, digest and receipt', async()=>{
  const link={link_id:'EVIDENCE-LINK-'+'E'.repeat(32),citation:'FICT-EXAMPLE@2',metadata_sha256:'f'.repeat(64),
    status:'available',record:{title:'Independent catalog fixture'}};
  const history={...q,source_context_state:'current_unreviewed_question',links:[link]};
  const [choice] = reviewChoices(q,history,null);
  assert.deepEqual(await verificationIntent(choice,run),{verification:'exact_version_metadata_only',synthetic:true,
    expected_result_sha256:run.result_sha256,link_id:link.link_id,citation:link.citation,expected_metadata_sha256:link.metadata_sha256});
  const proof={...common,verification:choice.kind,link_id:link.link_id,citation:link.citation,metadata_sha256:link.metadata_sha256};
  assert.equal(readVerificationReturn(proof,201,run,q,choice),proof.receipt_id);
  assert.throws(()=>readVerificationReturn({...proof,citation:'FICT-EXAMPLE@1'},201,run,q,choice));
  for(const h of [{...history,case_id:'CASE-ELSEWHERE'},{...history,links:[{...link,status:'rights_restricted',record:null}]},
    {...history,source_context_state:'source_reassessment_required'}]) assert.deepEqual(reviewChoices(q,h,null),[]);
});
