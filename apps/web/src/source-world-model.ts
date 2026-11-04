/** Read-only H1 source World Model contract.
 * A response is a derived report of fictional source statements, not clinical
 * judgment, consent, or authorization to execute an AI investigation.
 */
import type {SourceVersion} from './source-contracts.js';

export type WorldRef=Readonly<{source_id:string;source_line:number}>;
export type WorldObservation=Readonly<{
  source_id:string;document_id:string;document_version:number;source_sha256:string;
  source_kind:string;finding_key:string;reported_state:string;source_statement:string;
  source_line:number;specimen_id:string|null;event_date:string;issued_at:string;
  review_state:'not_established';clinical_meaning:null;
}>;
export type WorldLaboratoryObservation=Readonly<{
  source_id:string;document_id:string;document_version:number;source_sha256:string;
  observation_reference:string;loinc_code:string;effective_at:string;issued_at:string;
  status:'reported_value'|'reported_absent';value_text:string|null;unit_code:string|null;
  absent_reason:string|null;specimen_reference:string;source_reported:true;
  clinical_review:'not_performed';review_state:'not_established';clinical_meaning:null;
}>;
export type WorldLaboratoryTimeline=Readonly<{
  source_id:string;observation_reference:string;occurred_at:string;issued_at:string;
  loinc_code:string;status:'reported_value'|'reported_absent';
  clinical_interpretation:'not_performed';
}>;
export type WorldConflict=Readonly<{
  specimen_id:string;event_date:string;finding_key:string;
  status:'unresolved_source_disagreement';reported_states:readonly string[];
  source_refs:readonly WorldRef[];clinical_interpretation:'not_performed';
}>;
export type WorldSummary=Readonly<{
  current_sources:number;historical_sources:number;current_observations:number;
  current_laboratory_observations:number;unresolved_observations:number;
  source_disagreements:number;
}>;
export type SourceWorldModel=Readonly<{
  contract:'oi.pg-source-world-model/1';patient_id:string;case_id:string;access_receipt_id:string;synthetic:true;
  authority:'source_report_only_unreviewed';clinical_interpretation:false;
  research_review_invalidation_integrated:false;composer_execution_authorized:false;
  snapshot_fingerprint:string;as_of_received_at:string|null;summary:WorldSummary;
  current_sources:readonly SourceVersion[];history:readonly SourceVersion[];
  observations:readonly WorldObservation[];
  laboratory_observations:readonly WorldLaboratoryObservation[];
  laboratory_timeline:readonly WorldLaboratoryTimeline[];
  unresolved_refs:readonly WorldRef[];
  conflicts:readonly WorldConflict[];limitations:readonly string[];
}>;
const PID=/^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$/;
const CASE=/^CASE-[A-Z0-9-]{1,35}$/;
const SOURCE=/^SRC-[0-9A-F]{32}$/;
const SHA=/^[a-f0-9]{64}$/;
const RECEIPT=/^ACCESS-[0-9A-F]{32}$/;
const DAY=/^\d{4}-\d{2}-\d{2}$/;
const TYPES=new Set(['clinical','pathology','laboratory','imaging','molecular','other']);
const STATES=new Set(['reported','negative','pending','indeterminate','not-reported','not-assessed','conflicting']);
const UNRESOLVED=new Set(['pending','indeterminate','not-reported','not-assessed','conflicting']);
const error=():never=>{throw Error('world-model-contract');};
function shape(v:unknown,keys:readonly string[]):Record<string,unknown>{
  if(v===null||typeof v!=='object'||Array.isArray(v))return error();
  const object=v as Record<string,unknown>;
  if(Object.keys(object).length!==keys.length||keys.some(k=>!Object.hasOwn(object,k)))return error();
  return object;
}
function str(v:unknown,max=256):string{
  if(typeof v!=='string'||!v||v.length>max||/[\u0000-\u001f\u007f]/.test(v))return error();
  return v;
}
function date(v:unknown):string{
  const value=str(v,10);
  if(!DAY.test(value)||!Number.isFinite(Date.parse(value+'T00:00:00Z')))return error();
  return value;
}
function stamp(v:unknown):string{
  const value=str(v,80);
  if(!/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value)||!Number.isFinite(Date.parse(value)))return error();
  return value;
}
function pos(v:unknown):number{
  if(typeof v!=='number'||!Number.isSafeInteger(v)||v<1)return error();return v;
}
function count(v:unknown):number{
  if(typeof v!=='number'||!Number.isSafeInteger(v)||v<0)return error();return v;
}
function source(v:unknown):SourceVersion{
  const s=shape(v,['source_id','document_id','version','sha256','kind',
    'event_date','issued_at','received_at','specimen_id','state','supersedes_id']);
  if(!SOURCE.test(str(s.source_id,36))||!SHA.test(str(s.sha256,64))||
     !TYPES.has(String(s.kind))||!['current','superseded'].includes(String(s.state))||
     s.specimen_id!==null&&typeof s.specimen_id!=='string'||
     s.supersedes_id!==null&&(!SOURCE.test(str(s.supersedes_id,36))))return error();
  str(s.document_id,128);pos(s.version);date(s.event_date);date(s.issued_at);stamp(s.received_at);
  if(s.specimen_id!==null)str(s.specimen_id,128);
  return Object.freeze({...s} as SourceVersion);
}
function ref(v:unknown,currentIds:Set<string>):WorldRef{
  const r=shape(v,['source_id','source_line']);
  const id=str(r.source_id,36),line=pos(r.source_line);
  if(!SOURCE.test(id)||!currentIds.has(id))return error();
  return Object.freeze({source_id:id,source_line:line});
}
function labObs(v:unknown,current:Map<string,SourceVersion>):WorldLaboratoryObservation{
  const x=shape(v,['source_id','document_id','document_version','source_sha256',
    'observation_reference','loinc_code','effective_at','issued_at','status',
    'value_text','unit_code','absent_reason','specimen_reference','source_reported',
    'clinical_review','review_state','clinical_meaning']);
  const id=str(x.source_id,36),src=current.get(id),status=x.status;
  if(!src||src.kind!=='laboratory'||x.document_id!==src.document_id||
     x.document_version!==src.version||x.source_sha256!==src.sha256||
     !['reported_value','reported_absent'].includes(String(status))||
     x.source_reported!==true||x.clinical_review!=='not_performed'||
     x.review_state!=='not_established'||x.clinical_meaning!==null)return error();
  const observation_reference=str(x.observation_reference,128);
  const loinc_code=str(x.loinc_code,64),effective_at=stamp(x.effective_at),issued_at=stamp(x.issued_at);
  const specimen_reference=str(x.specimen_reference,128);
  if(status==='reported_value'){
    if(typeof x.value_text!=='string'||!x.value_text||x.value_text.length>128||
       typeof x.unit_code!=='string'||!x.unit_code||x.unit_code.length>64||
       x.absent_reason!==null)return error();
  }else if(x.value_text!==null||x.unit_code!==null||
           typeof x.absent_reason!=='string'||!['unknown','not-performed','error','masked'].includes(x.absent_reason))return error();
  return Object.freeze({...x,source_id:id,observation_reference,loinc_code,effective_at,
    issued_at,specimen_reference} as WorldLaboratoryObservation);
}
function labTimeline(v:unknown,current:Map<string,WorldLaboratoryObservation>):WorldLaboratoryTimeline{
  const x=shape(v,['source_id','observation_reference','occurred_at','issued_at',
    'loinc_code','status','clinical_interpretation']);
  const source_id=str(x.source_id,36),observation_reference=str(x.observation_reference,128);
  const item=current.get(source_id+':'+observation_reference);
  if(!item||x.occurred_at!==item.effective_at||x.issued_at!==item.issued_at||
     x.loinc_code!==item.loinc_code||x.status!==item.status||
     x.clinical_interpretation!=='not_performed')return error();
  stamp(x.occurred_at);stamp(x.issued_at);
  return Object.freeze({source_id,observation_reference,occurred_at:x.occurred_at as string,
    issued_at:x.issued_at as string,loinc_code:x.loinc_code as string,status:x.status as 'reported_value'|'reported_absent',
    clinical_interpretation:'not_performed'});
}
function obs(v:unknown,current:Map<string,SourceVersion>):WorldObservation{
  const x=shape(v,['source_id','document_id','document_version','source_sha256',
    'source_kind','finding_key','reported_state','source_statement','source_line',
    'specimen_id','event_date','issued_at','review_state','clinical_meaning']);
  const id=str(x.source_id,36),src=current.get(id);
  if(!src||x.document_id!==src.document_id||x.document_version!==src.version||
     x.source_sha256!==src.sha256||x.source_kind!==src.kind||
     x.event_date!==src.event_date||x.issued_at!==src.issued_at||
     x.specimen_id!==src.specimen_id||x.review_state!=='not_established'||
     x.clinical_meaning!==null||!STATES.has(String(x.reported_state)))return error();
  const quote=x.source_statement;
  if(typeof quote!=='string'||!quote||quote.length>8192)return error();
  str(x.finding_key,128);pos(x.source_line);
  return Object.freeze({...x} as WorldObservation);
}
export function parseSourceWorldModel(raw:unknown,expectedPatient:string,expectedCase:string):SourceWorldModel{
  if(!PID.test(expectedPatient)||!CASE.test(expectedCase))return error();
  const v=shape(raw,['contract','patient_id','case_id','access_receipt_id','synthetic','authority',
    'clinical_interpretation','research_review_invalidation_integrated',
    'composer_execution_authorized','snapshot_fingerprint','as_of_received_at',
    'summary','current_sources','history','observations','laboratory_observations',
    'laboratory_timeline','unresolved_refs','conflicts','limitations']);
  if(v.contract!=='oi.pg-source-world-model/1'||v.patient_id!==expectedPatient||
     v.case_id!==expectedCase||v.synthetic!==true||
     typeof v.access_receipt_id!=='string'||!RECEIPT.test(v.access_receipt_id)||
     v.authority!=='source_report_only_unreviewed'||
     v.clinical_interpretation!==false||
     v.research_review_invalidation_integrated!==false||
     v.composer_execution_authorized!==false||
     !SHA.test(str(v.snapshot_fingerprint,64)))return error();
  if(v.as_of_received_at!==null)stamp(v.as_of_received_at);
  if(!Array.isArray(v.current_sources)||!Array.isArray(v.history)||
     !Array.isArray(v.observations)||!Array.isArray(v.laboratory_observations)||
     !Array.isArray(v.laboratory_timeline)||!Array.isArray(v.unresolved_refs)||
     !Array.isArray(v.conflicts)||!Array.isArray(v.limitations)||
     v.current_sources.length>512||v.history.length>512||
     v.observations.length>4096||v.laboratory_observations.length>4096||
     v.laboratory_timeline.length>4096||v.unresolved_refs.length>4096||
     v.conflicts.length>1024||v.limitations.length>32)return error();
  const current=v.current_sources.map(source),history=v.history.map(source);
  if(current.some(s=>s.state!=='current')||history.some(s=>s.state!=='superseded'))return error();
  const ids=new Set<string>();
  for(const s of [...current,...history]){if(ids.has(s.source_id))return error();ids.add(s.source_id);}
  const currentById=new Map(current.map(s=>[s.source_id,s]));
  const observations=v.observations.map(x=>obs(x,currentById));
  const laboratory=v.laboratory_observations.map(x=>labObs(x,currentById));
  const laboratoryById=new Map<string,WorldLaboratoryObservation>();
  for(const x of laboratory){
    const key=x.source_id+':'+x.observation_reference;
    if(laboratoryById.has(key))return error();
    laboratoryById.set(key,x);
  }
  const timeline=v.laboratory_timeline.map(x=>labTimeline(x,laboratoryById));
  if(timeline.length!==laboratory.length||
     new Set(timeline.map(x=>x.source_id+':'+x.observation_reference)).size!==laboratory.length)return error();
  const refOf=(x:WorldRef)=>x.source_id+':'+x.source_line;
  const indexedRefs=new Map<string,WorldObservation>();
  for(const x of observations){
    const k=refOf(x);
    if(indexedRefs.has(k))return error();
    indexedRefs.set(k,x);
  }
  const unresolved=v.unresolved_refs.map(x=>ref(x,new Set(currentById.keys())));
  const expectedUnresolved=new Set(observations.filter(x=>UNRESOLVED.has(x.reported_state)).map(x=>refOf(x)));
  if(unresolved.length!==expectedUnresolved.size||
     unresolved.some(x=>!expectedUnresolved.has(refOf(x)))||
     new Set(unresolved.map(refOf)).size!==unresolved.length)return error();
  const conflicts:WorldConflict[]=v.conflicts.map(raw=>{
    const c=shape(raw,['specimen_id','event_date','finding_key','status',
      'reported_states','source_refs','clinical_interpretation']);
    if(c.status!=='unresolved_source_disagreement'||c.clinical_interpretation!=='not_performed'||
       !Array.isArray(c.reported_states)||!Array.isArray(c.source_refs)||
       c.source_refs.length<2||c.source_refs.length>4096||
       c.reported_states.length<2||c.reported_states.length>7)return error();
    const specimen=str(c.specimen_id,128),event=date(c.event_date),finding=str(c.finding_key,128);
    const refs=c.source_refs.map(x=>ref(x,new Set(currentById.keys())));
    const relevant=refs.map(x=>indexedRefs.get(refOf(x)));
    if(relevant.some(x=>!x||x.specimen_id!==specimen||x.event_date!==event||x.finding_key!==finding))return error();
    const states=new Set(relevant.map(x=>x!.reported_state));
    if(!states.has('reported')||!states.has('negative')||
       new Set(refs.map(refOf)).size!==refs.length||
       JSON.stringify([...states].sort())!==JSON.stringify(c.reported_states))return error();
    return Object.freeze({specimen_id:specimen,event_date:event,finding_key:finding,
      status:'unresolved_source_disagreement' as const,reported_states:Object.freeze([...states].sort()),
      source_refs:Object.freeze(refs),clinical_interpretation:'not_performed' as const});
  });
  const summary=shape(v.summary,['current_sources','historical_sources','current_observations',
    'current_laboratory_observations','unresolved_observations','source_disagreements']);
  const counts={current_sources:current.length,historical_sources:history.length,
    current_observations:observations.length+laboratory.length,
    current_laboratory_observations:laboratory.length,
    unresolved_observations:unresolved.length+laboratory.filter(x=>x.status==='reported_absent').length,
    source_disagreements:conflicts.length};
  for(const [key,value] of Object.entries(counts)){
    if(count(summary[key])!==value)return error();
  }
  if(v.limitations.some(x=>typeof x!=='string'||!x||x.length>512))return error();
  return Object.freeze({
    contract:'oi.pg-source-world-model/1',patient_id:expectedPatient,case_id:expectedCase,
    access_receipt_id:v.access_receipt_id as string,synthetic:true,
    authority:'source_report_only_unreviewed',clinical_interpretation:false,
    research_review_invalidation_integrated:false,composer_execution_authorized:false,
    snapshot_fingerprint:v.snapshot_fingerprint as string,
    as_of_received_at:v.as_of_received_at as string|null,
    summary:Object.freeze(counts),
    current_sources:Object.freeze(current),history:Object.freeze(history),
    observations:Object.freeze(observations),
    laboratory_observations:Object.freeze(laboratory),
    laboratory_timeline:Object.freeze(timeline),
    unresolved_refs:Object.freeze(unresolved),
    conflicts:Object.freeze(conflicts),limitations:Object.freeze(v.limitations.slice() as string[]),
  });
}
