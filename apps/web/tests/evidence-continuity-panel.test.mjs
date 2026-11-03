import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'vite';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {ready,transportFor,response,packet,questionId} from './authored-evidence-fixtures.mjs';

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
