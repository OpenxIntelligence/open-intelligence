/** Read-only H1 source World Model contract.
 * A response is a derived report of fictional source statements, not clinical
 * judgment, consent, or authorization to execute an AI investigation.
 */
import {parseOncologyContext} from './source-contracts.js';
import type {ReportedOncologyContext,SourceVersion} from './source-contracts.js';

export type WorldRef=Readonly<{source_id:string;source_line:number}>;
export type WorldObservation=Readonly<{
  oncology?:ReportedOncologyContext;
  source_id:string;document_id:string;document_version:number;source_sha256:string;
  source_kind:string;finding_key:string;reported_state:string;source_statement:string;
  source_line:number;specimen_id:string|null;event_date:string;issued_at:string;
  review_state:'not_established';clinical_meaning:null;
}>;
export type WorldLaboratoryObservation=Readonly<{
  source_id:string;document_id:string;document_version:number;source_sha256:string;
  observation_reference:string;loinc_code:string;effective_at:string;issued_at:string;
  specimen_reference:string;specimen_type_text:string;specimen_collected_at:string;
  report_reference:string;status:'reported_value'|'reported_absent';
  value_text:string|null;unit_code:string|null;absent_reason:string|null;
  source_reported:true;review_state:'not_established';
  clinical_review:'not_performed';clinical_meaning:null;
}>;
export type WorldLaboratoryTimelineItem=Readonly<{
  source_id:string;observation_reference:string;loinc_code:string;
  effective_at:string;issued_at:string;specimen_reference:string;
  status:'reported_value'|'reported_absent';clinical_interpretation:'not_performed';
}>;
export type WorldConflict=Readonly<{
  specimen_id:string;event_date:string;finding_key:string;
  status:'unresolved_source_disagreement';reported_states:readonly string[];
  source_refs:readonly WorldRef[];clinical_interpretation:'not_performed';
}>;
export type WorldSummary=Readonly<{
  current_sources:number;historical_sources:number;current_observations:number;
  current_laboratory_observations:number;unresolved_observations:number;source_disagreements:number;
}>;
export type SourceWorldModel=Readonly<{
  contract:'oi.pg-source-world-model/1';patient_id:string;case_id:string;access_receipt_id:string;synthetic:true;
  authority:'source_report_only_unreviewed';clinical_interpretation:false;
  research_review_invalidation_integrated:false;composer_execution_authorized:false;
  snapshot_fingerprint:string;as_of_received_at:string|null;summary:WorldSummary;
  current_sources:readonly SourceVersion[];history:readonly SourceVersion[];
  observations:readonly WorldObservation[];
  laboratory_observations:readonly WorldLaboratoryObservation[];
  laboratory_timeline:readonly WorldLaboratoryTimelineItem[];
  unresolved_refs:readonly WorldRef[];
  conflicts:readonly WorldConflict[];limitations:readonly string[];
}>;
export type SourceHistory=Readonly<{
  contract:'oi.pg-source-history/1';received_through:string;
  selection_basis:'received_at_inclusive';current_authority_required:true;historical_only:true;
  world_model:SourceWorldModel;
}>;

export function parseSourceHistory(raw:unknown,patient:string,caseId:string,cutoff:string):SourceHistory{
  const v=shape(raw,['contract','received_through','selection_basis','current_authority_required','historical_only','world_model']);
  const received=stamp(v.received_through);
  // Preserve PostgreSQL microseconds: JS Date alone would accept a different
  // cutoff in the same millisecond. The server emits ISO text, including Z.
  const instant=(s:string)=>{
    stamp(s);
    const fraction=s.match(/\.(\d+)(?:Z|[+-]\d{2}:\d{2})$/)?.[1]??'';
    if(fraction.length>6)return error();
    return BigInt(Date.parse(s))*1000n+BigInt(fraction.padEnd(6,'0').slice(3));
  };
  const boundary=instant(cutoff);
  if(v.contract!=='oi.pg-source-history/1'||v.selection_basis!=='received_at_inclusive'||
     v.current_authority_required!==true||v.historical_only!==true||instant(received)!==boundary)return error();
  const model=parseSourceWorldModel(v.world_model,patient,caseId);
  if([...model.current_sources,...model.history].some(s=>instant(s.received_at)>boundary))return error();
  return Object.freeze({contract:'oi.pg-source-history/1',received_through:received,
    selection_basis:'received_at_inclusive',current_authority_required:true,historical_only:true,world_model:model});
}
const PID=/^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$/;
const CASE=/^CASE-[A-Z0-9-]{1,35}$/;
const SOURCE=/^SRC-[0-9A-F]{32}$/;
const SHA=/^[a-f0-9]{64}$/;
const RECEIPT=/^ACCESS-[0-9A-F]{32}$/;
const DAY=/^\d{4}-\d{2}-\d{2}$/;
const TYPES=new Set(['clinical','pathology','laboratory','imaging','molecular','other']);
const STATES=new Set(['reported','negative','pending','indeterminate','not-reported','not-assessed','conflicting']);
const UNRESOLVED=new Set(['pending','indeterminate','not-reported','not-assessed','conflicting']);
const LAB_STATUS=new Set(['reported_value','reported_absent']);
const LOINC=/^[0-9]{1,6}-[0-9]$/;
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
export function isLaboratoryAbsentReason(value:unknown):boolean{
  return value==='unknown'||value==='not-performed'||value==='error'||value==='masked';
}

