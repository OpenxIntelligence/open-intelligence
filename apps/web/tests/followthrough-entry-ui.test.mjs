import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'vite';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {laboratoryFollowthroughEntry} from '../.test-dist/followthrough-view.js';

let FollowthroughPanel;
before(async()=>{
 await build({configFile:false,logLevel:'silent',build:{ssr:resolve('src/followthrough-panel.tsx'),
  outDir:'.test-dist/followthrough-entry-ui',emptyOutDir:true,
  rollupOptions:{output:{entryFileNames:'panel.mjs'}}}});
 ({FollowthroughPanel}=await import(pathToFileURL(resolve('.test-dist/followthrough-entry-ui/panel.mjs')).href));
});

function fixture(){
 const scope={patient_id:'PAT-HANDOFF',case_id:'CASE-HANDOFF'};
 const origin={source_id:'SRC-'+'A'.repeat(32),source_version:1,source_sha256:'a'.repeat(64),
  source_snapshot_contract:'oi.pg-source-world-model/1',source_snapshot_sha256:'b'.repeat(64),
  preflight_sha256:'c'.repeat(64),source_context_state:'current_unreviewed_question',observation_reference:'Observation/FICTIONAL-ZERO'};
 const question={...scope,...origin,question_id:'QUESTION-'+'B'.repeat(32)};
 const task={...scope,...origin,question_id:question.question_id,task_id:'TASK-'+'C'.repeat(32),source_line:null,
  title:'Inspect fictional zero & <source>',detail:'Bring the original report.',owner_label:'Fictional coordinator',
  due_date:null,review_trigger:'At the next discussion',status:'acknowledged',revision:3,
  needs_recheck:false,is_overdue:false,is_due_soon:false,history:[]};
 const other={...task,task_id:'TASK-'+'D'.repeat(32),question_id:'QUESTION-'+'E'.repeat(32),title:'Unrelated task title'};
 const state={...new RegistrySession().snapshot(),connected:true,phase:'ready',
  patient:{patient_id:scope.patient_id,status:'active'},cases:[{...scope,status:'active'}],
  worldPhase:'ready',worldModel:{...scope,snapshot_fingerprint:origin.source_snapshot_sha256},
  labQuestionListPhase:'ready',labQuestionHistory:{...scope,checked_source_snapshot_sha256:origin.source_snapshot_sha256,questions:[question]},
  followthroughPhase:'ready',followthroughCaseId:scope.case_id,
  followthrough:{...scope,contract:'oi.pg-question-followthrough/2',access_receipt_id:'ACCESS-'+'F'.repeat(32),
   evaluated_on:'2026-11-06',tasks:[other,task]}};
 const entry=laboratoryFollowthroughEntry(state,question,task.task_id);
 return {state,entry,task};
}
const render=(state,entry)=>renderToStaticMarkup(createElement(FollowthroughPanel,{
 state,entry,session:new RegistrySession(),busy:false,onClearEntry:()=>{},
}));

test('targeted task entry withholds stale and unrelated task bodies until a fresh matching read',()=>{
 const {state,entry}=fixture();
 assert.ok(entry);
 for(const current of [state,{...state,followthroughPhase:'loading'},{...state,followthroughPhase:'error'},
  {...state,followthrough:{...state.followthrough,access_receipt_id:'ACCESS-'+'9'.repeat(32),tasks:[state.followthrough.tasks[0]]}}]){
  const html=render(current,entry);
  assert.doesNotMatch(html,/data-testid="followthrough-task"|Unrelated task title|Inspect fictional zero/);
  assert.match(html,/data-testid="followthrough-entry-status"/);
  assert.doesNotMatch(html,/No recorded work is visible/);
 }
});

test('fresh task entry retains the canonical history and action controls with no other task substituted',()=>{
 const {state,entry,task}=fixture();
 state.followthrough={...state.followthrough,access_receipt_id:'ACCESS-'+'9'.repeat(32)};
 const html=render(state,entry);
 assert.equal((html.match(/data-testid="followthrough-task"/g)||[]).length,1);
 assert.match(html,/Inspect fictional zero &amp; &lt;source&gt;/);
 assert.doesNotMatch(html,/Unrelated task title|data-testid="followthrough-filter-all"/);
 assert.match(html,/data-testid="followthrough-history"/);
 assert.match(html,/data-testid="followthrough-complete"/);
 assert.ok(html.includes('id="followthrough-task-'+task.task_id+'" tabindex="-1"'));
 assert.match(html,/Show all follow-up work/);
 const all=render(state,null);
 assert.equal((all.match(/data-testid="followthrough-task"/g)||[]).length,2);
 assert.match(all,/Unrelated task title/);
});
