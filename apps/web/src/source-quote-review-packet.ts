/** Strict, read-only canonical H1 source quotation packet.
 * No clinical conclusion, publisher rights, evidence grade or model execution.
 */
import type {SourceQuestion} from './source-questions-view.js';

export type SourceQuote=Readonly<{
 source_id:string;document_id:string;document_version:number;source_sha256:string;
 source_line:number;finding_key:string;reported_state:string;source_statement:string;
 source_kind:string;specimen_id:string|null;event_date:string;issued_at:string;
 review_state:'not_established';clinical_meaning:null;
}>;
export type QuestionSourceReviewPacket=Readonly<{
 contract:'oi.synthetic-question-source-review-packet/1';
 patient_id:string;case_id:string;question_id:string;question:string;
 original_anchor:Readonly<{
  source_id:string;source_line:number;source_sha256:string;source_version:number;
  source_snapshot_sha256:string;source_snapshot_contract:string;
  preflight_sha256:string;
 }>;
 source_context_state:'current_unreviewed_source'|'source_reassessment_required';
 current_source_snapshot_sha256:string;selected_statement:SourceQuote|null;
 related_statements:readonly SourceQuote[];related_statement_count_total:number;
 related_statements_truncated:boolean;current_source_count:number;current_observation_count:number;
 external_biomedical_evidence_qualified:false;published_evidence_rights_verified:false;
 medical_interpretation_performed:false;clinical_review_connected:false;clinical_approval:false;
 reviewer_identity_verified:false;synthetic:true;
 review_next_step:'independent_source_verification_required'|'refresh_source_and_create_new_question';
 packet_sha256:string;source_access_receipt_id:string;
}>;

const ID=/^SRC-[0-9A-F]{32}$/;
const HASH=/^[0-9a-f]{64}$/;
const DOC=/^[A-Z][A-Z0-9-]{1,39}$/;
const DATE=/^\d{4}-\d{2}-\d{2}$/;
const STATES=['reported','negative','pending','indeterminate',
 'not-reported','not-assessed','conflicting'];
const KINDS=['clinical','pathology','laboratory','imaging','molecular','other'];
const anchorKeys=['source_id','source_line','source_sha256','source_version',
 'source_snapshot_sha256','source_snapshot_contract','preflight_sha256'];
const quoteKeys=['source_id','document_id','document_version','source_sha256',
 'source_line','finding_key','reported_state','source_statement','source_kind',
 'specimen_id','event_date','issued_at','review_state','clinical_meaning'];
const packetKeys=['contract','patient_id','case_id','question_id','question',
 'original_anchor','source_context_state','current_source_snapshot_sha256',
 'selected_statement','related_statements','related_statement_count_total',
 'related_statements_truncated','current_source_count','current_observation_count',
 'external_biomedical_evidence_qualified','published_evidence_rights_verified',
 'medical_interpretation_performed','clinical_review_connected','clinical_approval',
 'reviewer_identity_verified','synthetic','review_next_step',
 'packet_sha256','source_access_receipt_id'];
function obj(v:unknown,keys:readonly string[]):v is Record<string,unknown>{
 return v!==null&&typeof v==='object'&&!Array.isArray(v)&&
 Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
}
function positive(v:unknown):v is number{
 return typeof v==='number'&&Number.isSafeInteger(v)&&v>0;
}
function nonnegative(v:unknown):v is number{
 return typeof v==='number'&&Number.isSafeInteger(v)&&v>=0;
}
function date(v:unknown):boolean{return typeof v==='string'&&DATE.test(v)&&
 Number.isFinite(Date.parse(v+'T00:00:00Z'));}
