/** Source-owned H1 review inbox + immutable nonterminal return receipts.
 * This is not clinical approval, verified clinician identity or notification.
 */
import type {BackgroundBrief} from './background-brief.js';
import type {EvidenceReport} from './authored-evidence.js';
import {citationEvidenceTimestamp as time} from './evidence-timestamp.js';

export const FICTIONAL_RETURN_REASON =
  'Please independently verify this fictional source quotation and uncertainty.';
export type SourceSnapshotContract='oi.pg-source-world-model/1'|'oi.synthetic-postgres-world-model-sources/1';
export type ReviewFingerprintContract='oi.synthetic-source-review-return/1'|'oi.synthetic-source-review-return/2';
export type ReviewQueueItem=Readonly<{
 question_id:string;patient_id:string;case_id:string;question:string;
 source_id:string;source_line:number;source_sha256:string;source_version:number;
 source_snapshot_sha256:string;source_snapshot_contract:SourceSnapshotContract;
 preflight_sha256:string;created_at:string;
 queue_fingerprint_contract:'oi.synthetic-source-review-return/2';
 kind:'source-question';queue_fingerprint:string|null;
 source_context_state:'current_unreviewed_question'|'source_reassessment_required';
 review_state:'awaiting_independent_verification'|
  'returned_for_independent_verification'|'source_reassessment_required';
 current_return_receipt_id:string|null;return_count:number;prior_return_count:number;
 clinical_approval:false;reviewer_identity_verified:false;
}>;
export type ReviewHistoryReceipt=Readonly<{
 receipt_id:string;question_id:string;queue_fingerprint:string;
 source_snapshot_sha256:string;source_snapshot_contract:SourceSnapshotContract;
 queue_fingerprint_contract:ReviewFingerprintContract;actor_label:string;action:'returned';
 reason:string;created_at:string;reviewer_identity_verified:false;
 external_notification_sent:false;clinical_approval:false;
}>;
export type ReviewQueue=Readonly<{
 contract:'oi.synthetic-question-review-return-queue/2';patient_id:string;case_id:string;
 access_receipt_id:string;
 synthetic:true;items:readonly ReviewQueueItem[];receipts:readonly ReviewHistoryReceipt[];
 external_notification_sent:false;reviewer_identity_verified:false;
 clinical_approval:false;review_completion_supported:false;
}>;
export type ReviewReturnResult=Readonly<{receipt_id:string;question_id:string;duplicate:boolean}>;

const QID=/^QUESTION-[0-9A-F]{32}$/;
const SID=/^SRC-[0-9A-F]{32}$/;
const RID=/^REVIEW-[0-9A-F]{32}$/;
const SHA=/^[0-9a-f]{64}$/;
const ACCESS=/^ACCESS-[0-9A-F]{32}$/;
const CANONICAL='oi.pg-source-world-model/1',LEGACY='oi.synthetic-postgres-world-model-sources/1';
const FINGERPRINT='oi.synthetic-source-review-return/2',OLD_FINGERPRINT='oi.synthetic-source-review-return/1';
const itemFields=['question_id','patient_id','case_id','question','source_id',
  'source_line','source_sha256','source_version','source_snapshot_sha256',
  'source_snapshot_contract','queue_fingerprint_contract','preflight_sha256','created_at','kind','queue_fingerprint','source_context_state',
  'review_state','current_return_receipt_id','return_count','prior_return_count',
  'clinical_approval','reviewer_identity_verified'];
const receiptFields=['receipt_id','question_id','queue_fingerprint','source_snapshot_sha256',
 'source_snapshot_contract','queue_fingerprint_contract','actor_label','action','reason','created_at','reviewer_identity_verified',
 'external_notification_sent','clinical_approval'];
