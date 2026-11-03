/** Typed projection over the canonical follow-through owner. No client ledger or authority. */
import type {SourceQuestion} from './source-questions-view.js';
import type {SourceWorldModel} from './source-world-model.js';
import {canPrepareSourceBrief} from './source-brief.js';
import {citationEvidenceTimestamp} from './evidence-timestamp.js';

export type FollowthroughStatus='created'|'assigned'|'acknowledged'|'completed'|'deferred';
export type FollowthroughDraft=Readonly<{
 title:string;detail:string;owner_label:string;due_date:string|null;review_trigger:string;reason:string;
}>;
/** Unsent presentation input, bound to an already authorized question context. */
export type FollowthroughUnsentDraft=Readonly<{
 patient_id:string;case_id:string;source_snapshot_sha256:string;preflight_sha256:string;fields:FollowthroughDraft;
}>;
export type FollowthroughTransition=Readonly<{status:FollowthroughStatus;owner_label:string;reason:string}>;
export type FollowthroughEvent=Readonly<{
 event_id:string;revision:number;previous_status:FollowthroughStatus|null;status:FollowthroughStatus;
 owner_label:string;actor_label:string;reason:string;recorded_at:string;
}>;
export type FollowthroughTask=Readonly<{
 task_id:string;question_id:string;patient_id:string;case_id:string;
 title:string;detail:string;owner_label:string;due_date:string|null;review_trigger:string;
 created_at:string;status:FollowthroughStatus;revision:number;source_id:string;source_line:number;
 source_sha256:string;source_version:number;source_snapshot_contract:string;source_snapshot_sha256:string;
 preflight_sha256:string;source_context_state:'current_unreviewed_question'|'source_reassessment_required';
 needs_recheck:boolean;is_overdue:boolean;is_due_soon:boolean;clinical_approval:false;
 history:readonly FollowthroughEvent[];
}>;
export type FollowthroughList=Readonly<{
 contract:'oi.pg-question-followthrough/1';patient_id:string;case_id:string;access_receipt_id:string;
 evaluated_on:string;tasks:readonly FollowthroughTask[];synthetic:true;clinical_approval:false;external_notification_sent:false;
}>;
export type FollowthroughReceipt=Readonly<{
 task_id:string;question_id:string;event_id:string;revision:number;duplicate:boolean;
}>;
type CreationBody=Readonly<FollowthroughDraft&{
 synthetic:true;request_key:string;source_snapshot_contract:'oi.pg-source-world-model/1';
 expected_source_snapshot_sha256:string;expected_preflight_sha256:string;
}>;
type TransitionBody=Readonly<FollowthroughTransition&{synthetic:true;request_key:string;expected_revision:number}>;
export type FollowthroughIntent=Readonly<{
 kind:'create';patient_id:string;case_id:string;question_id:string;body:CreationBody;
}>|Readonly<{
 kind:'transition';patient_id:string;case_id:string;question_id:string;task_id:string;body:TransitionBody;
}>;

export const FOLLOWTHROUGH_TRANSITIONS:Readonly<Record<FollowthroughStatus,readonly FollowthroughStatus[]>>=Object.freeze({
 created:Object.freeze(['assigned','deferred'] as const),assigned:Object.freeze(['acknowledged','deferred'] as const),
 acknowledged:Object.freeze(['completed','deferred'] as const),deferred:Object.freeze(['assigned'] as const),completed:Object.freeze([]),
});
const canonical='oi.pg-source-world-model/1',legacy='oi.synthetic-postgres-world-model-sources/1';
const taskFields=['task_id','question_id','patient_id','case_id','title','detail','owner_label','due_date','review_trigger',
 'created_at','status','revision','source_id','source_line','source_sha256','source_version','source_snapshot_contract',
 'source_snapshot_sha256','preflight_sha256','source_context_state','needs_recheck','is_overdue','is_due_soon','clinical_approval','history'];
