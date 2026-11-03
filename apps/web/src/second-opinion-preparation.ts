import type {ViewState} from './registry-client.js';
import {patientContinuity} from './patient-continuity.js';
import {matchesFollowthroughFilter} from './followthrough-view.js';

export type SecondOpinionPreparationState='needs_check'|'needs_records'|'needs_question'|'needs_reassessment'|'inputs_prepared';

export function secondOpinionPreparation(state:ViewState){
 const continuity=patientContinuity(state);
 if(!continuity?.caseId)return null;
 const {patientId,caseId}=continuity;
 const index=state.recordsPhase==='ready'&&state.sourceIndex?.patient_id===patientId&&
  state.sourceIndex.case_id===caseId?state.sourceIndex:null;
 const records=index?{
  current:index.sources.filter(source=>source.state==='current').length,
  historical:index.sources.filter(source=>source.state==='superseded').length,
 }:null;
 const questions=continuity.questions;
 const attention=continuity.followthrough;
 // Question and task reads have independent grants. Never turn a task denial,
 // loading state, or other case's task history into a reassuring zero count.
 const questionWork=(questionId:string)=>{
  if(!attention)return null;
  const recorded=attention.list.tasks.filter(task=>task.question_id===questionId);
  const open=recorded.filter(task=>!matchesFollowthroughFilter(task,'history'));
  return {
   evaluatedOn:attention.list.evaluated_on,
   recordedCount:recorded.length,
   openCount:open.length,
   historicalCount:recorded.length-open.length,
   preview:open.slice(0,2).map(task=>({
    taskId:task.task_id,
    title:task.title,
    status:task.status,
    ownerLabel:task.owner_label,
    dueDate:task.due_date,
    reviewTrigger:task.review_trigger,
    needsRecheck:task.needs_recheck,
    revisitDatePassed:task.is_overdue,
   })),
  };
 };
 // Use only the successfully authorized case-bound question history. A loading,
 // denied, disconnected, or wrong-case read must never expose an older agenda.
 const authorizedQuestions=questions&&state.questions?state.questions:null;
 const agenda=authorizedQuestions?{
  total:authorizedQuestions.length,
  preview:authorizedQuestions.slice(0,5).map(question=>({
   questionId:question.question_id,
   text:question.question,
   sourceVersion:question.source_version,
   sourceLine:question.source_line,
   sourceContextState:question.source_context_state,
   work:questionWork(question.question_id),
  })),
 }:null;
 const openTasks=attention?.list.tasks.filter(task=>!matchesFollowthroughFilter(task,'history'))??null;
 const coordination=openTasks?{
  open:openTasks.length,
  assigned:openTasks.filter(task=>task.owner_label.trim().length>0).length,
  sourceChanged:openTasks.filter(task=>task.needs_recheck).length,
 }:null;
 let preparationState:SecondOpinionPreparationState='needs_check';
 if(records&&questions){
  preparationState=records.current===0?'needs_records':
   questions.reassessment>0?'needs_reassessment':
   questions.current===0?'needs_question':'inputs_prepared';
 }
 return {patientId,caseId,records,questions,agenda,coordination,state:preparationState} as const;
}
