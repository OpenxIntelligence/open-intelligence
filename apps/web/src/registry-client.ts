/** Transient UI state over the canonical patient API; never an authority or ledger. */
import {parseCaseBindingList, parseSourceIndex} from './source-contracts.js';
import type {CaseBinding, SourceIndex} from './source-contracts.js';
import {parseExactOriginal} from './source-original.js';
import type {ExactOriginal} from './source-original.js';
export type Patient = Readonly<{
  patient_id: string; origin_org: string; created_at: string;
  status: 'active' | 'suspended'; revision: number;
}>;
export type CreatedPatient = Readonly<{patient_id: string; duplicate: boolean}>;
export type ViewState = Readonly<{
  connected: boolean; phase: 'disconnected' | 'idle' | 'reading' | 'creating' | 'ready' | 'error';
  patient: Patient | null; created: CreatedPatient | null; message: string;
  cases: ReadonlyArray<CaseBinding> | null; sourceIndex: SourceIndex | null;
  original:ExactOriginal|null; originalPhase:'idle'|'loading'|'ready'|'error'; originalMessage:string;
  recordsPhase: 'idle' | 'loading-cases' | 'loading-sources' | 'ready' | 'error';
  recordMessage: string;
}>;
export type Transport = (input: string, init: RequestInit) => Promise<Response>;
const KEY = /^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$/;
const TOKEN = /^[A-Za-z0-9._~-]{32,256}$/;
const messages: Record<number,string> = {
  401:'Credential expired, revoked or unavailable. Connect again with an authorized synthetic credential.',
  403:'This action is not permitted by the current grant.',
  404:'Patient unavailable for this credential. Check the exact patient grant with the operator.',
  408:'The request exceeded its time limit. No outcome is assumed.',
  409:'This request key conflicts with an earlier request. Resolve it with the operator.',
  413:'The request exceeds the API limit.',
  422:'The API refused this request. Check the opaque identifiers.',
  503:'The patient registry or access service is unavailable. No cached patient is shown.',
};
const fresh = (): ViewState => Object.freeze({connected:false,phase:'disconnected',patient:null,created:null,message:'Connect a local synthetic credential to use the patient registry.',cases:null,sourceIndex:null,recordsPhase:'idle',recordMessage:'Open an authorized fictional patient in Overview first.',original:null,originalPhase:'idle',originalMessage:'Choose an exact source from a freshly authorized source index.'});
const emptyRecords=()=>({cases:null,sourceIndex:null,recordsPhase:'idle' as const,recordMessage:'Load the current authorized case mappings to inspect original source metadata.',original:null,originalPhase:'idle' as const,originalMessage:'Choose an exact source from a freshly authorized source index.'});
function exact(value: unknown, fields: string[]): value is Record<string,unknown> {
  return value !== null && typeof value==='object' && !Array.isArray(value) &&
    Object.keys(value).length===fields.length && fields.every(k=>Object.hasOwn(value,k));
}
function boundedKey(value: unknown): value is string { return typeof value==='string' && KEY.test(value); }
async function json(response: Response,maxBytes=65536): Promise<unknown> {
  if(!/^application\/json(?:\s*;|$)/i.test(response.headers.get('Content-Type') || '')) throw Error('contract');
  const declared=response.headers.get('Content-Length');
  if(declared && (!/^\d+$/.test(declared) || Number(declared)>maxBytes)) throw Error('contract');
  // Bounded streaming read also covers absent or dishonest Content-Length.
  const reader=response.body?.getReader(); if(!reader)throw Error('contract');
  let size=0; const parts:Uint8Array[]=[];
  try {
    while(true){ const {done,value}=await reader.read();if(done)break;size+=value.byteLength;
      if(size>maxBytes){await reader.cancel();throw Error('contract');}parts.push(value); }
  } finally {reader.releaseLock();}
  const all=new Uint8Array(size);let offset=0;for(const p of parts){all.set(p,offset);offset+=p.length;}
  return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(all));
}
function patient(value: unknown, expected: string): Patient {
  if(!exact(value,['patient_id','origin_org','created_at','status','revision']) ||
     value.patient_id!==expected || !boundedKey(value.patient_id) || !boundedKey(value.origin_org) ||
     typeof value.created_at!=='string' || !/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value.created_at) ||
     !Number.isFinite(Date.parse(value.created_at)) || !['active','suspended'].includes(String(value.status)) ||
     typeof value.revision!=='number' || !Number.isSafeInteger(value.revision) || value.revision<1) throw Error('contract');
  return Object.freeze(value as Patient);
}
function created(value: unknown): CreatedPatient {
  if(!exact(value,['patient_id','duplicate']) || !boundedKey(value.patient_id) || typeof value.duplicate!=='boolean')throw Error('contract');
  return Object.freeze(value as CreatedPatient);
}
export class RegistrySession {
  #token=''; #scope=0; #read=0; #records=0; #state:ViewState=fresh();
  #listeners=new Set<()=>void>(); #controllers=new Set<AbortController>(); #creating=false;
  constructor(private readonly transport:Transport=(url,init)=>fetch(url,init)) {}
  snapshot=():ViewState=>this.#state;
  subscribe=(listener:()=>void):(()=>void)=>{this.#listeners.add(listener);return()=>this.#listeners.delete(listener);};
  #publish(patch:Partial<ViewState>){this.#state=Object.freeze({...this.#state,...patch});for(const listener of this.#listeners)listener();}
  disconnect=()=>{
    this.#scope++;this.#read++;this.#records++;this.#token='';this.#creating=false;
    for(const c of this.#controllers)c.abort();this.#controllers.clear();
    this.#state=fresh();for(const listener of this.#listeners)listener();
  };
  connect=(token:string)=>{
    this.disconnect();
    if(!TOKEN.test(token)){this.#publish({message:'Enter a valid operator-issued synthetic credential (32–256 ASCII characters).'});return;}
    this.#token=token;this.#publish({connected:true,phase:'idle',message:'Credential held in memory only. The server decides each action.'});
  };
  #init(controller:AbortController,body?:string):RequestInit{return {
    method:body===undefined?'GET':'POST',headers:{Authorization:'Bearer '+this.#token,'Content-Type':'application/json','Accept':'application/json'},
    ...(body===undefined?{}:{body}),credentials:'omit',redirect:'error',cache:'no-store',signal:controller.signal,
  };}
  #httpError(status:number){
    if(status===401){this.disconnect();this.#publish({phase:'error',message:messages[401]});}
    else this.#publish({phase:'error',patient:null,message:messages[status] || 'Unexpected API response. No patient information is displayed.'});
  }
  async read(id:string):Promise<void>{
    const scope=this.#scope, request=++this.#read;
    this.#records++;this.#publish({patient:null,...emptyRecords()});
    if(!this.#token){this.#publish({message:'Connect an authorized synthetic credential first.'});return;}
    if(!boundedKey(id)){this.#publish({phase:'error',message:'Use an opaque patient ID, not a name or URL.'});return;}
    const control=new AbortController();this.#controllers.add(control);
    const current=()=>scope===this.#scope && request===this.#read;
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({phase:'reading',message:'Checking the current patient grant…'});
    try{
      const res=await this.transport('/v1/patients/'+encodeURIComponent(id),this.#init(control));
      if(!current())return;
      if(res.status!==200){this.#httpError(res.status);return;}
      const value=patient(await json(res),id); if(!current())return;
      this.#publish({patient:value,phase:'ready',message:'Patient identity read from the canonical registry. No clinical record is loaded.'});
    }catch(_){if(current())this.#publish({patient:null,phase:'error',message:'The patient response could not be verified. No cached patient is shown.'});}
    finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }
  async create(requestKey:string,confirmed:boolean):Promise<void>{
    if(this.#creating)return;
    if(!this.#token){this.#publish({message:'Connect an authorized synthetic credential first.'});return;}
    if(confirmed!==true || !boundedKey(requestKey)){this.#publish({phase:'error',message:'Confirm fictional identity creation and use a valid request key.'});return;}
    // A new creation is a new selection intent; an older read cannot restore it.
    this.#read++;this.#records++;
    const scope=this.#scope,control=new AbortController();this.#controllers.add(control);this.#creating=true;
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({phase:'creating',patient:null,created:null,...emptyRecords(),message:'Creating a fictional identity; reading it will still need an explicit grant…'});
    try{
      const res=await this.transport('/v1/patients',this.#init(control,JSON.stringify({synthetic:true,request_key:requestKey})));
      if(scope!==this.#scope)return;
      if(![200,201].includes(res.status)){this.#httpError(res.status);return;}
      const value=created(await json(res));if(scope!==this.#scope)return;
      this.#publish({phase:'idle',created:value,message:value.duplicate?'Original creation receipt recovered. No duplicate identity was created.':'Identity created. Ask the operator for its exact read grant before opening it.'});
    }catch(_){if(scope===this.#scope)this.#publish({phase:'error',message:'Creation outcome is unknown. Retry with the same request key to avoid duplication.'});}
    finally{clearTimeout(timeout);this.#controllers.delete(control);if(scope===this.#scope)this.#creating=false;}
  }

  /** Explicit, permission-checked metadata read; never create a second patient/case ledger. */
  async loadCases():Promise<void>{
    const patientId=this.#state.patient?.patient_id;
    if(!this.#token || !patientId || this.#state.phase!=='ready'){
      this.#publish({...emptyRecords(),recordsPhase:'error',recordMessage:'Open an authorized fictional patient in Overview first.'});
      return;
    }
    const scope=this.#scope,read=this.#read,request=++this.#records;
    const current=()=>scope===this.#scope && read===this.#read &&
      request===this.#records && this.#state.patient?.patient_id===patientId;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({cases:null,sourceIndex:null,original:null,originalPhase:'idle',originalMessage:'Choose an exact source from a freshly authorized source index.',recordsPhase:'loading-cases',recordMessage:'Checking current case mapping permissions…'});
    try{
      const res=await this.transport('/v1/patients/'+encodeURIComponent(patientId)+'/case-bindings',this.#init(control));
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status!==200){
        this.#publish({cases:null,sourceIndex:null,recordsPhase:'error',recordMessage:'Case mappings unavailable or permission changed. No records are shown.'});
        return;
      }
      const mappings=parseCaseBindingList(await json(res),patientId);
      if(!current())return;
      this.#publish({cases:mappings,sourceIndex:null,recordsPhase:'ready',
        recordMessage:mappings.length===0?'No permitted fictional case mappings were returned.':'Select an active case to check its original source metadata.'});
    }catch(_){
      if(current())this.#publish({cases:null,sourceIndex:null,recordsPhase:'error',
        recordMessage:'Case response failed validation or the service is unavailable. No records are shown.'});
    }finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }
  async loadSources(caseId:string):Promise<void>{
    const patientId=this.#state.patient?.patient_id;
    if(!patientId || !this.#token || this.#state.phase!=='ready' ||
       !this.#state.cases?.some(item=>item.case_id===caseId && item.status==='active')){
      this.#records++;
      this.#publish({sourceIndex:null,recordsPhase:'error',
        recordMessage:'Select an active, currently authorized case first.'});
      return;
    }
    const scope=this.#scope,read=this.#read,request=++this.#records;
    const current=()=>scope===this.#scope && read===this.#read &&
      request===this.#records && this.#state.patient?.patient_id===patientId;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({sourceIndex:null,original:null,originalPhase:'idle',originalMessage:'Choose an exact source from a freshly authorized source index.',recordsPhase:'loading-sources',
      recordMessage:'Checking exact source versions and current permissions…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+encodeURIComponent(caseId)+'/sources';
      const res=await this.transport(url,this.#init(control));
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status!==200){
        this.#publish({cases:null,sourceIndex:null,recordsPhase:'error',
          recordMessage:'Sources unavailable, denied or mapping revoked. Reload case permissions.'});
        return;
      }
      const index=parseSourceIndex(await json(res),patientId,caseId);
      if(!current())return;
      this.#publish({sourceIndex:index,recordsPhase:'ready',
        recordMessage:'Exact original source metadata read. Extracted statements are not clinical assessments.'});
    }catch(_){
      if(current())this.#publish({cases:null,sourceIndex:null,recordsPhase:'error',
        recordMessage:'Source response failed validation or the service is unavailable. No sources are shown.'});
    }finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }

  /** Independently authorized exact original; checks both identifier and bytes.
   * Prior results are cleared on every new read, patient selection, or case refresh.
   */
  async loadOriginal(sourceId:string):Promise<void>{
    const patientId=this.#state.patient?.patient_id,index=this.#state.sourceIndex;
    if(!patientId||!this.#token||this.#state.phase!=='ready'||!index||
       !/^SRC-[0-9A-F]{32}$/.test(sourceId)||
       !index.sources.some(s=>s.source_id===sourceId)){
      this.#records++;
      this.#publish({original:null,originalPhase:'error',
        originalMessage:'Select an original from the latest authorized source list.'});
      return;
    }
    const scope=this.#scope,read=this.#read,request=++this.#records;
    const current=()=>scope===this.#scope&&read===this.#read&&
      request===this.#records&&this.#state.patient?.patient_id===patientId&&
      this.#state.sourceIndex===index;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({original:null,originalPhase:'loading',
      originalMessage:'Checking original-read permission and verifying SHA-256…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+
        encodeURIComponent(index.case_id)+'/sources/'+encodeURIComponent(sourceId);
      const response=await this.transport(url,this.#init(control));
      if(!current())return;
      if(response.status===401){this.#httpError(401);return;}
      if(response.status!==200){
        this.#publish({original:null,originalPhase:'error',
          originalMessage:'Original bytes are unavailable under the current grant. Nothing is displayed.'});
        return;
      }
      const original=await parseExactOriginal(await json(response,131072),index,sourceId);
      if(!current())return;
      this.#publish({original,originalPhase:'ready',
        originalMessage:'Original bytes match the indexed SHA-256; source text is still unreviewed.'});
    }catch(_){
      if(current())this.#publish({original:null,originalPhase:'error',
        originalMessage:'Original response, version or SHA-256 could not be verified. Refresh source history.'});
    }finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }
}
