/** Exact packet contracts; a saved preparation is never a referral or clinical approval. */
import type {ViewState} from './registry-client.js';
import {citationEvidenceTimestamp} from './evidence-timestamp.js';
import {patientContinuity} from './patient-continuity.js';

export type PacketSource=Readonly<{source_id:string;document_id:string;version:number;sha256:string;kind:string;state:'current'|'superseded'}>;
export type PacketQuestion=Readonly<{question_id:string;question:string;source_id:string;source_line:number;
 source_context_state:'current_unreviewed_question'|'source_reassessment_required'}>;
export type SecondOpinionPacket=Readonly<{
 packet_id:string;patient_id:string;case_id:string;title:string;
 source_snapshot_contract:'oi.pg-source-world-model/1';source_snapshot_sha256:string;created_at:string;
 preparation_state:'current_preparation'|'source_reassessment_required';sources:readonly PacketSource[];questions:readonly PacketQuestion[];
 record_completeness_verified:false;recipient_verified:false;external_request_sent:false;clinical_approval:false;
}>;
export type SecondOpinionList=Readonly<{contract:'oi.pg-second-opinion-packets/1';patient_id:string;case_id:string;access_receipt_id:string;
 packets:readonly SecondOpinionPacket[];synthetic:true;recipient_verification_supported:false;external_dispatch_supported:false;clinical_approval:false}>;
export type PacketReceipt=Readonly<{packet_id:string;duplicate:boolean}>;
export type PacketDraft=Readonly<{patient_id:string;case_id:string;snapshot_sha256:string;title:string;
 source_ids:readonly string[];question_ids:readonly string[]}>;