function exact(value:unknown,fields:readonly string[]):value is Record<string,unknown>{
 return value!==null&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).length===fields.length&&
  fields.every(key=>Object.hasOwn(value,key));
}
function id(value:unknown,prefix:string):value is string{
 return typeof value==='string'&&value.length===prefix.length+32&&new RegExp('^'+prefix+'[0-9A-F]{32}$').test(value);
}
function hash(value:unknown):value is string{return typeof value==='string'&&value.length===64&&/^[0-9a-f]{64}$/.test(value);}
function positive(value:unknown):value is number{return typeof value==='number'&&Number.isSafeInteger(value)&&value>0;}
function status(value:unknown):value is FollowthroughStatus{
 return typeof value==='string'&&Object.hasOwn(FOLLOWTHROUGH_TRANSITIONS,value);
}
export function validFollowthroughText(value:unknown,min:number,max:number):value is string{
 return typeof value==='string'&&!/[\p{Cc}\p{Cf}\p{Cs}]/u.test(value)&&
  Array.from(value.trim()).length>=min&&Array.from(value).length<=max;
}
export function validFollowthroughDate(value:unknown):value is string{
 if(typeof value!=='string'||value.length!==10||!/^\d{4}-\d{2}-\d{2}$/.test(value)||value<'0001-01-01')return false;
 const time=Date.parse(value+'T00:00:00Z');return Number.isFinite(time)&&new Date(time).toISOString().slice(0,10)===value;
}
function instant(value:unknown):value is string{
 // Task and citation timestamps share PostgreSQL's seconds / up-to-six-digit
 // microsecond wire format. Validate its calendar without Date.parse rollover.
 return citationEvidenceTimestamp(value);
}
export function validFollowthroughDraft(draft:FollowthroughDraft):boolean{
 return validFollowthroughText(draft.title,3,160)&&validFollowthroughText(draft.detail,0,2000)&&
  validFollowthroughText(draft.owner_label,0,80)&&validFollowthroughText(draft.review_trigger,0,500)&&
  validFollowthroughText(draft.reason,3,600)&&(draft.due_date===null||validFollowthroughDate(draft.due_date))&&
  (draft.due_date!==null||draft.review_trigger.trim().length>0);
}
export function canCreateFollowthrough(question:SourceQuestion,world:SourceWorldModel|null):boolean{
 // Source identity is a prerequisite only. Each write still needs its own server grant.
 return canPrepareSourceBrief(question,world);
}
export function validFollowthroughTransition(task:FollowthroughTask,draft:FollowthroughTransition):boolean{
 return status(draft.status)&&FOLLOWTHROUGH_TRANSITIONS[task.status].includes(draft.status)&&
  validFollowthroughText(draft.reason,3,600)&&
  validFollowthroughText(draft.owner_label,draft.status==='assigned'?2:0,80)&&
  (draft.status==='assigned'||draft.owner_label==='');
}

export function decodeFollowthrough(value:unknown,patient:string,caseId:string):FollowthroughList{
 if(!exact(value,['contract','patient_id','case_id','access_receipt_id','evaluated_on','tasks','synthetic',
  'clinical_approval','external_notification_sent'])||value.contract!=='oi.pg-question-followthrough/1'||
  value.patient_id!==patient||value.case_id!==caseId||!id(value.access_receipt_id,'ACCESS-')||
  !validFollowthroughDate(value.evaluated_on)||!Array.isArray(value.tasks)||value.tasks.length>250||
  value.synthetic!==true||value.clinical_approval!==false||value.external_notification_sent!==false)throw Error('task contract');
 const taskIds=new Set<string>(),eventIds=new Set<string>();
 const evaluatedOn=value.evaluated_on,today=Date.parse(evaluatedOn+'T00:00:00Z');
 const tasks=Object.freeze(value.tasks.map((row:unknown)=>{
  if(!exact(row,taskFields)||!id(row.task_id,'TASK-')||taskIds.has(row.task_id)||
   !id(row.question_id,'QUESTION-')||row.patient_id!==patient||row.case_id!==caseId||
   !validFollowthroughText(row.title,3,160)||!validFollowthroughText(row.detail,0,2000)||
   !validFollowthroughText(row.owner_label,0,80)||!validFollowthroughText(row.review_trigger,0,500)||
   (row.due_date!==null&&!validFollowthroughDate(row.due_date))||
   (row.due_date===null&&row.review_trigger.trim()==='')||!instant(row.created_at)||
   !status(row.status)||!positive(row.revision)||!id(row.source_id,'SRC-')||
   !positive(row.source_line)||row.source_line>10000||!positive(row.source_version)||!hash(row.source_sha256)||
   !hash(row.source_snapshot_sha256)||!hash(row.preflight_sha256)||
   ![canonical,legacy].includes(String(row.source_snapshot_contract))||
   !['current_unreviewed_question','source_reassessment_required'].includes(String(row.source_context_state))||
   (row.source_snapshot_contract===legacy&&row.source_context_state!=='source_reassessment_required')||
   row.clinical_approval!==false||!Array.isArray(row.history)||row.history.length!==row.revision||row.history.length>750)
   throw Error('task row');
  taskIds.add(row.task_id);
  let previous:FollowthroughEvent|null=null;
  const history=Object.freeze(row.history.map((item:unknown,index:number)=>{
   if(!exact(item,['event_id','revision','previous_status','status','owner_label','actor_label','reason','recorded_at'])||
    !id(item.event_id,'TASK-EVENT-')||eventIds.has(item.event_id)||eventIds.size>=750||item.revision!==index+1||
    !status(item.status)||!validFollowthroughText(item.owner_label,item.status==='assigned'?2:0,80)||
    !validFollowthroughText(item.actor_label,3,128)||!validFollowthroughText(item.reason,3,600)||!instant(item.recorded_at)||
    (previous?(item.previous_status!==previous.status||!FOLLOWTHROUGH_TRANSITIONS[previous.status].includes(item.status)||
      (item.status!=='assigned'&&item.owner_label!==previous.owner_label)):
     (item.previous_status!==null||item.status!=='created')))throw Error('task history');
   eventIds.add(item.event_id);
   const event=Object.freeze({...item} as FollowthroughEvent);previous=event;return event;
  }));
  const last=history.at(-1),open=['created','assigned','acknowledged'].includes(row.status);
  const due=row.due_date===null?null:Date.parse((row.due_date as string)+'T00:00:00Z');
  if(!last||last.status!==row.status||last.owner_label!==row.owner_label||
   row.needs_recheck!==(open&&row.source_context_state==='source_reassessment_required')||
   row.is_overdue!==(open&&due!==null&&due<today)||
   row.is_due_soon!==(open&&due!==null&&due>=today&&due<=today+7*86400000))throw Error('task projection');
  return Object.freeze({...row,history} as FollowthroughTask);
 }));
 return Object.freeze({...value,tasks} as FollowthroughList);
}

