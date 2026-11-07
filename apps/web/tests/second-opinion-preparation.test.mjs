import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
const {secondOpinionPreparation}=await import('../.test-dist/second-opinion-preparation.js');

const base=()=>({...new RegistrySession().snapshot(),connected:true,phase:'ready',
 patient:{patient_id:'PAT-ONE',origin_org:'ORG-ONE',created_at:'2026-11-03T10:00:00Z',status:'active',revision:1},
 cases:[{patient_id:'PAT-ONE',case_id:'CASE-ONE',status:'active'}],
 worldPhase:'ready',worldModel:{patient_id:'PAT-ONE',case_id:'CASE-ONE',snapshot_fingerprint:'v1'},
 questionsCaseId:'CASE-ONE',questionsAccessReceiptId:'ACCESS-'+'A'.repeat(32),questionListPhase:'ready',questions:[]});
const sourceIndex=(sources=[])=>({contract:'oi.synthetic-original-sources/1',patient_id:'PAT-ONE',case_id:'CASE-ONE',
 access_receipt_id:'ACCESS-'+'B'.repeat(32),sources,source_reported_assertions:[],synthetic:true,
 clinical_interpretation:false,research_review_invalidation_integrated:false});
const source=(state='current',n=1)=>({source_id:'SRC-'+String(n).padStart(32,'0'),document_id:'DOC-'+n,version:n,
 sha256:'a'.repeat(64),kind:'clinical',event_date:'2026-11-01',issued_at:'2026-11-01',
 received_at:'2026-11-01T10:00:00Z',specimen_id:null,state,supersedes_id:null});
const question=sourceState=>({question_id:'QUESTION-'+'C'.repeat(32),patient_id:'PAT-ONE',case_id:'CASE-ONE',
 question:'What fictional finding should be prepared for discussion?',source_id:'SRC-'+String(1).padStart(32,'0'),
 source_line:1,source_sha256:'a'.repeat(64),source_version:1,source_snapshot_sha256:'b'.repeat(64),
 source_snapshot_contract:'oi.pg-source-world-model/1',preflight_sha256:'c'.repeat(64),
 created_at:'2026-11-03T10:00:00Z',source_context_state:sourceState,human_review_state:'not_submitted',
 clinical_approval:false,model_executed:false});

test('second-opinion preparation is unavailable without an authorized selected case',()=>{
 assert.equal(secondOpinionPreparation(new RegistrySession().snapshot()),null);
 assert.equal(secondOpinionPreparation({...base(),worldPhase:'error'}),null);
});

test('unchecked records or questions are never presented as complete',()=>{
 assert.equal(secondOpinionPreparation(base()).state,'needs_check');
 assert.equal(secondOpinionPreparation({...base(),recordsPhase:'ready',sourceIndex:sourceIndex([source()]),questions:null}).state,'needs_check');
});

test('current records without a current question require a focused question',()=>{
 const view=secondOpinionPreparation({...base(),recordsPhase:'ready',sourceIndex:sourceIndex([source()])});
 assert.equal(view.state,'needs_question');assert.deepEqual(view.records,{current:1,historical:0});
});

test('source reassessment blocks current preparation even when another question is current',()=>{
 const view=secondOpinionPreparation({...base(),recordsPhase:'ready',sourceIndex:sourceIndex([source()]),
  questions:[question('current_unreviewed_question'),{...question('source_reassessment_required'),question_id:'QUESTION-'+'D'.repeat(32)}]});
 assert.equal(view.state,'needs_reassessment');assert.deepEqual(view.questions,{current:1,reassessment:1});
});

test('organized inputs remain preparation only and coordination is descriptive',()=>{
 const view=secondOpinionPreparation({...base(),recordsPhase:'ready',sourceIndex:sourceIndex([source(),source('superseded',2)]),
  questions:[question('current_unreviewed_question')],followthroughPhase:'ready',followthroughCaseId:'CASE-ONE',
  followthrough:{contract:'oi.pg-question-followthrough/1',patient_id:'PAT-ONE',case_id:'CASE-ONE',
   access_receipt_id:'ACCESS-'+'E'.repeat(32),evaluated_on:'2026-11-03',synthetic:true,clinical_approval:false,
   external_notification_sent:false,tasks:[]}});
 assert.equal(view.state,'inputs_prepared');assert.deepEqual(view.records,{current:1,historical:1});
 assert.deepEqual(view.coordination,{open:0,assigned:0,sourceChanged:0});
});

