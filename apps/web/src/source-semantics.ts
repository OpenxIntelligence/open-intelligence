import {parseSourceHistory} from './source-world-model.js';
import type {SourceWorldModel,SourceHistory} from './source-world-model.js';

export type SourceSemanticReference=Readonly<{
  owner:'clinical_source';record_id:string;
  concept_id:'oi:source-statement'|'oi:laboratory-observation';concept_version:1;
  source_version_id:string;source_sha256:string;knowledge_kind:'reported';
  evidence_status:'present'|'negative'|'missing'|'pending'|'indeterminate'|'conflicting';
  original_state:string;
}>;
export type SourceSemantics=Readonly<{
  contract:'oi.source-semantics/1';patient_id:string;case_id:string;access_receipt_id:string;
  source_snapshot_sha256:string;synthetic:true;clinical_interpretation:false;
  records:readonly SourceSemanticReference[];
}>;
const states:Record<string,string>={reported:'present',negative:'negative',pending:'pending',
  indeterminate:'indeterminate','not-reported':'missing','not-assessed':'missing',conflicting:'conflicting'};
const absence:Record<string,string>={unknown:'indeterminate','not-performed':'missing',error:'indeterminate',masked:'missing'};
function shape(value:unknown,keys:string[]):Record<string,unknown>{
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==keys.length||
     keys.some(k=>!Object.hasOwn(value,k)))throw Error('source-semantics-contract');
  return value as Record<string,unknown>;
}
/** Validate every semantic reference against the currently displayed, validated source snapshot. */
export function parseSourceSemantics(raw:unknown,world:SourceWorldModel):SourceSemantics{
  const x=shape(raw,['contract','patient_id','case_id','access_receipt_id','source_snapshot_sha256',
    'synthetic','clinical_interpretation','records']);
  if(x.contract!=='oi.source-semantics/1'||x.patient_id!==world.patient_id||x.case_id!==world.case_id||
     x.source_snapshot_sha256!==world.snapshot_fingerprint||x.synthetic!==true||x.clinical_interpretation!==false||
     typeof x.access_receipt_id!=='string'||!/^ACCESS-[A-F0-9]{32}$/.test(x.access_receipt_id)||!Array.isArray(x.records))
    throw Error('source-semantics-scope');
  const expected=new Map([...world.observations.map(o=>({
    record_id:`${o.source_id}/line/${o.source_line}`,concept_id:'oi:source-statement',
    source_version_id:o.source_id,source_sha256:o.source_sha256,original_state:o.reported_state,
    evidence_status:states[o.reported_state],
  })),...world.laboratory_observations.map(o=>({
    record_id:`${o.source_id}/observation/${o.observation_reference}`,concept_id:'oi:laboratory-observation',
    source_version_id:o.source_id,source_sha256:o.source_sha256,original_state:o.absent_reason??o.status,
    evidence_status:o.status==='reported_value'?'present':absence[o.absent_reason!],
  }))].map(o=>[o.record_id,o]));
  if(x.records.length!==expected.size)throw Error('source-semantics-coverage');
  const records=x.records.map(raw=>{
    const r=shape(raw,['owner','record_id','concept_id','concept_version','source_version_id','knowledge_kind',
      'evidence_status','source_sha256','original_state']);
    const e=typeof r.record_id==='string'?expected.get(r.record_id):undefined;
    if(!e||r.owner!=='clinical_source'||r.concept_version!==1||r.knowledge_kind!=='reported'||
       Object.entries(e).some(([k,v])=>r[k]!==v))throw Error('source-semantics-reference');
    expected.delete(e.record_id);
    return Object.freeze({...r}) as SourceSemanticReference;
  });
  return Object.freeze({...x,records:Object.freeze(records)}) as SourceSemantics;
}

export function parseHistoricalSourceSemantics(raw:unknown,history:SourceHistory):SourceSemantics{
  const x=shape(raw,['contract','received_through','selection_basis','current_authority_required','historical_only','semantics']);
  if(x.contract!=='oi.source-semantics-history/1')throw Error('source-semantics-history-contract');
  // Reuse the source owner's microsecond-aware cutoff and current-authority checks.
  parseSourceHistory({contract:'oi.pg-source-history/1',received_through:x.received_through,
    selection_basis:x.selection_basis,current_authority_required:x.current_authority_required,
    historical_only:x.historical_only,world_model:history.world_model},
    history.world_model.patient_id,history.world_model.case_id,history.received_through);
  return parseSourceSemantics(x.semantics,history.world_model);
}