export function decodeFollowthroughReceipt(value:unknown,intent:FollowthroughIntent):FollowthroughReceipt{
 if(!exact(value,['task_id','question_id','event_id','revision','duplicate'])||!id(value.task_id,'TASK-')||
  value.question_id!==intent.question_id||!id(value.event_id,'TASK-EVENT-')||typeof value.duplicate!=='boolean'||
  value.revision!==(intent.kind==='create'?1:intent.body.expected_revision+1)||
  (intent.kind==='transition'&&value.task_id!==intent.task_id))throw Error('task receipt');
 return Object.freeze({...value} as FollowthroughReceipt);
}

export const FOLLOWTHROUGH_FILTERS=Object.freeze([
 {key:'all',label:'All work'},
 {key:'recheck',label:'Source changed'},
 {key:'overdue',label:'Revisit date passed'},
 {key:'unassigned',label:'Unassigned'},
 {key:'history',label:'Completed / deferred'},
] as const);
export type FollowthroughFilter=typeof FOLLOWTHROUGH_FILTERS[number]['key'];
export type FollowthroughAttention=Readonly<{
 list:FollowthroughList;counts:Readonly<Record<FollowthroughFilter,number>>;
}>;
export type FollowthroughFilterSelection=Readonly<{
 access_receipt_id:string;patient_id:string;case_id:string;filter:FollowthroughFilter;
}>;
type AttentionState=Pick<import('./registry-client.js').ViewState,
 'connected'|'phase'|'patient'|'cases'|'worldModel'|'followthrough'|'followthroughCaseId'|'followthroughPhase'>;

/** Operational categories may overlap. Never infer clinical urgency or recompute server dates. */
export function matchesFollowthroughFilter(task:FollowthroughTask,filter:FollowthroughFilter):boolean{
 const open=task.status==='created'||task.status==='assigned'||task.status==='acknowledged';
 switch(filter){
  case 'all':return true;
  case 'recheck':return open&&task.needs_recheck;
  case 'overdue':return open&&task.is_overdue;
  case 'unassigned':return open&&task.owner_label.trim()==='';
  case 'history':return task.status==='completed'||task.status==='deferred';
  default:return false;
 }
}

/** Read projection only: unknown/denied/mixed scope is unavailable, never a zero count. */
export function projectFollowthroughAttention(state:AttentionState):FollowthroughAttention|null{
 const list=state.followthrough,patient=state.patient,world=state.worldModel;
 if(!state.connected||state.phase!=='ready'||patient?.status!=='active'||
    state.followthroughPhase!=='ready'||!list||list.patient_id!==patient.patient_id||
    state.followthroughCaseId!==list.case_id||
    !state.cases?.some(row=>row.patient_id===patient.patient_id&&row.case_id===list.case_id&&row.status==='active')||
    (world&&(world.patient_id!==patient.patient_id||world.case_id!==list.case_id))||
    list.tasks.some(row=>row.patient_id!==patient.patient_id||row.case_id!==list.case_id)||
    new Set(list.tasks.map(row=>row.task_id)).size!==list.tasks.length)return null;
 const counts:Record<FollowthroughFilter,number>={all:0,recheck:0,overdue:0,unassigned:0,history:0};
 for(const row of list.tasks){
  for(const {key} of FOLLOWTHROUGH_FILTERS)if(matchesFollowthroughFilter(row,key))counts[key]++;
 }
 return Object.freeze({list,counts:Object.freeze(counts)});
}

/** Derive the reset during render; an effect would briefly show a new read under an old filter. */
export function followthroughFilterForRead(selection:FollowthroughFilterSelection|null,
 attention:FollowthroughAttention|null):FollowthroughFilter{
 if(!selection||!attention||selection.access_receipt_id!==attention.list.access_receipt_id||
    selection.patient_id!==attention.list.patient_id||selection.case_id!==attention.list.case_id||
    !FOLLOWTHROUGH_FILTERS.some(item=>item.key===selection.filter))return 'all';
 return selection.filter;
}
