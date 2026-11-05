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
 // Source and citation reads use separate grants. These counts are not evidence
 // appraisal, current clinical interpretations or options for treatment.
 const evidenceReadiness=(question:NonNullable<typeof authorizedQuestions>[number])=>{
  const original=question.source_context_state==='source_reassessment_required'?'changed':
   !index?'unchecked':index.sources.some(src=>src.source_id===question.source_id&&
    src.version===question.source_version&&src.sha256===question.source_sha256&&src.state==='current')
    ?'matched':'not_matched';
  const links=state.evidenceLinks;
  const checked=state.evidenceLinksPhase==='ready'&&state.evidenceQuestionId===question.question_id&&
   links?.contract==='oi.pg-question-evidence-links/1'&&links.patient_id===patientId&&
   links.case_id===caseId&&links.question_id===question.question_id&&
   links.source_context_state===question.source_context_state&&
   links.synthetic===true&&links.model_executed===false&&links.content_appraised===false&&
   links.clinical_approval===false&&Array.isArray(links.links)&&links.links.every(link=>
    ['available','rights_restricted','superseded','unavailable'].includes(link.status));
  const citations=checked&&links?{
   total:links.links.length,
   metadataOnly:links.links.filter(link=>link.status==='available').length,
   restricted:links.links.filter(link=>link.status==='rights_restricted').length,
   superseded:links.links.filter(link=>link.status==='superseded').length,
   unavailable:links.links.filter(link=>link.status==='unavailable').length,
  }:null;
  return {original,citations} as const;
 };
 // Case-owned, separately authorized human-authored evidence remains unreviewed.
 // The packet decoder already verifies digests and rights. This projection also
 // requires the *currently selected* patient, case, question and source snapshot.
 const comparisonReadiness=(question:NonNullable<typeof authorizedQuestions>[number])=>{
  const packet=state.evidencePacket;
  if(state.evidencePhase!=='ready'||!packet||packet.contract!=='oi.h1-question-evidence/1'||
    packet.patient_id!==patientId||packet.case_id!==caseId||
    packet.synthetic!==true||packet.human_review_state!=='not_performed'||
    packet.clinical_approval!==false||packet.model_executed!==false||
    !/^ACCESS-[0-9A-F]{32}$/.test(packet.access_receipt_id)||
    !packet.question||!Object.keys(question).every(key=>
      packet.question[key as keyof typeof question]===question[key as keyof typeof question])||
    packet.source_snapshot_sha256!==question.source_snapshot_sha256||
    state.worldModel?.snapshot_fingerprint!==packet.source_snapshot_sha256||
    !Array.isArray(packet.evidence)||!Array.isArray(packet.assessments)||!Array.isArray(packet.reports))
    return null;
  const knownEvidence=new Map(packet.evidence.map(row=>[row.evidence_id,row]));
  if(packet.assessments.some(row=>{
    const evidence=knownEvidence.get(row.evidence_id);
    return row.question_id!==question.question_id||
      row.source_snapshot_sha256!==question.source_snapshot_sha256||
      row.preflight_sha256!==question.preflight_sha256||
      !['current_unreviewed','reassessment_required','content_withheld'].includes(row.state)||
      !evidence||evidence.sha256!==row.evidence_sha256||
      evidence.rights_sha256!==row.rights_sha256||
      row.state==='current_unreviewed'&&(evidence.state!=='current'||evidence.statement===null);
  })||packet.reports.some(row=>row.question_id!==question.question_id||
    !['current_unreviewed','historical_reassessment_required','content_withheld'].includes(row.state)))
    return null;
  const current=packet.assessments.filter(row=>row.state==='current_unreviewed');
  return {
   proposed:{
    support:current.filter(row=>row.relation==='supports').length,
    contradiction:current.filter(row=>row.relation==='contradicts').length,
    context:current.filter(row=>row.relation==='context').length,
    unknown:current.filter(row=>row.relation==='unknown').length,
   },
   reassessment:packet.assessments.filter(row=>row.state==='reassessment_required').length,
   withheld:packet.assessments.filter(row=>row.state==='content_withheld').length,
   reports:{
    currentUnreviewed:packet.reports.filter(row=>row.state==='current_unreviewed').length,
    historical:packet.reports.filter(row=>row.state==='historical_reassessment_required').length,
    withheld:packet.reports.filter(row=>row.state==='content_withheld').length,
   },
  } as const;
 };
 const agenda=authorizedQuestions?{
  total:authorizedQuestions.length,
  preview:authorizedQuestions.slice(0,5).map(question=>({
   questionId:question.question_id,
   text:question.question,
   sourceVersion:question.source_version,
   sourceLine:question.source_line,
   sourceContextState:question.source_context_state,
   evidenceReadiness:evidenceReadiness(question),
   comparisonReadiness:comparisonReadiness(question),
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
