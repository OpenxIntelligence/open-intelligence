import type {SavedLabQuestion} from './laboratory-question.js';
import {isLaboratoryAbsentReason,type SourceWorldModel} from './source-world-model.js';
import {decodeQuestionEvidenceLinks,unwrapLaboratoryEvidence} from './question-evidence-view.js';
import type {QuestionEvidenceLinks} from './question-evidence-view.js';
import {citationEvidenceTimestamp} from './evidence-timestamp.js';

export type LaboratoryReportedResult=Readonly<{
  anchor_kind:'fhir_observation';kind:'laboratory';resource_reference:string;source_id:string;version:number;sha256:string;
  report_reference:string;document_id:string;specimen_reference:string;specimen_type_text:string;
  specimen_collected_at:string;effective_at:string;issued_at:string;loinc_code:string;
  status:'reported_value'|'reported_absent';value_text:string|null;unit_code:string|null;absent_reason:string|null;
  source_reported:true;review_state:'not_established';clinical_review:'not_performed';
}>;
export type LaboratoryInspection=Readonly<{
  question:string;result:LaboratoryReportedResult;citations:QuestionEvidenceLinks;
}>;
function exact(v:unknown,keys:string[]):v is Record<string,unknown>{
  return !!v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
}
const visible=(v:unknown,n:number):v is string=>typeof v==='string'&&v.length>0&&[...v].length<=n&&!/[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/u.test(v);
const sameInstant=(a:string,b:string)=>a.replace(/\+00:00$/,'Z')===b.replace(/\+00:00$/,'Z');

/** Decode against the selected row and the authorized source *version*. History
 * need not be in today's Observation list; only the server can recover its value. */
export function readLaboratoryCitationReport(raw:unknown,model:SourceWorldModel,q:SavedLabQuestion):LaboratoryInspection{
  if(!exact(raw,['contract','question','reported_result','citations','clinical_review','claim_appraisal'])||
    raw.contract!=='oi.laboratory-source-citation-inspection/1'||raw.question!==q.question||
    raw.clinical_review!=='not_performed'||raw.claim_appraisal!=='not_performed')throw Error('Invalid report');
  const citations=decodeQuestionEvidenceLinks(unwrapLaboratoryEvidence(raw.citations,q,false),model.patient_id,model.case_id,q.question_id);
  const r=raw.reported_result,source=[...model.current_sources,...model.history].find(x=>x.source_id===q.source_id);
  if(!source||source.kind!=='laboratory'||source.version!==q.source_version||source.sha256!==q.source_sha256||
    (citations.source_context_state==='current_unreviewed_question'&&(source.state!=='current'||model.snapshot_fingerprint!==q.source_snapshot_sha256))||
    !exact(r,['source_id','sha256','version','document_id','resource_reference','report_reference','specimen_reference',
      'specimen_type_text','specimen_collected_at','effective_at','issued_at','loinc_code','source_reported','clinical_review',
      'review_state','kind','anchor_kind','status','value_text','unit_code','absent_reason'])||
    r.source_id!==q.source_id||r.sha256!==q.source_sha256||r.version!==q.source_version||
    r.document_id!==source.document_id||r.resource_reference!==q.observation_reference||
    (!/^F-[A-F0-9]{32}$/.test(source.document_id)?r.report_reference!=='DiagnosticReport/'+source.document_id:
      typeof r.report_reference!=='string'||!/^DiagnosticReport\/[A-Z][A-Z0-9-]{1,39}$/.test(r.report_reference))||!source.specimen_id||r.specimen_reference!=='Specimen/'+source.specimen_id||
    !visible(r.specimen_type_text,100)||!visible(r.loinc_code,8)||!/^\d{1,6}-\d$/.test(r.loinc_code)||
    !citationEvidenceTimestamp(r.specimen_collected_at)||!citationEvidenceTimestamp(r.effective_at)||!citationEvidenceTimestamp(r.issued_at)||
    r.source_reported!==true||r.clinical_review!=='not_performed'||r.review_state!=='not_established'||
    r.kind!=='laboratory'||r.anchor_kind!=='fhir_observation')throw Error('Invalid original result');
  if(r.status==='reported_value'){
    if(!visible(r.value_text,64)||!(/^-?\d+(?:\.\d+)?$/).test(r.value_text)||!visible(r.unit_code,32)||r.absent_reason!==null)
      throw Error('Invalid reported measurement');
  }else if(r.status!=='reported_absent'||r.value_text!==null||r.unit_code!==null||
      !isLaboratoryAbsentReason(r.absent_reason))throw Error('Invalid reported absence');
  const current=model.laboratory_observations.find(o=>o.source_id===q.source_id&&o.observation_reference===q.observation_reference);
  if((source.state==='current'&&!current)||(current&&(
    r.report_reference!==current.report_reference||r.loinc_code!==current.loinc_code||r.specimen_type_text!==current.specimen_type_text||
    !sameInstant(r.effective_at,current.effective_at)||!sameInstant(r.issued_at,current.issued_at)||
    !sameInstant(r.specimen_collected_at,current.specimen_collected_at)||r.status!==current.status||
    r.value_text!==current.value_text||r.unit_code!==current.unit_code||r.absent_reason!==current.absent_reason)))throw Error('Result changed');
  return Object.freeze({question:q.question,result:Object.freeze({...r} as LaboratoryReportedResult),citations});
}