const labModel=()=>({...base().worldModel,current_sources:[{source_id:'SRC-LAB',version:1,
 sha256:'a'.repeat(64),kind:'laboratory',state:'current'}],history:[],
 laboratory_observations:[{source_id:'SRC-LAB',observation_reference:'Observation/ROW-1'}]});
const labHistory=(status='current_unreviewed_question')=>({
 patient_id:'PAT-ONE',case_id:'CASE-ONE',checked_source_snapshot_sha256:'v1',
 access_receipt_id:'ACCESS-'+'D'.repeat(32),questions:[{
 question_id:'QUESTION-'+'F'.repeat(32),source_id:'SRC-LAB',source_version:1,
 source_sha256:'a'.repeat(64),observation_reference:'Observation/ROW-1',
 source_context_state:status}],
});

test('second-opinion agenda does not claim no saved questions when only laboratory questions exist',()=>{
 const view=secondOpinionPreparation({...base(),worldModel:labModel(),recordsPhase:'ready',
  sourceIndex:sourceIndex([source()]),labQuestionListPhase:'ready',labQuestionHistory:labHistory()});
 assert.deepEqual(view.questions,{current:0,reassessment:0});
 assert.deepEqual(view.laboratoryQuestions,{current:1,reassessment:0});
 assert.equal(view.state,'needs_laboratory_review');
 assert.equal(view.agenda.total,0,'a text-only agenda must not fabricate a source line');
});

test('source-amended laboratory question blocks an all-current second-opinion status',()=>{
 const view=secondOpinionPreparation({...base(),worldModel:labModel(),recordsPhase:'ready',
  sourceIndex:sourceIndex([source()]),questions:[question('current_unreviewed_question')],
  labQuestionListPhase:'ready',labQuestionHistory:labHistory('source_reassessment_required')});
 assert.equal(view.state,'needs_reassessment');
 assert.deepEqual(view.laboratoryQuestions,{current:0,reassessment:1});
});

test('a current text question does not conceal an unreviewed laboratory question in second-opinion readiness',()=>{
 const view=secondOpinionPreparation({...base(),worldModel:labModel(),recordsPhase:'ready',
  sourceIndex:sourceIndex([source()]),questions:[question('current_unreviewed_question')],
  labQuestionListPhase:'ready',labQuestionHistory:labHistory()});
 assert.equal(view.state,'needs_laboratory_review');
 assert.deepEqual(view.laboratoryQuestions,{current:1,reassessment:0});
});

test('unavailable laboratory history cannot make a known laboratory case fully prepared',()=>{
 const view=secondOpinionPreparation({...base(),worldModel:labModel(),recordsPhase:'ready',
  sourceIndex:sourceIndex([source()]),questions:[question('current_unreviewed_question')],
  labQuestionListPhase:'error',labQuestionHistory:labHistory()});
 assert.equal(view.state,'needs_check');
 assert.equal(view.laboratoryAvailable,true);
 assert.equal(view.laboratoryQuestions,null);
});

const checkedCitation=(status='available')=>({
 contract:'oi.pg-question-evidence-links/1',patient_id:'PAT-ONE',case_id:'CASE-ONE',
 question_id:'QUESTION-'+'C'.repeat(32),source_context_state:'current_unreviewed_question',
 source_access_receipt_id:'ACCESS-'+'F'.repeat(32),synthetic:true,
 model_executed:false,content_appraised:false,clinical_approval:false,
 links:[{status,link_id:'EVIDENCE-LINK-'+'D'.repeat(32)}],
});
const preparedState=()=>({...base(),recordsPhase:'ready',sourceIndex:sourceIndex([source()]),
 questions:[question('current_unreviewed_question')]});
