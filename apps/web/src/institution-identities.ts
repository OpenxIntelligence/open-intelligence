/** Exact synthetic identity-review contracts. A linked tuple is not verified identity. */
export type InstitutionIdentity=Readonly<{identity_id:string;source_organization:string;source_system:string;
  source_subject_ref:string;primary_identity:boolean;status:'quarantined'|'active'|'rejected';review_ref:string|null}>;
export type InstitutionCommand=Readonly<{body:string;identityId?:string}>;
const exact=(v:unknown,keys:string[]):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v)&&
  Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
const label=(v:unknown):v is string=>typeof v==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$/.test(v);
export function parseInstitution(v:unknown):InstitutionIdentity{
  if(!exact(v,['identity_id','source_organization','source_system','source_subject_ref','primary_identity','status','review_ref'])||
    typeof v.identity_id!=='string'||!/^IDENTITY-[A-F0-9]{32}$/.test(v.identity_id)||
    !label(v.source_organization)||!label(v.source_system)||!label(v.source_subject_ref)||
    typeof v.primary_identity!=='boolean'||!['quarantined','active','rejected'].includes(String(v.status))||
    (v.status==='quarantined'?v.review_ref!==null:!label(v.review_ref))||
    (v.primary_identity&&v.status!=='active'))throw Error('Invalid institution identity response');
  return Object.freeze(v as InstitutionIdentity);
}
export function parseInstitutions(v:unknown,patientId:string,caseId:string):readonly InstitutionIdentity[]{
  if(!exact(v,['patient_id','case_id','identities','source_identity_verified'])||v.patient_id!==patientId||
    v.case_id!==caseId||v.source_identity_verified!==false||!Array.isArray(v.identities)||v.identities.length>100)
    throw Error('Invalid institution list');
  const rows=v.identities.map(parseInstitution);
  if(new Set(rows.map(i=>i.identity_id)).size!==rows.length)throw Error('Repeated identity');
  return Object.freeze(rows);
}
export function parseInstitutionReceipt(v:unknown):InstitutionIdentity{
  if(!exact(v,['identity','duplicate','source_identity_verified'])||typeof v.duplicate!=='boolean'||
    v.source_identity_verified!==false)throw Error('Invalid identity receipt');
  return parseInstitution(v.identity);
}
export function parseSourceInstitution(v:unknown,patientId:string,caseId:string,sourceId:string,documentId:string,sha:string){
  if(!exact(v,['patient_id','case_id','source_id','document_id','sha256','source_organization','source_system',
      'subject_reference','report_reference','source_identity_verified'])||
    v.patient_id!==patientId||v.case_id!==caseId||v.source_id!==sourceId||v.document_id!==documentId||v.sha256!==sha||
    !label(v.source_organization)||!label(v.source_system)||v.source_identity_verified!==false||
    typeof v.subject_reference!=='string'||!/^Patient\/[A-Za-z0-9.-]{1,64}$/.test(v.subject_reference)||
    typeof v.report_reference!=='string'||!/^DiagnosticReport\/[A-Z][A-Z0-9-]{1,39}$/.test(v.report_reference))
    throw Error('Invalid source institution');
  return {subject:v.subject_reference,report:v.report_reference,organization:v.source_organization,system:v.source_system};
}
