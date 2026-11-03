/** Read-only, fail-closed decoding of the existing H1 PostgreSQL source contracts.
 * This client never creates patient/source authority, extracts clinical meaning,
 * or treats a source-reported finding as a reviewed medical conclusion.
 */
export type BoundCase=Readonly<{
  case_id:string; patient_id:string; status:'active'|'revoked';
  source_organization:string; source_system:string; revision:number;
}>;
export type SourceVersion=Readonly<{
  source_id:string; document_id:string; version:number; sha256:string;
  kind:'clinical'|'pathology'|'laboratory'|'imaging'|'molecular'|'other';
  event_date:string; issued_at:string; received_at:string; specimen_id:string|null;
  state:'current'|'superseded'; supersedes_id:string|null;
}>;
export type SourceStatement=Readonly<{
  source_id:string; finding_key:string; reported_state:string;
  source_statement:string; source_line:number; clinical_review_state:'not_established';
}>;
export type SourceIndex=Readonly<{
  patient_id:string; case_id:string; sources:readonly SourceVersion[];
  source_reported_assertions:readonly SourceStatement[];
}>;
export type OriginalSource=Readonly<{
  source_id:string; case_id:string; document_id:string; version:number;
  state:'current'|'superseded'; sha256:string; original_text:string;
}>;
const CASE=/^CASE-[A-Z0-9-]{1,35}$/;
const SOURCE=/^SRC-[0-9A-F]{32}$/;
const SHA=/^[0-9a-f]{64}$/;
const DATE=/^\d{4}-\d{2}-\d{2}$/;
const TYPES=new Set(['clinical','pathology','laboratory','imaging','molecular','other']);
function fail():never{throw new Error('source-contract');}
function object(value:unknown,fields:readonly string[]):Record<string,unknown>{
  if(value===null||typeof value!=='object'||Array.isArray(value))return fail();
  const entry=value as Record<string,unknown>;
  if(Object.keys(entry).length!==fields.length||fields.some(k=>!Object.hasOwn(entry,k)))return fail();
  return entry;
}
function string(value:unknown,max=256):string{
  if(typeof value!=='string'||!value.length||value.length>max)return fail();
  return value;
}
function id(value:unknown,pattern:RegExp):string{const v=string(value,128);if(!pattern.test(v))return fail();return v;}
function positive(value:unknown):number{
  if(typeof value!=='number'||!Number.isSafeInteger(value)||value<1)return fail();return value;
}
function date(value:unknown):string{
  const v=string(value,10);if(!DATE.test(v)||!Number.isFinite(Date.parse(v+'T00:00:00Z')))return fail();return v;
}
function timestamp(value:unknown):string{
  const v=string(value,64);
  if(!/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(v)||!Number.isFinite(Date.parse(v)))return fail();
  return v;
}
function status(value:unknown):'current'|'superseded'{
  if(value!=='current'&&value!=='superseded')return fail();return value;
}
function sha(value:unknown):string{const v=string(value,64);if(!SHA.test(v))return fail();return v;}
function sameId(value:unknown,expected:string):string{if(value!==expected)return fail();return expected;}
export function validCaseId(value:string):boolean{return CASE.test(value);}
export function validSourceId(value:string):boolean{return SOURCE.test(value);}

export function decodeCases(raw:unknown,patientId:string):readonly BoundCase[]{
  const response=object(raw,['patient_id','mappings','synthetic','source_identity_verified','clinical_sources_linked']);
  sameId(response.patient_id,patientId);
  if(response.synthetic!==true||response.source_identity_verified!==false||response.clinical_sources_linked!==false||!Array.isArray(response.mappings))return fail();
  if(response.mappings.length>256)return fail();
  const seen=new Set<string>();
  const items=response.mappings.map(v=>{
    const r=object(v,['case_id','patient_id','source_organization','source_system','source_subject_ref','review_ref','status','revision','created_at','revoked_at','source_identity_verified','clinical_sources_linked','clinical_conclusions']);
    const case_id=id(r.case_id,CASE);sameId(r.patient_id,patientId);
    if(seen.has(case_id)||!['active','revoked'].includes(String(r.status))||r.source_identity_verified!==false||r.clinical_sources_linked!==false||r.clinical_conclusions!==false)return fail();
    seen.add(case_id);
    const created_at=timestamp(r.created_at);
    if(r.revoked_at!==null)timestamp(r.revoked_at);
    if((r.status==='active')!==(r.revoked_at===null))return fail();
    string(r.source_subject_ref,128);string(r.review_ref,128);
    return Object.freeze({case_id,patient_id:patientId,status:r.status as 'active'|'revoked',
      source_organization:string(r.source_organization,128),source_system:string(r.source_system,128),
      revision:positive(r.revision)});
  });
  return Object.freeze(items);
}

