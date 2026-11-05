import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'vite';
import {parseSourceWorldModel} from '../.test-dist/source-world-model.js';

let WorldModelView;
before(async()=>{
 await build({configFile:false,logLevel:'silent',build:{ssr:resolve('src/world-model-view.tsx'),outDir:'.test-dist/laboratory-world-ui',emptyOutDir:true,rollupOptions:{output:{entryFileNames:'world-model-view.mjs'}}}});
 ({WorldModelView}=await import(pathToFileURL(resolve('.test-dist/laboratory-world-ui/world-model-view.mjs')).href));
});
import {patient,caseId,sourceId,hash,projection} from './laboratory-projection-fixture.mjs';
const idleQuestionSave = {questionSavePhase:'idle', questionSaveMessage:''};
const render=model=>renderToStaticMarkup(createElement(WorldModelView,{session:{},state:{...idleQuestionSave,patient:{patient_id:patient},cases:[],worldPhase:'ready',recordsPhase:'ready',worldMessage:'Fresh read',worldModel:model},busy:false,onOverview(){}}));
test('laboratory-only projection renders zero, negative and absent results with exact unreviewed provenance',()=>{
 const html=render(parseSourceWorldModel(projection(),patient,caseId));
 assert.equal((html.match(/data-testid="world-laboratory-observation"/g)||[]).length,3);
 assert.match(html,/data-testid="world-laboratory-count">3/);
 assert.match(html,/<strong>0<\/strong>/);assert.match(html,/<strong>-0\.25<\/strong>/);
 assert.match(html,/Result absent · source reason: <strong>not-performed<\/strong>/);
 for(const text of ['777-3','10*9/L',sourceId,hash,'Specimen/FICTIONAL-SPECIMEN-A','DiagnosticReport/FICTIONAL-REPORT-A','2026-04-04T12:00:00Z','Source-reported, not clinically reviewed'])assert.ok(html.includes(text));
 assert.ok(html.includes('&lt;script&gt;plasma&lt;/script&gt;'));assert.ok(!html.includes('<script>plasma'));
 assert.ok(!html.includes('No source-reported observations are available.'));
});
test('result order follows the validated server chronology without calculating a trend',()=>{
 const html=render(parseSourceWorldModel(projection(),patient,caseId));
 assert.ok(html.indexOf('Observation/FICTIONAL-OBS-2')<html.indexOf('Observation/FICTIONAL-OBS-1'));
 assert.ok(html.indexOf('Observation/FICTIONAL-OBS-1')<html.indexOf('Observation/FICTIONAL-OBS-0'));
 assert.ok(!html.includes('improving'));assert.ok(!html.includes('normal range'));
});
test('clearing the current projection removes all previously displayed lab values and locators',()=>{
 const html=render(null);assert.ok(!html.includes('world-laboratory-observation'));assert.ok(!html.includes('FICTIONAL-OBS-'));
});

function nodes(value){
 if(!value||typeof value!=='object')return [];
 if(Array.isArray(value))return value.flatMap(nodes);
 return [value,...nodes(value.props?.children)];
}
test('laboratory provenance opens the exact projected case through the Records callback',()=>{
 const calls=[],model=parseSourceWorldModel(projection(),patient,caseId);
 const tree=WorldModelView({session:{},state:{...idleQuestionSave,patient:{patient_id:patient},cases:[],worldPhase:'ready',recordsPhase:'ready',worldMessage:'Fresh read',worldModel:model},busy:false,onOverview(){},onRecords:id=>calls.push(id)});
 const buttons=nodes(tree).filter(n=>n.props?.['data-testid']==='world-laboratory-records');
 assert.equal(buttons.length,3);assert.equal(calls.length,0);
 buttons[0].props.onClick();assert.deepEqual(calls,['CASE-FICTIONAL-LAB']);
 assert.equal(buttons[0].props.type,'button');
});
test('laboratory Records actions are unavailable while the scope is loading or busy',()=>{
 for(const state of [{worldPhase:'loading',recordsPhase:'ready',busy:false},{worldPhase:'ready',recordsPhase:'loading-original',busy:false},{worldPhase:'ready',recordsPhase:'ready',busy:true}]){
 const tree=WorldModelView({session:{},state:{...idleQuestionSave,patient:{patient_id:patient},cases:[],worldModel:parseSourceWorldModel(projection(),patient,caseId),...state},busy:state.busy,onOverview(){},onRecords(){}});
 const buttons=nodes(tree).filter(n=>n.props?.['data-testid']==='world-laboratory-records');assert.equal(buttons.length,3);assert.ok(buttons.every(b=>b.props.disabled));
 }
});

test('saved laboratory question shows historical provenance and reassessment without displaying a replacement value',()=>{
 const model=parseSourceWorldModel(projection(),patient,caseId),oldSource='SRC-'+'E'.repeat(32),prior='e'.repeat(64);
 const row={question_id:'QUESTION-'+'C'.repeat(32),question:'What changed since the original report?',source_id:oldSource,source_version:1,source_sha256:prior,observation_reference:'Observation/FICTIONAL-OLD',source_snapshot_sha256:'a'.repeat(64),preflight_sha256:'b'.repeat(64),source_context_state:'source_reassessment_required'};
 const historicalOnly={...model,laboratory_observations:[],laboratory_timeline:[]};
 const html=renderToStaticMarkup(createElement(WorldModelView,{session:{},state:{...idleQuestionSave,patient:{patient_id:patient},cases:[],worldPhase:'ready',recordsPhase:'ready',worldMessage:'Fresh read',worldModel:historicalOnly,labQuestionHistory:{questions:[row],access_receipt_id:'ACCESS-'+'E'.repeat(32)},labQuestionListPhase:'ready',labQuestionWritePhase:'idle'},onOverview(){},busy:false}));
 assert.ok(html.includes('data-testid="lab-questions-reopen"'));assert.ok(!html.includes('data-testid="world-laboratory-results"'));
 const saved=html.split('data-testid="lab-saved-question"')[1].split('</li>')[0];
 for(const value of [row.question,'Needs reassessment',row.observation_reference,'source version 1',oldSource,prior,row.question_id])assert.ok(saved.includes(value),value);
 assert.ok(!saved.includes('10*9/L'));assert.ok(!saved.includes('write a source-linked question'));assert.ok(!saved.includes('source line'));
});
