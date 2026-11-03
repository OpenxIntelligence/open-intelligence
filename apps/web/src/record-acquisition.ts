/** Transient acquisition UI over the existing patient/source owners; no credentials or ledger. */
import type {SourceIndex, SourceVersion, CaseBinding} from './source-contracts.js';
export const RECORD_KINDS=['clinical','pathology','laboratory','imaging','molecular','other'] as const;
export type RequestDraft=Readonly<{kind:string;record_label:string;source_organization:string}>;
export type SourceReference=Readonly<{case_id:string;source_id:string;version:number;sha256:string}>;
export type RecordRequest=Readonly<RequestDraft & {
 request_id:string;patient_id:string;status:'requested'|'received'|'cancelled';revision:number;
 created_at:string;updated_at:string;receipt_status:'not_received'|'source_current_unreviewed'|
 'source_superseded_reconciliation_required'|'binding_revoked_not_usable';
 source_reference:SourceReference|null;external_request_sent:false;
}>;
export type AcquisitionCommand=Readonly<{
 operation:'list'|'create'|'cancel'|'receive';patientId:string;requestId?:string;
 sourceId?:string;version?:number;body?:Readonly<Record<string,unknown>>;
}>;
export type AcquisitionReceipt=Readonly<{request_id:string;duplicate:boolean;source_id?:string;version?:number}>;
export type AcquisitionState=Readonly<{
 phase:'idle'|'loading'|'ready'|'error';requests:readonly RecordRequest[]|null;message:string;
 draft:RequestDraft;writePhase:'idle'|'sending'|'confirmed'|'unknown'|'rejected';
 intent:AcquisitionCommand|null;receipt:AcquisitionReceipt|null;writeMessage:string;
}>;
type Context={scope:string;patientId:string|null;ready:boolean;sourceIndex:SourceIndex|null;cases:readonly CaseBinding[]|null;sourceBusy:boolean};
type Host={context:()=>Context;send:(command:AcquisitionCommand,signal:AbortSignal)=>Promise<Response>;expired:()=>void};
const RID=/^RECORD-[0-9A-F]{32}$/, SID=/^SRC-[0-9A-F]{32}$/, CID=/^CASE-[A-Z0-9-]{1,35}$/, HASH=/^[0-9a-f]{64}$/;
const fields=['request_id','patient_id','kind','record_label','source_organization','status','revision','created_at','updated_at','receipt_status','source_reference','external_request_sent'];
function exact(v:unknown,keys:readonly string[]):v is Record<string,unknown>{return v!==null&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));}
function label(v:unknown,max:number):v is string{return typeof v==='string'&&v.trim().length>0&&Array.from(v.trim()).length<=max&&!/[\x00-\x1f\x7f]/.test(v);}
function timestamp(v:unknown):v is string{return typeof v==='string'&&/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(v)&&Number.isFinite(Date.parse(v));}
function version(v:unknown):v is number{return typeof v==='number'&&Number.isSafeInteger(v)&&v>=1;}
function sourceRef(raw:unknown):SourceReference|null{
 if(raw===null)return null;
 if(!exact(raw,['case_id','source_id','version','sha256'])||typeof raw.case_id!=='string'||!CID.test(raw.case_id)||
 typeof raw.source_id!=='string'||!SID.test(raw.source_id)||!version(raw.version)||typeof raw.sha256!=='string'||!HASH.test(raw.sha256))throw Error('contract');
 return Object.freeze({...raw} as SourceReference);
}
export function decodeRequests(value:unknown,patientId:string):readonly RecordRequest[]{
 if(!exact(value,['patient_id','requests','synthetic','external_request_sent','source_receipts_enabled'])||value.patient_id!==patientId||
 value.synthetic!==true||value.external_request_sent!==false||value.source_receipts_enabled!==true||!Array.isArray(value.requests)||value.requests.length>1000)throw Error('contract');
 const seen=new Set<string>();
 return Object.freeze(value.requests.map(raw=>{
  if(!exact(raw,fields)||typeof raw.request_id!=='string'||!RID.test(raw.request_id)||seen.has(raw.request_id)||raw.patient_id!==patientId||
  !RECORD_KINDS.includes(raw.kind as typeof RECORD_KINDS[number])||!label(raw.record_label,140)||!label(raw.source_organization,100)||
  !['requested','received','cancelled'].includes(String(raw.status))||!version(raw.revision)||!timestamp(raw.created_at)||!timestamp(raw.updated_at)||
  Date.parse(raw.updated_at)<Date.parse(raw.created_at)||raw.external_request_sent!==false)throw Error('contract');
  const ref=sourceRef(raw.source_reference);
  if(raw.status==='received'){
   if(raw.revision!==2||!['source_current_unreviewed','source_superseded_reconciliation_required','binding_revoked_not_usable'].includes(String(raw.receipt_status))||
   (raw.receipt_status==='binding_revoked_not_usable'&&ref!==null))throw Error('contract');
  }else if(raw.receipt_status!=='not_received'||ref!==null||raw.revision!==(raw.status==='requested'?1:2))throw Error('contract');
  seen.add(raw.request_id);return Object.freeze({...raw,source_reference:ref} as RecordRequest);
 }));
}
export function decodeReceipt(value:unknown,intent:AcquisitionCommand):AcquisitionReceipt{
 const keys=intent.operation==='receive'?['request_id','source_id','version','duplicate']:['request_id','duplicate'];
 if(!exact(value,keys)||typeof value.request_id!=='string'||!RID.test(value.request_id)||typeof value.duplicate!=='boolean'||
 (intent.requestId!==undefined&&value.request_id!==intent.requestId))throw Error('contract');
 if(intent.operation==='receive'&&(value.source_id!==intent.sourceId||value.version!==intent.version))throw Error('contract');
 return Object.freeze({...value} as AcquisitionReceipt);
}
export function receiptLabel(row:RecordRequest):string{
 if(row.status==='cancelled')return 'Tracking cancelled · no external cancellation sent';
 const labels={not_received:'Awaiting record · not sent externally',source_current_unreviewed:'Original linked · not clinically reviewed',
 source_superseded_reconciliation_required:'Original amended · reassessment needed',binding_revoked_not_usable:'Case access revoked · source withheld'};
 return labels[row.receipt_status];
}
export function eligibleSources(row:RecordRequest,patientId:string,index:SourceIndex|null,cases:readonly CaseBinding[]|null):readonly SourceVersion[]{
 if(row.patient_id!==patientId||row.status!=='requested'||!index||index.patient_id!==patientId||!cases?.some(c=>c.patient_id===patientId&&c.case_id===index.case_id&&c.status==='active'))return [];
 return index.sources.filter(s=>s.kind===row.kind&&s.state==='current');
}
const fresh=():AcquisitionState=>Object.freeze({phase:'idle',requests:null,message:'Check record requests for the open patient.',
 draft:Object.freeze({kind:'clinical',record_label:'',source_organization:''}),writePhase:'idle',intent:null,receipt:null,writeMessage:''});
