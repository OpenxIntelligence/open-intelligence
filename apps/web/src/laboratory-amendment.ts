import type {FollowthroughTask} from './followthrough-view.js';
import {validFollowthroughText} from './followthrough-view.js';
import {authoredEvidenceTimestamp,citationEvidenceTimestamp} from './evidence-timestamp.js';
import {isLaboratoryAbsentReason} from './source-world-model.js';

export type AmendmentScope=Readonly<{patient_id:string;case_id:string}>;
export type AmendmentItem=Readonly<{request_id:string;task_id:string;question_id:string;latest_source_id:string}>;
export type Disposition='transcription_checked'|'needs_clarification';
type Observation=Readonly<{loinc_code:string;status:'reported_value'|'reported_absent';value_text:string|null;
 unit_code:string|null;absent_reason:string|null;specimen_reference:string;effective_at:string;issued_at:string}>;
export type AmendmentVersion=Readonly<{source_id:string;version:number;sha256:string;document_id:string;observation:Observation|null}>;
type Entry=Readonly<{entry_id:string;request_id:string;action:'request'|'respond';actor:string;recorded_at:string;
 reason:string;disposition:Disposition|null;original_source_id:string;latest_source_id:string;latest_sha256:string}>;
export type AmendmentDetail=Readonly<AmendmentScope&{task_id:string;question_id:string;observation_reference:string;
 original:AmendmentVersion;latest:AmendmentVersion;entries:readonly Entry[]}>;
export type AmendmentIntent=Readonly<{action:'request'|'respond';reason:string;request_key:string;synthetic:true;
 expected_latest_source_id:string;expected_latest_sha256:string;request_id?:string;disposition?:Disposition}>;
export type AmendmentReceipt=Readonly<{entry_id:string;request_id:string;duplicate:boolean}>;

function invalid():never{throw Error('Laboratory amendment response did not match the selected record');}
function exact(value:unknown,fields:string):value is Record<string,unknown>{
 const keys=fields.split(' ');
 return !!value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).length===keys.length&&keys.every(k=>Object.hasOwn(value,k));
}
function id(value:unknown,prefix:string):value is string{
 return typeof value==='string'&&value.startsWith(prefix+'-')&&value.length===prefix.length+33&&/^[A-F0-9]{32}$/.test(value.slice(-32));
}
function digest(value:unknown):value is string{return typeof value==='string'&&value.length===64&&/^[a-f0-9]+$/.test(value);}
export function validAmendmentReason(value:unknown):value is string{return validFollowthroughText(value,3,600)&&value===value.trim();}
export function validDisposition(value:unknown):value is Disposition{return value==='transcription_checked'||value==='needs_clarification';}

export function decodeAmendmentInbox(value:unknown,scope:AmendmentScope):readonly AmendmentItem[]{
 if(!exact(value,'contract patient_id case_id requests clinical_approval')||value.contract!=='oi.laboratory-amendment-inbox/1'||
    value.patient_id!==scope.patient_id||value.case_id!==scope.case_id||value.clinical_approval!==false||
    !Array.isArray(value.requests)||value.requests.length>750)return invalid();
 const seen=new Set<string>(),bases=new Set<string>();
 return Object.freeze(value.requests.map((row:unknown)=>{
  if(!exact(row,'request_id task_id question_id latest_source_id')||!id(row.request_id,'VERIFY')||seen.has(row.request_id)||
     !id(row.task_id,'TASK')||!id(row.question_id,'QUESTION')||!id(row.latest_source_id,'SRC'))return invalid();
  const basis=row.task_id+'/'+row.latest_source_id;if(bases.has(basis))return invalid();
  seen.add(row.request_id);bases.add(basis);
  return Object.freeze({...row} as AmendmentItem);
 }));
}

function version(value:unknown,allowMissing:boolean):AmendmentVersion{
 if(!exact(value,'source_id version sha256 document_id observation')||!id(value.source_id,'SRC')||!digest(value.sha256)||
    !validFollowthroughText(value.document_id,1,128)||!Number.isSafeInteger(value.version)||Number(value.version)<1)return invalid();
 const obs=value.observation;
 if(obs===null&&allowMissing)return Object.freeze({...value} as AmendmentVersion);
 if(!exact(obs,'loinc_code status value_text unit_code absent_reason specimen_reference effective_at issued_at')||
    typeof obs.loinc_code!=='string'||!/^\d{1,6}-\d$/.test(obs.loinc_code)||
    typeof obs.specimen_reference!=='string'||!/^Specimen\/[A-Za-z0-9.-]{1,64}$/.test(obs.specimen_reference)||
    !authoredEvidenceTimestamp(obs.effective_at)||!authoredEvidenceTimestamp(obs.issued_at))return invalid();
 if(obs.status==='reported_value'){
  if(!validFollowthroughText(obs.value_text,1,64)||!validFollowthroughText(obs.unit_code,1,32)||obs.absent_reason!==null)return invalid();
 }else if(obs.status!=='reported_absent'||obs.value_text!==null||obs.unit_code!==null||!isLaboratoryAbsentReason(obs.absent_reason))return invalid();
 return Object.freeze({...value,observation:Object.freeze({...obs})} as AmendmentVersion);
}