export type PacketDraftPatch=Partial<Pick<PacketDraft,'title'|'source_ids'|'question_ids'>>;
export type PacketIntent=Readonly<{patient_id:string;case_id:string;body:string}>;
const ID={source:/^SRC-[0-9A-F]{32}$/,question:/^QUESTION-[0-9A-F]{32}$/,packet:/^SECONDOP-[0-9A-F]{32}$/,receipt:/^ACCESS-[0-9A-F]{32}$/};
const HEX=/^[a-f0-9]{64}$/;
const fail=():never=>{throw Error('second-opinion-packet-contract');};
function exact(v:unknown,keys:readonly string[]):Record<string,unknown>{
 if(!v||typeof v!=='object'||Array.isArray(v))return fail();
 const row=v as Record<string,unknown>;
 if(Object.keys(row).length!==keys.length||keys.some(key=>!Object.hasOwn(row,key)))return fail();return row;
}
function text(v:unknown,min:number,max:number):v is string{
 return typeof v==='string'&&Array.from(v).length>=min&&Array.from(v).length<=max&&
  !/[\u0000-\u001f\u007f]/.test(v)&&new TextDecoder('utf-8',{fatal:true}).decode(new TextEncoder().encode(v))===v;
}
function id(v:unknown,kind:keyof typeof ID):v is string{return typeof v==='string'&&ID[kind].test(v);}
function positive(v:unknown,max=Number.MAX_SAFE_INTEGER):v is number{return typeof v==='number'&&Number.isSafeInteger(v)&&v>0&&v<=max;}
function unique(rows:readonly string[]):boolean{return new Set(rows).size===rows.length;}
export function decodeSecondOpinionReceipt(value:unknown,status:number):PacketReceipt{
 const row=exact(value,['packet_id','duplicate']);
 if(!id(row.packet_id,'packet')||!((status===201&&row.duplicate===false)||(status===200&&row.duplicate===true)))return fail();
 return Object.freeze({packet_id:row.packet_id,duplicate:row.duplicate as boolean});
}
export function decodeSecondOpinionList(value:unknown,patientId:string,caseId:string):SecondOpinionList{
 const v=exact(value,['contract','patient_id','case_id','access_receipt_id','packets','synthetic',
  'recipient_verification_supported','external_dispatch_supported','clinical_approval']);
 if(v.contract!=='oi.pg-second-opinion-packets/1'||v.patient_id!==patientId||v.case_id!==caseId||
  !id(v.access_receipt_id,'receipt')||!Array.isArray(v.packets)||v.packets.length>100||v.synthetic!==true||
  v.recipient_verification_supported!==false||v.external_dispatch_supported!==false||v.clinical_approval!==false)return fail();
 const packets=v.packets.map(raw=>{
  const p=exact(raw,['packet_id','patient_id','case_id','title','source_snapshot_contract','source_snapshot_sha256',
   'created_at','preparation_state','sources','questions','record_completeness_verified','recipient_verified','external_request_sent','clinical_approval']);
  if(!id(p.packet_id,'packet')||p.patient_id!==patientId||p.case_id!==caseId||!text(p.title,8,300)||p.title!==p.title.trim()||
   p.source_snapshot_contract!=='oi.pg-source-world-model/1'||typeof p.source_snapshot_sha256!=='string'||!HEX.test(p.source_snapshot_sha256)||
   !citationEvidenceTimestamp(p.created_at)||!['current_preparation','source_reassessment_required'].includes(String(p.preparation_state))||
   p.record_completeness_verified!==false||p.recipient_verified!==false||p.external_request_sent!==false||p.clinical_approval!==false||
   !Array.isArray(p.sources)||!p.sources.length||p.sources.length>32||!Array.isArray(p.questions)||!p.questions.length||p.questions.length>16)return fail();
  const sources=p.sources.map(raw=>{
   const s=exact(raw,['source_id','document_id','version','sha256','kind','state']);
   if(!id(s.source_id,'source')||!text(s.document_id,1,128)||!positive(s.version)||typeof s.sha256!=='string'||!HEX.test(s.sha256)||
    !['clinical','pathology','laboratory','imaging','molecular','other'].includes(String(s.kind))||!['current','superseded'].includes(String(s.state)))return fail();
   return Object.freeze({...s} as PacketSource);
  });
  if(!unique(sources.map(s=>s.source_id)))return fail();
  const questions=p.questions.map(raw=>{
   const q=exact(raw,['question_id','question','source_id','source_line','source_context_state']);
   if(!id(q.question_id,'question')||!text(q.question,8,500)||!id(q.source_id,'source')||!sources.some(s=>s.source_id===q.source_id)||
    !positive(q.source_line,10000)||!['current_unreviewed_question','source_reassessment_required'].includes(String(q.source_context_state)))return fail();
   return Object.freeze({...q} as PacketQuestion);
  });
  if(!unique(questions.map(q=>q.question_id))||p.preparation_state==='current_preparation'&&
    (sources.some(s=>s.state!=='current')||questions.some(q=>q.source_context_state!=='current_unreviewed_question')))return fail();
  return Object.freeze({...p,sources:Object.freeze(sources),questions:Object.freeze(questions)} as SecondOpinionPacket);
 });
 if(!unique(packets.map(p=>p.packet_id)))return fail();
 return Object.freeze({...v,packets:Object.freeze(packets)} as SecondOpinionList);
}
/** Only existing, successfully decoded reads can offer selectable source versions. */
export function packetInputs(state:ViewState){
 const continuity=patientContinuity(state),world=state.worldModel;
 if(!continuity?.caseId||!continuity.questions||!world)return null;
 const sources=world.current_sources;
 const questions=state.questions!.filter(q=>q.source_context_state==='current_unreviewed_question'&&
  q.source_snapshot_contract===world.contract&&q.source_snapshot_sha256===world.snapshot_fingerprint&&
  sources.some(s=>s.source_id===q.source_id&&s.version===q.source_version&&s.sha256===q.source_sha256));
 return {patient_id:continuity.patientId,case_id:continuity.caseId,snapshot_sha256:world.snapshot_fingerprint,sources,questions};
}
export function activePacketDraft(state:ViewState):PacketDraft|null{
 const input=packetInputs(state),draft=state.secondOpinionDraft;
 return input&&draft&&draft.patient_id===input.patient_id&&draft.case_id===input.case_id&&draft.snapshot_sha256===input.snapshot_sha256&&
  draft.source_ids.every(id=>input.sources.some(s=>s.source_id===id))&&
  draft.question_ids.every(id=>input.questions.some(q=>q.question_id===id))?draft:null;
}
export function validPacketPatch(patch:PacketDraftPatch):boolean{
 if(!patch||typeof patch!=='object'||Array.isArray(patch)||!Object.keys(patch).length)return false;
 return Object.entries(patch).every(([key,value])=>key==='title'?typeof value==='string'&&Array.from(value).length<=300&&
  !/[\u0000-\u001f\u007f]/.test(value):key==='source_ids'||key==='question_ids'?
  Array.isArray(value)&&value.length<=(key==='source_ids'?32:16)&&unique(value)&&value.every(v=>id(v,key==='source_ids'?'source':'question')):false);
}
export function canSavePacket(state:ViewState):boolean{
 const input=packetInputs(state),draft=activePacketDraft(state);
 return !!(input&&draft&&text(draft.title,8,300)&&draft.title===draft.title.trim()&&draft.source_ids.length&&draft.question_ids.length&&
  draft.question_ids.every(id=>{const q=input.questions.find(q=>q.question_id===id);return q&&draft.source_ids.includes(q.source_id);})&&
  !['saving','unknown'].includes(state.secondOpinionWritePhase));
}
