/** Exact read-only contracts from the existing H1 PostgreSQL API.
 * Never infer clinical truth or consent from source-reported text.
 */
export type CaseBinding = Readonly<{
  case_id:string; patient_id:string; source_organization:string;
  source_system:string; source_subject_ref:string; review_ref:string;
  status:'active'|'revoked'; revision:number; created_at:string;
  revoked_at:string|null; source_identity_verified:false;
  clinical_sources_linked:false; clinical_conclusions:false;
}>;
export type SourceVersion = Readonly<{
  source_id:string; document_id:string; version:number; sha256:string;
  kind:string; event_date:string; issued_at:string; received_at:string;
  specimen_id:string|null; state:'current'|'superseded';
  supersedes_id:string|null;
}>;
export type ReportedOncologyContext = Readonly<{
  role:'primary'|'metastasis'; episode_id:string|null;
}>;
export type SourceFinding = Readonly<{
  oncology?:ReportedOncologyContext;
  source_id:string; finding_key:string; reported_state:string;
  source_statement:string; source_line:number; clinical_review_state:'not_established';
}>;
export type SourceIndex = Readonly<{
  contract:'oi.synthetic-original-sources/1'; patient_id:string; case_id:string; access_receipt_id:string;
  sources:ReadonlyArray<SourceVersion>;
  source_reported_assertions:ReadonlyArray<SourceFinding>;
  synthetic:true; clinical_interpretation:false;
  research_review_invalidation_integrated:false;
}>;
const PATIENT=/^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$/;
const CASE=/^CASE-[A-Z0-9-]{1,35}$/;
const SOURCE=/^SRC-[0-9A-F]{32}$/;
const SHA=/^[a-f0-9]{64}$/;
const RECEIPT=/^ACCESS-[0-9A-F]{32}$/;
function exact(v:unknown,keys:readonly string[]):v is Record<string,unknown>{
  return v!==null && typeof v==='object' && !Array.isArray(v) &&
    Object.keys(v).length===keys.length && keys.every(k=>Object.hasOwn(v,k));
}
export function parseOncologyContext(value:unknown):ReportedOncologyContext {
  if(!exact(value,['role','episode_id']) || (value.role!=='primary' && value.role!=='metastasis') ||
     !(value.episode_id===null || (typeof value.episode_id==='string' &&
       /^EP-[A-Z0-9][A-Z0-9-]{0,35}$/.test(value.episode_id) && value.episode_id.trim()===value.episode_id))) {
    throw Error('Invalid source oncology attribution');
  }
  return Object.freeze({role:value.role,episode_id:value.episode_id});
}
function str(v:unknown,max=256):v is string{
  return typeof v==='string' && v.length>0 && v.length<=max &&
    !/[\u0000-\u001f\u007f]/.test(v);
}
function optional(v:unknown,max=256):v is string|null{
  return v===null || str(v,max);
}
function positive(v:unknown):v is number{
  return typeof v==='number' && Number.isSafeInteger(v) && v>=1;
}
function timestamp(v:unknown):v is string{
  return str(v,80) && /^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(v) &&
    Number.isFinite(Date.parse(v));
}
function day(v:unknown):v is string{
  return str(v,10) && /^\d{4}-\d{2}-\d{2}$/.test(v);
}
export function parseCaseBindingList(v:unknown,expectedPatient:string):ReadonlyArray<CaseBinding>{
  if(!PATIENT.test(expectedPatient) ||
    !exact(v,['patient_id','mappings','synthetic','source_identity_verified','clinical_sources_linked']) ||
    v.patient_id!==expectedPatient || v.synthetic!==true ||
    v.source_identity_verified!==false || v.clinical_sources_linked!==false ||
    !Array.isArray(v.mappings) || v.mappings.length>256) throw Error('contract');
  const result:CaseBinding[]=[];const seen=new Set<string>();
  for(const raw of v.mappings){
    if(!exact(raw,['case_id','patient_id','source_organization','source_system',
      'source_subject_ref','review_ref','status','revision','created_at',
      'revoked_at','source_identity_verified','clinical_sources_linked','clinical_conclusions']) ||
      typeof raw.case_id!=='string' || !CASE.test(raw.case_id) ||
      seen.has(raw.case_id) || raw.patient_id!==expectedPatient ||
      !str(raw.source_organization,128) || !str(raw.source_system,128) ||
      !str(raw.source_subject_ref,128) || !str(raw.review_ref,128) ||
      !['active','revoked'].includes(String(raw.status)) || !positive(raw.revision) ||
      !timestamp(raw.created_at) || !(raw.revoked_at===null || timestamp(raw.revoked_at)) ||
      raw.source_identity_verified!==false || raw.clinical_sources_linked!==false ||
      raw.clinical_conclusions!==false) throw Error('contract');
    seen.add(raw.case_id);result.push(Object.freeze(raw as CaseBinding));
  }
  return Object.freeze(result);
}
export function sourceIndexPath(patientId:string,caseId:string):string{
  return '/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+encodeURIComponent(caseId)+'/sources';
}
export function parseSourceIndex(v:unknown,expectedPatient:string,expectedCase:string):SourceIndex{
  if(!PATIENT.test(expectedPatient) || !CASE.test(expectedCase) ||
    !exact(v,['contract','patient_id','case_id','access_receipt_id','sources','source_reported_assertions',
      'synthetic','clinical_interpretation','research_review_invalidation_integrated']) ||
    v.contract!=='oi.synthetic-original-sources/1' ||
    v.patient_id!==expectedPatient || v.case_id!==expectedCase ||
    typeof v.access_receipt_id!=='string' || !RECEIPT.test(v.access_receipt_id) ||
    v.synthetic!==true || v.clinical_interpretation!==false ||
    v.research_review_invalidation_integrated!==false ||
    !Array.isArray(v.sources) || v.sources.length>256 ||
    !Array.isArray(v.source_reported_assertions) ||
    v.source_reported_assertions.length>512) throw Error('contract');
  const versions:SourceVersion[]=[];const seen=new Set<string>(),current=new Set<string>();
  for(const raw of v.sources){
    if(!exact(raw,['source_id','document_id','version','sha256','kind','event_date',
      'issued_at','received_at','specimen_id','state','supersedes_id']) ||
      typeof raw.source_id!=='string' || !SOURCE.test(raw.source_id) ||
      seen.has(raw.source_id) || !str(raw.document_id,128) ||
      !positive(raw.version) || typeof raw.sha256!=='string' || !SHA.test(raw.sha256) ||
      !['clinical','pathology','laboratory','imaging','molecular','other'].includes(String(raw.kind)) ||
      !day(raw.event_date) || !day(raw.issued_at) || !timestamp(raw.received_at) ||
      !optional(raw.specimen_id,128) ||
      !['current','superseded'].includes(String(raw.state)) ||
      !(raw.supersedes_id===null || (typeof raw.supersedes_id==='string' && SOURCE.test(raw.supersedes_id)))) throw Error('contract');
    seen.add(raw.source_id);
    if(raw.state==='current')current.add(raw.source_id);
    versions.push(Object.freeze(raw as SourceVersion));
  }
  const findings:SourceFinding[]=[];
  for(const raw of v.source_reported_assertions){
    const typed=raw!==null && typeof raw==='object' && Object.hasOwn(raw,'oncology');
    if(!exact(raw,['source_id','finding_key','reported_state','source_statement',
      'source_line','clinical_review_state',...(typed?['oncology']:[])]) ||
      typeof raw.source_id!=='string' || !current.has(raw.source_id) ||
      !str(raw.finding_key,128) || !str(raw.reported_state,128) ||
      !str(raw.source_statement,8192) || !positive(raw.source_line) ||
      raw.clinical_review_state!=='not_established') throw Error('contract');
    findings.push(Object.freeze({...raw,...(typed?{oncology:parseOncologyContext(raw.oncology)}:{})} as SourceFinding));
  }
  return Object.freeze({
    contract:'oi.synthetic-original-sources/1',patient_id:expectedPatient,case_id:expectedCase,
    access_receipt_id:v.access_receipt_id as string,
    sources:Object.freeze(versions),source_reported_assertions:Object.freeze(findings),
    synthetic:true,clinical_interpretation:false,
    research_review_invalidation_integrated:false,
  });
}
