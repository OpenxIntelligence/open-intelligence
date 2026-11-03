/** Bounded source-only Composer preflight contract; never a model-run token. */
import type {SourceWorldModel,WorldObservation} from './source-world-model.js';

export const DEFAULT_SOURCE_QUESTION =
  'What source provenance and reported uncertainty require independent verification?';

export type ComposerSource = Readonly<{
 source_id:string;document_id:string;version:number;sha256:string;line:number;
 finding_key:string;reported_state:string;statement:string;kind:string;
 event_date:string;issued_at:string;specimen_id:string|null;
}>;
export type ComposerPreflight = Readonly<{
 contract:'oi.synthetic-source-composer-preflight/2';
 source_snapshot_contract:'oi.pg-source-world-model/1';access_receipt_id:string;
 patient_id:string;case_id:string;question:string;
 source_snapshot_sha256:string;selected_source:ComposerSource;
 source_context_only:true;biomedical_evidence_rights_verified:false;
 model_execution_authorized:false;durable_question_created:false;
 durable_review_connected:false;clinical_approval:false;
 clinical_interpretation:'not_performed';
 reassessment_policy:'revalidate_source_and_authority_before_any_future_write';
 limitations:string;preflight_sha256:string;
}>;

const HEX=/^[0-9a-f]{64}$/;
const SRC=/^SRC-[0-9A-F]{32}$/;
const DOC=/^[A-Z][A-Z0-9-]{1,39}$/;
const FIELDS=['contract','source_snapshot_contract','access_receipt_id','patient_id','case_id','question','source_snapshot_sha256',
 'selected_source','source_context_only','biomedical_evidence_rights_verified',
 'model_execution_authorized','durable_question_created','durable_review_connected',
 'clinical_approval','clinical_interpretation','reassessment_policy','limitations',
 'preflight_sha256'];
const ANCHOR=['source_id','document_id','version','sha256','line','finding_key',
 'reported_state','statement','kind','event_date','issued_at','specimen_id'];
function exact(value:unknown,keys:readonly string[]):value is Record<string,unknown>{
 return value!==null&&typeof value==='object'&&!Array.isArray(value)&&
 Object.keys(value).length===keys.length&&keys.every(k=>Object.hasOwn(value,k));
}
export function decodeComposerPreflight(value:unknown,world:SourceWorldModel,
  observation:WorldObservation,question:string):ComposerPreflight{
 if(!exact(value,FIELDS)||
    value.contract!=='oi.synthetic-source-composer-preflight/2'||
    value.source_snapshot_contract!=='oi.pg-source-world-model/1'||
    typeof value.access_receipt_id!=='string'||!/^ACCESS-[0-9A-F]{32}$/.test(value.access_receipt_id)||
    value.patient_id!==world.patient_id||value.case_id!==world.case_id||
    value.question!==question||
    value.source_snapshot_sha256!==world.snapshot_fingerprint||
    value.source_context_only!==true||
    value.biomedical_evidence_rights_verified!==false||
    value.model_execution_authorized!==false||
    value.durable_question_created!==false||
    value.durable_review_connected!==false||
    value.clinical_approval!==false||
    value.clinical_interpretation!=='not_performed'||
    value.reassessment_policy!=='revalidate_source_and_authority_before_any_future_write'||
    typeof value.preflight_sha256!=='string'||!HEX.test(value.preflight_sha256)||
    typeof value.limitations!=='string'||value.limitations.length<20||
    value.limitations.length>1000||
    !exact(value.selected_source,ANCHOR))throw Error('contract');
 const item=value.selected_source;
 if(typeof item.source_id!=='string'||!SRC.test(item.source_id)||
    item.source_id!==observation.source_id||
    typeof item.document_id!=='string'||!DOC.test(item.document_id)||
    item.document_id!==observation.document_id||
    item.version!==observation.document_version||
    typeof item.sha256!=='string'||!HEX.test(item.sha256)||
    item.sha256!==observation.source_sha256||
    item.line!==observation.source_line||
    item.finding_key!==observation.finding_key||
    item.reported_state!==observation.reported_state||
    item.statement!==observation.source_statement||
    item.kind!==observation.source_kind||
    item.event_date!==observation.event_date||
    item.issued_at!==observation.issued_at||
    item.specimen_id!==observation.specimen_id)throw Error('contract');
 return Object.freeze({...value,
  selected_source:Object.freeze({...item} as ComposerSource)} as ComposerPreflight);
}