function exact(value:unknown,keys:readonly string[]):value is Record<string,unknown>{
 return value!==null&&typeof value==='object'&&!Array.isArray(value)&&
 Object.keys(value).length===keys.length&&keys.every(k=>Object.hasOwn(value,k));
}
function nonneg(value:unknown):value is number{
 return typeof value==='number'&&Number.isSafeInteger(value)&&value>=0;
}
function visible(value:unknown,min:number,max:number):value is string{
 return typeof value==='string'&&value.length>=min&&value.length<=max&&
 value===value.trim()&&
 !/[\p{Cc}\p{Cf}\p{Cs}]/u.test(value);
}
export function validReturnReason(value:unknown):value is string{return visible(value,10,600);}
export function decodeReviewReturnResult(value:unknown,question:string):ReviewReturnResult{
 if(!exact(value,['receipt_id','question_id','duplicate'])||
    typeof value.receipt_id!=='string'||!RID.test(value.receipt_id)||
    value.question_id!==question||typeof value.duplicate!=='boolean')throw Error('contract');
 return Object.freeze(value as ReviewReturnResult);
}
export type ReviewEvidence = Readonly<{
 run_id:string; result_sha256:string; report_id:string; report_snapshot_sha256:string;
}>;

export function selectedReviewEvidence(item:ReviewQueueItem, run:BackgroundBrief|null,
                                       report:EvidenceReport|null):ReviewEvidence|null{
 const brief=run?.result?.brief, snapshot=report?.snapshot, status=run?.status;
 if(!brief||!snapshot||!status?.result_sha256||status.state!=='completed'||run?.busy||
    report?.state!=='current_unreviewed'||item.queue_fingerprint===null||
    [brief.question,snapshot.question].some(q=>q.patient_id!==item.patient_id||q.case_id!==item.case_id||
      q.question_id!==item.question_id||q.source_snapshot_sha256!==item.source_snapshot_sha256||
      q.preflight_sha256!==item.preflight_sha256))return null;
 return Object.freeze({run_id:status.run_id,result_sha256:status.result_sha256,report_id:report.report_id,
  report_snapshot_sha256:report.snapshot_sha256});
}

export function decodeEvidenceReturn(value:unknown,question:string,pins:ReviewEvidence,status:number):ReviewReturnResult{
 const identifiers=['run_id','result_sha256','report_id','report_snapshot_sha256'] as const;
 if(!exact(value,['receipt_id','question_id','duplicate',...identifiers,'verification','clinical_approval'])||
    identifiers.some(key=>pins[key]!==value[key])||value.verification!=='matched_current_source_and_evidence'||
    value.clinical_approval!==false||value.duplicate!==(status===200))throw Error('contract');
 return decodeReviewReturnResult({receipt_id:value.receipt_id,question_id:value.question_id,duplicate:value.duplicate},question);
}

