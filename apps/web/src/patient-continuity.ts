import type {ViewState} from './registry-client.js';

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
 // Retain a neutral path back to an *uncertain* return even if refreshing
 // original sources removed the World Model. The exact return's own captured
 // patient and case must still match an actively mapped patient/case.
 // A different selected case never silently reuses the older return.
 const intent=state.reviewReturnIntent;
 const recoveryCaseId=state.reviewReturnPhase==='unknown'&&intent&&
   intent.patient_id===patient.patient_id&&(!caseId||caseId===intent.case_id)&&
   state.cases?.some(c=>c.patient_id===patient.patient_id&&c.case_id===intent.case_id&&c.status==='active')
   ?intent.case_id:null;
 return {patientId:patient.patient_id,caseId,questions,draft,recoveryCaseId} as const;
}
