/** Transient UI state over the canonical patient API; never an authority or ledger. */
export {patientContinuity} from './patient-continuity.js';
import {parseCaseBindingList, parseSourceIndex} from './source-contracts.js';
import {decodeQuestionSourcePacket} from './source-quote-review-packet.js';
import type {QuestionSourceReviewPacket} from './source-quote-review-packet.js';
import type {CaseBinding, SourceIndex} from './source-contracts.js';
import {prepareSource,parseImportReceipt,verifyOriginal} from './source-intake.js';
import type {ImportReceipt,OriginalSource} from './source-intake.js';
import {parseSourceWorldModel} from './source-world-model.js';
import type {SourceWorldModel} from './source-world-model.js';
import {decodeComposerPreflight,DEFAULT_SOURCE_QUESTION} from './composer-preflight-view.js';
import type {ComposerPreflight} from './composer-preflight-view.js';
import {decodeSavedQuestion,decodeSourceQuestions} from './source-questions-view.js';
import type {SavedQuestion,SourceQuestion} from './source-questions-view.js';
import {decodeReviewQueue,decodeReviewReturnResult,validReturnReason,FICTIONAL_RETURN_REASON} from './review-queue-view.js';
import type {ReviewQueue,ReviewReturnResult} from './review-queue-view.js';
import {canPrepareSourceBrief,decodeSourceBrief} from './source-brief.js';
import type {SourceBrief} from './source-brief.js';
import {QuestionEvidenceSession,emptyEvidenceState} from './authored-evidence-session.js';
import type {EvidenceState} from './authored-evidence-session.js';
import type {ContentItem,Permissions,Relation,Applicability} from './authored-evidence.js';
export type Patient = Readonly<{
  patient_id: string; origin_org: string; created_at: string;
  status: 'active' | 'suspended'; revision: number;
}>;
export type CreatedPatient = Readonly<{patient_id: string; duplicate: boolean}>;
export type ReviewReturnIntent=Readonly<{
  patient_id:string;case_id:string;question_id:string;queue_fingerprint:string;reason:string;
}>;
export type QuestionDraft = Readonly<{case_id:string;source_id:string;source_line:number;
  snapshot_fingerprint:string;question:string}>;