export function decodeReviewQueue(value:unknown,patient:string,caseId:string):ReviewQueue{
 if(!exact(value,['contract','patient_id','case_id','synthetic','items','receipts','access_receipt_id',
  'external_notification_sent','reviewer_identity_verified','clinical_approval',
  'review_completion_supported'])||
  value.contract!=='oi.synthetic-question-review-return-queue/2'||
  typeof value.access_receipt_id!=='string'||!ACCESS.test(value.access_receipt_id)||
  value.patient_id!==patient||value.case_id!==caseId||
  value.synthetic!==true||value.external_notification_sent!==false||
  value.reviewer_identity_verified!==false||value.clinical_approval!==false||
  value.review_completion_supported!==false||!Array.isArray(value.items)||
  !Array.isArray(value.receipts)||value.items.length>250||value.receipts.length>750)throw Error('contract');
 const questions=new Set<string>(),receipts=new Map<string,ReviewHistoryReceipt>();
 const history=value.receipts.map((r:unknown)=>{
  if(!exact(r,receiptFields)||typeof r.receipt_id!=='string'||!RID.test(r.receipt_id)||
    receipts.has(r.receipt_id)||typeof r.question_id!=='string'||!QID.test(r.question_id)||
    typeof r.queue_fingerprint!=='string'||!SHA.test(r.queue_fingerprint)||
    typeof r.source_snapshot_sha256!=='string'||!SHA.test(r.source_snapshot_sha256)||
    !((r.source_snapshot_contract===CANONICAL&&r.queue_fingerprint_contract===FINGERPRINT)||
      (r.source_snapshot_contract===LEGACY&&r.queue_fingerprint_contract===OLD_FINGERPRINT))||
    !visible(r.actor_label,3,128)||r.action!=='returned'||
    !visible(r.reason,10,600)||!time(r.created_at)||
    r.reviewer_identity_verified!==false||r.external_notification_sent!==false||
    r.clinical_approval!==false)throw Error('contract');
  const receipt=Object.freeze(r as ReviewHistoryReceipt);receipts.set(receipt.receipt_id,receipt);
  return receipt;
 });
 const items=value.items.map((item:unknown)=>{
  if(!exact(item,itemFields)||typeof item.question_id!=='string'||!QID.test(item.question_id)||
   questions.has(item.question_id)||item.patient_id!==patient||item.case_id!==caseId||
   !visible(item.question,8,500)||typeof item.source_id!=='string'||!SID.test(item.source_id)||
   !nonneg(item.source_line)||item.source_line<1||item.source_line>10000||
   typeof item.source_sha256!=='string'||!SHA.test(item.source_sha256)||
   !nonneg(item.source_version)||item.source_version<1||
   typeof item.source_snapshot_sha256!=='string'||!SHA.test(item.source_snapshot_sha256)||
   typeof item.preflight_sha256!=='string'||!SHA.test(item.preflight_sha256)||
   ![CANONICAL,LEGACY].includes(String(item.source_snapshot_contract))||
   item.queue_fingerprint_contract!==FINGERPRINT||
   !time(item.created_at)||item.kind!=='source-question'||
   !['current_unreviewed_question','source_reassessment_required'].includes(String(item.source_context_state))||
   !['awaiting_independent_verification','returned_for_independent_verification','source_reassessment_required'].includes(String(item.review_state))||
   !(item.queue_fingerprint===null||
     (typeof item.queue_fingerprint==='string'&&SHA.test(item.queue_fingerprint)))||
   !(item.current_return_receipt_id===null||
     (typeof item.current_return_receipt_id==='string'&&RID.test(item.current_return_receipt_id)))||
   !nonneg(item.return_count)||!nonneg(item.prior_return_count)||
   item.clinical_approval!==false||item.reviewer_identity_verified!==false)throw Error('contract');
  questions.add(item.question_id);
  const prior=history.filter(r=>r.question_id===item.question_id);
  if(prior.length!==item.return_count+item.prior_return_count)throw Error('contract');
  const matching=prior.filter(r=>item.queue_fingerprint!==null&&
    item.source_snapshot_contract===CANONICAL&&r.source_snapshot_contract===CANONICAL&&
    r.queue_fingerprint_contract===FINGERPRINT&&r.queue_fingerprint===item.queue_fingerprint&&
    r.source_snapshot_sha256===item.source_snapshot_sha256);
  if(item.source_snapshot_contract===LEGACY&&item.source_context_state!=='source_reassessment_required')throw Error('contract');
  if(matching.length!==item.return_count)throw Error('contract');
  if(item.source_context_state==='source_reassessment_required'){
   if(item.queue_fingerprint!==null||item.review_state!=='source_reassessment_required'||
      item.return_count!==0||item.current_return_receipt_id!==null)throw Error('contract');
  }else if(item.queue_fingerprint===null||item.review_state==='source_reassessment_required')throw Error('contract');
  if(item.review_state==='returned_for_independent_verification'){
   if(matching.length===0||item.current_return_receipt_id!==matching.at(-1)?.receipt_id)
     throw Error('contract');
  }else if(item.current_return_receipt_id!==null||item.return_count!==0)throw Error('contract');
  return Object.freeze(item as ReviewQueueItem);
 });
 if(history.some(r=>!questions.has(r.question_id)))throw Error('contract');
 return Object.freeze({...value,items:Object.freeze(items),
  receipts:Object.freeze(history)} as ReviewQueue);
}

