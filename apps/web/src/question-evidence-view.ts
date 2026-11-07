/** Fictional metadata projections. A citation link is not a claim assessment. */
import {citationEvidenceTimestamp as instant} from './evidence-timestamp.js';

export type EvidenceSourceState='current_unreviewed_question'|'source_reassessment_required';
export type QuestionEvidenceRecord=Readonly<{
 citation:string;id:string;version:string;source_kind:'fictional';title:string;licence:string;link:string;
 metadata_sha256:string;availability:'metadata_only';rights_status:'granted';
}>;
type EvidenceScope=Readonly<{
 patient_id:string;case_id:string;question_id:string;source_context_state:EvidenceSourceState;
 source_access_receipt_id:string;synthetic:true;model_executed:false;content_appraised:false;clinical_approval:false;
}>;
export type QuestionEvidenceSearch=EvidenceScope&Readonly<{
 contract:'oi.pg-question-evidence-search/1';query:string;records:readonly QuestionEvidenceRecord[];
}>;
export type QuestionEvidenceLink=Readonly<{
 link_id:string;citation:string;metadata_sha256:string;created_at:string;actor_label:string;
 status:'available'|'rights_restricted'|'superseded'|'unavailable';record:QuestionEvidenceRecord|null;
}>;
export type QuestionEvidenceLinks=EvidenceScope&Readonly<{
 contract:'oi.pg-question-evidence-links/1';links:readonly QuestionEvidenceLink[];
}>;
export type QuestionEvidenceReceipt=Readonly<{
 link_id:string;citation:string;metadata_sha256:string;duplicate:boolean;
}>;
export type QuestionEvidenceIntent=Readonly<{
 patient_id:string;case_id:string;question_id:string;
 body:Readonly<{synthetic:true;request_key:string;citation:string;expected_metadata_sha256:string;
  source_snapshot_contract:'oi.pg-source-world-model/1';expected_source_snapshot_sha256:string;expected_preflight_sha256:string}>;
}>;
const scopeFields=['contract','patient_id','case_id','question_id','source_context_state','source_access_receipt_id',
 'synthetic','model_executed','content_appraised','clinical_approval'];
