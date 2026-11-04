/** Source-qualified metadata projections. A citation link is not a claim assessment. */
export type EvidenceSourceState='current_unreviewed_question'|'source_reassessment_required';
type EvidenceRecordBase=Readonly<{
 citation:string;id:string;version:string;title:string;licence:string;link:string;
 metadata_sha256:string;availability:'metadata_only';rights_status:'granted';
}>;
export type CrossrefBibliography=Readonly<{
 doi:string;journal:string|null;year:number|null;publication_type:string|null;authors:readonly string[];
 retrieved_at:string;record_url:string;rights_basis:string;access_policy:string;
 adapter_version:'oi.crossref-metadata/1';projection_sha256:string;
 acquisition_mode:'provider_lookup'|'protocol_fixture';
}>;
export type QuestionEvidenceRecord=EvidenceRecordBase&(
 Readonly<{source_kind:'fictional'}>|Readonly<{source_kind:'crossref';bibliography:CrossrefBibliography}>);
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
const bibliographyFields=['doi','journal','year','publication_type','authors','retrieved_at','record_url',
 'rights_basis','access_policy','adapter_version','projection_sha256','acquisition_mode'];
const CROSSREF_RIGHTS='https://www.crossref.org/documentation/retrieve-metadata/';
const CROSSREF_ACCESS='https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/';
const CROSSREF_LICENCE='Crossref factual bibliographic metadata; article rights not granted';
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
 if(!text(value,1,265))return false;
 const parts=value.split('@');
 return parts.length===2&&(
  (parts[0].length<=128&&/^FICT-[A-Z0-9-]+$/.test(parts[0])&&parts[1].length<=64&&/^[A-Za-z0-9._-]+$/.test(parts[1]))||
  (normalizePublicDoi(parts[0])===parts[0]&&hash(parts[1])));
}
function instant(value:unknown):value is string{
 if(!text(value,1,64)||!/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value)||!Number.isFinite(Date.parse(value)))return false;
 const date=value.slice(0,10),time=Date.parse(date+'T00:00:00Z');
 return Number.isFinite(time)&&new Date(time).toISOString().slice(0,10)===date;
}
export function validEvidenceQuery(value:unknown):value is string{return text(value,1,200);}
/** An explicit public identifier only. Syntax validation is not a privacy detector. */
export function normalizePublicDoi(value:unknown):string|null{
 if(!text(value,1,200)||!/^10\.[0-9]{4,9}\/[A-Za-z0-9._;()/+\-]{1,200}$/.test(value))return null;
 const doi=value.toLowerCase();
 return ('https://doi.org/'+encodedDoi(doi)).length<=512?doi:null;
}
function encodedDoi(doi:string):string{
 // Match the existing Python adapter's quote(doi, safe=''), including parentheses.
 return encodeURIComponent(doi).replace(/[!'()*]/g,ch=>'%'+ch.charCodeAt(0).toString(16).toUpperCase());
}
export function safeDoiEvidenceLink(value:unknown,doi:unknown):value is string{
 return typeof doi==='string'&&normalizePublicDoi(doi)===doi&&value==='https://doi.org/'+encodedDoi(doi);
}
function retrievedInstant(value:unknown):value is string{
 if(!text(value,1,64))return false;
 const match=/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(?:Z|[+-](\d{2}):(\d{2}))$/.exec(value);
 if(!match||Number(match[2])>23||Number(match[3])>59||Number(match[4])>59||
  (match[5]!==undefined&&(Number(match[5])>14||Number(match[6])>59||(Number(match[5])===14&&Number(match[6])!==0))))return false;
 const date=Date.parse(match[1]+'T00:00:00Z'),utc=Date.parse(value),utcYear=new Date(utc).getUTCFullYear();
 return Number(match[1].slice(0,4))>=1&&Number.isFinite(date)&&new Date(date).toISOString().slice(0,10)===match[1]&&
  Number.isFinite(utc)&&utcYear>=1&&utcYear<=9999;
}
/** This synthetic catalog has no live biomedical or patient links. */
export function safeFictionalEvidenceLink(value:unknown):value is string{
 if(!text(value,1,512)||!/^https:\/\/example\.invalid\/fictional\/[A-Za-z0-9._/-]+$/.test(value))return false;
 try{const url=new URL(value);return url.href===value&&url.protocol==='https:'&&url.host==='example.invalid'&&
  url.username===''&&url.password===''&&url.search===''&&url.hash===''&&url.pathname.startsWith('/fictional/');}
 catch{return false;}
}
function decodeRecord(value:unknown):QuestionEvidenceRecord{
 if(!exact(value,recordFields)&&!exact(value,[...recordFields,'bibliography']))throw Error('evidence record');
 if(!citation(value.citation)||value.citation!==value.id+'@'+value.version||
  !hash(value.metadata_sha256)||value.availability!=='metadata_only'||value.rights_status!=='granted')throw Error('evidence record');
 if(value.source_kind==='fictional'){
  if(!exact(value,recordFields)||!text(value.id,1,128)||!/^FICT-[A-Z0-9-]+$/.test(value.id)||
   !text(value.version,1,64)||!(/^[A-Za-z0-9._-]+$/).test(value.version)||
   !text(value.title,1,300)||!text(value.licence,1,128)||!safeFictionalEvidenceLink(value.link))throw Error('fictional evidence');
  return Object.freeze({...value} as QuestionEvidenceRecord);
 }
 if(value.source_kind!=='crossref'||!exact(value,[...recordFields,'bibliography'])||
  normalizePublicDoi(value.id)!==value.id||!hash(value.version)||!text(value.title,1,500)||
  value.licence!==CROSSREF_LICENCE||!safeDoiEvidenceLink(value.link,value.id))throw Error('Crossref evidence');
 const b=value.bibliography;
 if(!exact(b,bibliographyFields)||b.doi!==value.id||b.projection_sha256!==value.version||
  b.record_url!=='https://api.crossref.org/works/'+encodedDoi(String(value.id))||b.rights_basis!==CROSSREF_RIGHTS||
  b.access_policy!==CROSSREF_ACCESS||b.adapter_version!=='oi.crossref-metadata/1'||
  (b.acquisition_mode!=='provider_lookup'&&b.acquisition_mode!=='protocol_fixture')||!retrievedInstant(b.retrieved_at)||
  !(b.journal===null||text(b.journal,1,300))||!(b.publication_type===null||text(b.publication_type,1,90))||
  !(b.year===null||(typeof b.year==='number'&&Number.isInteger(b.year)&&b.year>=1500&&b.year<=2200))||
  !Array.isArray(b.authors)||b.authors.length>100||!b.authors.every(author=>text(author,1,150)))throw Error('Crossref bibliography');
 const bibliography=Object.freeze({...b,authors:Object.freeze([...b.authors])}) as CrossrefBibliography;
 return Object.freeze({...value,bibliography} as QuestionEvidenceRecord);
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