test('second-opinion source and citation checks are distinct, never inferred',()=>{
 const s=preparedState(),id=s.questions[0].question_id;
 let row=secondOpinionPreparation(s).agenda.preview[0];
 assert.equal(row.evidenceReadiness.original,'matched');
 assert.equal(row.evidenceReadiness.citations,null);
 row=secondOpinionPreparation({...s,evidenceFamily:'text',evidenceQuestionId:id,evidenceLinksPhase:'ready',
  evidenceLinks:{...checkedCitation(),links:[]}}).agenda.preview[0];
 assert.deepEqual(row.evidenceReadiness.citations,{total:0,metadataOnly:0,restricted:0,superseded:0,unavailable:0});
});
test('citation metadata counts are not scientific appraisals or eligibility',()=>{
 const s=preparedState(),id=s.questions[0].question_id;
 const links=['available','rights_restricted','superseded','unavailable'].map((status,n)=>({status,link_id:'LINK-'+n}));
 const row=secondOpinionPreparation({...s,evidenceFamily:'text',evidenceQuestionId:id,evidenceLinksPhase:'ready',
  evidenceLinks:{...checkedCitation(),links}}).agenda.preview[0];
 assert.deepEqual(row.evidenceReadiness.citations,{total:4,metadataOnly:1,restricted:1,superseded:1,unavailable:1});
});
test('stale, denied or wrong-case citation read cannot surface as evidence',()=>{
 const s={...preparedState(),evidenceFamily:'text',evidenceQuestionId:'QUESTION-'+'C'.repeat(32),
  evidenceLinksPhase:'ready',evidenceLinks:checkedCitation()};
 for(const patch of [{evidenceLinksPhase:'error'},{evidenceLinksPhase:'loading'},
  {evidenceQuestionId:'QUESTION-'+'A'.repeat(32)},
  {evidenceLinks:{...checkedCitation(),patient_id:'PAT-OTHER'}},
  {evidenceLinks:{...checkedCitation(),case_id:'CASE-OTHER'}},
  {evidenceLinks:{...checkedCitation(),source_context_state:'source_reassessment_required'}},
  {evidenceLinks:{...checkedCitation(),content_appraised:true}}]){
  assert.equal(secondOpinionPreparation({...s,...patch}).agenda.preview[0].evidenceReadiness.citations,null,JSON.stringify(patch));
 }
});
test('changed original or missing exact source hash cannot be called a current match',()=>{
 const s=preparedState();
 assert.equal(secondOpinionPreparation({...s,questions:[question('source_reassessment_required')]}).agenda.preview[0].evidenceReadiness.original,'changed');
 assert.equal(secondOpinionPreparation({...s,recordsPhase:'error'}).agenda.preview[0].evidenceReadiness.original,'unchecked');
 assert.equal(secondOpinionPreparation({...s,sourceIndex:sourceIndex([{...source(),sha256:'b'.repeat(64)}])}).agenda.preview[0].evidenceReadiness.original,'not_matched');
});