function quote(v:unknown):SourceQuote{
 if(!obj(v,quoteKeys)||typeof v.source_id!=='string'||!ID.test(v.source_id)||
   typeof v.document_id!=='string'||!DOC.test(v.document_id)||
   !positive(v.document_version)||typeof v.source_sha256!=='string'||!HASH.test(v.source_sha256)||
   !positive(v.source_line)||v.source_line>10000||
   typeof v.finding_key!=='string'||!/^[a-z][a-z0-9_-]{0,59}$/.test(v.finding_key)||
   typeof v.reported_state!=='string'||!STATES.includes(v.reported_state)||
   typeof v.source_statement!=='string'||v.source_statement.length===0||
   v.source_statement.length>1200||typeof v.source_kind!=='string'||!KINDS.includes(v.source_kind)||
   (v.specimen_id!==null&&(typeof v.specimen_id!=='string'||!DOC.test(v.specimen_id)))||
   !date(v.event_date)||!date(v.issued_at)||
   v.review_state!=='not_established'||v.clinical_meaning!==null)throw Error('contract');
 return Object.freeze(v as SourceQuote);
}
function stableJson(v:unknown):string{
 if(Array.isArray(v))return '['+v.map(stableJson).join(',')+']';
 if(v!==null&&typeof v==='object'){
   const data=v as Record<string,unknown>;
   return '{'+Object.keys(data).sort().map(k=>JSON.stringify(k)+':'+stableJson(data[k])).join(',')+'}';
 }
 return JSON.stringify(v);
}
export async function decodeQuestionSourcePacket(
 value:unknown,expected:SourceQuestion,caseId:string,patientId:string,
 currentFingerprint?:string):Promise<QuestionSourceReviewPacket>{
 if(!obj(value,packetKeys)||
    value.contract!=='oi.synthetic-question-source-review-packet/1'||
    value.patient_id!==patientId||value.case_id!==caseId||
    value.question_id!==expected.question_id||value.question!==expected.question||
    !obj(value.original_anchor,anchorKeys)||
    value.original_anchor.source_id!==expected.source_id||
    value.original_anchor.source_line!==expected.source_line||
    value.original_anchor.source_sha256!==expected.source_sha256||
    value.original_anchor.source_version!==expected.source_version||
    value.original_anchor.source_snapshot_sha256!==expected.source_snapshot_sha256||
    value.original_anchor.source_snapshot_contract!==expected.source_snapshot_contract||
    value.original_anchor.preflight_sha256!==expected.preflight_sha256||
    typeof value.current_source_snapshot_sha256!=='string'||
    !HASH.test(value.current_source_snapshot_sha256)||
    typeof value.packet_sha256!=='string'||!HASH.test(value.packet_sha256)||
    typeof value.source_access_receipt_id!=='string'||
    !/^ACCESS-[0-9A-F]{32}$/.test(value.source_access_receipt_id)||
    !Array.isArray(value.related_statements)||value.related_statements.length>16||
    !nonnegative(value.related_statement_count_total)||
    value.related_statement_count_total<value.related_statements.length||
    typeof value.related_statements_truncated!=='boolean'||
    value.related_statements_truncated!==(value.related_statement_count_total>value.related_statements.length)||
    !nonnegative(value.current_source_count)||!nonnegative(value.current_observation_count)||
    value.external_biomedical_evidence_qualified!==false||
    value.published_evidence_rights_verified!==false||
    value.medical_interpretation_performed!==false||
    value.clinical_review_connected!==false||value.clinical_approval!==false||
    value.reviewer_identity_verified!==false||value.synthetic!==true)throw Error('contract');

 let selected:SourceQuote|null=null,related:SourceQuote[]=[];
 if(value.source_context_state==='current_unreviewed_source'){
   if(value.review_next_step!=='independent_source_verification_required'||
      value.current_source_snapshot_sha256!==expected.source_snapshot_sha256||
      (currentFingerprint!==undefined&&currentFingerprint!==value.current_source_snapshot_sha256)||
      value.selected_statement===null)throw Error('contract');
   selected=quote(value.selected_statement);
   if(selected.source_id!==expected.source_id||
      selected.source_line!==expected.source_line||
      selected.source_sha256!==expected.source_sha256||
      selected.document_version!==expected.source_version)throw Error('contract');
   related=value.related_statements.map(quote);
   for(const other of related){
     if((other.source_id===selected.source_id&&other.source_line===selected.source_line)||
       other.finding_key!==selected.finding_key||other.specimen_id===null||
       selected.specimen_id===null||other.specimen_id!==selected.specimen_id||
       other.event_date!==selected.event_date)throw Error('contract');
   }
 }else if(value.source_context_state==='source_reassessment_required'){
   if(value.review_next_step!=='refresh_source_and_create_new_question'||
     value.selected_statement!==null||value.related_statements.length!==0||
     value.related_statement_count_total!==0||value.related_statements_truncated!==false)throw Error('contract');
 }else throw Error('contract');
 const stable={...value} as Record<string,unknown>;
 delete stable.packet_sha256;delete stable.source_access_receipt_id;
 if(!globalThis.crypto?.subtle)throw Error('contract');
 const digest=await globalThis.crypto.subtle.digest('SHA-256',
   new TextEncoder().encode(stableJson(stable)));
 const actual=Array.from(new Uint8Array(digest),n=>n.toString(16).padStart(2,'0')).join('');
 if(actual!==value.packet_sha256)throw Error('contract');
 return Object.freeze({...value,selected_statement:selected,
  related_statements:Object.freeze(related)} as QuestionSourceReviewPacket);
}
