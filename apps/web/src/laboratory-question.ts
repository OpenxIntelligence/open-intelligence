import type {SourceWorldModel, WorldLaboratoryObservation} from './source-world-model.js';

export function validLabQuestion(text:string):boolean {
  return text===text.trim() && [...text].length>=8 && [...text].length<=500 && !/[\u0000-\u001f\u007f]/.test(text);
}
export type LabPreparation = Readonly<{receipt:string; fingerprint:string}>;

function record(x:unknown):x is Record<string,unknown> {
  return x!==null && typeof x==='object' && !Array.isArray(x);
}
function matches(x:unknown, expected:Record<string,unknown>, timestamps:readonly string[]=[]):boolean {
  return record(x) && Object.keys(x).length===Object.keys(expected).length &&
    Object.entries(expected).every(([k,v])=>{
      if(!Object.hasOwn(x,k))return false;
      const actual=x[k];
      // The World Model serializes datetime UTC as Z; the preparation preserves
      // PostgreSQL's +00:00 spelling. Never round fractional seconds via Date.
      return actual===v || (timestamps.includes(k) && typeof actual==='string' && typeof v==='string' &&
        actual.replace(/\+00:00$/,'Z')===v.replace(/\+00:00$/,'Z'));
    });
}

/** Accept only the selected, already authorized observation, with its literal source context. */
export function readLabPreparation(x:unknown, world:SourceWorldModel, item:WorldLaboratoryObservation, question:string):LabPreparation {
  if(!record(x)) throw Error('Invalid laboratory preparation');
  const {selected_source, access_receipt_id, preflight_sha256, ...body}=x;
  if(!matches(body,{
    contract:'oi.synthetic-laboratory-question-preflight/1', patient_id:world.patient_id, case_id:world.case_id, question,
    source_snapshot_contract:world.contract, source_snapshot_sha256:world.snapshot_fingerprint, synthetic:true,
    source_context_only:true, durable_question_created:false, durable_review_connected:false,
    biomedical_evidence_rights_verified:false, model_execution_authorized:false, clinical_approval:false,
    clinical_interpretation:'not_performed', terminology_validation:'not_performed',
    reassessment_policy:'revalidate_source_and_authority_before_any_future_write',
  }) || !matches(selected_source,{
    anchor_kind:'fhir_observation', source_id:item.source_id, document_id:item.document_id,
    version:item.document_version, sha256:item.source_sha256, kind:'laboratory',
    resource_reference:item.observation_reference, specimen_reference:item.specimen_reference,
    specimen_type_text:item.specimen_type_text, specimen_collected_at:item.specimen_collected_at,
    report_reference:item.report_reference, loinc_code:item.loinc_code, effective_at:item.effective_at,
    issued_at:item.issued_at, status:item.status, value_text:item.value_text, unit_code:item.unit_code,
    absent_reason:item.absent_reason, source_reported:true, review_state:'not_established', clinical_review:'not_performed',
  },['effective_at','issued_at','specimen_collected_at']) || typeof access_receipt_id!=='string' || !/^ACCESS-[0-9A-F]{32}$/.test(access_receipt_id) ||
      typeof preflight_sha256!=='string' || !/^[0-9a-f]{64}$/.test(preflight_sha256)) throw Error('Invalid laboratory preparation');
  return Object.freeze({receipt:access_receipt_id,fingerprint:preflight_sha256});
}

export type SavedLabQuestion=Readonly<{
  question_id:string;question:string;source_id:string;source_version:number;source_sha256:string;
  observation_reference:string;source_snapshot_sha256:string;preflight_sha256:string;
  source_context_state:'current_unreviewed_question'|'source_reassessment_required';
}>;
export type LabQuestionList=Readonly<{access_receipt_id:string;questions:readonly SavedLabQuestion[]}>;
export type LabQuestionView=Readonly<{
  labQuestionHistory:LabQuestionList|null;labQuestionListPhase:'idle'|'loading'|'ready'|'error';
  labQuestionListMessage:string;labQuestionWritePhase:'idle'|'saving'|'unknown'|'saved'|'error';
  labQuestionWriteMessage:string;labQuestionSavedId:string|null;
}>;
export const emptyLabQuestions=():LabQuestionView=>({labQuestionHistory:null,labQuestionListPhase:'idle',
  labQuestionListMessage:'',labQuestionWritePhase:'idle',labQuestionWriteMessage:'',labQuestionSavedId:null});
const hash=(v:unknown):v is string=>typeof v==='string'&&/^[0-9a-f]{64}$/.test(v);
function fields(v:unknown,keys:readonly string[]):v is Record<string,unknown>{
  return record(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
}
/** Link a fresh authorized list to the selected case's current or historical source version.
 * No clinical values are reconstructed from a historical observation reference. */
export function readLabQuestionList(raw:unknown,model:SourceWorldModel):LabQuestionList{
  if(!fields(raw,['patient_id','case_id','access_receipt_id','questions'])||raw.patient_id!==model.patient_id||raw.case_id!==model.case_id||
    typeof raw.access_receipt_id!=='string'||!/^ACCESS-[0-9A-F]{32}$/.test(raw.access_receipt_id)||!Array.isArray(raw.questions)||raw.questions.length>512)throw Error('laboratory questions');
  const ids=new Set<string>(),sources=new Map([...model.current_sources,...model.history].map(s=>[s.source_id,s]));
  const currentObservations=new Set(model.laboratory_observations.map(o=>o.source_id+'|'+o.observation_reference));
  const questions=raw.questions.map((row:unknown)=>{
    if(!fields(row,['question_id','question','source_id','source_version','source_sha256','observation_reference','source_snapshot_sha256','preflight_sha256','source_context_state'])||
      typeof row.question_id!=='string'||!/^QUESTION-[0-9A-F]{32}$/.test(row.question_id)||ids.has(row.question_id)||
      typeof row.question!=='string'||!validLabQuestion(row.question)||typeof row.source_id!=='string'||
      typeof row.observation_reference!=='string'||!/^Observation\/[A-Za-z0-9.-]{1,64}$/.test(row.observation_reference)||
      !hash(row.source_sha256)||!hash(row.preflight_sha256)||!hash(row.source_snapshot_sha256)||
      !['current_unreviewed_question','source_reassessment_required'].includes(String(row.source_context_state)))throw Error('laboratory question');
    const source=sources.get(row.source_id);
    if(!source||source.kind!=='laboratory'||source.version!==row.source_version||source.sha256!==row.source_sha256||
      (row.source_context_state==='current_unreviewed_question'&&(row.source_snapshot_sha256!==model.snapshot_fingerprint||source.state!=='current'||!currentObservations.has(row.source_id+'|'+row.observation_reference))))throw Error('laboratory question source');
    ids.add(row.question_id);return Object.freeze(row as SavedLabQuestion);
  });
  return Object.freeze({access_receipt_id:raw.access_receipt_id,questions:Object.freeze(questions)});
}
