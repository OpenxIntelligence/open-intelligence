/** Strict view over first-party PostgreSQL source-derived World Model.
 * Neither a diagnosis nor an authorized Composer/review result.
 */
export type WorldSource = Readonly<{
 source_version_id:string;document_id:string;version:number;source_sha256:string;
 kind:string;specimen_id:string|null;event_date:string;issued_at:string;
 received_at:string;state:'current'|'superseded';supersedes_source_id:string|null;
}>;
export type WorldObservation = Readonly<{
 assertion_id:number;finding_key:string;reported_state:string;source_statement:string;
 source_line:number;source_version_id:string;document_id:string;document_version:number;
 source_sha256:string;source_kind:string;specimen_id:string|null;event_date:string;
 issued_at:string;received_at:string;review_state:'not_established';clinical_meaning:null;
}>;
export type WorldConflict = Readonly<{
 specimen_id:string;event_date:string;finding_key:string;
 status:'unresolved_source_disagreement';reported_states:readonly string[];
 observation_refs:readonly Readonly<{assertion_id:number;source_version_id:string;source_line:number}>[];
 clinical_interpretation:'not_performed';
}>;
export type SourceWorldModel = Readonly<{
 contract:'oi.synthetic-postgres-world-model-sources/1';synthetic:true;
 patient_id:string;case_id:string;source_snapshot_sha256:string;
 authority:'source_report_only_unreviewed';clinical_interpretation:'not_generated';
 clinical_approval:false;review_workflow_connected:false;
 summary:Readonly<{current_sources:number;superseded_sources:number;
  current_observations:number;unresolved_observations:number;source_disagreements:number}>;
 current_sources:readonly WorldSource[];history:readonly WorldSource[];
 observations:readonly WorldObservation[];unresolved:readonly WorldObservation[];
 conflicts:readonly WorldConflict[];limitations:readonly string[];
}>;
const SOURCE=/^SRC-[0-9A-F]{32}$/;
const DOC=/^[A-Z][A-Z0-9-]{1,39}$/;
const HASH=/^[0-9a-f]{64}$/;
const DATE=/^\d{4}-\d{2}-\d{2}$/;
const KINDS=['clinical','pathology','laboratory','imaging','molecular','other'];
const STATES=['reported','negative','pending','indeterminate','not-reported','not-assessed','conflicting'];
const UNRESOLVED=['pending','indeterminate','not-reported','not-assessed','conflicting'];
function obj(value:unknown,keys:readonly string[]):value is Record<string,unknown>{
 return value!==null&&typeof value==='object'&&!Array.isArray(value)&&
  Object.keys(value).length===keys.length&&keys.every(k=>Object.hasOwn(value,k));
}
function integer(value:unknown):value is number{
 return typeof value==='number'&&Number.isSafeInteger(value)&&value>=0;
}
function text(value:unknown,max:number):value is string{
 return typeof value==='string'&&value.length>0&&value.length<=max&&
  !/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(value);
}
function date(value:unknown):value is string{
 return typeof value==='string'&&DATE.test(value)&&
  Number.isFinite(Date.parse(value+'T00:00:00Z'));
}
function timestamp(value:unknown):value is string{
 return typeof value==='string'&&/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value)&&
  Number.isFinite(Date.parse(value));
}
const sourceKeys=['source_version_id','document_id','version','source_sha256','kind','specimen_id',
 'event_date','issued_at','received_at','state','supersedes_source_id'];
const obsKeys=['assertion_id','finding_key','reported_state','source_statement','source_line',
 'source_version_id','document_id','document_version','source_sha256','source_kind',
 'specimen_id','event_date','issued_at','received_at','review_state','clinical_meaning'];
