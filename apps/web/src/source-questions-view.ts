/** Strict H1 source-question intake contracts. No clinical review/approval. */
export type SourceQuestion = Readonly<{
  question_id:string;patient_id:string;case_id:string;question:string;
  source_id:string;source_line:number;source_sha256:string;source_version:number;
  source_snapshot_sha256:string;preflight_sha256:string;created_at:string;
  source_snapshot_contract:'oi.pg-source-world-model/1'|'oi.synthetic-postgres-world-model-sources/1';
  source_context_state:'current_unreviewed_question'|'source_reassessment_required';
  human_review_state:'not_submitted';clinical_approval:false;model_executed:false;
}>;
export type SavedQuestion = Readonly<{question_id:string;duplicate:boolean}>;
export type SourceQuestionHistory = Readonly<{
  contract:'oi.synthetic-source-questions/2';access_receipt_id:string;
  questions:readonly SourceQuestion[];
}>;

const QID=/^QUESTION-[0-9A-F]{32}$/;
const SID=/^SRC-[0-9A-F]{32}$/;
const HEX=/^[0-9a-f]{64}$/;
const QFIELDS=['question_id','patient_id','case_id','question','source_id',
 'source_line','source_sha256','source_version','source_snapshot_sha256','source_snapshot_contract',
 'preflight_sha256','created_at','source_context_state','human_review_state',
 'clinical_approval','model_executed'];
function exact(value:unknown,keys:readonly string[]):value is Record<string,unknown>{
 return value!==null&&typeof value==='object'&&!Array.isArray(value)&&
 Object.keys(value).length===keys.length&&keys.every(k=>Object.hasOwn(value,k));
}
function positive(value:unknown):value is number{
 return typeof value==='number'&&Number.isSafeInteger(value)&&value>0;
}
export function decodeSavedQuestion(value:unknown):SavedQuestion{
 if(!exact(value,['question_id','duplicate'])||
   typeof value.question_id!=='string'||!QID.test(value.question_id)||
   typeof value.duplicate!=='boolean')throw Error('contract');
 return Object.freeze(value as SavedQuestion);
}
export function decodeSourceQuestions(value:unknown,patient:string,caseId:string):SourceQuestionHistory{
 if(!exact(value,['contract','access_receipt_id','patient_id','case_id','questions','synthetic',
                  'clinical_review_connected','clinical_approval'])||
   value.contract!=='oi.synthetic-source-questions/2'||
   typeof value.access_receipt_id!=='string'||!/^ACCESS-[0-9A-F]{32}$/.test(value.access_receipt_id)||
   value.patient_id!==patient||value.case_id!==caseId||
   value.synthetic!==true||value.clinical_review_connected!==false||
   value.clinical_approval!==false||!Array.isArray(value.questions)||
   value.questions.length>250)throw Error('contract');
 const ids=new Set<string>();
 const questions=Object.freeze(value.questions.map((row:unknown)=>{
   if(!exact(row,QFIELDS)||typeof row.question_id!=='string'||!QID.test(row.question_id)||
     ids.has(row.question_id)||row.patient_id!==patient||row.case_id!==caseId||
     typeof row.question!=='string'||row.question.length<8||row.question.length>500||
     /[\u0000-\u001f\u007f]/.test(row.question)||
     typeof row.source_id!=='string'||!SID.test(row.source_id)||
     !positive(row.source_line)||row.source_line>10000||
     typeof row.source_sha256!=='string'||!HEX.test(row.source_sha256)||
     !positive(row.source_version)||
     typeof row.source_snapshot_sha256!=='string'||!HEX.test(row.source_snapshot_sha256)||
     !['oi.pg-source-world-model/1','oi.synthetic-postgres-world-model-sources/1'].includes(String(row.source_snapshot_contract))||
     (row.source_snapshot_contract!=='oi.pg-source-world-model/1'&&row.source_context_state!=='source_reassessment_required')||
     typeof row.preflight_sha256!=='string'||!HEX.test(row.preflight_sha256)||
     typeof row.created_at!=='string'||!/\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(row.created_at)||
     !Number.isFinite(Date.parse(row.created_at))||
     !['current_unreviewed_question','source_reassessment_required'].includes(String(row.source_context_state))||
     row.human_review_state!=='not_submitted'||row.clinical_approval!==false||
     row.model_executed!==false)throw Error('contract');
   ids.add(row.question_id);
   return Object.freeze({...row} as SourceQuestion);
 }));
 return Object.freeze({contract:'oi.synthetic-source-questions/2',
   access_receipt_id:value.access_receipt_id,questions});
}
