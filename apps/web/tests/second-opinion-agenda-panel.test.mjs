import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'vite';
import {RegistrySession} from '../.test-dist/registry-client.js';

let SecondOpinionPreparation;
before(async()=>{
 await build({configFile:false,logLevel:'silent',build:{ssr:resolve('src/second-opinion-preparation-view.tsx'),
  outDir:'.test-dist/second-opinion-agenda-ui',emptyOutDir:true,
  rollupOptions:{output:{entryFileNames:'second-opinion-preparation-view.mjs'}}}});
 ({SecondOpinionPreparation}=await import(pathToFileURL(resolve('.test-dist/second-opinion-agenda-ui/second-opinion-preparation-view.mjs')).href));
});
const patientId='PAT-AGENDA';
const caseId='CASE-AGENDA';
function base(){
 return {...new RegistrySession().snapshot(),connected:true,phase:'ready',
 patient:{patient_id:patientId,origin_org:'ORG-ONE',created_at:'2026-11-03T10:00:00Z',status:'active',revision:1},
 cases:[{patient_id:patientId,case_id:caseId,status:'active'}],
 worldPhase:'ready',worldModel:{patient_id:patientId,case_id:caseId,snapshot_fingerprint:'context-v1'},
 questionsCaseId:caseId,questionsAccessReceiptId:'ACCESS-'+'B'.repeat(32),questionListPhase:'ready',questions:[],
 recordsPhase:'ready',sourceIndex:{patient_id:patientId,case_id:caseId,sources:[{state:'current'}]}};
}
function question(state='current_unreviewed_question'){
 return {question_id:'QUESTION-'+'A'.repeat(32),patient_id:patientId,case_id:caseId,
  question:'Could we discuss fictional marker & <unverified note>?',source_version:2,source_line:14,
  source_context_state:state};
}
const render=state=>renderToStaticMarkup(createElement(SecondOpinionPreparation,{state,onNavigate:()=>{},onResumeQuestion:()=>{},onCheckEvidence:()=>{}}));

test('saved agenda rows offer question-specific inspection and keep unsent passage recovery distinct',()=>{
 const saved=question(),draft={...question(),question_id:'QUESTION-'+'C'.repeat(32),question:'Another fictional question'};
 const state={...base(),questions:[saved,draft],manualPassageDraftQuestionIds:[draft.question_id]};
 const html=render(state);
 assert.equal((html.match(/data-testid="second-opinion-open-question"/g)||[]).length,1);
 assert.equal((html.match(/data-testid="second-opinion-resume-passages"/g)||[]).length,1);
 assert.match(html,/aria-label="Inspect records and reports for: Could we discuss fictional marker &amp; &lt;unverified note&gt;\?"/);
 for(const patch of [{questionListPhase:'loading'},{questionListPhase:'error'},
  {questionsCaseId:'CASE-OTHER'},{connected:false}]){
  assert.doesNotMatch(render({...state,...patch}),/data-testid="(?:second-opinion-open-question|second-opinion-resume-passages)"/,JSON.stringify(patch));
 }
});

test('preparation separates primary question status from unchecked attached passages and reports',()=>{
 const html=render({...base(),questions:[question()]});
 assert.match(html,/Primary source version 2, line 14/);
 assert.match(html,/Primary source context is current; not clinically reviewed/);
 assert.match(html,/Attached passages and preserved reports need a separate freshness check in Investigations/);
});

test('agenda identifies unfinished passage work without treating it as saved or exposing quotations',()=>{
 const state={...base(),questions:[question()],manualPassageDraftQuestionIds:[question().question_id]};
 const html=render(state);
 assert.match(html,/data-testid="second-opinion-passage-drafts"/);
 assert.match(html,/data-testid="second-opinion-resume-passages"/);
 assert.match(html,/Resume unsaved record passages/);
 assert.match(html,/not yet attached/);
 assert.doesNotMatch(render({...state,questionListPhase:'error'}),/second-opinion-resume-passages|second-opinion-passage-drafts/);
 assert.doesNotMatch(render({...state,manualPassageDraftQuestionIds:[]}),/second-opinion-resume-passages|second-opinion-passage-drafts/);
});