export function decodeSources(raw:unknown,patientId:string,caseId:string):SourceIndex{
  const response=object(raw,['contract','patient_id','case_id','sources','source_reported_assertions','synthetic','clinical_interpretation','research_review_invalidation_integrated']);
  sameId(response.patient_id,patientId);sameId(response.case_id,caseId);
  if(response.contract!=='oi.synthetic-original-sources/1'||response.synthetic!==true||
     response.clinical_interpretation!==false||response.research_review_invalidation_integrated!==false||
     !Array.isArray(response.sources)||!Array.isArray(response.source_reported_assertions)||
     response.sources.length>512||response.source_reported_assertions.length>2048)return fail();
  const ids=new Set<string>();
  const sources=response.sources.map(v=>{
    const s=object(v,['source_id','document_id','version','sha256','kind','event_date','issued_at','received_at','specimen_id','state','supersedes_id']);
    const source_id=id(s.source_id,SOURCE);
    if(ids.has(source_id))return fail();ids.add(source_id);
    if(!TYPES.has(String(s.kind)))return fail();
    if(s.supersedes_id!==null)id(s.supersedes_id,SOURCE);
    if(s.specimen_id!==null)string(s.specimen_id,128);
    return Object.freeze({source_id,document_id:string(s.document_id,128),version:positive(s.version),
      sha256:sha(s.sha256),kind:s.kind as SourceVersion['kind'],event_date:date(s.event_date),
      issued_at:date(s.issued_at),received_at:timestamp(s.received_at),specimen_id:s.specimen_id as string|null,
      state:status(s.state),supersedes_id:s.supersedes_id as string|null});
  });
  const currentIds=new Set(sources.filter(s=>s.state==='current').map(s=>s.source_id));
  const assertions=response.source_reported_assertions.map(v=>{
    const a=object(v,['source_id','finding_key','reported_state','source_statement','source_line','clinical_review_state']);
    const source_id=id(a.source_id,SOURCE);
    if(!currentIds.has(source_id)||a.clinical_review_state!=='not_established')return fail();
    return Object.freeze({source_id,finding_key:string(a.finding_key,128),
      reported_state:string(a.reported_state,128),source_statement:string(a.source_statement,65536),
      source_line:positive(a.source_line),clinical_review_state:'not_established' as const});
  });
  return Object.freeze({patient_id:patientId,case_id:caseId,
    sources:Object.freeze(sources),source_reported_assertions:Object.freeze(assertions)});
}

export async function decodeOriginal(raw:unknown,index:SourceIndex,sourceId:string):Promise<OriginalSource>{
  const record=object(raw,['source_id','case_id','document_id','version','state','sha256','original_text','synthetic','clinical_review_state']);
  sameId(record.source_id,sourceId);sameId(record.case_id,index.case_id);
  const known=index.sources.find(s=>s.source_id===sourceId);
  if(!known||record.synthetic!==true||record.clinical_review_state!=='not_established')return fail();
  const text=string(record.original_text,65536);
  const bytes=new TextEncoder().encode(text);
  if(bytes.byteLength>65536)return fail();
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)))
    .map(b=>b.toString(16).padStart(2,'0')).join('');
  if(digest!==known.sha256||sha(record.sha256)!==digest||
     record.document_id!==known.document_id||record.version!==known.version||
     status(record.state)!==known.state)return fail();
  return Object.freeze({source_id:sourceId,case_id:index.case_id,document_id:known.document_id,
    version:known.version,state:known.state,sha256:digest,original_text:text});
}
