/** Literal, source-linked question brief. No model execution or clinical review. */
import type {RegistrySession} from './registry-client.js';
import type {SourceWorldModel} from './source-world-model.js';
import type {ComposerSource} from './composer-preflight-view.js';
import {decodeSourceQuestion} from './source-questions-view.js';
import type {SourceQuestion} from './source-questions-view.js';

export type SourceBrief=Readonly<{
 contract:'oi.synthetic-source-brief/2';synthetic:true;patient_id:string;case_id:string;
 source_snapshot_contract:'oi.pg-source-world-model/1';source_snapshot_sha256:string;
 access_receipt_id:string;question:SourceQuestion;selected_source:ComposerSource;
 prepared_at:string;media_type:'text/plain;charset=utf-8';body:string;body_sha256:string;
 clinical_approval:false;model_executed:false;biomedical_evidence_included:false;
}>;
const FIELDS=['contract','synthetic','patient_id','case_id','source_snapshot_contract',
 'source_snapshot_sha256','access_receipt_id','question','selected_source','prepared_at',
 'media_type','body','body_sha256','clinical_approval','model_executed','biomedical_evidence_included'];
const ANCHOR=['source_id','document_id','version','sha256','line','finding_key',
 'reported_state','statement','kind','event_date','issued_at','specimen_id'];
function exact(value:unknown,keys:readonly string[]):value is Record<string,unknown>{
 return value!==null&&typeof value==='object'&&!Array.isArray(value)&&
  Object.keys(value).length===keys.length&&keys.every(k=>Object.hasOwn(value,k));
}

/** Local prerequisite only. The server independently checks the saved question and export grant. */
export function canPrepareSourceBrief(question:SourceQuestion,world:SourceWorldModel|null):boolean{
 return Boolean(world&&question.patient_id===world.patient_id&&question.case_id===world.case_id&&
  question.source_snapshot_contract==='oi.pg-source-world-model/1'&&
  question.source_context_state==='current_unreviewed_question'&&
  question.source_snapshot_sha256===world.snapshot_fingerprint&&
  world.observations.some(o=>o.source_id===question.source_id&&o.source_line===question.source_line&&
    o.source_sha256===question.source_sha256&&o.document_version===question.source_version));
}

export async function decodeSourceBrief(value:unknown,world:SourceWorldModel,
                                       selected:SourceQuestion):Promise<SourceBrief>{
 if(!canPrepareSourceBrief(selected,world)||!exact(value,FIELDS)||
  value.contract!=='oi.synthetic-source-brief/2'||value.synthetic!==true||
  value.patient_id!==world.patient_id||value.case_id!==world.case_id||
  value.source_snapshot_contract!=='oi.pg-source-world-model/1'||
  value.source_snapshot_sha256!==world.snapshot_fingerprint||
  typeof value.access_receipt_id!=='string'||value.access_receipt_id.length!==39||
  !/^ACCESS-[0-9A-F]{32}$/.test(value.access_receipt_id)||
  value.media_type!=='text/plain;charset=utf-8'||value.clinical_approval!==false||
  value.model_executed!==false||value.biomedical_evidence_included!==false||
  typeof value.prepared_at!=='string'||value.prepared_at.length>64||
  !/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value.prepared_at)||
  !Number.isFinite(Date.parse(value.prepared_at))||
  typeof value.body!=='string'||value.body.trim().length===0||
  typeof value.body_sha256!=='string'||value.body_sha256.length!==64||
  !/^[0-9a-f]{64}$/.test(value.body_sha256)||!exact(value.selected_source,ANCHOR))throw Error('brief contract');
 const question=decodeSourceQuestion(value.question,world.patient_id,world.case_id);
 if(!Object.entries(selected).every(([key,expected])=>question[key as keyof SourceQuestion]===expected))
  throw Error('brief question');
 const observation=world.observations.find(o=>o.source_id===selected.source_id&&o.source_line===selected.source_line);
 const item=value.selected_source;
 if(!observation||item.source_id!==observation.source_id||item.document_id!==observation.document_id||
  item.version!==observation.document_version||item.sha256!==observation.source_sha256||
  item.line!==observation.source_line||item.finding_key!==observation.finding_key||
  item.reported_state!==observation.reported_state||item.statement!==observation.source_statement||
  item.kind!==observation.source_kind||item.event_date!==observation.event_date||
  item.issued_at!==observation.issued_at||item.specimen_id!==observation.specimen_id)throw Error('brief anchor');
 const bytes=new TextEncoder().encode(value.body);
 if(bytes.byteLength>65536||new TextDecoder('utf-8',{fatal:true}).decode(bytes)!==value.body)
  throw Error('brief bytes');
 const hash=await crypto.subtle.digest('SHA-256',bytes);
 const actual=Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');
 if(actual!==value.body_sha256)throw Error('brief integrity');
 return Object.freeze({...value,question,selected_source:Object.freeze({...item} as ComposerSource)} as SourceBrief);
}

/** A preview is never an export permission. Fetch and verify again before creating any Blob. */
export async function downloadSourceBrief(session:RegistrySession,questionId:string):Promise<void>{
 const brief=await session.prepareSourceBrief(questionId);
 if(!brief||session.snapshot().sourceBrief!==brief)return;
 const url=URL.createObjectURL(new Blob([brief.body],{type:brief.media_type}));
 const link=document.createElement('a');
 link.href=url;link.download='open-intelligence-source-question-brief.txt';
 try{document.body.append(link);link.click();}finally{
  link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }
}