export type ViewState = Readonly<EvidenceState & {
  connected: boolean; phase: 'disconnected' | 'idle' | 'reading' | 'creating' | 'ready' | 'error';
  patient: Patient | null; created: CreatedPatient | null; message: string;
  cases: ReadonlyArray<CaseBinding> | null; sourceIndex: SourceIndex | null;
  recordsPhase: 'idle' | 'loading-cases' | 'loading-sources' | 'loading-original' | 'ready' | 'error';
  original:OriginalSource|null; importReceipt:ImportReceipt|null;
  importOutcome:'idle'|'sending'|'confirmed'|'rejected'|'unknown'; importMessage:string;
  recordMessage: string;
  worldModel:SourceWorldModel|null;
  worldPhase:'idle'|'loading'|'ready'|'error';
  worldMessage:string;
  questionDraft:QuestionDraft|null;
  composerPreview:ComposerPreflight|null;
  composerPhase:'idle'|'loading'|'ready'|'error';composerMessage:string;
  savedQuestion:SavedQuestion|null;questionSavePhase:'idle'|'saving'|'saved'|'error';questionSaveMessage:string;
  questions:readonly SourceQuestion[]|null;questionListPhase:'idle'|'loading'|'ready'|'error';questionListMessage:string;
  questionsAccessReceiptId:string|null;questionsCaseId:string|null;
  reviewQueue:ReviewQueue|null;reviewPhase:'idle'|'loading'|'ready'|'error';reviewMessage:string;
  reviewReturn:ReviewReturnResult|null;reviewReturnPhase:'idle'|'saving'|'saved'|'unknown'|'error';
  reviewReturnMessage:string;reviewReturnIntent:ReviewReturnIntent|null;
  sourceBrief:SourceBrief|null;briefPhase:'idle'|'loading'|'ready'|'error';briefMessage:string;
  sourceQuotePacket:QuestionSourceReviewPacket|null;
  sourceQuotePhase:'idle'|'loading'|'ready'|'error';sourceQuoteMessage:string;
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
const emptyIntake=()=>({original:null,importReceipt:null,importOutcome:'idle' as const,importMessage:''});
const emptyWorld=()=>({worldModel:null,worldPhase:'idle' as const,worldMessage:'Choose an authorized active fictional case to inspect its source-derived World Model.'});
const emptyReview=()=>({reviewQueue:null,reviewPhase:'idle' as const,
  reviewMessage:'Open the current patient case to inspect saved questions and verification returns.',
  reviewReturn:null,reviewReturnPhase:'idle' as const,reviewReturnIntent:null,
  reviewReturnMessage:'No return action is in progress.'});
const emptyBrief=()=>({sourceBrief:null,briefPhase:'idle' as const,
  briefMessage:'Prepare a source-linked brief from a current saved question. Each download checks permission again.'});
const emptyInvestigation=()=>({questionDraft:null,composerPreview:null,composerPhase:'idle' as const,
  composerMessage:'Select an exact current source observation to prepare a non-executing context.',
  savedQuestion:null,questionSavePhase:'idle' as const,
  questionSaveMessage:'Save a verified preflight to create one unreviewed source-linked question.',
  questions:null,questionsAccessReceiptId:null,questionsCaseId:null,questionListPhase:'idle' as const,
  questionListMessage:'Open an authorized case to inspect saved source questions.',
  ...emptyEvidenceState(),...emptyBrief(),sourceQuotePacket:null,sourceQuotePhase:'idle' as const,
  sourceQuoteMessage:'Select a saved question to inspect its source quotation and evidence gaps.'});
const fresh = (): ViewState => Object.freeze({connected:false,phase:'disconnected',patient:null,created:null,message:'Connect a local synthetic credential to use the patient registry.',cases:null,sourceIndex:null,recordsPhase:'idle',recordMessage:'Open an authorized fictional patient in Overview first.',...emptyIntake(),...emptyWorld(),...emptyInvestigation(),...emptyReview()});
const emptyRecords=()=>({...emptyIntake(),...emptyWorld(),cases:null,sourceIndex:null,recordsPhase:'idle' as const,recordMessage:'Load the current authorized case mappings to inspect original source metadata.'});
function exact(value: unknown, fields: string[]): value is Record<string,unknown> {
  return value !== null && typeof value==='object' && !Array.isArray(value) &&
    Object.keys(value).length===fields.length && fields.every(k=>Object.hasOwn(value,k));
}
function boundedKey(value: unknown): value is string { return typeof value==='string' && KEY.test(value); }
async function json(response: Response, limit=65536): Promise<unknown> {
  if(!/^application\/json(?:\s*;|$)/i.test(response.headers.get('Content-Type') || '')) throw Error('contract');
  const declared=response.headers.get('Content-Length');
  if(declared && (!/^\d+$/.test(declared) || Number(declared)>limit)) throw Error('contract');
  // Bounded streaming read also covers absent or dishonest Content-Length.
  const reader=response.body?.getReader(); if(!reader)throw Error('contract');
  let size=0; const parts:Uint8Array[]=[];
  try {
    while(true){ const {done,value}=await reader.read();if(done)break;size+=value.byteLength;
      if(size>limit){await reader.cancel();throw Error('contract');}parts.push(value); }
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
  #worldRead=0; #composerRead=0; #questionRead=0; #questionWrite=0; #briefRead=0;
  #questionKey=''; #questionFingerprint=''; #savingQuestion=false;
  #reviewRead=0; #reviewWrite=0; #reviewKey=''; #reviewIntent=''; #savingReview=false;
  #quoteRead=0;
  #inspectionQuestionId:string|null=null;
  #listeners=new Set<()=>void>(); #controllers=new Set<AbortController>(); #creating=false; #uploading=false;
  #evidenceSession:QuestionEvidenceSession;
  constructor(private readonly transport:Transport=(url,init)=>fetch(url,init)) {
    this.#evidenceSession=new QuestionEvidenceSession({snapshot:this.snapshot,
      publish:patch=>this.#publish(patch),scope:()=>[this.#scope,this.#read,this.#worldRead,this.#questionRead].join(':'),
      request:(url,control,body)=>this.transport(url,this.#init(control,body)),json,
      add:control=>this.#controllers.add(control),remove:control=>this.#controllers.delete(control),
      expire:()=>this.#httpError(401)});
  }
  dismissQuestionEvidence=()=>this.#evidenceSession.dismiss();
  loadQuestionEvidence=(questionId:string)=>{this.#focusSavedQuestion(questionId);return this.#evidenceSession.load(questionId);};
  importQuestionEvidence=(questionId:string,text:string,item:ContentItem,permissions:Permissions)=>this.#evidenceSession.import(questionId,text,item,permissions);
  assessQuestionEvidence=(questionId:string,evidenceId:string,quote:string,relation:Relation,applicability:Applicability,rationale:string)=>this.#evidenceSession.assess(questionId,evidenceId,quote,relation,applicability,rationale);
  withdrawQuestionEvidence=(questionId:string,evidenceId:string,reason:string)=>this.#evidenceSession.withdraw(questionId,evidenceId,reason);
  prepareEvidenceReport=(questionId:string,assessmentIds:readonly string[])=>this.#evidenceSession.prepareReport(questionId,assessmentIds);
  readEvidenceReport=(questionId:string,reportId:string)=>this.#evidenceSession.readReport(questionId,reportId);
  loadEvidenceOriginal=(questionId:string,evidenceId:string)=>this.#evidenceSession.original(questionId,evidenceId);
  retryEvidenceWrite=()=>this.#evidenceSession.retry();
  snapshot=():ViewState=>this.#state;
  subscribe=(listener:()=>void):(()=>void)=>{this.#listeners.add(listener);return()=>this.#listeners.delete(listener);};
  #publish(patch:Partial<ViewState>){this.#state=Object.freeze({...this.#state,...patch});for(const listener of this.#listeners)listener();}
  #resetReview(preserveCase?:string){
    this.#reviewRead++;this.#reviewWrite++;this.#savingReview=false;
    const intent=this.#state.reviewReturnIntent;
    if(intent&&intent.patient_id===this.#state.patient?.patient_id&&intent.case_id===preserveCase&&
       ['saving','unknown'].includes(this.#state.reviewReturnPhase)){
      return {...emptyReview(),reviewReturnIntent:intent,reviewReturnPhase:'unknown' as const,
        reviewReturnMessage:'The earlier return outcome is uncertain. Retry its exact saved intent to recover its receipt; it is not a new current-source return.'};
    }
    this.#reviewKey='';this.#reviewIntent='';
    return emptyReview();
  }
  #resetInvestigation(preserveReviewCase?:string){
    this.#inspectionQuestionId=null;
    this.#worldRead++;this.#composerRead++;this.#questionRead++;this.#questionWrite++;this.#briefRead++;this.#quoteRead++;
    this.#questionKey='';this.#questionFingerprint='';this.#savingQuestion=false;
    return {...emptyInvestigation(),...this.#evidenceSession.reset(preserveReviewCase),...this.#resetReview(preserveReviewCase)};
  }
  #resetWorld(preserveReviewCase?:string){
    this.#publish({...emptyWorld(),...this.#resetInvestigation(preserveReviewCase)});
  }
  /** The two independently authorized readers share one UI selection, not a
   * new domain record. A switch invalidates both readers before either awaits.
   * This prevents a late response for question A restoring beside question B.
   * A null selection returns to an authored draft or a new source preflight.
   */
  #focusSavedQuestion(questionId:string|null):void{
    if(this.#inspectionQuestionId===questionId)return;
    this.#inspectionQuestionId=questionId;
    this.dismissSourceBrief();
    this.dismissSourceQuotePacket();
    this.dismissQuestionEvidence();
  }
  dismissSourceBrief=()=>{
    this.#briefRead++;
    this.#publish(emptyBrief());
  };
  dismissSourceQuotePacket=()=>{
    this.#quoteRead++;
    this.#publish({sourceQuotePacket:null,sourceQuotePhase:'idle',
      sourceQuoteMessage:'Select a saved question to inspect its source quotation and evidence gaps.'});
  };
  disconnect=()=>{
    this.#scope++;this.#read++;this.#records++;this.#token='';this.#creating=false;this.#uploading=false;
    this.#resetInvestigation();
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
    this.#records++;this.#publish({patient:null,...emptyRecords(),...this.#resetInvestigation()});
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
    this.#publish({phase:'creating',patient:null,created:null,...emptyRecords(),...this.#resetInvestigation(),message:'Creating a fictional identity; reading it will still need an explicit grant…'});
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
      this.#publish({...emptyRecords(),...this.#resetInvestigation(),recordsPhase:'error',recordMessage:'Open an authorized fictional patient in Overview first.',...emptyIntake()});
      return;
    }
    const retainedCase=this.#state.reviewReturnIntent?.case_id??this.#state.evidenceWriteIntent?.case_id;
    const scope=this.#scope,read=this.#read,request=++this.#records;
    const current=()=>scope===this.#scope && read===this.#read &&
      request===this.#records && this.#state.patient?.patient_id===patientId;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({...emptyIntake(),...emptyWorld(),...this.#resetInvestigation(retainedCase),cases:null,sourceIndex:null,recordsPhase:'loading-cases',recordMessage:'Checking current case mapping permissions…'});
    try{
      const res=await this.transport('/v1/patients/'+encodeURIComponent(patientId)+'/case-bindings',this.#init(control));
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status!==200){
        this.#publish({cases:null,sourceIndex:null,recordsPhase:'error',
          ...([403,404].includes(res.status)?this.#resetReview():{}),
          recordMessage:'Case mappings unavailable or permission changed. No records are shown.'});
        return;
      }
      const mappings=parseCaseBindingList(await json(res),patientId);
      if(!current())return;
      this.#publish({cases:mappings,sourceIndex:null,recordsPhase:'ready',
        ...(retainedCase&&!mappings.some(item=>item.case_id===retainedCase&&item.status==='active')?this.#resetReview():{}),
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
      this.#publish({...emptyIntake(),...emptyWorld(),...this.#resetInvestigation(),sourceIndex:null,recordsPhase:'error',
        recordMessage:'Select an active, currently authorized case first.'});
      return;
    }
    const scope=this.#scope,read=this.#read,request=++this.#records;
    const current=()=>scope===this.#scope && read===this.#read &&
      request===this.#records && this.#state.patient?.patient_id===patientId;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({...emptyWorld(),...this.#resetInvestigation(caseId),...(this.#state.sourceIndex?.case_id!==caseId?emptyIntake():{original:null}),sourceIndex:null,recordsPhase:'loading-sources',
      recordMessage:'Checking exact source versions and current permissions…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+encodeURIComponent(caseId)+'/sources';
      const res=await this.transport(url,this.#init(control));
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status!==200){
        this.#publish({cases:null,sourceIndex:null,recordsPhase:'error',
          ...([403,404].includes(res.status)?this.#resetReview():{}),
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

  /** The inbox is derived from existing questions. Reading it never authorizes a return. */
  async loadReviewQueue(caseId:string):Promise<void>{
    const retained=this.#resetReview(caseId);
    const patientId=this.#state.patient?.patient_id;
    this.#publish(retained);
    // The retained intent already matches this patient and exact captured case.
    // Missing metadata cannot authorize a read or erase uncertain write recovery.
    if(patientId&&this.#token&&this.#state.phase==='ready'&&!this.#uploading&&
       this.#state.cases===null&&retained.reviewReturnIntent){
      this.#publish({reviewPhase:'error',reviewMessage:
        'Recheck authorized cases in Records before refreshing this inbox. The exact earlier return remains saved.'});
      return;
    }
    if(!patientId||!this.#token||this.#state.phase!=='ready'||this.#uploading||
       !/^CASE-[A-Z0-9-]{1,35}$/.test(caseId)||
       !this.#state.cases?.some(item=>item.case_id===caseId&&item.status==='active')){
      this.#publish({...this.#resetReview(),reviewPhase:'error',
        reviewMessage:'Open an authorized patient and active source case before reading the inbox.'});
      return;
    }
    const query=this.#reviewRead,scope=this.#scope,selection=this.#read;
    const current=()=>query===this.#reviewRead&&scope===this.#scope&&selection===this.#read&&
      this.#state.patient?.patient_id===patientId;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({reviewPhase:'loading',reviewMessage:'Checking independent question, source and review-inbox permissions…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+encodeURIComponent(caseId)+'/review-queue';
      const res=await this.transport(url,this.#init(control));
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status!==200){
        this.#publish({...([403,404].includes(res.status)?this.#resetReview():{}),reviewQueue:null,reviewPhase:'error',
          reviewMessage:'Review inbox unavailable under the current patient, source or review permissions.'});
        return;
      }
      const result=decodeReviewQueue(await json(res,2097152),patientId,caseId);
      if(!current())return;
      this.#publish({reviewQueue:result,reviewPhase:'ready',reviewMessage:result.items.length?
        'Saved source questions and immutable verification-return history. No clinical review is completed.':
        'No saved source questions are visible under this grant.'});
    }catch(_){
      if(current())this.#publish({reviewQueue:null,reviewPhase:'error',
        reviewMessage:'The current review projection could not be verified. Prior inbox content is cleared.'});
    }finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }

  async retryReviewReturn():Promise<void>{
    const intent=this.#state.reviewReturnIntent;
    if(this.#state.reviewReturnPhase!=='unknown'||!intent)return;
    await this.returnReviewQuestion(intent.question_id,intent.queue_fingerprint,intent.reason);
  }

  async returnReviewQuestion(questionId:string,fingerprint:string,
                             reason:string=FICTIONAL_RETURN_REASON):Promise<void>{
    if(this.#savingReview)return;
    const patientId=this.#state.patient?.patient_id;
    const previous=this.#state.reviewReturnIntent;
    const recovering=this.#state.reviewReturnPhase==='unknown'&&previous!==null&&this.#reviewKey!=='';
    if(recovering&&(previous.question_id!==questionId||previous.queue_fingerprint!==fingerprint||previous.reason!==reason)){
      this.#publish({reviewReturnMessage:'Resolve the earlier uncertain return with its exact reason and source context before starting a different return.'});
      return;
    }
    const queue=this.#state.reviewQueue,caseId=recovering?previous.case_id:queue?.case_id;
    const item=queue?.items.find(row=>row.question_id===questionId);
    if(recovering&&patientId===previous.patient_id&&this.#token&&this.#state.phase==='ready'&&
       this.#state.cases===null){
      this.#publish({reviewReturnMessage:'Recheck authorized cases before retrying this exact return. Its original request remains saved.'});
      return;
    }
    if(!patientId||!caseId||!this.#token||this.#state.phase!=='ready'||!validReturnReason(reason)||
       !this.#state.cases?.some(row=>row.case_id===caseId&&row.status==='active')||
       (recovering?previous.patient_id!==patientId:
        (this.#state.reviewPhase!=='ready'||!item||item.source_snapshot_contract!=='oi.pg-source-world-model/1'||
         item.review_state==='source_reassessment_required'||item.queue_fingerprint===null||item.queue_fingerprint!==fingerprint))){
      this.#publish({reviewReturnPhase:'error',reviewReturnMessage:
        'Select a current source question and a visible 10–600 character verification reason.'});
      return;
    }
    const intent=JSON.stringify([patientId,caseId,questionId,fingerprint,reason]);
    if(this.#reviewIntent!==intent||!this.#reviewKey){this.#reviewKey=crypto.randomUUID();this.#reviewIntent=intent;}
    const requestKey=this.#reviewKey,query=++this.#reviewWrite,scope=this.#scope,selection=this.#read;
    const captured=Object.freeze({patient_id:patientId,case_id:caseId,question_id:questionId,queue_fingerprint:fingerprint,reason});
    const current=()=>query===this.#reviewWrite&&scope===this.#scope&&selection===this.#read&&
      this.#state.patient?.patient_id===patientId&&this.#reviewIntent===intent;
    const uncertain=()=>{
      this.#reviewRead++;
      this.#publish({reviewQueue:null,reviewPhase:'idle',reviewReturn:null,reviewReturnPhase:'unknown',
        reviewMessage:'Refresh the inbox to check current sources and history.',
        reviewReturnMessage:'Return outcome uncertain. Retry this exact return to recover its original receipt without creating another request.'});
    };
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);this.#savingReview=true;
    this.#publish({reviewReturn:null,reviewReturnIntent:captured,reviewReturnPhase:'saving',
      reviewReturnMessage:recovering?'Recovering the exact earlier return receipt under current permissions…':
        'Rechecking the source fingerprint and separate return permission before recording…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+encodeURIComponent(caseId)+
        '/questions/'+encodeURIComponent(questionId)+'/return-for-verification';
      const res=await this.transport(url,this.#init(control,JSON.stringify({synthetic:true,
        request_key:requestKey,expected_queue_fingerprint:fingerprint,reason})));
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status===408||res.status>=500){uncertain();return;}
      if(res.status!==200&&res.status!==201){
        this.#publish({...this.#resetReview(),reviewReturnPhase:'error',reviewReturnMessage:res.status===409?
          'The source or return intent is no longer current. Refresh the inbox; no new request was created.':
          'Return permission or source context is unavailable. Prior review content is cleared.'});
        return;
      }
      const saved=decodeReviewReturnResult(await json(res),questionId);
      if(!current())return;
      this.#publish({reviewReturn:saved,reviewReturnPhase:'saved',reviewReturnMessage:saved.duplicate?
        'Original verification-return receipt recovered. The same request was not recorded twice.':
        'Verification return recorded. Refresh the inbox for its history. No clinician or external provider was notified.'});
    }catch(_){if(current())uncertain();}
    finally{clearTimeout(timeout);this.#controllers.delete(control);
      if(query===this.#reviewWrite&&scope===this.#scope)this.#savingReview=false;}
  }

  /** Source-only context is a read, never an authorization to execute Composer.
   * Request generation prevents responses from earlier patients/cases/credentials
   * or amended source views from repopulating the UI.
   */
  async loadWorldModel(caseId:string):Promise<void>{
    const inquiry=this.#resetInvestigation(caseId);
    const patientId=this.#state.patient?.patient_id;
    if(!this.#token||!patientId||this.#state.phase!=='ready'||this.#uploading||
       !/^CASE-[A-Z0-9-]{1,35}$/.test(caseId)||
       !this.#state.cases?.some(x=>x.case_id===caseId&&x.status==='active')){
      this.#records++;
      this.#publish({...emptyWorld(),...inquiry,...this.#resetReview(),worldPhase:'error',
        worldMessage:'Open an authorized fictional patient and active case first.'});
      return;
    }
    const scope=this.#scope,read=this.#read,request=++this.#records;
    const current=()=>scope===this.#scope&&read===this.#read&&request===this.#records&&
      this.#state.patient?.patient_id===patientId&&
      this.#state.cases?.some(x=>x.case_id===caseId&&x.status==='active');
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({...emptyWorld(),...inquiry,worldPhase:'loading',
      worldMessage:'Checking source-derived World Model and current permissions…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+encodeURIComponent(caseId)+'/world-model';
      const response=await this.transport(url,this.#init(control));
      if(!current())return;
      if(response.status===401){this.#httpError(401);return;}
      if(response.status!==200){
        this.#publish({...emptyWorld(),...([403,404].includes(response.status)?this.#resetReview():{}),worldPhase:'error',
          worldMessage:'World Model source scope unavailable or revoked. Previous snapshot cleared.'});
        return;
      }
      const model=parseSourceWorldModel(await json(response,1048576),patientId,caseId);
      if(!current())return;
      this.#publish({worldModel:model,worldPhase:'ready',
        worldMessage:'Source-derived snapshot verified at last read; no clinical assessment or AI execution is authorized.'});
    }catch(_){
      if(current())this.#publish({...emptyWorld(),worldPhase:'error',
        worldMessage:'World Model response failed validation or transport. Previous snapshot cleared.'});
    }finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }

  /** A question draft belongs to one current source and World Model snapshot.
   * Never persist editable text, credentials or preflight data outside memory.
   */
  chooseQuestionDraft(sourceId:string,sourceLine:number):void{
    if(this.#savingQuestion||this.#state.questionSaveMessage.startsWith('Save outcome unknown.')){
      this.#publish({composerMessage:'Resolve the uncertain question save with the same request key before changing its source.'});
      return;
    }
    const model=this.#state.worldModel;
    if(!model||this.#state.worldPhase!=='ready'||!this.#token||
       !model.observations.some(o=>o.source_id===sourceId&&o.source_line===sourceLine)){
      this.#publish({composerMessage:'Choose a currently authorized source statement before writing.'});
      return;
    }
    this.#focusSavedQuestion(null);
    const existing=this.#state.questionDraft;
    if(existing?.case_id===model.case_id&&existing.source_id===sourceId&&
       existing.source_line===sourceLine&&existing.snapshot_fingerprint===model.snapshot_fingerprint)return;
    this.#composerRead++;this.#questionWrite++;
    this.#questionKey='';this.#questionFingerprint='';
    this.#publish({
      questionDraft:Object.freeze({case_id:model.case_id,source_id:sourceId,
        source_line:sourceLine,snapshot_fingerprint:model.snapshot_fingerprint,
        question:DEFAULT_SOURCE_QUESTION}),
      composerPreview:null,composerPhase:'idle',
      composerMessage:'Edit the authored fictional question, then explicitly prepare source context.',
      savedQuestion:null,questionSavePhase:'idle',
      questionSaveMessage:'The question is a draft. It has not been saved or clinically reviewed.',
    });
  }

  changeQuestionDraft(text:string):void{
    const draft=this.#state.questionDraft;
    if(!draft||this.#savingQuestion||this.#state.questionSaveMessage.startsWith('Save outcome unknown.')||
       typeof text!=='string'||text.length>500||draft.question===text)return;
    this.#focusSavedQuestion(null);
    // A changed character makes an earlier preflight response and save key
    // invalid. The previous saved question, if any, remains on the server.
    this.#composerRead++;this.#questionWrite++;
    this.#questionKey='';this.#questionFingerprint='';
    this.#publish({questionDraft:Object.freeze({...draft,question:text}),
      composerPreview:null,composerPhase:'idle',
      composerMessage:'Draft changed. Re-prepare this exact question before saving.',
      savedQuestion:null,questionSavePhase:'idle',
      questionSaveMessage:'No save attempted for the edited draft.'});
  }

  discardQuestionDraft():void{
    if(this.#savingQuestion||this.#state.questionSaveMessage.startsWith('Save outcome unknown.')){
      this.#publish({composerMessage:'Save outcome is unknown. Retry with the existing request key before discarding.'});
      return;
    }
    this.#composerRead++;this.#questionWrite++;
    this.#questionKey='';this.#questionFingerprint='';
    this.#publish({questionDraft:null,composerPreview:null,composerPhase:'idle',
      composerMessage:'Unsaved question draft discarded. No server write was made by this action.',
      savedQuestion:null,questionSavePhase:'idle',
      questionSaveMessage:'Select another source statement to prepare a new question.'});
  }

  async prepareDraftQuestion():Promise<void>{
    const draft=this.#state.questionDraft,model=this.#state.worldModel;
    if(!draft||!model||draft.case_id!==model.case_id||
       draft.snapshot_fingerprint!==model.snapshot_fingerprint){
      this.#publish({composerPhase:'error',composerMessage:'This draft no longer matches the current case/source snapshot. Refresh the case.'});
      return;
    }
    await this.prepareSourceContext(draft.source_id,draft.source_line,draft.question);
  }

  async prepareSourceContext(sourceId:string,sourceLine:number,
                             question:string=DEFAULT_SOURCE_QUESTION):Promise<void>{
    if(this.#savingQuestion)return;
    this.#focusSavedQuestion(null);
    const model=this.#state.worldModel;
    const patientId=this.#state.patient?.patient_id;
    const observation=model?.observations.find(o=>
      o.source_id===sourceId&&o.source_line===sourceLine);
    const query=++this.#composerRead,scope=this.#scope,selection=this.#read,
      worldQuery=this.#worldRead;
    this.#questionRead++;this.#briefRead++;
    this.#publish({...emptyBrief(),questions:null,questionsAccessReceiptId:null,questionsCaseId:null,questionListPhase:'idle',
      questionListMessage:'Refresh current questions after preparing source context.'});
    // An old preview is never a durable permission or context for a new run.
    this.#publish({composerPreview:null,composerPhase:'idle',
      composerMessage:'Preparing source context requires an independent authorization.'});
    if(!patientId||!model||!observation||this.#state.worldPhase!=='ready'||!this.#token||
       typeof question!=='string'||question.trim()!==question||
       question.length<8||question.length>500||/[\u0000-\u001f\u007f]/.test(question)){
      this.#publish({composerPhase:'error',composerMessage:
        'Select an authorized current source statement and valid question first.'});
      return;
    }
    const current=()=>scope===this.#scope&&selection===this.#read&&
      worldQuery===this.#worldRead&&query===this.#composerRead&&
      this.#state.patient?.patient_id===patientId&&
      this.#state.worldModel?.snapshot_fingerprint===model.snapshot_fingerprint;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({composerPhase:'loading',composerMessage:
      'Rechecking exact source version and separate Composer-context grant…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+
        encodeURIComponent(model.case_id)+'/composer/source-preflight';
      const payload={synthetic:true,
        expected_source_snapshot_sha256:model.snapshot_fingerprint,
        source_id:sourceId,source_line:sourceLine,question};
      const res=await this.transport(url,this.#init(control,JSON.stringify(payload)));
      if(!current())return;
      if(res.status===401){this.#httpError(res.status);return;}
      if(res.status!==200){
        // A failed preflight must not leave stale patient observations visible
        // as though they remained currently permitted. Only the exact earlier
        // return survives a non-authoritative failure; retry checks its own grant.
        this.#resetWorld([403,404].includes(res.status)?undefined:model.case_id);
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
        this.#resetWorld(model.case_id);
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
       !this.#state.worldModel||!this.#token||!this.#questionKey||
       this.#state.worldModel.case_id!==prepared.case_id||
       this.#state.worldModel.snapshot_fingerprint!==prepared.source_snapshot_sha256){
      this.#publish({questionSavePhase:'error',questionSaveMessage:
        'Prepare the current, authorized source context before saving a question.'});
      return;
    }
    const key=this.#questionKey,query=++this.#questionWrite;
    this.#briefRead++;
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
    this.#publish({...emptyBrief(),savedQuestion:null,questionSavePhase:'saving',
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
        if(![403,404,409,413,422].includes(res.status))throw Error('unconfirmed');
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

  async loadQuestionSourcePacket(questionId:string):Promise<void>{
    this.#focusSavedQuestion(questionId);
    const pid=this.#state.patient?.patient_id;
    const caseId=this.#state.questionsCaseId;
    const question=this.#state.questions?.find(q=>q.question_id===questionId);
    const scope=this.#scope,read=this.#read,questionRead=this.#questionRead,
      worldRead=this.#worldRead,query=++this.#quoteRead;
    this.#publish({sourceQuotePacket:null,sourceQuotePhase:'idle',
      sourceQuoteMessage:'This inspection requires a fresh independent source-packet grant.'});
    if(!pid||!caseId||!question||!this.#token||this.#state.questionListPhase!=='ready'||
       !this.#state.cases?.some(x=>x.case_id===caseId&&x.status==='active')){
      this.#publish({sourceQuotePhase:'error',
        sourceQuoteMessage:'Open an authorized current case and saved question first.'});
      return;
    }
    const current=()=>scope===this.#scope&&read===this.#read&&
      questionRead===this.#questionRead&&worldRead===this.#worldRead&&
      query===this.#quoteRead&&this.#state.patient?.patient_id===pid&&
      this.#state.questionsCaseId===caseId&&
      this.#state.questions?.some(q=>q.question_id===questionId);
    const controller=new AbortController();this.#controllers.add(controller);
    const timeout=setTimeout(()=>controller.abort(),10000);
    this.#publish({sourceQuotePhase:'loading',
      sourceQuoteMessage:'Rechecking exact canonical original, question and source-quote rights…'});
    try{
      const path='/v1/patients/'+encodeURIComponent(pid)+'/cases/'+
        encodeURIComponent(caseId)+'/questions/'+encodeURIComponent(questionId)+
        '/source-review-packet';
      const res=await this.transport(path,this.#init(controller));
      if(!current())return;
      if(res.status===401){this.#httpError(res.status);return;}
      if(res.status!==200){
        this.#publish({sourceQuotePacket:null,sourceQuotePhase:'error',
          sourceQuoteMessage:'Source quote packet unavailable or not authorized. Previous quote cleared.'});
        return;
      }
      const fingerprint=this.#state.worldModel?.case_id===caseId
        ?this.#state.worldModel.snapshot_fingerprint:undefined;
      const packet=await decodeQuestionSourcePacket(
        await json(res,1048576),question,caseId,pid,fingerprint);
      if(!current())return;
      this.#publish({sourceQuotePacket:packet,sourceQuotePhase:'ready',
        sourceQuoteMessage:packet.selected_statement?
         'Current authored source statement inspected. Independent evidence appraisal remains missing.':
         'Historical source changed. The old question must be reassessed; no current quote is promoted.'});
    }catch(_){
      if(current())this.#publish({sourceQuotePacket:null,sourceQuotePhase:'error',
        sourceQuoteMessage:'Source quote or packet integrity could not be verified. Nothing is displayed.'});
    }finally{clearTimeout(timeout);this.#controllers.delete(controller);}
  }

  async loadSavedQuestions(caseId:string):Promise<void>{
    this.dismissQuestionEvidence();
    this.dismissSourceQuotePacket();
    const patientId=this.#state.patient?.patient_id;
    const query=++this.#questionRead,scope=this.#scope,patientRead=this.#read,worldRead=this.#worldRead;
    this.#briefRead++;
    this.#publish({...emptyBrief(),questions:null,questionsAccessReceiptId:null,questionsCaseId:null,questionListPhase:'idle',
      questionListMessage:'Checking current authorization for saved source-linked questions…'});
    if(!patientId||!this.#token||!/^CASE-[A-Z0-9-]{1,35}$/.test(caseId)||
       !this.#state.cases?.some(item=>item.case_id===caseId&&item.status==='active')){
      this.#publish({questionListPhase:'error',questionListMessage:
        'Open an authorized patient and exact source case before reading questions.'});
      return;
    }
    const current=()=>query===this.#questionRead&&scope===this.#scope&&
      patientRead===this.#read&&worldRead===this.#worldRead&&this.#state.patient?.patient_id===patientId;
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
        this.#publish({...([403,404].includes(res.status)?{...this.#resetReview(),reviewPhase:'error' as const,
          reviewMessage:'Question or source access is unavailable. Previous review content is cleared.'}:{}),
          questions:null,questionListPhase:'error',
          questionListMessage:'Saved questions unavailable under current authority.'});
        return;
      }
      const history=decodeSourceQuestions(await json(res,1048576),patientId,caseId);
      if(!current())return;
      this.#publish({questions:history.questions,questionsAccessReceiptId:history.access_receipt_id,
        questionsCaseId:caseId,questionListPhase:'ready',
        questionListMessage:history.questions.length?
          'Authorized source-linked questions, including any reopened reassessment needs.':
          'No saved source questions are available under this grant.'});
    }catch(_){
      if(current())this.#publish({questions:null,questionListPhase:'error',
        questionListMessage:'Question history could not be verified; no cached questions are shown.'});
    }finally{clearTimeout(timeout);this.#controllers.delete(controller);}
  }

  /** Fresh export of one persisted source question; no model, evidence synthesis or review. */
  async prepareSourceBrief(questionId:string):Promise<SourceBrief|null>{
    this.#focusSavedQuestion(questionId);
    const query=++this.#briefRead,scope=this.#scope,patientRead=this.#read,
      worldRead=this.#worldRead,questionRead=this.#questionRead;
    const model=this.#state.worldModel,patientId=this.#state.patient?.patient_id;
    const question=this.#state.questions?.find(item=>item.question_id===questionId);
    this.#publish({...emptyBrief()});
    if(!this.#token||!patientId||!model||!question||this.#uploading||this.#savingQuestion||
       this.#state.phase!=='ready'||this.#state.worldPhase!=='ready'||
       this.#state.questionListPhase!=='ready'||this.#state.questionsCaseId!==model.case_id||
       model.patient_id!==patientId||!canPrepareSourceBrief(question,model)){
      this.#publish({briefPhase:'error',briefMessage:
        'Choose a current saved question with its exact source context. Refresh changed sources before preparing a brief.'});
      return null;
    }
    const control=new AbortController();this.#controllers.add(control);
    const current=()=>query===this.#briefRead&&scope===this.#scope&&
      patientRead===this.#read&&worldRead===this.#worldRead&&questionRead===this.#questionRead&&
      this.#state.patient?.patient_id===patientId&&this.#state.worldModel===model&&
      this.#state.questions?.find(item=>item.question_id===questionId)===question;
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({briefPhase:'loading',briefMessage:'Checking current source context and separate export permission…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+encodeURIComponent(model.case_id)+
        '/questions/'+encodeURIComponent(questionId)+'/brief';
      const body=JSON.stringify({synthetic:true,source_snapshot_contract:'oi.pg-source-world-model/1',
        expected_source_snapshot_sha256:model.snapshot_fingerprint,
        expected_preflight_sha256:question.preflight_sha256});
      const res=await this.transport(url,this.#init(control,body));
      if(!current())return null;
      if(control.signal.aborted)throw Error('brief timeout');
      if(res.status===401){this.#httpError(401);return null;}
      if(res.status!==200){
        this.#resetWorld([403,404].includes(res.status)?undefined:model.case_id);
        this.#publish({briefPhase:'error',briefMessage:res.status===409?
          'The source changed. Refresh Investigations and use a current saved question before preparing a new brief.':
          'Source brief unavailable under current authority. No earlier preview can be downloaded.'});
        return null;
      }
      const prepared=await decodeSourceBrief(await json(res),model,question);
      // Digest verification also awaits: a changed patient, case or question must still win.
      if(!current())return null;
      if(control.signal.aborted)throw Error('brief timeout');
      this.#publish({sourceBrief:prepared,briefPhase:'ready',briefMessage:
        'Source-linked brief verified. Download checks current permission again. Human review has not been submitted.'});
      return prepared;
    }catch(_){
      if(current()){
        this.#resetWorld(model.case_id);
        this.#publish({...emptyBrief(),briefPhase:'error',briefMessage:
          'The source brief could not be verified. No earlier preview can be downloaded.'});
      }
      return null;
    }finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }

  /** Original is an independently permission-checked read; hash verification is not clinical validation. */
  dismissOriginal=()=>{
    this.#records++;
    this.#publish({...(this.#state.worldPhase==='loading'?emptyWorld():{}),original:null,recordsPhase:'ready'});
  };
  async loadOriginal(sourceId:string):Promise<void>{
    const patientId=this.#state.patient?.patient_id,index=this.#state.sourceIndex;
    const source=index?.sources.find(s=>s.source_id===sourceId);
    this.#publish({original:null});
    if(!this.#token||!patientId||!index||!source||this.#uploading)return;
    const scope=this.#scope,read=this.#read,request=++this.#records,caseId=index.case_id;
    const current=()=>scope===this.#scope&&read===this.#read&&request===this.#records&&
      this.#state.patient?.patient_id===patientId&&this.#state.sourceIndex?.case_id===caseId;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({...(this.#state.worldPhase==='loading'?emptyWorld():{}),
      recordsPhase:'loading-original',recordMessage:'Checking original-document permission and exact source hash…'});
    try{
      const res=await this.transport('/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+encodeURIComponent(caseId)+'/sources/'+encodeURIComponent(sourceId),this.#init(control));
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status!==200){this.#publish({original:null,recordsPhase:'error',recordMessage:'Original unavailable or permission denied. No previously opened text is retained.'});return;}
      // A 64 KiB original can expand under JSON escaping. Keep the envelope bounded too.
      const original=await verifyOriginal(await json(res,524288),caseId,source);
      if(!current())return;
      this.#publish({original,recordsPhase:'ready',recordMessage:'Exact original bytes verified against the selected source hash. Clinical review remains not established.'});
    }catch(_){if(current())this.#publish({original:null,recordsPhase:'error',recordMessage:'Original failed verification or service unavailable. Reload metadata before trying again.'});}
    finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }
  /** Only the existing server decides import/duplicate/quarantine. No retry or inferred rollback. */
  async importSource(caseId:string,text:string,confirmed:boolean):Promise<void>{
    if(this.#uploading)return;
    const patientId=this.#state.patient?.patient_id;
    if(!this.#token||!patientId||this.#state.phase!=='ready'||this.#state.sourceIndex?.case_id!==caseId||
      !this.#state.cases?.some(c=>c.case_id===caseId&&c.status==='active')||confirmed!==true){
      this.#publish({importOutcome:'rejected',importReceipt:null,importMessage:'Select an authorized active case, inspect the original and confirm fictional data first.'});return;
    }
    try{
      if(typeof text!=='string'||prepareSource(new TextEncoder().encode(text),'original.txt').text!==text)throw Error('input');
      if(new TextEncoder().encode(JSON.stringify({synthetic:true,original_text:text})).length>72000)throw Error('envelope');
    }
    catch(_){this.#publish({importOutcome:'rejected',importReceipt:null,importMessage:'Unsupported original source. Nothing was sent.'});return;}
    const scope=this.#scope,read=this.#read,request=++this.#records;
    const current=()=>scope===this.#scope&&read===this.#read&&request===this.#records&&
      this.#state.patient?.patient_id===patientId&&this.#state.sourceIndex?.case_id===caseId;
    const control=new AbortController();this.#controllers.add(control);this.#uploading=true;
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({...emptyWorld(),...this.#resetInvestigation(caseId),original:null,importOutcome:'sending',importReceipt:null,importMessage:'Sending this original once. Do not switch context until its receipt returns.'});
    try{
      const res=await this.transport('/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+encodeURIComponent(caseId)+'/sources',
        this.#init(control,JSON.stringify({synthetic:true,original_text:text})));
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if([403,404,409,413,422].includes(res.status)){
        this.#publish({cases:null,sourceIndex:null,original:null,recordsPhase:'error',importOutcome:'rejected',
          ...([403,404].includes(res.status)?this.#resetReview():{}),
          importMessage:'The server rejected this import. Reload current case permissions; no success is claimed.'});return;
      }
      if(![200,201].includes(res.status))throw Error('unconfirmed');
      const receipt=parseImportReceipt(await json(res));if(!current())return;
      this.#publish({importReceipt:receipt,importOutcome:'confirmed',importMessage:receipt.result==='quarantined'?
        'Quarantined: different declared case. No findings were attached to this case.':receipt.result==='duplicate'?
        'Duplicate: the original already exists. No new source version was created.':
        'Original saved as version '+receipt.version+'. Source statements are not clinical approval.'});
      await this.loadSources(caseId);
    }catch(_){if(current())this.#publish({importReceipt:null,importOutcome:'unknown',importMessage:'Import outcome unknown. It may have been saved. Inspect current source versions before any explicit retry; nothing was automatically retried.'});}
    finally{clearTimeout(timeout);this.#controllers.delete(control);if(scope===this.#scope)this.#uploading=false;}
  }
}
