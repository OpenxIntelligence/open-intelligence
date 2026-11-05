import type {ViewState} from './registry-client.js';
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
  if(questions===null) add('questions-unchecked','Check saved questions',
   'Question history was not successfully checked for this case; an unavailable read is not a verified empty list.',
   'Investigations','Check question history');
  else if(questions.current+questions.reassessment===0&&model.observations.length>0)
   add('prepare-a-question','Prepare a source-linked question',
    'No saved questions were returned in the last authorized question read. This does not mean no care questions exist.',
    'Journey','Choose a source statement');
 }
 return {patientId:patient.patient_id,caseId,questions,draft,followthrough,
  preparation:Object.freeze(preparation.slice(0,3)),preparationTotal:preparation.length} as const;
}