function labObs(v:unknown,current:Map<string,SourceVersion>):WorldLaboratoryObservation{
  const x=shape(v,['source_id','document_id','document_version','source_sha256',
    'observation_reference','loinc_code','effective_at','issued_at','specimen_reference',
    'specimen_type_text','specimen_collected_at','report_reference','status','value_text',
    'unit_code','absent_reason','source_reported','review_state','clinical_review','clinical_meaning']);
  const id=str(x.source_id,36),src=current.get(id);
  if(!src||src.kind!=='laboratory'||x.document_id!==src.document_id||
     x.document_version!==src.version||x.source_sha256!==src.sha256||
     x.source_reported!==true||x.review_state!=='not_established'||
     x.clinical_review!=='not_performed'||x.clinical_meaning!==null||
     !LAB_STATUS.has(String(x.status)))return error();
  str(x.observation_reference,128);const loinc=str(x.loinc_code,64);
  if(!LOINC.test(loinc))return error();
  stamp(x.effective_at);stamp(x.issued_at);str(x.specimen_reference,128);
  str(x.specimen_type_text,100);stamp(x.specimen_collected_at);str(x.report_reference,128);
  if(x.status==='reported_value'){
    if(typeof x.value_text!=='string'||!x.value_text||x.value_text.length>64||
       typeof x.unit_code!=='string'||!x.unit_code||x.unit_code.length>32||
       x.absent_reason!==null)return error();
  }else if(x.value_text!==null||x.unit_code!==null||
           !isLaboratoryAbsentReason(x.absent_reason))return error();
  return Object.freeze({...x} as WorldLaboratoryObservation);
}
function obs(v:unknown,current:Map<string,SourceVersion>):WorldObservation{
  const typed=v!==null && typeof v==='object' && Object.hasOwn(v,'oncology');
  const x=shape(v,['source_id','document_id','document_version','source_sha256',
    'source_kind','finding_key','reported_state','source_statement','source_line',
    'specimen_id','event_date','issued_at','review_state','clinical_meaning',...(typed?['oncology']:[])]);
  const id=str(x.source_id,36),src=current.get(id);
  if(!src||x.document_id!==src.document_id||x.document_version!==src.version||
     x.source_sha256!==src.sha256||x.source_kind!==src.kind||
     x.event_date!==src.event_date||x.issued_at!==src.issued_at||
     x.specimen_id!==src.specimen_id||x.review_state!=='not_established'||
     x.clinical_meaning!==null||!STATES.has(String(x.reported_state)))return error();
  const quote=x.source_statement;
  if(typeof quote!=='string'||!quote||quote.length>8192)return error();
  str(x.finding_key,128);pos(x.source_line);
  return Object.freeze({...x,...(typed?{oncology:parseOncologyContext(x.oncology)}:{})} as WorldObservation);
}
export function parseSourceWorldModel(raw:unknown,expectedPatient:string,expectedCase:string):SourceWorldModel{
  if(!PID.test(expectedPatient)||!CASE.test(expectedCase))return error();
  if(raw===null||typeof raw!=='object'||Array.isArray(raw))return error();
  const rawObject=raw as Record<string,unknown>;
  const hasLaboratory=Object.hasOwn(rawObject,'laboratory_observations')||
    Object.hasOwn(rawObject,'laboratory_timeline');
  const v=shape(raw,hasLaboratory?
    ['contract','patient_id','case_id','access_receipt_id','synthetic','authority',
     'clinical_interpretation','research_review_invalidation_integrated',
     'composer_execution_authorized','snapshot_fingerprint','as_of_received_at',
     'summary','current_sources','history','observations','laboratory_observations',
     'laboratory_timeline','unresolved_refs','conflicts','limitations']:
    ['contract','patient_id','case_id','access_receipt_id','synthetic','authority',
     'clinical_interpretation','research_review_invalidation_integrated',
     'composer_execution_authorized','snapshot_fingerprint','as_of_received_at',
     'summary','current_sources','history','observations','unresolved_refs','conflicts','limitations']);
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
     !Array.isArray(v.observations)||!Array.isArray(v.unresolved_refs)||
     !Array.isArray(v.conflicts)||!Array.isArray(v.limitations)||
     v.current_sources.length>512||v.history.length>512||
     v.observations.length>4096||v.unresolved_refs.length>4096||
     v.conflicts.length>1024||v.limitations.length>32)return error();
  const rawLabs=hasLaboratory?v.laboratory_observations:[];
  const rawTimeline=hasLaboratory?v.laboratory_timeline:[];
  if(!Array.isArray(rawLabs)||!Array.isArray(rawTimeline)||
     rawLabs.length>4096||rawTimeline.length>4096)return error();
  const current=v.current_sources.map(source),history=v.history.map(source);
  if(current.some(s=>s.state!=='current')||history.some(s=>s.state!=='superseded'))return error();
  const ids=new Set<string>();
  for(const s of [...current,...history]){if(ids.has(s.source_id))return error();ids.add(s.source_id);}
  const currentById=new Map(current.map(s=>[s.source_id,s]));
  const observations=v.observations.map(x=>obs(x,currentById));
  const laboratory=rawLabs.map(x=>labObs(x,currentById));
  const labByKey=new Map<string,WorldLaboratoryObservation>();
  for(const x of laboratory){
    const key=x.source_id+':'+x.observation_reference;
    if(labByKey.has(key))return error();
    labByKey.set(key,x);
  }
  const timeline:WorldLaboratoryTimelineItem[]=rawTimeline.map(raw=>{
    const x=shape(raw,['source_id','observation_reference','loinc_code','effective_at','issued_at',
      'specimen_reference','status','clinical_interpretation']);
    const key=str(x.source_id,36)+':'+str(x.observation_reference,128),lab=labByKey.get(key);
    if(!lab||x.loinc_code!==lab.loinc_code||x.effective_at!==lab.effective_at||
       x.issued_at!==lab.issued_at||x.specimen_reference!==lab.specimen_reference||
       x.status!==lab.status||x.clinical_interpretation!=='not_performed')return error();
    return Object.freeze({source_id:lab.source_id,observation_reference:lab.observation_reference,
      loinc_code:lab.loinc_code,effective_at:lab.effective_at,issued_at:lab.issued_at,
      specimen_reference:lab.specimen_reference,status:lab.status,
      clinical_interpretation:'not_performed' as const});
  });
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
    const context=relevant[0]?.oncology;
    if(context?.episode_id===null || relevant.some(x=>x?.oncology?.episode_id!==context?.episode_id ||
       x?.oncology?.role!==context?.role))return error();
    const states=new Set(relevant.map(x=>x!.reported_state));
    if(!states.has('reported')||!states.has('negative')||
       new Set(refs.map(refOf)).size!==refs.length||
       JSON.stringify([...states].sort())!==JSON.stringify(c.reported_states))return error();
    return Object.freeze({specimen_id:specimen,event_date:event,finding_key:finding,
      status:'unresolved_source_disagreement' as const,reported_states:Object.freeze([...states].sort()),
      source_refs:Object.freeze(refs),clinical_interpretation:'not_performed' as const});
  });
  const summary=shape(v.summary,hasLaboratory?
    ['current_sources','historical_sources','current_observations',
     'current_laboratory_observations','unresolved_observations','source_disagreements']:
    ['current_sources','historical_sources','current_observations',
     'unresolved_observations','source_disagreements']);
  const counts={current_sources:current.length,historical_sources:history.length,
    current_observations:observations.length+laboratory.length,
    current_laboratory_observations:laboratory.length,
    unresolved_observations:unresolved.length+
      laboratory.filter(x=>x.status==='reported_absent').length,
    source_disagreements:conflicts.length};
  for(const [key,value] of Object.entries(counts)){
    if(key==='current_laboratory_observations'&&!hasLaboratory)continue;
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
    laboratory_observations:Object.freeze(laboratory),laboratory_timeline:Object.freeze(timeline),
    unresolved_refs:Object.freeze(unresolved),
    conflicts:Object.freeze(conflicts),limitations:Object.freeze(v.limitations.slice() as string[]),
  });
}
