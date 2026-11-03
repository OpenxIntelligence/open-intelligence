import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'vite';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {ready,transportFor,response,packet,questionId,patientId,caseId} from './authored-evidence-fixtures.mjs';

let SourceQuestionPanel;
before(async()=>{
 // Bundle the real composed component using the already-pinned application
 // builder. This exercises child controls without adding a DOM/test dependency.
 await build({configFile:false,logLevel:'silent',build:{ssr:resolve('src/source-question-panel.tsx'),
  outDir:'.test-dist/evidence-continuity-ui',emptyOutDir:true,
  rollupOptions:{output:{entryFileNames:'source-question-panel.mjs'}}}});
 ({SourceQuestionPanel}=await import(pathToFileURL(resolve('.test-dist/evidence-continuity-ui/source-question-panel.mjs')).href));
});

test('a canonical saved question exposes both citation discovery and authored comparisons without replacing follow-up',async()=>{
 const s=new RegistrySession(transportFor(()=>response(packet())));await ready(s);
 const html=renderToStaticMarkup(createElement(SourceQuestionPanel,{state:s.snapshot(),session:s,busy:false}));
 assert.ok(html.includes(questionId));
 assert.match(html,/Find evidence citations for this question/,'source-qualified metadata discovery remains reachable');
 assert.match(html,/Inspect evidence and human comparisons/,'the same question must also open authored evidence and preserved reports');
 assert.match(html,/data-testid="followthrough-open-create"/,'existing question-owned follow-up remains reachable');
 const ids=Array.from(html.matchAll(/data-testid="([^"]+)"/g),match=>match[1]);
 const openIds=ids.filter(id=>/evidence.*open/.test(id));
 assert.equal(new Set(openIds).size,openIds.length,'metadata and authored controls need distinct targets');
});

test('same-question evidence and follow-up attention coexist, with denied work distinct from an empty read',async()=>{
 let denied=false,writes=0;
 const fallback=transportFor(()=>response(packet()));
 const s=new RegistrySession((url,init)=>{
  if(init.method==='POST')writes++;
  if(url.endsWith('/followthrough'))return denied?response({detail:'Denied'},403):response({
   contract:'oi.pg-question-followthrough/1',patient_id:patientId,case_id:caseId,
   access_receipt_id:'ACCESS-'+'D'.repeat(32),evaluated_on:'2026-11-03',tasks:[],
   synthetic:true,clinical_approval:false,external_notification_sent:false});
  return fallback(url,init);
 });
 await ready(s);await s.loadQuestionEvidence(questionId);await s.loadFollowthrough(caseId);
 const render=()=>renderToStaticMarkup(createElement(SourceQuestionPanel,{state:s.snapshot(),session:s,busy:false}));
 const html=render();
 assert.equal(s.snapshot().evidencePhase,'ready');
 assert.match(html,/Fictional comparison manuscript/);
 assert.match(html,/data-testid="followthrough-attention"/,'combined evidence workspace must expose the existing follow-up filters');
 assert.match(html,/All work \(0\)/,'an authorized empty task read has a known zero');
 denied=true;await s.loadFollowthrough(caseId);
 const deniedHtml=render();
 assert.doesNotMatch(deniedHtml,/data-testid="followthrough-attention"/,'denied work cannot display old counts');
 assert.match(deniedHtml,/Fictional comparison manuscript/,'independent task denial must not replace the evidence owner');
 assert.equal(writes,0,'reading and presentation do not create tasks or evidence');
});
