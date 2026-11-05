import {citationEvidenceTimestamp} from './evidence-timestamp.js';
import type {LaboratoryFile} from './laboratory-fhir.js';
import type {CaseBinding} from './source-contracts.js';

export class LaboratoryPreviewRejected extends Error {}
export const LABORATORY_PREVIEW_REJECTED='This file does not match the supported laboratory format or the case mapping.';

type Result = Readonly<{
  reference:string; loinc_code:string; effective_at:string; issued_at:string;
  source_reported:true; clinical_review:'not_performed';
} & (
  {status:'reported_value'; value_text:string; unit_code:string; absent_reason:null} |
  {status:'reported_absent'; value_text:null; unit_code:null; absent_reason:'unknown'|'not-performed'|'error'|'masked'}
)>;

export type LaboratoryPreview = Readonly<{
  specimen_reference:string; specimen_type_text:string; specimen_collected_at:string;
  report_reference:string|null; observations:readonly Result[];
}>;

function fields(value:unknown, keys:string[]):value is Record<string,unknown> {
  return !!value && typeof value==='object' && !Array.isArray(value) &&
    Object.keys(value).length===keys.length && keys.every(key=>Object.hasOwn(value,key));
}

function boundedText(value:unknown, max:number):value is string {
  return typeof value==='string' && value.length>0 && !/[\u0000-\u001f\u007f]/u.test(value) &&
    [...value].length<=max;
}

function reference(value:unknown, kind:string):value is string {
  if(typeof value!=='string' || !value.startsWith(kind+'/')) return false;
  const id=value.slice(kind.length+1);
  return id.length>0 && id.length<=64 && !/[^A-Za-z0-9.-]/.test(id);
}

function laboratoryTimestamp(value:unknown):value is string {
  return citationEvidenceTimestamp(value) && /(?:Z|[+-](?:(?:0\d|1[0-3]):[0-5]\d|14:00))$/.test(value);
}

function readResult(row:unknown):Result {
  if (!fields(row,['reference','loinc_code','effective_at','issued_at','status','source_reported',
      'clinical_review','value_text','unit_code','absent_reason']) ||
      !reference(row.reference,'Observation') || !boundedText(row.loinc_code,8) ||
      !/^\d{1,6}-\d$/.test(row.loinc_code) ||
      !laboratoryTimestamp(row.effective_at) || !laboratoryTimestamp(row.issued_at) ||
      row.source_reported!==true || row.clinical_review!=='not_performed') {
    throw new LaboratoryPreviewRejected('Invalid laboratory preview observation');
  }
  if (row.status==='reported_value' && boundedText(row.value_text,64) &&
      /^-?\d+(?:\.\d+)?$/.test(row.value_text) && boundedText(row.unit_code,32) && row.absent_reason===null) {
    return Object.freeze(row as Result);
  }
  if (row.status==='reported_absent' && row.value_text===null && row.unit_code===null &&
      typeof row.absent_reason==='string' && ['unknown','not-performed','error','masked'].includes(row.absent_reason)) {
    return Object.freeze(row as Result);
  }
  throw new LaboratoryPreviewRejected('Invalid laboratory preview result');
}

export function readLaboratoryPreview(value:unknown, file:LaboratoryFile, binding:CaseBinding):LaboratoryPreview {
  if (!fields(value,['contract','patient_id','case_id','source_organization','source_system',
      'mapped_subject_reference','original_sha256','original_byte_count','specimen_reference',
      'specimen_type_text','specimen_collected_at','report_reference','observations','synthetic',
      'persisted','clinical_review','verified_identity','source_version_created']) ||
      value.contract!=='oi.fhir-r4-laboratory-preview/1' || value.synthetic!==true || value.persisted!==false ||
      value.verified_identity!==false || value.source_version_created!==false || value.clinical_review!=='not_performed' ||
      value.patient_id!==binding.patient_id || value.case_id!==binding.case_id ||
      value.source_organization!==binding.source_organization || value.source_system!==binding.source_system ||
      value.mapped_subject_reference!=='Patient/'+binding.source_subject_ref ||
      value.original_sha256!==file.sha256 || value.original_byte_count!==file.byteCount ||
      !reference(value.specimen_reference,'Specimen') || !boundedText(value.specimen_type_text,100) ||
      !laboratoryTimestamp(value.specimen_collected_at) ||
      !(value.report_reference===null || reference(value.report_reference,'DiagnosticReport')) ||
      !Array.isArray(value.observations) || value.observations.length<1 || value.observations.length>16) {
    throw new LaboratoryPreviewRejected('Laboratory preview does not match the selected file and case');
  }
  const observations=value.observations.map(readResult);
  if(new Set(observations.map(row=>row.reference)).size!==observations.length) {
    throw new LaboratoryPreviewRejected('Duplicate laboratory preview observation');
  }
  return Object.freeze({
    specimen_reference:value.specimen_reference, specimen_type_text:value.specimen_type_text,
    specimen_collected_at:value.specimen_collected_at, report_reference:value.report_reference,
    observations:Object.freeze(observations),
  });
}
