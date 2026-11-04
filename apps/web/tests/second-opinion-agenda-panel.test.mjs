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
const render=state=>renderToStaticMarkup(createElement(SecondOpinionPreparation,{state,onNavigate:()=>{},onResumeQuestion:()=>{}}));

test('saved agenda rows offer question-specific inspection and keep unsent passage recovery distinct',()=>{
 const saved=question(),draft={...question(),question_id:'QUESTION-'+'C'.repeat(32),question:'Another fictional question'};
 const state={...base(),questions:[saved,draft],manualPassageDraftQuestionIds:[draft.question_id]};
 const html=render(state);
 assert.equal((html.match(/data-testid="second-opinion-open-question"/g)||[]).length,1);
 assert.equal((html.match(/data-testid="second-opinion-resume-passages"/g)||[]).length,1);
 assert.match(html,/aria-label="Inspect records and reports for: Could we discuss fictional marker &amp; &lt;unverified note&gt;\?"/);
 for(const patch of [{questionListPhase:'loading'},{questionListPhase:'error'},
  {questionsCaseId:'CASE-OTHER'},{connected:false}]){
  assert.doesNotMatch(render({...state,...patch}),/second-opinion-open-question|second-opinion-resume-passages/);
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
