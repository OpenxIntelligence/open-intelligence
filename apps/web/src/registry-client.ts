/** Transient UI state over the canonical patient API; never an authority or ledger. */
export type Patient = Readonly<{
  patient_id: string; origin_org: string; created_at: string;
  status: 'active' | 'suspended'; revision: number;
}>;
export type CreatedPatient = Readonly<{patient_id: string; duplicate: boolean}>;
export type ViewState = Readonly<{
  connected: boolean; phase: 'disconnected' | 'idle' | 'reading' | 'creating' | 'ready' | 'error';
  patient: Patient | null; created: CreatedPatient | null; message: string;
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
const fresh = (): ViewState => Object.freeze({connected:false,phase:'disconnected',patient:null,created:null,message:'Connect a local synthetic credential to use the patient registry.'});
function exact(value: unknown, fields: string[]): value is Record<string,unknown> {
  return value !== null && typeof value==='object' && !Array.isArray(value) &&
    Object.keys(value).length===fields.length && fields.every(k=>Object.hasOwn(value,k));
}
function boundedKey(value: unknown): value is string { return typeof value==='string' && KEY.test(value); }
async function json(response: Response): Promise<unknown> {
  if(!/^application\/json(?:\s*;|$)/i.test(response.headers.get('Content-Type') || '')) throw Error('contract');
  const declared=response.headers.get('Content-Length');
  if(declared && (!/^\d+$/.test(declared) || Number(declared)>65536)) throw Error('contract');
  // Bounded streaming read also covers absent or dishonest Content-Length.
  const reader=response.body?.getReader(); if(!reader)throw Error('contract');
  let size=0; const parts:Uint8Array[]=[];
  try {
    while(true){ const {done,value}=await reader.read();if(done)break;size+=value.byteLength;
      if(size>65536){await reader.cancel();throw Error('contract');}parts.push(value); }
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
  #token=''; #scope=0; #read=0; #state:ViewState=fresh();
  #listeners=new Set<()=>void>(); #controllers=new Set<AbortController>(); #creating=false;
  constructor(private readonly transport:Transport=(url,init)=>fetch(url,init)) {}
  snapshot=():ViewState=>this.#state;
  subscribe=(listener:()=>void):(()=>void)=>{this.#listeners.add(listener);return()=>this.#listeners.delete(listener);};
  #publish(patch:Partial<ViewState>){this.#state=Object.freeze({...this.#state,...patch});for(const listener of this.#listeners)listener();}
  disconnect=()=>{
    this.#scope++;this.#read++;this.#token='';this.#creating=false;
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
    this.#publish({patient:null});
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
    const scope=this.#scope,control=new AbortController();this.#controllers.add(control);this.#creating=true;
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({phase:'creating',created:null,message:'Creating a fictional identity; reading it will still need an explicit grant…'});
    try{
      const res=await this.transport('/v1/patients',this.#init(control,JSON.stringify({synthetic:true,request_key:requestKey})));
      if(scope!==this.#scope)return;
      if(![200,201].includes(res.status)){this.#httpError(res.status);return;}
      const value=created(await json(res));if(scope!==this.#scope)return;
      this.#publish({phase:'idle',created:value,message:value.duplicate?'Original creation receipt recovered. No duplicate identity was created.':'Identity created. Ask the operator for its exact read grant before opening it.'});
    }catch(_){if(scope===this.#scope)this.#publish({phase:'error',message:'Creation outcome is unknown. Retry with the same request key to avoid duplication.'});}
    finally{clearTimeout(timeout);this.#controllers.delete(control);if(scope===this.#scope)this.#creating=false;}
  }
}
