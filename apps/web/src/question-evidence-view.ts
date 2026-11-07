/** Fictional metadata projections. A citation link is not a claim assessment. */
import type {SavedLabQuestion} from './laboratory-question.js';
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
 patient_id:string;case_id:string;question_id:string;laboratoryAnchor?:LaboratoryEvidenceAnchor;
 body:Readonly<{synthetic:true;request_key:string;citation:string;expected_metadata_sha256:string;
  source_snapshot_contract:'oi.pg-source-world-model/1';expected_source_snapshot_sha256:string;expected_preflight_sha256:string}>;
}>;
const labAnchorFields=['source_id','source_version','source_sha256','observation_reference','source_snapshot_sha256','preflight_sha256'] as const;
type LaboratoryEvidenceAnchor=Pick<SavedLabQuestion,typeof labAnchorFields[number]>;
export function laboratoryEvidenceAnchor(row:SavedLabQuestion):LaboratoryEvidenceAnchor{
 return Object.freeze({source_id:row.source_id,source_version:row.source_version,source_sha256:row.source_sha256,
  observation_reference:row.observation_reference,source_snapshot_sha256:row.source_snapshot_sha256,preflight_sha256:row.preflight_sha256});
}
export function matchesLaboratoryEvidenceAnchor(value:unknown,expected:LaboratoryEvidenceAnchor):boolean{
 return exact(value,labAnchorFields)&&labAnchorFields.every(field=>value[field]===expected[field]);
}
/** Both modalities use the same catalog projection; only a laboratory response
 * must also identify the exact selected Observation and preserved question context. */
export function unwrapLaboratoryEvidence(raw:unknown,question:SavedLabQuestion,search:boolean):unknown{
 if(raw===null||typeof raw!=='object'||Array.isArray(raw))throw Error('laboratory evidence');
 const {question_anchor,...metadata}=raw as Record<string,unknown>;
 if(!matchesLaboratoryEvidenceAnchor(question_anchor,question)||
  (search&&metadata.source_context_state!=='current_unreviewed_question')||
  (question.source_context_state==='source_reassessment_required'&&metadata.source_context_state!==question.source_context_state))
  throw Error('laboratory evidence scope');
 return metadata;
}
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
