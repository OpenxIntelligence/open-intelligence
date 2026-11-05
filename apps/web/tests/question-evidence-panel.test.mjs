import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

let QuestionEvidencePanel,QuestionEvidenceRecovery;
before(async()=>{
 // Render the actual component with the already-installed compiler and React.
 execFileSync(process.execPath,[resolve('node_modules/typescript/bin/tsc'),'--target','ES2022','--module','ES2022',
  '--moduleResolution','Bundler','--jsx','react-jsx','--strict','--skipLibCheck','--outDir','.test-dist/evidence-ui',
  'src/question-evidence-panel.tsx'],{stdio:'pipe'});
 ({QuestionEvidencePanel,QuestionEvidenceRecovery}=await import(pathToFileURL(resolve('.test-dist/evidence-ui/question-evidence-panel.js')).href));
});
const pid='PAT-EXAMPLE-001',cid='CASE-ALPHA',qid='QUESTION-'+'A'.repeat(32),other='QUESTION-'+'D'.repeat(32);
const source='SRC-'+'B'.repeat(32),hash='a'.repeat(64),metadata='b'.repeat(64);
const question={question_id:qid,patient_id:pid,case_id:cid,question:'Which fictional source detail needs verification?',
 source_id:source,source_line:8,source_sha256:hash,source_version:1,source_snapshot_sha256:hash,
 source_snapshot_contract:'oi.pg-source-world-model/1',preflight_sha256:hash,source_context_state:'current_unreviewed_question'};
const record={citation:'FICT-ENTRY@v1',id:'FICT-ENTRY',version:'v1',source_kind:'fictional',title:'Fictional discussion metadata',
 licence:'original-synthetic',link:'https://example.invalid/fictional/discussion',metadata_sha256:metadata,
 availability:'metadata_only',rights_status:'granted'};
const scope={patient_id:pid,case_id:cid,question_id:qid,source_context_state:'current_unreviewed_question',
 source_access_receipt_id:'ACCESS-'+'C'.repeat(32),synthetic:true,model_executed:false,content_appraised:false,clinical_approval:false};
const state=(overrides={})=>({phase:'ready',connected:true,patient:{patient_id:pid},questionsCaseId:cid,questionListPhase:'ready',
 worldPhase:'ready',worldModel:{patient_id:pid,case_id:cid,snapshot_fingerprint:hash,
 observations:[{source_id:source,source_line:8,source_sha256:hash,document_version:1}]},
 evidenceQuestionId:qid,evidenceSearch:{contract:'oi.pg-question-evidence-search/1',...scope,query:'fictional',records:[record]},
 evidenceSearchPhase:'ready',evidenceSearchMessage:'Fictional metadata found.',evidenceLinks:null,evidenceLinksPhase:'idle',evidenceLinksMessage:'',
 evidenceLinkIntent:null,evidenceLinkReceipt:null,evidenceLinkPhase:'idle',evidenceLinkMessage:'',...overrides});
const render=(snapshot,selected=question)=>renderToStaticMarkup(createElement(QuestionEvidencePanel,{state:snapshot,question:selected,session:{},busy:false}));