export function decodeAmendmentReview(value:unknown,task:FollowthroughTask,selected?:AmendmentItem|null):AmendmentDetail{
 if(!exact(value,'contract patient_id case_id task_id question_id observation_reference original latest entries clinical_approval')||
    value.contract!=='oi.laboratory-amendment-review/1'||value.clinical_approval!==false||task.source_line!==null||
    value.patient_id!==task.patient_id||value.case_id!==task.case_id||value.task_id!==task.task_id||
    value.question_id!==task.question_id||value.observation_reference!==task.observation_reference||
    !Array.isArray(value.entries)||value.entries.length>750)return invalid();
 const original=version(value.original,false),latest=version(value.latest,true);
 if(original.source_id!==task.source_id||original.sha256!==task.source_sha256||original.version!==task.source_version||
    latest.document_id!==original.document_id||latest.version<=original.version||latest.source_id===original.source_id)return invalid();
 const ids=new Set<string>(),answered=new Set<string>(),bases=new Set<string>(),requests=new Map<string,Entry>();
 const entries=value.entries.map((row:unknown)=>{
  if(!exact(row,'entry_id request_id action actor recorded_at reason disposition original_source_id latest_source_id latest_sha256')||
     !id(row.entry_id,'VERIFY')||ids.has(row.entry_id)||!id(row.request_id,'VERIFY')||
     !validAmendmentReason(row.reason)||!validFollowthroughText(row.actor,3,128)||!citationEvidenceTimestamp(row.recorded_at)||
     row.original_source_id!==original.source_id||!id(row.latest_source_id,'SRC')||row.latest_source_id===original.source_id||
     !digest(row.latest_sha256)||(row.latest_source_id===latest.source_id&&row.latest_sha256!==latest.sha256))return invalid();
  const entry=Object.freeze({...row} as Entry);
  ids.add(entry.entry_id);
  if(entry.action==='request'){
   if(entry.entry_id!==entry.request_id||entry.disposition!==null||bases.has(entry.latest_source_id))return invalid();
   bases.add(entry.latest_source_id);requests.set(entry.request_id,entry);
  }else{
   const prior=requests.get(entry.request_id);
   if(entry.action!=='respond'||!prior||answered.has(entry.request_id)||!validDisposition(entry.disposition)||
      prior.actor===entry.actor||prior.latest_source_id!==entry.latest_source_id||prior.latest_sha256!==entry.latest_sha256)return invalid();
   answered.add(entry.request_id);
  }
  return entry;
 });
 if(selected&&(selected.task_id!==task.task_id||selected.question_id!==task.question_id||
    requests.get(selected.request_id)?.latest_source_id!==selected.latest_source_id))return invalid();
 return Object.freeze({patient_id:task.patient_id,case_id:task.case_id,task_id:task.task_id,question_id:task.question_id,
  observation_reference:task.observation_reference,original,latest,entries:Object.freeze(entries)});
}

export function amendmentAction(detail:AmendmentDetail,selection:AmendmentItem|null):'request'|'respond'|null{
 if(!selection)return detail.entries.some(e=>e.action==='request'&&e.latest_source_id===detail.latest.source_id)?null:'request';
 if(selection.latest_source_id!==detail.latest.source_id)return null;
 const entries=detail.entries.filter(e=>e.request_id===selection.request_id);
 return entries.length===1&&entries[0].action==='request'&&entries[0].latest_source_id===detail.latest.source_id?'respond':null;
}
export function decodeAmendmentReceipt(value:unknown,body:AmendmentIntent,status:number):AmendmentReceipt{
 if(!exact(value,'entry_id request_id duplicate')||!id(value.entry_id,'VERIFY')||!id(value.request_id,'VERIFY')||
    value.duplicate!==(status===200)||(status!==200&&status!==201)||
    (body.action==='request'?value.request_id!==value.entry_id:value.request_id!==body.request_id||value.entry_id===value.request_id))return invalid();
 return Object.freeze({...value} as AmendmentReceipt);
}