test('agenda renders literal user-authored questions as escaped text, provenance and review status',()=>{
 const html=render({...base(),questions:[question('source_reassessment_required')]});
 assert.match(html,/data-testid="second-opinion-agenda-item"/);
 assert.match(html,/data-source-context="source_reassessment_required"/);
 assert.match(html,/Could we discuss fictional marker &amp; &lt;unverified note&gt;\?/);
 assert.doesNotMatch(html,/<unverified note>/);
 assert.match(html,/Primary source version 2, line 14/);
 assert.match(html,/Source changed: reassessment required/);
 assert.match(html,/Showing 1 of 1 saved question/);
});

test('an unsuccessful authorization refresh withholds old question text instead of showing false empty',()=>{
 const old={...base(),questions:[question()]};
 const denied=render({...old,questionListPhase:'error'});
 const waiting=render({...old,questionListPhase:'loading'});
 for(const html of [denied,waiting]){
  assert.match(html,/data-testid="second-opinion-agenda-unavailable"/);
  assert.doesNotMatch(html,/Could we discuss fictional marker/);
  assert.doesNotMatch(html,/data-testid="second-opinion-agenda-item"/);
  assert.doesNotMatch(html,/data-testid="second-opinion-agenda-empty"/);
 }
});

test('verified empty history is explicit and never asserts care completeness',()=>{
 const html=render(base());
 assert.match(html,/data-testid="second-opinion-agenda-empty"/);
 assert.match(html,/does not establish that there are no care questions/);
 assert.doesNotMatch(html,/data-testid="second-opinion-agenda-item"/);
});

const withTasks=(tasks=[])=>({followthroughPhase:'ready',followthroughCaseId:caseId,followthrough:{
 patient_id:patientId,case_id:caseId,access_receipt_id:'ACCESS-'+'D'.repeat(32),evaluated_on:'2026-11-03',
 tasks,synthetic:true,clinical_approval:false,external_notification_sent:false}});
const task=(status='assigned')=>({task_id:'TASK-'+'C'.repeat(32),question_id:question().question_id,
 patient_id:patientId,case_id:caseId,title:'Fictional <test> & follow-up',owner_label:'Fictional <owner> & care team',
 status,due_date:'2026-10-30',review_trigger:'After fictional source correction',needs_recheck:true,is_overdue:true});