test('evidence inspection renders exact citation, metadata rights and fixture URL inside a saved-question panel',()=>{
 const html=render(state());
 for(const expected of [record.citation,record.id,record.version,record.licence,record.metadata_sha256])assert.ok(html.includes(expected));
 assert.match(html,/<details[^>]*data-testid="evidence-result"/);
 assert.ok(html.includes('href="https://example.invalid/fictional/discussion"'));
 assert.match(html,/rel="[^"]*noopener[^"]*noreferrer/);
 assert.match(html,/data-testid="evidence-query"/);assert.match(html,/data-testid="evidence-save"/);
 assert.match(html,/fictional/i);assert.match(html,/metadata only/i);assert.match(html,/not appraised/i);
});

test('stale source context disables the save control while retaining metadata inspection',()=>{
 const html=render(state({evidenceSearch:{contract:'oi.pg-question-evidence-search/1',...scope,
  source_context_state:'source_reassessment_required',query:'fictional',records:[record]}}));
 assert.ok(html.includes(record.citation));assert.match(html,/<button[^>]*data-testid="evidence-save"[^>]*disabled/);
 assert.match(html,/reassessment/i);
});

test('restricted citation history shows status and immutable identifiers without stale metadata',()=>{
 const html=render(state({evidenceSearch:null,evidenceSearchPhase:'idle',evidenceLinksPhase:'ready',
  evidenceLinks:{contract:'oi.pg-question-evidence-links/1',...scope,links:[{
   link_id:'EVIDENCE-LINK-'+'E'.repeat(32),citation:record.citation,metadata_sha256:metadata,
   created_at:'2026-11-03T10:00:00Z',actor_label:'ACTOR-FICTIONAL',status:'rights_restricted',record:null}]}}));
 assert.ok(html.includes(record.citation));assert.match(html,/restricted/i);
 assert.ok(!html.includes(record.title));assert.ok(!html.includes(record.link));assert.ok(!html.includes('data-testid="evidence-save"'));
});

test('another question cannot display the selected question metadata',()=>{
 const html=render(state(),{...question,question_id:other});
 assert.ok(!html.includes(record.title));assert.ok(!html.includes(record.link));assert.ok(!html.includes(record.citation));
});

test('uncertain save recovery remains explicitly bound to its question and warns that abandonment is not cancellation',()=>{
 const html=render(state({evidenceQuestionId:other,evidenceSearch:null,evidenceSearchPhase:'idle',evidenceLinkPhase:'unknown',
  evidenceLinkIntent:{patient_id:pid,case_id:cid,question_id:qid,body:{citation:record.citation,
   expected_metadata_sha256:metadata,request_key:'fictional-request-key'}}}));
 assert.ok(html.includes(record.citation));assert.match(html,/data-testid="evidence-retry"/);
 assert.match(html,/data-testid="evidence-abandon"/);assert.match(html,/does not cancel|does not undo/i);
});

test('outside-list recovery keeps retry progress and the original receipt visible after same-case refresh',()=>{
 const intent={patient_id:pid,case_id:cid,question_id:qid,body:{citation:record.citation,
  expected_metadata_sha256:metadata,request_key:'fictional-request-key'}};
 const renderRecovery=snapshot=>renderToStaticMarkup(createElement(QuestionEvidenceRecovery,{state:snapshot,session:{},busy:false}));
 const saving=renderRecovery(state({questions:null,questionsCaseId:null,evidenceSearch:null,evidenceSearchPhase:'idle',
  evidenceLinkIntent:intent,evidenceLinkPhase:'saving',evidenceLinkMessage:'Recovering the exact earlier citation save under current permissions…'}));
 assert.ok(saving.includes(qid));assert.match(saving,/Recovering the exact/);assert.match(saving,/data-testid="evidence-link-status"/);
 assert.ok(!saving.includes('data-testid="evidence-retry"'));
 const saved=renderRecovery(state({questions:null,questionsCaseId:null,evidenceSearch:null,evidenceSearchPhase:'idle',
  evidenceLinkPhase:'saved',evidenceLinkReceipt:{link_id:'EVIDENCE-LINK-'+'E'.repeat(32),citation:record.citation,
   metadata_sha256:metadata,duplicate:true},evidenceLinkMessage:'Original citation receipt recovered.',
  evidenceLinksPhase:'error',evidenceLinksMessage:'Refresh the authorized case and saved questions before reading citation links.'}));
 assert.ok(saved.includes(qid));assert.ok(saved.includes(record.citation));assert.match(saved,/data-testid="evidence-link-receipt"/);
 assert.match(saved,/Refresh the authorized case/);
 const failed=renderRecovery(state({questions:null,questionsCaseId:null,evidenceSearch:null,evidenceLinkPhase:'error',
  evidenceLinkMessage:'The citation save was refused by current permission.'}));
 assert.ok(failed.includes(qid));assert.match(failed,/save was refused/);
});

test('rendering treats titles as text and refuses unsafe anchor destinations',()=>{
 const html=render(state({evidenceSearch:{contract:'oi.pg-question-evidence-search/1',...scope,query:'fictional',
  records:[{...record,title:'Fictional <script>alert(1)</script>',link:'javascript:alert(1)'}]}}));
 assert.ok(!html.includes('<script>'));assert.ok(!html.includes('javascript:'));
 assert.ok(html.includes('&lt;script&gt;'));
});
