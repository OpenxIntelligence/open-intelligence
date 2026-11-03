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
const render=state=>renderToStaticMarkup(createElement(SecondOpinionPreparation,{state,onNavigate:()=>{}}));

test('agenda renders literal user-authored questions as escaped text, provenance and review status',()=>{
 const html=render({...base(),questions:[question('source_reassessment_required')]});
 assert.match(html,/data-testid="second-opinion-agenda-item"/);
 assert.match(html,/data-source-context="source_reassessment_required"/);
 assert.match(html,/Could we discuss fictional marker &amp; &lt;unverified note&gt;\?/);
 assert.doesNotMatch(html,/<unverified note>/);
 assert.match(html,/Original source version 2, line 14/);
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
