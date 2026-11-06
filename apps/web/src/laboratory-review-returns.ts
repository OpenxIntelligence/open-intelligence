/** A nonterminal verification request against an exact reopened inspection. */
import type {LaboratoryInspection} from './laboratory-citation-report.js';
import type {InspectionSnapshot} from './laboratory-inspection-snapshots.js';
import {validReturnReason} from './review-queue-view.js';
import {citationEvidenceTimestamp} from './evidence-timestamp.js';
export type InspectionReturn=Readonly<{
 receipt_id:string;question_id:string;snapshot_id:string;captured_report_sha256:string;report_sha256:string;
 source_context_state:'current_unreviewed_question'|'source_reassessment_required';queue_fingerprint:string;
 actor_label:string;action:'returned';reason:string;created_at:string;clinical_approval:false;
 reviewer_identity_verified:false;external_notification_sent:false;
}>;
export type InspectionReview=Readonly<{
 contract:'oi.laboratory-inspection-review-returns/1';patient_id:string;case_id:string;question_id:string;
 snapshot_id:string;captured_report_sha256:string;current_report_sha256:string;
 source_context_state:'current_unreviewed_question'|'source_reassessment_required';queue_fingerprint:string;
 source_access_receipt_id:string;review_state:'awaiting_independent_verification'|'returned_for_independent_verification'|'source_reassessment_required';
 current_return_receipt_id:string|null;return_count:number;prior_return_count:number;receipts:readonly InspectionReturn[];
 synthetic:true;clinical_approval:false;reviewer_identity_verified:false;external_notification_sent:false;
}>;
export type OpenedInspection=Readonly<{snapshot:InspectionSnapshot;report:LaboratoryInspection;generation:number}>;
export type CheckedInspection=OpenedInspection & Readonly<{review:InspectionReview}>;
const digest=(v:unknown):v is string=>typeof v==='string'&&v.length===64&&/^[a-f0-9]+$/.test(v);
const receiptId=(v:unknown):v is string=>typeof v==='string'&&v.length===39&&/^REVIEW-[A-F0-9]{32}$/.test(v);
const state=(v:unknown)=>v==='current_unreviewed_question'||v==='source_reassessment_required';
const flags=(v:Record<string,unknown>)=>v.clinical_approval===false&&v.reviewer_identity_verified===false&&v.external_notification_sent===false;
const exact=(v:unknown,keys:string[]):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v)&&
 Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
export function inspectionReturnReceipt(v:unknown,question:string,snapshot:string,status:number){
 if(!exact(v,['receipt_id','question_id','snapshot_id','duplicate'])||!receiptId(v.receipt_id)||v.question_id!==question||
 v.snapshot_id!==snapshot||![200,201].includes(status)||v.duplicate!==(status===200))throw Error('Invalid inspection return receipt');
 return Object.freeze({receipt_id:v.receipt_id,question_id:question,snapshot_id:snapshot,duplicate:status===200});
}
export function inspectionReview(v:unknown,opened:OpenedInspection):InspectionReview{
 const {report,snapshot}=opened,c=report.citations;
 if(!exact(v,['contract','patient_id','case_id','question_id','snapshot_id','captured_report_sha256','current_report_sha256',
 'source_context_state','queue_fingerprint','source_access_receipt_id','review_state','current_return_receipt_id',
 'return_count','prior_return_count','receipts','synthetic','clinical_approval','reviewer_identity_verified','external_notification_sent'])||
 v.contract!=='oi.laboratory-inspection-review-returns/1'||v.patient_id!==c.patient_id||v.case_id!==c.case_id||v.question_id!==c.question_id||
 v.snapshot_id!==snapshot.snapshot_id||v.captured_report_sha256!==snapshot.captured_report_sha256||v.current_report_sha256!==report.report_sha256||
 v.source_context_state!==c.source_context_state||!digest(v.queue_fingerprint)||typeof v.source_access_receipt_id!=='string'||
 v.source_access_receipt_id.length!==39||!/^ACCESS-[A-F0-9]{32}$/.test(v.source_access_receipt_id)||
 v.synthetic!==true||!flags(v)||!Array.isArray(v.receipts)||v.receipts.length>100)throw Error('Inspection or review context changed');
 const ids=new Set<string>();
 const receipts=v.receipts.map((r:unknown)=>{
  if(!exact(r,['receipt_id','question_id','snapshot_id','captured_report_sha256','report_sha256','source_context_state',
   'queue_fingerprint','actor_label','action','reason','created_at','clinical_approval','reviewer_identity_verified','external_notification_sent'])||
   !receiptId(r.receipt_id)||ids.has(r.receipt_id)||r.question_id!==c.question_id||r.snapshot_id!==snapshot.snapshot_id||
   r.captured_report_sha256!==snapshot.captured_report_sha256||!digest(r.report_sha256)||!digest(r.queue_fingerprint)||!state(r.source_context_state)||
   typeof r.actor_label!=='string'||r.actor_label.length<3||r.actor_label.length>128||r.actor_label!==r.actor_label.trim()||
   /[\p{Cc}\p{Cf}\p{Cs}]/u.test(r.actor_label)||r.action!=='returned'||!validReturnReason(r.reason)||!citationEvidenceTimestamp(r.created_at)||!flags(r))
   throw Error('Invalid inspection return history');
  ids.add(r.receipt_id);return Object.freeze(r as InspectionReturn);
 });
 const matching=receipts.filter(r=>r.queue_fingerprint===v.queue_fingerprint);
 if(matching.some(r=>r.report_sha256!==report.report_sha256||r.source_context_state!==c.source_context_state)||
  v.return_count!==matching.length||v.prior_return_count!==receipts.length-matching.length||
  v.current_return_receipt_id!==(matching.length?matching.at(-1)!.receipt_id:null)||
  v.review_state!==(c.source_context_state==='source_reassessment_required'?'source_reassessment_required':
    matching.length?'returned_for_independent_verification':'awaiting_independent_verification'))throw Error('Inconsistent inspection return state');
 return Object.freeze({...v,receipts:Object.freeze(receipts)} as InspectionReview);
}