const examplePacket=(q,patch={})=>({
 contract:'oi.h1-question-evidence/1',patient_id:'PAT-ONE',case_id:'CASE-ONE',
 question:q,source_snapshot_sha256:q.source_snapshot_sha256,
 access_receipt_id:'ACCESS-'+'A'.repeat(32),packet_sha256:'e'.repeat(64),
 evidence:[],assessments:[],reports:[],
 synthetic:true,human_review_state:'not_performed',clinical_approval:false,model_executed:false,...patch
});
const comparisonState=(packet)=>({
 worldModel:{...base().worldModel,snapshot_fingerprint:packet.source_snapshot_sha256},
 evidencePhase:'ready',evidencePacket:packet,
});
test('comparison status separates not-read from authorized checked empty',()=>{
 const q=question('current_unreviewed_question');
 const prior=secondOpinionPreparation({...base(),questions:[q]}).agenda.preview[0];
 assert.equal(prior.comparisonReadiness,null);
 const packet=examplePacket(q),actual=secondOpinionPreparation({
  ...base(),questions:[q],...comparisonState(packet)}).agenda.preview[0].comparisonReadiness;
 assert.deepEqual(actual,{
  proposed:{support:0,contradiction:0,context:0,unknown:0},
  reassessment:0,withheld:0,reports:{currentUnreviewed:0,historical:0,withheld:0}
 });
});
test('proposed support and contradiction are separate from historical and withheld comparisons',()=>{
 const q=question('current_unreviewed_question');
 const evidence=Array.from({length:6},(_,i)=>({
  evidence_id:'EVIDENCE-'+String(i).padStart(32,'0'),sha256:'a'.repeat(64),
  rights_sha256:'b'.repeat(64),state:'current',statement:'Independently fictional original statement.'
 }));
 const relations=['supports','contradicts','context','unknown','supports','contradicts'];
 const statuses=['current_unreviewed','current_unreviewed','current_unreviewed','current_unreviewed',
  'reassessment_required','content_withheld'];
 const assessments=relations.map((relation,i)=>({
  question_id:q.question_id,evidence_id:evidence[i].evidence_id,
  evidence_sha256:evidence[i].sha256,rights_sha256:evidence[i].rights_sha256,
  source_snapshot_sha256:q.source_snapshot_sha256,preflight_sha256:q.preflight_sha256,
  relation,state:statuses[i]
 }));
 const reports=['current_unreviewed','historical_reassessment_required','content_withheld']
  .map(state=>({question_id:q.question_id,state}));
 const packet=examplePacket(q,{evidence,assessments,reports});
 const result=secondOpinionPreparation({...base(),questions:[q],
  ...comparisonState(packet)}).agenda.preview[0].comparisonReadiness;
 assert.deepEqual(result,{
  proposed:{support:1,contradiction:1,context:1,unknown:1},
  reassessment:1,withheld:1,reports:{currentUnreviewed:1,historical:1,withheld:1}
 });
});
test('comparison readback never survives an error, wrong patient, other question or model flag',()=>{
 const q=question('current_unreviewed_question'),packet=examplePacket(q);
 const state={...base(),questions:[q],...comparisonState(packet)};
 assert.ok(secondOpinionPreparation(state).agenda.preview[0].comparisonReadiness);
 for(const patch of [
  {evidencePhase:'loading'},{evidencePhase:'error'},
  {evidencePacket:{...packet,patient_id:'PAT-OTHER'}},
  {evidencePacket:{...packet,case_id:'CASE-OTHER'}},
  {evidencePacket:{...packet,question:{...q,question_id:'QUESTION-'+'D'.repeat(32)}}},
  {evidencePacket:{...packet,question:{...q,source_sha256:'0'.repeat(64)}}},
  {evidencePacket:{...packet,model_executed:true}},
  {evidencePacket:{...packet,human_review_state:'performed'}},
  {evidencePacket:{...packet,access_receipt_id:'ACCESS-BAD'}},
  {worldModel:{...state.worldModel,snapshot_fingerprint:'0'.repeat(64)}},
 ]){
  assert.equal(secondOpinionPreparation({...state,...patch}).agenda.preview[0].comparisonReadiness,
   null,JSON.stringify(patch));
 }
});
test('evidence comparison with incompatible lineage or missing content is withheld',()=>{
 const q=question('current_unreviewed_question');
 const ev={evidence_id:'EVIDENCE-'+'F'.repeat(32),sha256:'a'.repeat(64),
  rights_sha256:'b'.repeat(64),state:'current',statement:'Synthetic evidence original'};
 const row={question_id:q.question_id,evidence_id:ev.evidence_id,evidence_sha256:ev.sha256,
  rights_sha256:ev.rights_sha256,source_snapshot_sha256:q.source_snapshot_sha256,
  preflight_sha256:q.preflight_sha256,state:'current_unreviewed',relation:'supports'};
 const packet=examplePacket(q,{evidence:[ev],assessments:[row]});
 const state={...base(),questions:[q],...comparisonState(packet)};
 assert.equal(secondOpinionPreparation(state).agenda.preview[0].comparisonReadiness?.proposed.support,1);
 for(const change of [
  {evidence:[{...ev,statement:null}]},
  {evidence:[{...ev,sha256:'f'.repeat(64)}]},
  {assessments:[{...row,preflight_sha256:'0'.repeat(64)}]},
  {assessments:[{...row,question_id:'QUESTION-'+'A'.repeat(32)}]},
 ]) assert.equal(secondOpinionPreparation({...state,evidencePacket:{...packet,...change}})
  .agenda.preview[0].comparisonReadiness,null,JSON.stringify(change));
});

test('second-opinion text agenda requires a text citation read even when identifiers coincide',()=>{
 const state=preparedState(),textQuestion=state.questions[0];
 const history=labHistory(),laboratoryQuestion=history.questions[0];
 const both={...state,worldModel:labModel(),labQuestionListPhase:'ready',
  labQuestionHistory:{...history,questions:[{...laboratoryQuestion,question_id:textQuestion.question_id}]},
  evidenceLinksPhase:'ready',evidenceQuestionId:textQuestion.question_id,evidenceLinks:checkedCitation()};
 for(const evidenceFamily of ['laboratory',null]){
  const view=secondOpinionPreparation({...both,evidenceFamily});
  assert.deepEqual(view.laboratoryQuestions,{current:1,reassessment:0});
  assert.equal(view.agenda.preview[0].evidenceReadiness.citations,null);
 }
 assert.equal(secondOpinionPreparation({...both,evidenceFamily:'text'})
  .agenda.preview[0].evidenceReadiness.citations.metadataOnly,1);
});
