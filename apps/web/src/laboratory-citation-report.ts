import type {SavedLabQuestion} from './laboratory-question.js';
import type {SourceWorldModel} from './source-world-model.js';
import {laboratoryValueKeys,readLaboratoryValue,sameLaboratoryValue,type LaboratoryValue} from './laboratory-result.js';
import {decodeQuestionEvidenceLinks,unwrapLaboratoryEvidence} from './question-evidence-view.js';
import type {QuestionEvidenceLinks} from './question-evidence-view.js';
import {citationEvidenceTimestamp} from './evidence-timestamp.js';

export type LaboratoryReportedResult=Readonly<{
  anchor_kind:'fhir_observation';kind:'laboratory';resource_reference:string;source_id:string;version:number;sha256:string;
  report_reference:string;document_id:string;specimen_reference:string;specimen_type_text:string;
  specimen_collected_at:string;effective_at:string;issued_at:string;loinc_code:string;
  source_reported:true;review_state:'not_established';clinical_review:'not_performed';
}>&LaboratoryValue;
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
      'review_state','kind','anchor_kind',...laboratoryValueKeys(r)])||
    r.source_id!==q.source_id||r.sha256!==q.source_sha256||r.version!==q.source_version||
    r.document_id!==source.document_id||r.resource_reference!==q.observation_reference||
    r.report_reference!=='DiagnosticReport/'+source.document_id||!source.specimen_id||r.specimen_reference!=='Specimen/'+source.specimen_id||
    !visible(r.specimen_type_text,100)||!visible(r.loinc_code,8)||!/^\d{1,6}-\d$/.test(r.loinc_code)||
    !citationEvidenceTimestamp(r.specimen_collected_at)||!citationEvidenceTimestamp(r.effective_at)||!citationEvidenceTimestamp(r.issued_at)||
    r.source_reported!==true||r.clinical_review!=='not_performed'||r.review_state!=='not_established'||
    r.kind!=='laboratory'||r.anchor_kind!=='fhir_observation')throw Error('Invalid original result');
  const value=readLaboratoryValue(r);
  if(value.status==='reported_value'&&(!visible(value.value_text,64)||!(/^-?\d+(?:\.\d+)?$/).test(value.value_text)||
    !visible(value.unit_code,32)))throw Error('Invalid reported measurement');
  const current=model.laboratory_observations.find(o=>o.source_id===q.source_id&&o.observation_reference===q.observation_reference);
  if((source.state==='current'&&!current)||(current&&(
    r.loinc_code!==current.loinc_code||r.specimen_type_text!==current.specimen_type_text||
    !sameInstant(r.effective_at,current.effective_at)||!sameInstant(r.issued_at,current.issued_at)||
    !sameInstant(r.specimen_collected_at,current.specimen_collected_at)||!sameLaboratoryValue(value,current))))throw Error('Result changed');
  return Object.freeze({question:q.question,result:Object.freeze({...r,...value} as LaboratoryReportedResult),citations});
}