test('per-question work renders literal owner and task text safely with recorded source/date flags',()=>{
 const html=render({...base(),questions:[question('source_reassessment_required')],...withTasks([task()])});
 assert.match(html,/data-testid="second-opinion-question-work"[^>]*data-work-state="ready"/);
 assert.match(html,/data-testid="second-opinion-question-task"[^>]*data-task-id="TASK-/);
 assert.match(html,/Fictional &lt;test&gt; &amp; follow-up/);
 assert.match(html,/Fictional &lt;owner&gt; &amp; care team/);
 assert.doesNotMatch(html,/<owner>|<test>/);
 assert.match(html,/Recorded status: assigned/);
 assert.match(html,/Revisit date: 2026-10-30/);
 assert.match(html,/Source changed: recorded work requires reassessment/);
 assert.match(html,/Revisit date passed as of 2026-11-03 \(operational flag, not clinical urgency\)/);
});

test('separate task grant denial withholds all task identifiers while preserving question text',()=>{
 const state={...base(),questions:[question()],...withTasks([task()])};
 for(const patch of [{followthroughPhase:'error'},{followthroughPhase:'loading'},
  {followthroughCaseId:'CASE-OTHER'}]){
  const html=render({...state,...patch});
  assert.match(html,/Could we discuss fictional marker/);
  assert.match(html,/data-testid="second-opinion-question-work-unavailable"/);
  assert.doesNotMatch(html,/data-testid="second-opinion-question-task"/);
  assert.doesNotMatch(html,/Fictional &lt;test&gt; &amp; follow-up/);
 }
 const empty=render({...state,...withTasks([])});
 assert.match(empty,/data-testid="second-opinion-question-work-empty"/);
 assert.doesNotMatch(empty,/data-testid="second-opinion-question-work-unavailable"/);
});

test('historical-only task status is counted, never presented as an open action',()=>{
 const html=render({...base(),questions:[question()],...withTasks([task('completed')])});
 assert.match(html,/data-open-count="0"[^>]*data-history-count="1"/);
 assert.doesNotMatch(html,/data-testid="second-opinion-question-task"/);
 assert.match(html,/Historical work remains available in Investigations/);
});

test('second-opinion UI shows laboratory questions as a separate unreviewed source, never a fictional line',()=>{
 const state=base(),sid='SRC-'+'F'.repeat(32),sha='a'.repeat(64);
 const snapshot=state.worldModel.snapshot_fingerprint;
 const scope={...state,worldModel:{...state.worldModel,current_sources:[{source_id:sid,version:1,
  sha256:sha,kind:'laboratory',state:'current'}],history:[],laboratory_observations:[{
  source_id:sid,observation_reference:'Observation/FICTIONAL-OBS'}]},labQuestionListPhase:'ready',
  labQuestionHistory:{patient_id:patientId,case_id:caseId,checked_source_snapshot_sha256:snapshot,
   access_receipt_id:'ACCESS-'+'D'.repeat(32),questions:[{question_id:'QUESTION-'+'F'.repeat(32),
   source_id:sid,source_version:1,source_sha256:sha,source_context_state:'current_unreviewed_question'}]}};
 const html=renderToStaticMarkup(createElement(SecondOpinionPreparation,
  {state:scope,onNavigate(){},onResumeQuestion(){}}));
 assert.match(html,/data-state="needs_laboratory_review"/);
 assert.match(html,/data-testid="second-opinion-lab-questions"/);
 assert.match(html,/1 current · 0 needing source reassessment/);
 assert.match(html,/Open saved laboratory questions in Journey to inspect the original result/);
 assert.match(html,/No text-anchored questions were returned/);
 assert.doesNotMatch(html,/Primary source version 1, line 0/);
});

test('question-specific citation readiness distinguishes unchecked from checked empty',()=>{
 const s={...base(),questions:[question()]};
 assert.match(render(s),/data-testid="second-opinion-citations-unchecked"/);
 const e={contract:'oi.pg-question-evidence-links/1',patient_id:patientId,case_id:caseId,
  question_id:question().question_id,source_context_state:'current_unreviewed_question',
  source_access_receipt_id:'ACCESS-'+'A'.repeat(32),synthetic:true,model_executed:false,
  content_appraised:false,clinical_approval:false,links:[]};
 const checked=render({...s,evidenceFamily:'text',evidenceQuestionId:question().question_id,evidenceLinksPhase:'ready',evidenceLinks:e});
 assert.match(checked,/data-testid="second-opinion-citations-empty"/);
 assert.doesNotMatch(checked,/data-testid="second-opinion-citations-unchecked"/);
 assert.match(checked,/does not establish that no scientific evidence exists/);
 assert.match(checked,/Trial eligibility, treatment benefit and clinical decisions have not been assessed/);
});
test('citation denial hides prior counted links but preserves separately authorized question',()=>{
 const s={...base(),questions:[question()]};
 const e={contract:'oi.pg-question-evidence-links/1',patient_id:patientId,case_id:caseId,
  question_id:question().question_id,source_context_state:'current_unreviewed_question',
  source_access_receipt_id:'ACCESS-'+'A'.repeat(32),synthetic:true,model_executed:false,
  content_appraised:false,clinical_approval:false,links:[{status:'available'}]};
 const ready={...s,evidenceFamily:'text',evidenceQuestionId:question().question_id,evidenceLinksPhase:'ready',evidenceLinks:e};
 assert.match(render(ready),/data-testid="second-opinion-citations-counts"/);
 const denied=render({...ready,evidenceLinksPhase:'error'});
 assert.match(denied,/data-testid="second-opinion-citations-unchecked"/);
 assert.doesNotMatch(denied,/data-testid="second-opinion-citations-counts"/);
 assert.match(denied,/Could we discuss fictional marker/);
 assert.doesNotMatch(render({...ready,questionListPhase:'error'}),/data-testid="second-opinion-question-evidence"/);
});

test('second-opinion proposal status distinguishes unread from verified no comparisons',()=>{
 const s={...base(),questions:[question()]};
 assert.match(render(s),/data-testid="second-opinion-proposals-unchecked"/);
 const q=question();
 const packet={contract:'oi.h1-question-evidence/1',patient_id:patientId,case_id:caseId,
  question:q,source_snapshot_sha256:q.source_snapshot_sha256,
  access_receipt_id:'ACCESS-'+'A'.repeat(32),packet_sha256:'e'.repeat(64),
  evidence:[],assessments:[],reports:[],synthetic:true,
  human_review_state:'not_performed',clinical_approval:false,model_executed:false};
 const checked=render({...s,worldModel:{...s.worldModel,snapshot_fingerprint:q.source_snapshot_sha256},
  evidencePhase:'ready',evidencePacket:packet});
 assert.match(checked,/data-testid="second-opinion-proposals-checked"/);
 assert.match(checked,/data-testid="second-opinion-proposals-empty"/);
 assert.doesNotMatch(checked,/data-testid="second-opinion-proposals-unchecked"/);
 assert.match(checked,/not a scientific evidence grade/);
});
test('separately revoked comparison access withholds old counts and keeps saved question',()=>{
 const s={...base(),questions:[question()]},q=question();
 const ev={evidence_id:'EVIDENCE-'+'F'.repeat(32),sha256:'a'.repeat(64),
  rights_sha256:'b'.repeat(64),state:'current',statement:'Synthetic text'};
 const packet={contract:'oi.h1-question-evidence/1',patient_id:patientId,case_id:caseId,
  question:q,source_snapshot_sha256:q.source_snapshot_sha256,
  access_receipt_id:'ACCESS-'+'A'.repeat(32),packet_sha256:'e'.repeat(64),
  evidence:[ev],assessments:[{question_id:q.question_id,evidence_id:ev.evidence_id,
   evidence_sha256:ev.sha256,rights_sha256:ev.rights_sha256,
   source_snapshot_sha256:q.source_snapshot_sha256,preflight_sha256:q.preflight_sha256,
   state:'current_unreviewed',relation:'contradicts'}],
  reports:[],synthetic:true,human_review_state:'not_performed',clinical_approval:false,model_executed:false};
 const ready={...s,worldModel:{...s.worldModel,snapshot_fingerprint:q.source_snapshot_sha256},
  evidencePhase:'ready',evidencePacket:packet};
 assert.match(render(ready),/1 proposed contradiction/);
 const denied=render({...ready,evidencePhase:'error'});
 assert.match(denied,/data-testid="second-opinion-proposals-unchecked"/);
 assert.doesNotMatch(denied,/1 proposed contradiction/);
 assert.match(denied,/Could we discuss fictional marker/);
 assert.doesNotMatch(render({...ready,questionListPhase:'error'}),/data-testid="second-opinion-proposal-readiness"/);
});

test('authored comparisons require an explicit click and are disabled during uncertain writes',()=>{
 const s={...base(),questions:[question()]};
 const initial=render(s);
 assert.match(initial,/data-testid="second-opinion-check-proposals"/);
 assert.match(initial,/Use the button above to request an authorized read here/);
 assert.match(initial,/data-checked="false"/);
 const pending=render({...s,evidenceWritePhase:'unknown'});
 assert.match(pending,/data-testid="second-opinion-check-proposals" disabled=""/);
 assert.doesNotMatch(render({...s,questionListPhase:'error'}),/data-testid="second-opinion-check-proposals"/);
});
