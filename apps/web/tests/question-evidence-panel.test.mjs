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
 assert.match(html,/<input[^>]*data-testid="evidence-doi-input"[^>]*disabled/);
 assert.match(html,/<input[^>]*data-testid="evidence-doi-acknowledge"[^>]*disabled/);
 assert.doesNotMatch(html,/<input[^>]*data-testid="evidence-query"[^>]*disabled/);
 assert.match(html,/before looking up a DOI or saving another link/);
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

const publicDoi='10.5555/oi-synthetic-001',projection='e'.repeat(64);
const crossref={...record,source_kind:'crossref',id:publicDoi,version:projection,citation:publicDoi+'@'+projection,
 title:'Authored public metadata fixture <script>hostile()</script>',
 licence:'Crossref factual bibliographic metadata; article rights not granted',link:'https://doi.org/10.5555%2Foi-synthetic-001',
 bibliography:{doi:publicDoi,journal:'Fictional journal',year:2025,publication_type:'journal-article',authors:['Fictional Author'],
  retrieved_at:'2026-11-03T12:34:56+00:00',record_url:'https://api.crossref.org/works/10.5555%2Foi-synthetic-001',
  rights_basis:'https://www.crossref.org/documentation/retrieve-metadata/',
  access_policy:'https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/',
  adapter_version:'oi.crossref-metadata/1',projection_sha256:projection,acquisition_mode:'protocol_fixture'}};
test('public DOI entry starts empty with explicit acknowledgement and disabled submission',()=>{
 const html=render(state());
 assert.match(html,/<input[^>]*data-testid="evidence-doi-input"[^>]*value=""/);
 assert.match(html,/data-testid="evidence-doi-acknowledge"/);
 assert.match(html,/<button[^>]*data-testid="evidence-doi-lookup"[^>]*disabled/);
 assert.match(html,/Only the DOI|only the DOI/);assert.match(html,/disabled by default/i);
});

test('public DOI presentation identifies Crossref and retrieval snapshot without labelling the publication fictional',()=>{
 const html=render(state({evidenceSearch:{contract:'oi.pg-question-evidence-search/1',...scope,query:publicDoi,records:[crossref]}}));
 assert.match(html,/data-testid="evidence-bibliography"/);assert.match(html,/data-testid="evidence-doi-link"/);
 assert.match(html,/href="https:\/\/doi.org\/10.5555%2Foi-synthetic-001"/);
 assert.match(html,/First retrieved|first retrieved/);assert.ok(html.includes('2025'));
 assert.ok(html.includes(crossref.bibliography.retrieved_at));assert.ok(html.includes(crossref.bibliography.journal));
 assert.ok(html.includes(crossref.bibliography.authors[0]));assert.match(html,/metadata only/i);
 assert.ok(!html.includes('Metadata only · fictional fixture'));assert.ok(!html.includes('Granted for this fixture'));
 assert.match(html,/protocol fixture/i);assert.match(html,/no live provider request/i);
 assert.ok(!html.includes('<script>'));assert.ok(html.includes('&lt;script&gt;'));
});

test('public DOI panel refuses a forged DOI destination even when given an unvalidated component prop',()=>{
 const html=render(state({evidenceSearch:{contract:'oi.pg-question-evidence-search/1',...scope,query:publicDoi,
  records:[{...crossref,link:'https://evil.test/article'}]}}));
 assert.ok(!html.includes('href="https://evil.test/'));assert.ok(!html.includes('data-testid="evidence-doi-link"'));
});