function source(value:unknown):WorldSource{
 if(!obj(value,sourceKeys)||
   typeof value.source_version_id!=='string'||!SOURCE.test(value.source_version_id)||
   typeof value.document_id!=='string'||!DOC.test(value.document_id)||
   !integer(value.version)||value.version<1||
   typeof value.source_sha256!=='string'||!HASH.test(value.source_sha256)||
   typeof value.kind!=='string'||!KINDS.includes(value.kind)||
   (value.specimen_id!==null&&(typeof value.specimen_id!=='string'||!DOC.test(value.specimen_id)))||
   !date(value.event_date)||!date(value.issued_at)||!timestamp(value.received_at)||
   !['current','superseded'].includes(String(value.state))||
   (value.supersedes_source_id!==null&&
     (typeof value.supersedes_source_id!=='string'||!SOURCE.test(value.supersedes_source_id))))throw Error('contract');
 return Object.freeze(value as WorldSource);
}
function observation(value:unknown, current:Map<string,WorldSource>):WorldObservation{
 if(!obj(value,obsKeys)||!integer(value.assertion_id)||value.assertion_id<1||
   typeof value.finding_key!=='string'||!/^[a-z][a-z0-9_-]{0,59}$/.test(value.finding_key)||
   typeof value.reported_state!=='string'||!STATES.includes(value.reported_state)||
   !text(value.source_statement,1200)||!integer(value.source_line)||value.source_line<1||
   typeof value.source_version_id!=='string'||!current.has(value.source_version_id)||
   !integer(value.document_version)||value.document_version<1||
   value.review_state!=='not_established'||value.clinical_meaning!==null)throw Error('contract');
 const original=current.get(value.source_version_id)!;
 if(value.document_id!==original.document_id||
   value.document_version!==original.version||value.source_sha256!==original.source_sha256||
   value.source_kind!==original.kind||value.specimen_id!==original.specimen_id||
   value.event_date!==original.event_date||value.issued_at!==original.issued_at||
   value.received_at!==original.received_at)throw Error('contract');
 return Object.freeze(value as WorldObservation);
}
export function decodeSourceWorldModel(value:unknown,patientId:string,caseId:string):SourceWorldModel{
 const keys=['contract','synthetic','patient_id','case_id','source_snapshot_sha256','authority',
  'clinical_interpretation','clinical_approval','review_workflow_connected','summary',
  'current_sources','history','observations','unresolved','conflicts','limitations'];
 if(!obj(value,keys)||value.contract!=='oi.synthetic-postgres-world-model-sources/1'||
   value.synthetic!==true||value.patient_id!==patientId||value.case_id!==caseId||
   typeof value.source_snapshot_sha256!=='string'||!HASH.test(value.source_snapshot_sha256)||
   value.authority!=='source_report_only_unreviewed'||value.clinical_interpretation!=='not_generated'||
   value.clinical_approval!==false||value.review_workflow_connected!==false||
   !obj(value.summary,['current_sources','superseded_sources','current_observations',
    'unresolved_observations','source_disagreements'])||
   !Object.values(value.summary).every(integer)||
   !Array.isArray(value.current_sources)||value.current_sources.length>128||
   !Array.isArray(value.history)||value.history.length>128||
   !Array.isArray(value.observations)||value.observations.length>512||
   !Array.isArray(value.unresolved)||value.unresolved.length>512||
   !Array.isArray(value.conflicts)||value.conflicts.length>256||
   !Array.isArray(value.limitations)||value.limitations.length===0||
   !value.limitations.every((x:unknown)=>text(x,500)))throw Error('contract');
 const currentSources=value.current_sources.map(source);
 const history=value.history.map(source);
 const sourceIds=new Set<string>();
 for(const item of [...currentSources,...history]){
   if(sourceIds.has(item.source_version_id))throw Error('contract');
   sourceIds.add(item.source_version_id);
 }
 if(currentSources.some(x=>x.state!=='current')||history.some(x=>x.state!=='superseded')||
   currentSources.length!==value.summary.current_sources||
   history.length!==value.summary.superseded_sources)throw Error('contract');
 const byCurrent=new Map(currentSources.map(x=>[x.source_version_id,x]));
 const seen=new Set<number>(),seenLines=new Set<string>();
 const observations=value.observations.map((o:unknown)=>{
   const x=observation(o,byCurrent),line=x.source_version_id+':'+x.source_line;
   if(seen.has(x.assertion_id)||seenLines.has(line))throw Error('contract');
   seen.add(x.assertion_id);seenLines.add(line);return x;
 });
 const unresolved=value.unresolved.map((o:unknown)=>observation(o,byCurrent));
 const expectedUnresolved=observations.filter(x=>UNRESOLVED.includes(x.reported_state));
 if(unresolved.length!==expectedUnresolved.length||
   unresolved.some((x,i)=>x.assertion_id!==expectedUnresolved[i].assertion_id))throw Error('contract');
 const byAssertion=new Map(observations.map(x=>[x.assertion_id,x]));
 const conflicts=value.conflicts.map((c:unknown)=>{
   if(!obj(c,['specimen_id','event_date','finding_key','status','reported_states','observation_refs','clinical_interpretation'])||
      typeof c.specimen_id!=='string'||!DOC.test(c.specimen_id)||
      !date(c.event_date)||typeof c.finding_key!=='string'||!/^[a-z][a-z0-9_-]{0,59}$/.test(c.finding_key)||
      c.status!=='unresolved_source_disagreement'||c.clinical_interpretation!=='not_performed'||
      !Array.isArray(c.reported_states)||c.reported_states.length!==2||
      !c.reported_states.includes('reported')||!c.reported_states.includes('negative')||
      !Array.isArray(c.observation_refs)||c.observation_refs.length<2)throw Error('contract');
   for(const ref of c.observation_refs){
     if(!obj(ref,['assertion_id','source_version_id','source_line']))throw Error('contract');
     const observation=byAssertion.get(ref.assertion_id);
     if(!observation||observation.source_version_id!==ref.source_version_id||
       observation.source_line!==ref.source_line||observation.specimen_id!==c.specimen_id||
       observation.event_date!==c.event_date||observation.finding_key!==c.finding_key)throw Error('contract');
   }
   return Object.freeze(c as WorldConflict);
 });
 if(observations.length!==value.summary.current_observations||
   unresolved.length!==value.summary.unresolved_observations||
   conflicts.length!==value.summary.source_disagreements)throw Error('contract');
 return Object.freeze({...value,current_sources:Object.freeze(currentSources),history:Object.freeze(history),
  observations:Object.freeze(observations),unresolved:Object.freeze(unresolved),
  conflicts:Object.freeze(conflicts)} as SourceWorldModel);
}
