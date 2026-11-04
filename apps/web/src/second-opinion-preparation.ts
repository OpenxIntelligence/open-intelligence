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
 return {patientId,caseId,records,questions,coordination,state:preparationState} as const;
}
