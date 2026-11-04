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
const patient='PAT-FICTIONAL-LAB',caseId='CASE-FICTIONAL-LAB',sourceId='SRC-'+'A'.repeat(32),hash='b'.repeat(64);
function projection(){
 const src={source_id:sourceId,document_id:'FICTIONAL-REPORT-A',version:1,sha256:hash,kind:'laboratory',event_date:'2026-04-03',issued_at:'2026-04-04',received_at:'2026-11-04T10:00:00Z',specimen_id:'FICTIONAL-SPECIMEN-A',state:'current',supersedes_id:null};
 const observations=['0','-0.25',null].map((value,i)=>({source_id:sourceId,document_id:src.document_id,document_version:1,source_sha256:hash,observation_reference:'Observation/FICTIONAL-OBS-'+i,loinc_code:'777-3',effective_at:'2026-04-03T09:0'+i+':00-04:00',issued_at:'2026-04-04T12:00:00Z',specimen_reference:'Specimen/FICTIONAL-SPECIMEN-A',specimen_type_text:'Fictional <script>plasma</script>',specimen_collected_at:'2026-04-03T09:00:00-04:00',report_reference:'DiagnosticReport/FICTIONAL-REPORT-A',status:value===null?'reported_absent':'reported_value',value_text:value,unit_code:value===null?null:'10*9/L',absent_reason:value===null?'not-performed':null,source_reported:true,review_state:'not_established',clinical_review:'not_performed',clinical_meaning:null}));
 const timeline=observations.map(o=>({source_id:o.source_id,observation_reference:o.observation_reference,loinc_code:o.loinc_code,effective_at:o.effective_at,issued_at:o.issued_at,specimen_reference:o.specimen_reference,status:o.status,clinical_interpretation:'not_performed'})).reverse();
 return {contract:'oi.pg-source-world-model/1',patient_id:patient,case_id:caseId,access_receipt_id:'ACCESS-'+'C'.repeat(32),synthetic:true,authority:'source_report_only_unreviewed',clinical_interpretation:false,research_review_invalidation_integrated:false,composer_execution_authorized:false,snapshot_fingerprint:'d'.repeat(64),as_of_received_at:src.received_at,summary:{current_sources:1,historical_sources:0,current_observations:3,current_laboratory_observations:3,unresolved_observations:1,source_disagreements:0},current_sources:[src],history:[],observations:[],laboratory_observations:observations,laboratory_timeline:timeline,unresolved_refs:[],conflicts:[],limitations:['Independently fictional; source-reported only.']};
}
const render=model=>renderToStaticMarkup(createElement(WorldModelView,{session:{},state:{patient:{patient_id:patient},cases:[],worldPhase:'ready',recordsPhase:'ready',worldMessage:'Fresh read',worldModel:model},busy:false,onOverview(){}}));
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
 const tree=WorldModelView({session:{},state:{patient:{patient_id:patient},cases:[],worldPhase:'ready',recordsPhase:'ready',worldMessage:'Fresh read',worldModel:model},busy:false,onOverview(){},onRecords:id=>calls.push(id)});
 const buttons=nodes(tree).filter(n=>n.props?.['data-testid']==='world-laboratory-records');
 assert.equal(buttons.length,3);assert.equal(calls.length,0);
 buttons[0].props.onClick();assert.deepEqual(calls,['CASE-FICTIONAL-LAB']);
 assert.equal(buttons[0].props.type,'button');
});
test('laboratory Records actions are unavailable while the scope is loading or busy',()=>{
 for(const state of [{worldPhase:'loading',recordsPhase:'ready',busy:false},{worldPhase:'ready',recordsPhase:'loading-original',busy:false},{worldPhase:'ready',recordsPhase:'ready',busy:true}]){
 const tree=WorldModelView({session:{},state:{patient:{patient_id:patient},cases:[],worldModel:parseSourceWorldModel(projection(),patient,caseId),...state},busy:state.busy,onOverview(){},onRecords(){}});
 const buttons=nodes(tree).filter(n=>n.props?.['data-testid']==='world-laboratory-records');assert.equal(buttons.length,3);assert.ok(buttons.every(b=>b.props.disabled));
 }
});
