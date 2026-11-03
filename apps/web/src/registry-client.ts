import {decodeOriginal,decodeRecordRequests} from './record-views.js';
import {decodeSourceWorldModel} from './world-model-views.js';
import {decodeComposerPreflight,DEFAULT_SOURCE_QUESTION} from './composer-preflight-view.js';
import {decodeSavedQuestion,decodeSourceQuestions} from './source-questions-view.js';
import type {SavedQuestion,SourceQuestion} from './source-questions-view.js';
import type {ComposerPreflight} from './composer-preflight-view.js';
import type {SourceWorldModel} from './world-model-views.js';
import type {OriginalSource,RecordRequest} from './record-views.js';
/** Transient UI state over the canonical patient API; never an authority or ledger. */
export type Patient = Readonly<{
  patient_id: string; origin_org: string; created_at: string;
  status: 'active' | 'suspended'; revision: number;
}>;
export type CreatedPatient = Readonly<{patient_id: string; duplicate: boolean}>;
export type ViewState = Readonly<{
  connected: boolean; phase: 'disconnected' | 'idle' | 'reading' | 'creating' | 'ready' | 'error';
  patient: Patient | null; created: CreatedPatient | null; message: string;
  records: readonly RecordRequest[] | null;
  recordsPhase:'idle'|'loading'|'ready'|'error'; recordsMessage:string;
  original:OriginalSource|null;
  originalPhase:'idle'|'loading'|'ready'|'error'; originalMessage:string;
  worldModel:SourceWorldModel|null;
  worldPhase:'idle'|'loading'|'ready'|'error';worldMessage:string;
  composerPreview:ComposerPreflight|null;
  composerPhase:'idle'|'loading'|'ready'|'error';composerMessage:string;
  savedQuestion:SavedQuestion|null;questionSavePhase:'idle'|'saving'|'saved'|'error';questionSaveMessage:string;
  questions:readonly SourceQuestion[]|null;questionListPhase:'idle'|'loading'|'ready'|'error';questionListMessage:string;
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
const fresh = (): ViewState => Object.freeze({
  connected:false,phase:'disconnected',patient:null,created:null,
  message:'Connect a local synthetic credential to use the patient registry.',
  records:null,recordsPhase:'idle',recordsMessage:'Open an authorized patient to inspect record requests.',
  original:null,originalPhase:'idle',originalMessage:'Original text is never loaded automatically.',
  worldModel:null,worldPhase:'idle',worldMessage:'Open an authorized patient and select a source case.',
  composerPreview:null,composerPhase:'idle',
  composerMessage:'Select an exact current source observation to prepare a non-executing context.',
  savedQuestion:null,questionSavePhase:'idle',questionSaveMessage:'Save a verified preflight to create one unreviewed source-linked question.',
  questions:null,questionListPhase:'idle',questionListMessage:'Open an authorized case to inspect saved source questions.',
});
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
  #token=''; #scope=0; #read=0; #recordsRead=0; #originalRead=0; #worldRead=0; #composerRead=0;
  #questionWrite=0; #questionRead=0; #questionKey=''; #questionFingerprint=''; #savingQuestion=false;
  #state:ViewState=fresh();
  #listeners=new Set<()=>void>(); #controllers=new Set<AbortController>(); #creating=false;
  constructor(private readonly transport:Transport=(url,init)=>fetch(url,init)) {}
  snapshot=():ViewState=>this.#state;
  subscribe=(listener:()=>void):(()=>void)=>{this.#listeners.add(listener);return()=>this.#listeners.delete(listener);};
  #publish(patch:Partial<ViewState>){this.#state=Object.freeze({...this.#state,...patch});for(const listener of this.#listeners)listener();}
  #resetQuestions(){
    this.#questionWrite++;this.#questionRead++;this.#savingQuestion=false;
    this.#questionKey='';this.#questionFingerprint='';
    this.#publish({savedQuestion:null,questionSavePhase:'idle',
      questionSaveMessage:'Save a verified preflight to create one unreviewed source-linked question.',
      questions:null,questionListPhase:'idle',
      questionListMessage:'Open an authorized case to inspect saved source questions.'});
  }
  #resetWorld(){
    this.#worldRead++;this.#composerRead++;this.#resetQuestions();
    this.#publish({worldModel:null,worldPhase:'idle',worldMessage:
      'Open an authorized patient and select a source case.',
      composerPreview:null,composerPhase:'idle',composerMessage:
      'Select an exact current source observation to prepare a non-executing context.'});
  }
  clearWorldModel=()=>this.#resetWorld();
  #resetRecords(){
    this.#recordsRead++;this.#originalRead++;this.#worldRead++;this.#composerRead++;
    this.#resetQuestions();
    this.#publish({records:null,recordsPhase:'idle',recordsMessage:'Open an authorized patient to inspect record requests.',
      original:null,originalPhase:'idle',originalMessage:'Original text is never loaded automatically.',
      worldModel:null,worldPhase:'idle',worldMessage:'Open an authorized patient and select a source case.',
      composerPreview:null,composerPhase:'idle',composerMessage:
        'Select an exact current source observation to prepare a non-executing context.'});
  }
  disconnect=()=>{
    this.#scope++;this.#read++;this.#recordsRead++;this.#originalRead++;this.#worldRead++;this.#composerRead++;
    this.#questionRead++;this.#questionWrite++;this.#questionKey='';this.#questionFingerprint='';
    this.#savingQuestion=false;this.#token='';this.#creating=false;
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
    this.#resetRecords();
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
  async loadWorldModel(caseId:string):Promise<void>{
    const patientId=this.#state.patient?.patient_id;
    const query=++this.#worldRead,scope=this.#scope,selection=this.#read;
    this.#composerRead++;this.#resetQuestions();
    // Every new read clears previous source observations and preflights.
    this.#publish({composerPreview:null,composerPhase:'idle',
      composerMessage:'Source context must be re-prepared after a source refresh.',
      worldModel:null,worldPhase:'idle',
      worldMessage:'Source observations must be reauthorized for this patient and case.'});
    if(!patientId||!this.#token||!/^CASE-[A-Z0-9-]{1,35}$/.test(caseId)){
      this.#publish({worldPhase:'error',worldMessage:
        'An authorized patient and exact CASE-* identifier are required.'});
      return;
    }
    const current=()=>query===this.#worldRead&&scope===this.#scope&&
      selection===this.#read&&this.#state.patient?.patient_id===patientId;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({worldPhase:'loading',worldMessage:'Checking canonical source-read grant and original versions…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+
        encodeURIComponent(caseId)+'/world-model';
      const res=await this.transport(url,this.#init(control));
      if(!current())return;
      if(res.status===401){this.#httpError(res.status);return;}
      if(res.status!==200){
        this.#publish({worldPhase:'error',worldModel:null,worldMessage:
          messages[res.status]||'Source observation access unavailable; no prior observations shown.'});
        return;
      }
      const result=decodeSourceWorldModel(await json(res),patientId,caseId);
      if(!current())return;
      this.#publish({worldModel:result,worldPhase:'ready',
        worldMessage:'Read-only, current source-reported observations. No clinical reasoning or model execution.'});
    }catch(_){
      if(current())this.#publish({worldModel:null,worldPhase:'error',worldMessage:
        'Unable to verify the source projection. No previous observation is displayed.'});
    }finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }

  async prepareSourceContext(sourceId:string,sourceLine:number,
                             question:string=DEFAULT_SOURCE_QUESTION):Promise<void>{
    const model=this.#state.worldModel;
    const patientId=this.#state.patient?.patient_id;
    const observation=model?.observations.find(o=>
      o.source_version_id===sourceId&&o.source_line===sourceLine);
    const query=++this.#composerRead,scope=this.#scope,selection=this.#read,
      worldQuery=this.#worldRead;
    this.#questionRead++;
    this.#publish({questions:null,questionListPhase:'idle',
      questionListMessage:'Refresh current questions after preparing source context.'});
    // An old preview is never a durable permission or context for a new run.
    this.#publish({composerPreview:null,composerPhase:'idle',
      composerMessage:'Preparing source context requires an independent authorization.'});
    if(!patientId||!model||!observation||this.#state.worldPhase!=='ready'||!this.#token||
       typeof question!=='string'||question.trim()!==question||
       question.length<8||question.length>500){
      this.#publish({composerPhase:'error',composerMessage:
        'Select an authorized current source statement and valid question first.'});
      return;
    }
    const current=()=>scope===this.#scope&&selection===this.#read&&
      worldQuery===this.#worldRead&&query===this.#composerRead&&
      this.#state.patient?.patient_id===patientId&&
      this.#state.worldModel?.source_snapshot_sha256===model.source_snapshot_sha256;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({composerPhase:'loading',composerMessage:
      'Rechecking exact source version and separate Composer-context grant…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+
        encodeURIComponent(model.case_id)+'/composer/source-preflight';
      const payload={synthetic:true,
        expected_source_snapshot_sha256:model.source_snapshot_sha256,
        source_id:sourceId,source_line:sourceLine,question};
      const res=await this.transport(url,this.#init(control,JSON.stringify(payload)));
      if(!current())return;
      if(res.status===401){this.#httpError(res.status);return;}
      if(res.status!==200){
        // A failed preflight must not leave stale patient observations visible
        // as though they remained currently permitted.
        this.#resetWorld();
        this.#publish({composerPhase:'error',composerMessage:res.status===409?
          'The original source changed. Refresh Investigations before preparing a new context.':
          'Composer context unavailable under current authority. Source observations were cleared.'});
        return;
      }
      const prepared=decodeComposerPreflight(await json(res),model,observation,question);
      if(!current())return;
      if(this.#questionFingerprint!==prepared.preflight_sha256){
        this.#questionFingerprint=prepared.preflight_sha256;
        this.#questionKey=crypto.randomUUID();
        this.#questionWrite++;
        this.#publish({savedQuestion:null,questionSavePhase:'idle',
          questionSaveMessage:'Save the source-linked question with an explicit, idempotent request.'});
      }
      this.#publish({composerPreview:prepared,composerPhase:'ready',composerMessage:
        'Source-only preflight prepared. It cannot execute a model or approve clinical work.'});
    }catch(_){
      if(current()){
        this.#resetWorld();
        this.#publish({composerPreview:null,composerPhase:'error',composerMessage:
          'The Composer preflight failed validation. Refresh current source context.'});
      }
    }finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }

  async savePreparedQuestion():Promise<void>{
    const prepared=this.#state.composerPreview;
    const patientId=this.#state.patient?.patient_id;
    if(this.#savingQuestion)return;
    if(!patientId||!prepared||this.#state.composerPhase!=='ready'||
       !this.#state.worldModel||!this.#token||!this.#questionKey){
      this.#publish({questionSavePhase:'error',questionSaveMessage:
        'Prepare the current, authorized source context before saving a question.'});
      return;
    }
    const key=this.#questionKey,query=++this.#questionWrite;
    const scope=this.#scope,patientRead=this.#read,worldRead=this.#worldRead,
      composerRead=this.#composerRead;
    const current=()=>query===this.#questionWrite&&scope===this.#scope&&
      patientRead===this.#read&&worldRead===this.#worldRead&&
      composerRead===this.#composerRead&&
      this.#state.patient?.patient_id===patientId&&
      this.#state.composerPreview?.preflight_sha256===prepared.preflight_sha256;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#savingQuestion=true;
    this.#publish({savedQuestion:null,questionSavePhase:'saving',
      questionSaveMessage:'Revalidating source and saving one canonical fictional question…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+
        encodeURIComponent(prepared.case_id)+'/questions';
      const body=JSON.stringify({
        synthetic:true,request_key:key,question:prepared.question,
        source_id:prepared.selected_source.source_id,
        source_line:prepared.selected_source.line,
        expected_source_snapshot_sha256:prepared.source_snapshot_sha256,
        expected_preflight_sha256:prepared.preflight_sha256,
      });
      const res=await this.transport(url,this.#init(control,body));
      if(!current())return;
      if(res.status===401){this.#httpError(res.status);return;}
      if(![200,201].includes(res.status)){
        if(res.status===409){
          this.#resetWorld();
          this.#publish({questionSavePhase:'error',questionSaveMessage:
            'Source/version or request intent changed. Refresh current originals and saved questions.'});
        }else{
          this.#publish({questionSavePhase:'error',questionSaveMessage:
            'Question save refused by current authorization. No successful save is assumed.'});
        }
        return;
      }
      const value=decodeSavedQuestion(await json(res));
      if(!current())return;
      this.#publish({savedQuestion:value,questionSavePhase:'saved',
        questionSaveMessage:value.duplicate?
        'Original question receipt recovered. The same request was not saved twice.':
        'Source-linked question saved. No clinician review was submitted or approved.'});
    }catch(_){
      if(current())this.#publish({savedQuestion:null,questionSavePhase:'error',
        questionSaveMessage:'Save outcome unknown. Retry this same prepared question to preserve its request key.'});
    }finally{clearTimeout(timeout);this.#controllers.delete(control);
      if(query===this.#questionWrite)this.#savingQuestion=false;}
  }

  async loadSavedQuestions(caseId:string):Promise<void>{
    const patientId=this.#state.patient?.patient_id;
    const query=++this.#questionRead,scope=this.#scope,patientRead=this.#read;
    this.#publish({questions:null,questionListPhase:'idle',
      questionListMessage:'Checking current authorization for saved source-linked questions…'});
    if(!patientId||!this.#token||!/^CASE-[A-Z0-9-]{1,35}$/.test(caseId)){
      this.#publish({questionListPhase:'error',questionListMessage:
        'Open an authorized patient and exact source case before reading questions.'});
      return;
    }
    const current=()=>query===this.#questionRead&&scope===this.#scope&&
      patientRead===this.#read&&this.#state.patient?.patient_id===patientId;
    const controller=new AbortController();this.#controllers.add(controller);
    const timeout=setTimeout(()=>controller.abort(),10000);
    this.#publish({questionListPhase:'loading',questionListMessage:'Reading source-current and reassessment states…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+
        encodeURIComponent(caseId)+'/questions';
      const res=await this.transport(url,this.#init(controller));
      if(!current())return;
      if(res.status===401){this.#httpError(res.status);return;}
      if(res.status!==200){
        this.#publish({questions:null,questionListPhase:'error',
          questionListMessage:'Saved questions unavailable under current authority.'});
        return;
      }
      const rows=decodeSourceQuestions(await json(res),patientId,caseId);
      if(!current())return;
      this.#publish({questions:rows,questionListPhase:'ready',
        questionListMessage:rows.length?
          'Authorized source-linked questions, including any reopened reassessment needs.':
          'No saved source questions are available under this grant.'});
    }catch(_){
      if(current())this.#publish({questions:null,questionListPhase:'error',
        questionListMessage:'Question history could not be verified; no cached questions are shown.'});
    }finally{clearTimeout(timeout);this.#controllers.delete(controller);}
  }

  async loadRecords():Promise<void>{
    const patientId=this.#state.patient?.patient_id;
    if(!patientId||!this.#token){
      this.#resetRecords();
      this.#publish({recordsPhase:'error',recordsMessage:'Open an authorized patient before loading requests.'});
      return;
    }
    const scope=this.#scope,selection=this.#read,query=++this.#recordsRead;
    this.#originalRead++;this.#resetWorld();
    const current=()=>scope===this.#scope && selection===this.#read &&
      query===this.#recordsRead && this.#state.patient?.patient_id===patientId;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({records:null,recordsPhase:'loading',recordsMessage:'Checking current request-read authorization…',
      original:null,originalPhase:'idle',originalMessage:'Original source access requires a separate action.'});
    try{
      const res=await this.transport('/v1/patients/'+encodeURIComponent(patientId)+'/record-requests',this.#init(control));
      if(!current())return;
      if(res.status===401){this.#httpError(res.status);return;}
      if(res.status!==200){
        this.#publish({records:null,recordsPhase:'error',recordsMessage:
          messages[res.status]||'Record requests could not be authorized. No previous records are shown.'});
        return;
      }
      const rows=decodeRecordRequests(await json(res),patientId);
      if(!current())return;
      this.#publish({records:rows,recordsPhase:'ready',recordsMessage:
        rows.length ? 'Current authorized record requests. No external request was sent by this workspace.' :
        'No record requests are currently visible under this grant.'});
    }catch(_){
      if(current())this.#publish({records:null,recordsPhase:'error',recordsMessage:
        'The record response could not be verified. Previous records remain cleared.'});
    }finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }

  async openOriginal(caseId:string,sourceId:string):Promise<void>{
    const patientId=this.#state.patient?.patient_id;
    const ref=this.#state.records?.find(r=>r.status==='received' &&
      r.source_reference?.case_id===caseId && r.source_reference.source_id===sourceId)?.source_reference;
    const query=++this.#originalRead,scope=this.#scope,selection=this.#read,recordsQuery=this.#recordsRead;
    this.#publish({original:null,originalPhase:'idle',originalMessage:'Original text requires its own grant.'});
    if(!patientId||!ref||!this.#token||this.#state.recordsPhase!=='ready'){
      this.#publish({originalPhase:'error',originalMessage:'No authorized exact source reference is selected.'});
      return;
    }
    const current=()=>scope===this.#scope && selection===this.#read &&
      query===this.#originalRead && recordsQuery===this.#recordsRead &&
      this.#state.patient?.patient_id===patientId;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({originalPhase:'loading',originalMessage:'Checking original-text authority and SHA-256…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+
        encodeURIComponent(caseId)+'/sources/'+encodeURIComponent(sourceId);
      const res=await this.transport(url,this.#init(control));
      if(!current())return;
      if(res.status===401){this.#httpError(res.status);return;}
      if(res.status!==200){
        this.#publish({original:null,originalPhase:'error',originalMessage:
          messages[res.status]||'Original text unavailable for this credential.'});
        return;
      }
      const source=await decodeOriginal(await json(res),ref);
      if(!current())return;
      this.#publish({original:source,originalPhase:'ready',originalMessage:
        source.state==='superseded' ?
          'Historical original only. This source was superseded; reconciliation is required.' :
          'Exact fictional original verified against the selected receipt fingerprint; not clinically reviewed.'});
    }catch(_){
      if(current())this.#publish({original:null,originalPhase:'error',originalMessage:
        'Original content or fingerprint could not be verified. No source text is shown.'});
    }finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }

  async create(requestKey:string,confirmed:boolean):Promise<void>{
    if(this.#creating)return;
    if(!this.#token){this.#publish({message:'Connect an authorized synthetic credential first.'});return;}
    if(confirmed!==true || !boundedKey(requestKey)){this.#publish({phase:'error',message:'Confirm fictional identity creation and use a valid request key.'});return;}
    // A new creation is a new selection intent; an older read cannot restore it.
    this.#read++;this.#resetRecords();
    const scope=this.#scope,control=new AbortController();this.#controllers.add(control);this.#creating=true;
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({phase:'creating',patient:null,created:null,message:'Creating a fictional identity; reading it will still need an explicit grant…'});
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
