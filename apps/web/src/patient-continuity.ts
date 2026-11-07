import type {ViewState} from './registry-client.js';
import {questionSaveBlocksSourceChange} from './source-questions-view.js';
import {projectFollowthroughAttention} from './followthrough-view.js';

export type PreparationPrompt=Readonly<{
 key:string; title:string; detail:string;
 destination:'Journey'|'Records'|'Investigations'; action:string;
}>;

/** A last-read navigation projection, never a task ledger or access decision. */
export function patientContinuity(state:ViewState){
 const patient=state.patient;
 if(!state.connected||state.phase!=='ready'||!patient||patient.status!=='active')return null;
 const model=state.worldModel;
 const caseId=state.worldPhase==='ready'&&model?.patient_id===patient.patient_id&&
  state.cases?.some(c=>c.patient_id===patient.patient_id&&c.case_id===model.case_id&&c.status==='active')
  ?model.case_id:null;
 const history=caseId&&state.questionsCaseId===caseId&&state.questionsAccessReceiptId&&
  state.questionListPhase==='ready'&&state.questions?.every(q=>q.patient_id===patient.patient_id&&q.case_id===caseId)
  ?state.questions:null;
 const questions=history?{
  current:history.filter(q=>q.source_context_state==='current_unreviewed_question').length,
  reassessment:history.filter(q=>q.source_context_state==='source_reassessment_required').length,
 }:null;
 // Laboratory history has an independent read/permission contract. Never
 // combine it into the source-line count, nor call an unchecked read zero.
 // The case and World Model snapshot were captured by the strict laboratory
 // response decoder; a later scope/snapshot change invalidates the count.
 const labHistory=caseId&&state.labQuestionListPhase==='ready'&&
  state.labQuestionHistory?.patient_id===patient.patient_id&&
  state.labQuestionHistory.case_id===caseId&&
  state.labQuestionHistory.checked_source_snapshot_sha256===model?.snapshot_fingerprint&&
  /^ACCESS-[0-9A-F]{32}$/.test(state.labQuestionHistory.access_receipt_id)
  ?state.labQuestionHistory:null;
 const sourceVersions=new Map([...(model?.current_sources??[]),...(model?.history??[])]
  .map(source=>[source.source_id+'|'+source.version,source]));
 const validLabHistory=labHistory&&labHistory.questions.every(question=>{
  const source=sourceVersions.get(question.source_id+'|'+question.source_version);
  return source?.kind==='laboratory'&&source.version===question.source_version&&
   source.sha256===question.source_sha256&&
   (question.source_context_state!=='current_unreviewed_question'||source.state==='current')&&
   (question.source_context_state==='current_unreviewed_question'||
    question.source_context_state==='source_reassessment_required');
 });
 const laboratoryQuestions=validLabHistory?{
  current:labHistory.questions.filter(q=>q.source_context_state==='current_unreviewed_question').length,
  reassessment:labHistory.questions.filter(q=>q.source_context_state==='source_reassessment_required').length,
 }:null;
 const laboratoryAvailable=Boolean(caseId&&(model?.laboratory_observations?.length||
  model?.current_sources?.some(s=>s.kind==='laboratory')||
  model?.history?.some(s=>s.kind==='laboratory')||laboratoryQuestions));
 const draftMatches=caseId&&state.questionDraft?.case_id===caseId&&
  state.questionDraft.snapshot_fingerprint===model?.snapshot_fingerprint;
 const draft=draftMatches?(state.questionSavePhase==='saved'&&state.savedQuestion?'saved':
  state.questionSavePhase==='saving'?'saving':state.questionSavePhase==='error'?'needs_attention':'unsaved'):null;
 const attention=caseId?projectFollowthroughAttention(state):null;
 const followthrough=attention?.list.case_id===caseId?attention:null;
 // Suggestions are deterministic shortcuts over independently authorized reads.
 // They are not clinical triage, inferred test indications, or a completeness claim.
 const preparation:PreparationPrompt[]=[];
 if(caseId&&model?.summary){
  const add=(key:string,title:string,detail:string,
   destination:PreparationPrompt['destination'],action:string)=>{
   preparation.push({key,title,detail,destination,action});
  };
  if(questions?.reassessment) add('question-recheck','Revisit changed-source questions',
   questions.reassessment+' saved question(s) need source reassessment before relying on a previous brief.',
   'Investigations','Inspect affected questions');
  if(laboratoryQuestions?.reassessment) add('laboratory-question-recheck','Revisit changed laboratory questions',
   laboratoryQuestions.reassessment+' saved laboratory question(s) need rechecking against the amended source. Original result references remain historical.',
   'Journey','Reopen saved laboratory questions');
  if(model.summary.source_disagreements>0) add('source-disagreements','Inspect differing source reports',
   model.summary.source_disagreements+' unresolved disagreement(s) were found among structured source statements. No clinical conclusion is inferred.',
   'Journey','Inspect source disagreements');
  if(model.summary.unresolved_observations>0) add('unresolved-statements','Review unresolved source statements',
   model.summary.unresolved_observations+' pending, indeterminate or otherwise unresolved source statement(s) remain in the checked structured view. Categories can overlap.',
   'Journey','Inspect source statements');
  if(followthrough?.counts.recheck) add('task-recheck','Review changed-source follow-up',
   followthrough.counts.recheck+' recorded follow-up task(s) have a source recheck flag. This is not a clinical urgency score.',
   'Investigations','Inspect follow-up work');
  if(model.summary.current_sources===0) add('check-record-coverage','Check available original records',
   'No current structured source was returned in the last authorized World Model read. Reviewed text/PDF records and unconnected providers are outside this count.',
   'Records','Check original records');
  if(laboratoryAvailable&&laboratoryQuestions===null) add('laboratory-questions-unchecked','Check saved laboratory questions',
   'Laboratory question history has not been checked for this case; an unavailable read is not zero.',
   'Journey','Reopen laboratory question history');
  if(questions===null) add('questions-unchecked','Check saved questions',
   'Text-source question history was not successfully checked for this case; an unavailable read is not a verified empty list.',
   'Investigations','Check question history');
  else if(questions.current+questions.reassessment===0&&model.observations.length>0&&
          !questionSaveBlocksSourceChange(state))
   add('prepare-a-question','Prepare a source-linked question',
    'No saved text-source questions were returned in the last authorized read. Laboratory questions are checked separately; this does not mean no care questions exist.',
    'Journey','Choose a source statement');
 }
 return {patientId:patient.patient_id,caseId,questions,laboratoryQuestions,laboratoryAvailable,draft,followthrough,
  preparation:Object.freeze(preparation.slice(0,3)),preparationTotal:preparation.length} as const;
}
