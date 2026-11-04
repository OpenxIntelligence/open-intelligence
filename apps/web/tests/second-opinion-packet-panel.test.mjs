import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'vite';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {ready,transportFor,response,sourceId,questionId} from './authored-evidence-fixtures.mjs';
let Panel;
before(async()=>{
 await build({configFile:false,logLevel:'silent',build:{ssr:resolve('src/second-opinion-packet-panel.tsx'),outDir:'.test-dist/packet-ui',emptyOutDir:true,
  rollupOptions:{output:{entryFileNames:'packet-ui.mjs'}}}});
 ({SecondOpinionPacketPanel:Panel}=await import(pathToFileURL(resolve('.test-dist/packet-ui/packet-ui.mjs')).href));
});
const render=(session,state=session.snapshot())=>renderToStaticMarkup(createElement(Panel,{session,state,onInvestigations:()=>{}}));
test('packet editor shows exact source and saved question with no preselected material',async()=>{
 const session=new RegistrySession(transportFor(()=>response({})));await ready(session);
 const html=render(session);
 assert.match(html,/Save preparation packet/);assert.match(html,new RegExp(sourceId));assert.match(html,new RegExp(questionId));
 assert.doesNotMatch(html,/checked=""/);assert.doesNotMatch(html,/data-testid="packet-empty"/);
 assert.match(html,/no referral, recipient verification, record transmission or clinical approval/);
});
test('packet title is escaped and a pending write disables authoring',async()=>{
 const session=new RegistrySession(transportFor(()=>response({})));await ready(session);
 session.editSecondOpinionPacket({title:'<img src=x onerror=alert(1)>',source_ids:[sourceId],question_ids:[questionId]});
 const html=render(session,{...session.snapshot(),secondOpinionWritePhase:'unknown'});
 assert.match(html,/&lt;img/);assert.doesNotMatch(html,/<img/);assert.match(html,/<fieldset disabled=""/);
 assert.match(html,/Recover exact save receipt/);assert.match(html,/does not undo a saved packet/);
});
test('disconnect hides packet workspace and an unavailable source scope hides retained draft input',async()=>{
 const session=new RegistrySession(transportFor(()=>response({})));await ready(session);
 session.editSecondOpinionPacket({title:'Private fictional packet selection'});
 const html=render(session,{...session.snapshot(),worldPhase:'loading'});
 assert.doesNotMatch(html,/Private fictional packet selection/);
 session.disconnect();assert.equal(render(session),'');
});