async function body(response:Response):Promise<unknown>{
 if(!/^application\/json(?:\s*;|$)/i.test(response.headers.get('Content-Type')??''))throw Error('contract');
 const length=response.headers.get('Content-Length');if(length!==null&&(!/^\d+$/.test(length)||Number(length)>524288))throw Error('limit');
 const reader=response.body?.getReader();if(!reader)throw Error('body');
 const chunks:Uint8Array[]=[];let size=0;
 try{while(true){const part=await reader.read();if(part.done)break;size+=part.value.length;if(size>524288){await reader.cancel();throw Error('limit')}chunks.push(part.value)}}finally{reader.releaseLock()}
 const bytes=new Uint8Array(size);let at=0;for(const c of chunks){bytes.set(c,at);at+=c.length}
 return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
}
export class RecordAcquisition{
 #state=fresh();#generation=0;#reads=0;#writes=0;#listeners=new Set<()=>void>();#controllers=new Set<AbortController>();
 constructor(private readonly host:Host){}
 snapshot=():AcquisitionState=>this.#state;
 subscribe=(listener:()=>void)=>{this.#listeners.add(listener);return()=>this.#listeners.delete(listener)};
 #publish(patch:Partial<AcquisitionState>){this.#state=Object.freeze({...this.#state,...patch});for(const l of this.#listeners)l()}
 clear=()=>{this.#generation++;this.#reads++;this.#writes++;for(const c of this.#controllers)c.abort();this.#controllers.clear();this.#state=fresh();for(const l of this.#listeners)l()};
 /** A source change/refresh makes previous freshness unknown; exact uncertain intent survives. */
 invalidate=()=>{this.#reads++;this.#publish({requests:null,phase:'idle',message:'Source context changed. Recheck request and receipt status.'})};
 setDraft=(draft:RequestDraft)=>{if(['sending','unknown'].includes(this.#state.writePhase))return;
  if(typeof draft.kind!=='string'||typeof draft.record_label!=='string'||typeof draft.source_organization!=='string')return;
  this.#publish({draft:Object.freeze({...draft})})};
 #current(ctx:Context,generation:number){const now=this.host.context();return generation===this.#generation&&now.ready&&now.scope===ctx.scope&&now.patientId===ctx.patientId}
 async load():Promise<void>{
  const ctx=this.host.context();if(!ctx.ready||!ctx.patientId||this.#state.writePhase==='sending')return;
  const generation=this.#generation,read=++this.#reads,control=new AbortController();this.#controllers.add(control);
  const current=()=>this.#current(ctx,generation)&&read===this.#reads;
  const timer=setTimeout(()=>control.abort(),10000);
  this.#publish({requests:null,phase:'loading',message:'Checking current request permissions and original receipt status…'});
  try{
   const res=await this.host.send({operation:'list',patientId:ctx.patientId},control.signal);if(!current())return;
   if(res.status===401){this.clear();this.host.expired();return}
   if(res.status!==200)throw Error('unavailable');
   const rows=decodeRequests(await body(res),ctx.patientId);if(!current())return;
   this.#publish({requests:rows,phase:'ready',message:rows.length?'Request history checked. These are internal tracking records, not sent provider requests.':'No tracked record requests were returned. This does not establish a complete record.'});
  }catch(_){if(current())this.#publish({requests:null,phase:'error',message:'Request history unavailable or permission denied. The number of missing records is unknown.'})}
  finally{clearTimeout(timer);this.#controllers.delete(control)}
 }
 async create(confirmed:boolean):Promise<void>{
  if(['sending','unknown'].includes(this.#state.writePhase))return;
  const ctx=this.host.context(),draft=this.#state.draft;
  if(!ctx.ready||!ctx.patientId||confirmed!==true||!RECORD_KINDS.includes(draft.kind as typeof RECORD_KINDS[number])||
   !label(draft.record_label,140)||!label(draft.source_organization,100))return;
  await this.#write(Object.freeze({operation:'create',patientId:ctx.patientId,body:Object.freeze({synthetic:true,request_key:crypto.randomUUID(),kind:draft.kind,record_label:draft.record_label.trim(),source_organization:draft.source_organization.trim()})}));
 }
 async cancel(requestId:string,reason:string,confirmed:boolean):Promise<void>{
  if(['sending','unknown'].includes(this.#state.writePhase))return;
  const ctx=this.host.context(),row=this.#state.requests?.find(r=>r.request_id===requestId);
  if(!ctx.ready||!ctx.patientId||!row||row.patient_id!==ctx.patientId||row.status!=='requested'||confirmed!==true||!label(reason,200))return;
  await this.#write(Object.freeze({operation:'cancel',patientId:ctx.patientId,requestId,body:Object.freeze({synthetic:true,reason:reason.trim()})}));
 }
 async receive(requestId:string,sourceId:string,confirmed:boolean):Promise<void>{
  if(['sending','unknown'].includes(this.#state.writePhase))return;
  const ctx=this.host.context(),row=this.#state.requests?.find(r=>r.request_id===requestId);
  if(!ctx.ready||!ctx.patientId||!row||confirmed!==true||ctx.sourceBusy)return;
  const source=eligibleSources(row,ctx.patientId,ctx.sourceIndex,ctx.cases).find(s=>s.source_id===sourceId);
  if(!source||!ctx.sourceIndex)return;
  await this.#write(Object.freeze({operation:'receive',patientId:ctx.patientId,requestId,sourceId,version:source.version,
   body:Object.freeze({synthetic:true,case_id:ctx.sourceIndex.case_id,source_id:sourceId})}));
 }
 async retry():Promise<void>{
  const intent=this.#state.intent,ctx=this.host.context();
  if(this.#state.writePhase!=='unknown'||!intent||!ctx.ready||ctx.patientId!==intent.patientId)return;
  // Exact original command, even if source subsequently amended. The server decides recovery.
  await this.#write(intent);
 }
 async #write(intent:AcquisitionCommand):Promise<void>{
  const ctx=this.host.context();if(!ctx.ready||ctx.patientId!==intent.patientId||this.#state.writePhase==='sending')return;
  const recovering=this.#state.writePhase==='unknown';
  const generation=this.#generation,write=++this.#writes;this.#reads++;
  const current=()=>this.#current(ctx,generation)&&write===this.#writes;
  const control=new AbortController();this.#controllers.add(control);const timer=setTimeout(()=>control.abort(),10000);
  this.#publish({requests:null,phase:'idle',intent,receipt:null,writePhase:'sending',writeMessage:'Saving this exact tracking action once…'});
  let confirmed=false;
  try{
   const res=await this.host.send(intent,control.signal);if(!current())return;
   if(res.status===401){this.clear();this.host.expired();return}
   if([403,404,409,413,422].includes(res.status)){
    this.#publish({intent:recovering?intent:null,writePhase:recovering?'unknown':'rejected',writeMessage:recovering?'Recovery was refused. The original action remains uncertain; keep its exact intent and recheck permissions.':'This attempt was refused. Recheck current records and grants; no new success is claimed.'});return;
   }
   if(![200,201].includes(res.status))throw Error('uncertain');
   const receipt=decodeReceipt(await body(res),intent);if(!current())return;
   this.#publish({intent:null,receipt,writePhase:'confirmed',...(intent.operation==='create'?{draft:fresh().draft}:{}),
    writeMessage:intent.operation==='create'?'Record need saved for tracking. No provider request was sent.':intent.operation==='cancel'?'Tracking cancellation recorded. No external cancellation was sent.':'Exact original linked as received. This does not establish clinical review or external delivery.'});confirmed=true;
  }catch(_){if(current())this.#publish({receipt:null,writePhase:'unknown',writeMessage:'The outcome is unknown. No automatic retry was made. Retry the exact saved action to recover its receipt.'})}
  finally{clearTimeout(timer);this.#controllers.delete(control)}
  if(confirmed&&current())await this.load();
 }
}