const recordFields=['citation','id','version','source_kind','title','licence','link','metadata_sha256','availability','rights_status'];
function exact(value:unknown,fields:readonly string[]):value is Record<string,unknown>{
 return value!==null&&typeof value==='object'&&!Array.isArray(value)&&
  Object.keys(value).length===fields.length&&fields.every(field=>Object.hasOwn(value,field));
}
function text(value:unknown,min:number,max:number):value is string{
 return typeof value==='string'&&value.trim()===value&&!/[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/u.test(value)&&
  Array.from(value).length>=min&&Array.from(value).length<=max;
}
function hash(value:unknown):value is string{return typeof value==='string'&&value.length===64&&/^[0-9a-f]{64}$/.test(value);}
function opaque(value:unknown,prefix:string):value is string{
 return typeof value==='string'&&value.length===prefix.length+32&&new RegExp('^'+prefix+'[0-9A-F]{32}$').test(value);
}
function citation(value:unknown):value is string{
 if(!text(value,1,193))return false;
 const parts=value.split('@');
 return parts.length===2&&parts[0].length<=128&&/^FICT-[A-Z0-9-]+$/.test(parts[0])&&
  parts[1].length<=64&&/^[A-Za-z0-9._-]+$/.test(parts[1]);
}
export function validEvidenceQuery(value:unknown):value is string{return text(value,1,200);}
/** This synthetic catalog has no live biomedical or patient links. */
export function safeFictionalEvidenceLink(value:unknown):value is string{
 if(!text(value,1,512)||!/^https:\/\/example\.invalid\/fictional\/[A-Za-z0-9._/-]+$/.test(value))return false;
 try{const url=new URL(value);return url.href===value&&url.protocol==='https:'&&url.host==='example.invalid'&&
  url.username===''&&url.password===''&&url.search===''&&url.hash===''&&url.pathname.startsWith('/fictional/');}
 catch{return false;}
}
function decodeRecord(value:unknown):QuestionEvidenceRecord{
 if(!exact(value,recordFields)||!citation(value.citation)||!text(value.id,1,128)||!/^FICT-[A-Z0-9-]+$/.test(value.id)||
  !text(value.version,1,64)||!(/^[A-Za-z0-9._-]+$/).test(value.version)||value.citation!==value.id+'@'+value.version||
  value.source_kind!=='fictional'||!text(value.title,1,300)||!text(value.licence,1,128)||!safeFictionalEvidenceLink(value.link)||
  !hash(value.metadata_sha256)||value.availability!=='metadata_only'||value.rights_status!=='granted')throw Error('evidence record');
 return Object.freeze({...value} as QuestionEvidenceRecord);
}
function scoped(value:Record<string,unknown>,patient:string,caseId:string,questionId:string):boolean{
 return value.patient_id===patient&&value.case_id===caseId&&value.question_id===questionId&&opaque(questionId,'QUESTION-')&&
  opaque(value.source_access_receipt_id,'ACCESS-')&&
  ['current_unreviewed_question','source_reassessment_required'].includes(String(value.source_context_state))&&
  value.synthetic===true&&value.model_executed===false&&value.content_appraised===false&&value.clinical_approval===false;
}
export function decodeQuestionEvidenceSearch(value:unknown,patient:string,caseId:string,questionId:string,query:string):QuestionEvidenceSearch{
 if(!exact(value,[...scopeFields,'query','records'])||value.contract!=='oi.pg-question-evidence-search/1'||
  !scoped(value,patient,caseId,questionId)||value.query!==query||!validEvidenceQuery(value.query)||
  !Array.isArray(value.records)||value.records.length>25)throw Error('evidence search');
 const seen=new Set<string>();
 const records=Object.freeze(value.records.map((row:unknown)=>{
  const record=decodeRecord(row);if(seen.has(record.citation))throw Error('duplicate citation');seen.add(record.citation);return record;
 }));
 return Object.freeze({...value,records} as QuestionEvidenceSearch);
}
export function decodeQuestionEvidenceLinks(value:unknown,patient:string,caseId:string,questionId:string):QuestionEvidenceLinks{
 if(!exact(value,[...scopeFields,'links'])||value.contract!=='oi.pg-question-evidence-links/1'||
  !scoped(value,patient,caseId,questionId)||!Array.isArray(value.links)||value.links.length>100)throw Error('evidence links');
 const seen=new Set<string>();
 const links=Object.freeze(value.links.map((row:unknown)=>{
  if(!exact(row,['link_id','citation','metadata_sha256','created_at','actor_label','status','record'])||
   !opaque(row.link_id,'EVIDENCE-LINK-')||seen.has(row.link_id)||!citation(row.citation)||!hash(row.metadata_sha256)||
   !instant(row.created_at)||!text(row.actor_label,3,128)||!(/^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$/).test(row.actor_label)||
   !['available','rights_restricted','superseded','unavailable'].includes(String(row.status)))throw Error('evidence link');
  seen.add(row.link_id);
  const record=row.status==='available'?decodeRecord(row.record):null;
  if(record?(record.citation!==row.citation||record.metadata_sha256!==row.metadata_sha256):row.record!==null)
   throw Error('evidence link identity or redaction');
  return Object.freeze({...row,record} as QuestionEvidenceLink);
 }));
 return Object.freeze({...value,links} as QuestionEvidenceLinks);
}
export function decodeQuestionEvidenceReceipt(value:unknown,intent:QuestionEvidenceIntent):QuestionEvidenceReceipt{
 if(!exact(value,['link_id','citation','metadata_sha256','duplicate'])||!opaque(value.link_id,'EVIDENCE-LINK-')||
  value.citation!==intent.body.citation||value.metadata_sha256!==intent.body.expected_metadata_sha256||
  typeof value.duplicate!=='boolean')throw Error('evidence receipt');
 return Object.freeze({...value} as QuestionEvidenceReceipt);
}

export type PassageReviewSelection=Readonly<{
 source_id:string;document_id:string;source_version:number;original_sha256:string;
 annotation_revision_id:string;annotation_revision:number;review_sha256:string;
 selected_by:string;selected_at:string;selected_state:string;quote:string;line:number;
 page:number|null;classification_origin:'user_selected';clinical_review:'not_performed';
 anchor_sha256:string;selection_state:'current_unreviewed_selection'|'selection_reassessment_required';
}>;
export type PassageReviewPreparation=EvidenceScope&Readonly<{
 contract:'oi.pg-passage-review-preparation/1';source_id:string;question_text:string;
 selection:PassageReviewSelection;links:readonly QuestionEvidenceLink[];
 human_review_state:'not_performed';
 next_step:'independent_verification_required'|'source_reassessment_required';
 packet_sha256:string;
}>;
const passageSelectionFields=['source_id','document_id','source_version','original_sha256',
 'annotation_revision_id','annotation_revision','review_sha256','selected_by','selected_at',
 'selected_state','quote','line','page','classification_origin','clinical_review',
 'anchor_sha256','selection_state'];
export function decodePassageReviewPreparation(value:unknown,patient:string,caseId:string,
 source:string,questionId:string,expectedAnchor:string,expectedQuestion:string,
 expectedQuote:string,expectedLine:number,expectedRevision:number):PassageReviewPreparation{
 if(!exact(value,[...scopeFields,'source_id','question_text','selection','links',
      'human_review_state','next_step','packet_sha256'])||
  value.contract!=='oi.pg-passage-review-preparation/1'||
  !scoped(value,patient,caseId,questionId)||value.source_id!==source||
  !opaque(value.source_id,'SRC-')||value.question_text!==expectedQuestion||
  !text(value.question_text,8,500)||value.human_review_state!=='not_performed'||
  !hash(value.packet_sha256))throw Error('passage review preparation');
 const selection=value.selection;
 if(!exact(selection,passageSelectionFields)||selection.source_id!==source||
   !text(selection.document_id,2,40)||typeof selection.source_version!=='number'||!Number.isInteger(selection.source_version)||selection.source_version<1||
   !hash(selection.original_sha256)||!opaque(selection.annotation_revision_id,'ANN-')||
   typeof selection.annotation_revision!=='number'||!Number.isInteger(selection.annotation_revision)||selection.annotation_revision<1||
   !hash(selection.review_sha256)||!text(selection.selected_by,3,128)||
   !instant(selection.selected_at)||typeof selection.quote!=='string'||
   selection.quote.length<1||selection.quote.length>1200||selection.quote!==expectedQuote||
   selection.line!==expectedLine||selection.annotation_revision!==expectedRevision||
   typeof selection.line!=='number'||!Number.isInteger(selection.line)||selection.line<1||selection.line>512||
   !(selection.page===null||(Number.isInteger(selection.page)&&Number(selection.page)>=1))||
   !['reported','negative','pending','indeterminate','not-reported','not-assessed','conflicting'].includes(String(selection.selected_state))||
   selection.classification_origin!=='user_selected'||selection.clinical_review!=='not_performed'||
   !hash(selection.anchor_sha256)||selection.anchor_sha256!==expectedAnchor||
   !['current_unreviewed_selection','selection_reassessment_required'].includes(String(selection.selection_state)))
  throw Error('passage review selection');
 const current=value.source_context_state==='current_unreviewed_question';
 if((selection.selection_state==='current_unreviewed_selection')!==current||
  value.next_step!==(current?'independent_verification_required':'source_reassessment_required'))
  throw Error('stale passage review status');
 const linked=decodeQuestionEvidenceLinks({
  ...Object.fromEntries(scopeFields.map(k=>[k,value[k]])),
  contract:'oi.pg-question-evidence-links/1',links:value.links
 },patient,caseId,questionId);
 return Object.freeze({...value,selection:Object.freeze({...selection}),
  links:linked.links} as PassageReviewPreparation);
}
