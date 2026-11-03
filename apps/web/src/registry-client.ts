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
import {canCreateFollowthrough,decodeFollowthrough,decodeFollowthroughReceipt,
  validFollowthroughDraft,validFollowthroughTransition} from './followthrough-view.js';
import type {FollowthroughDraft,FollowthroughUnsentDraft,FollowthroughIntent,FollowthroughList,
  FollowthroughReceipt,FollowthroughTransition} from './followthrough-view.js';
import {decodeQuestionEvidenceSearch,decodeQuestionEvidenceLinks,decodeQuestionEvidenceReceipt,
  validEvidenceQuery} from './question-evidence-view.js';
import type {QuestionEvidenceSearch,QuestionEvidenceLinks,QuestionEvidenceIntent,
  QuestionEvidenceReceipt} from './question-evidence-view.js';
import {QuestionEvidenceSession,emptyEvidenceState} from './authored-evidence-session.js';
import type {EvidenceState,EvidenceDraftPatch} from './authored-evidence-session.js';
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
  followthrough:FollowthroughList|null;followthroughCaseId:string|null;
  followthroughDrafts:Readonly<Record<string,FollowthroughUnsentDraft>>;
  followthroughPhase:'idle'|'loading'|'ready'|'error';followthroughMessage:string;
  followthroughReceipt:FollowthroughReceipt|null;followthroughIntent:FollowthroughIntent|null;
  followthroughWritePhase:'idle'|'saving'|'saved'|'unknown'|'error';followthroughWriteMessage:string;
  sourceQuotePacket:QuestionSourceReviewPacket|null;
  sourceQuotePhase:'idle'|'loading'|'ready'|'error';sourceQuoteMessage:string;
  evidenceQuestionId:string|null;
  evidenceSearch:QuestionEvidenceSearch|null;evidenceSearchPhase:'idle'|'loading'|'ready'|'error';evidenceSearchMessage:string;
  evidenceLinks:QuestionEvidenceLinks|null;evidenceLinksPhase:'idle'|'loading'|'ready'|'error';evidenceLinksMessage:string;
  evidenceLinkIntent:QuestionEvidenceIntent|null;evidenceLinkReceipt:QuestionEvidenceReceipt|null;
  evidenceLinkPhase:'idle'|'saving'|'saved'|'unknown'|'error';evidenceLinkMessage:string;
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
const emptyFollowthrough=()=>({followthrough:null,followthroughCaseId:null,followthroughPhase:'idle' as const,
  followthroughDrafts:Object.freeze({}) as Readonly<Record<string,FollowthroughUnsentDraft>>,
  followthroughMessage:'Choose an authorized case to inspect work recorded for its saved questions.',
  followthroughReceipt:null,followthroughIntent:null,followthroughWritePhase:'idle' as const,
  followthroughWriteMessage:'No follow-up action is in progress.'});
const emptyEvidenceMetadata=()=>({evidenceSearch:null,evidenceSearchPhase:'idle' as const,
  evidenceSearchMessage:'Enter your own terms to search the original fictional catalog.',
  evidenceLinks:null,evidenceLinksPhase:'idle' as const,
  evidenceLinksMessage:'Refresh saved citations to check their current availability.'});
const emptyEvidence=()=>({...emptyEvidenceMetadata(),evidenceQuestionId:null,evidenceLinkIntent:null,evidenceLinkReceipt:null,
  evidenceLinkPhase:'idle' as const,evidenceLinkMessage:'No citation link is being saved.'});
const emptyInvestigation=()=>({questionDraft:null,composerPreview:null,composerPhase:'idle' as const,
  composerMessage:'Select an exact current source observation to prepare a non-executing context.',
  savedQuestion:null,questionSavePhase:'idle' as const,
  questionSaveMessage:'Save a verified preflight to create one unreviewed source-linked question.',
  questions:null,questionsAccessReceiptId:null,questionsCaseId:null,questionListPhase:'idle' as const,
  questionListMessage:'Open an authorized case to inspect saved source questions.',
  ...emptyEvidenceState(),...emptyBrief(),sourceQuotePacket:null,sourceQuotePhase:'idle' as const,
  sourceQuoteMessage:'Select a saved question to inspect its source quotation and evidence gaps.'});
const fresh = (): ViewState => Object.freeze({connected:false,phase:'disconnected',patient:null,created:null,message:'Connect a local synthetic credential to use the patient registry.',cases:null,sourceIndex:null,recordsPhase:'idle',recordMessage:'Open an authorized fictional patient in Overview first.',...emptyIntake(),...emptyWorld(),...emptyInvestigation(),...emptyReview(),...emptyFollowthrough(),...emptyEvidence()});
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
  #followRead=0; #followWrite=0; #savingFollowthrough=false;
  #evidenceRead=0; #evidenceWrite=0; #savingEvidence=false;
  #quoteRead=0;
  #inspectionQuestionId:string|null=null;
  #listeners=new Set<()=>void>(); #controllers=new Set<AbortController>(); #creating=false; #uploading=false;
  #evidenceSession:QuestionEvidenceSession;
  constructor(private readonly transport:Transport=(url,init)=>fetch(url,init)) {
    this.#evidenceSession=new QuestionEvidenceSession({snapshot:this.snapshot,
      publish:patch=>this.#publish(patch),scope:()=>[this.#scope,this.#read,this.#worldRead,this.#questionRead].join(':'),
      selectedQuestion:()=>this.#inspectionQuestionId,
      request:(url,control,body)=>this.transport(url,this.#init(control,body)),json,
      add:control=>this.#controllers.add(control),remove:control=>this.#controllers.delete(control),
      expire:()=>this.#httpError(401)});
  }
  selectEvidenceComparison=(questionId:string,evidenceId:string)=>this.#evidenceSession.beginComparison(questionId,evidenceId);
  editEvidenceComparison=(patch:EvidenceDraftPatch)=>this.#evidenceSession.editComparison(patch);
  discardEvidenceComparison=()=>this.#evidenceSession.discardComparison();
  saveEvidenceComparison=()=>this.#evidenceSession.saveComparison();
  dismissQuestionEvidence=()=>this.#evidenceSession.dismiss();
  dismissEvidenceMetadata=()=>this.#publish(this.#resetEvidence(this.#state.evidenceLinkIntent?.case_id??this.#state.questionsCaseId??undefined));
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
  #resetEvidence(preserveCase?:string){
    this.#evidenceRead++;this.#evidenceWrite++;this.#savingEvidence=false;
    const intent=this.#state.evidenceLinkIntent;
    if(intent&&intent.patient_id===this.#state.patient?.patient_id&&intent.case_id===preserveCase&&
       ['saving','unknown'].includes(this.#state.evidenceLinkPhase)){
      return {...emptyEvidence(),evidenceLinkIntent:intent,evidenceLinkPhase:'unknown' as const,
        evidenceLinkMessage:'The earlier citation save is uncertain. Retry its exact recorded intent, or explicitly abandon recovery. No new citation is assumed.'};
    }
    return emptyEvidence();
  }
  #resetFollowthrough(preserveCase?:string){
    this.#followRead++;this.#followWrite++;this.#savingFollowthrough=false;
    const intent=this.#state.followthroughIntent;
    const drafts=Object.freeze(Object.fromEntries(Object.entries(this.#state.followthroughDrafts)
      .filter(([,draft])=>draft.patient_id===this.#state.patient?.patient_id&&draft.case_id===preserveCase)));
    if(intent&&intent.patient_id===this.#state.patient?.patient_id&&intent.case_id===preserveCase&&
       ['saving','unknown'].includes(this.#state.followthroughWritePhase)){
      return {...emptyFollowthrough(),followthroughDrafts:drafts,followthroughCaseId:preserveCase,followthroughIntent:intent,
        followthroughWritePhase:'unknown' as const,followthroughWriteMessage:
          'The earlier write outcome is uncertain. Retry its exact recorded intent to recover the receipt, or explicitly abandon recovery.'};
    }
    return {...emptyFollowthrough(),followthroughDrafts:drafts,followthroughCaseId:preserveCase??null};
  }
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
  #resetInvestigation(preserveReviewCase?:string,preserveFollowthroughCase=preserveReviewCase,preserveEvidenceCase=preserveReviewCase,preserveAuthoredEvidenceCase=preserveReviewCase){
    this.#inspectionQuestionId=null;
    this.#worldRead++;this.#composerRead++;this.#questionRead++;this.#questionWrite++;this.#briefRead++;this.#quoteRead++;
    this.#questionKey='';this.#questionFingerprint='';this.#savingQuestion=false;
    return {...emptyInvestigation(),...this.#resetReview(preserveReviewCase),...this.#resetFollowthrough(preserveFollowthroughCase),
      ...this.#resetEvidence(preserveEvidenceCase),...this.#evidenceSession.reset(preserveAuthoredEvidenceCase)};
  }
  #resetWorld(preserveReviewCase?:string){
    this.#publish({...emptyWorld(),...this.#resetInvestigation(preserveReviewCase)});
  }
  /** Independently authorized readers share one UI selection, not a
   * new domain record. A switch invalidates both readers before either awaits.
   * This prevents a late response for question A restoring beside question B.
   * A null selection returns to an authored draft or a new source preflight.
   */
  #focusSavedQuestion(questionId:string|null):void{
    if(this.#inspectionQuestionId===questionId)return;
    this.#inspectionQuestionId=questionId;
    this.dismissSourceBrief();
    this.dismissSourceQuotePacket();
    this.dismissEvidenceMetadata();
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
    const pendingEvidence=this.#state.evidenceWriteIntent;
    const preserveEvidence=pendingEvidence?.patient_id===id&&
      ['saving','unknown'].includes(this.#state.evidenceWritePhase)?pendingEvidence:null;
    this.#records++;this.#publish({patient:null,...emptyRecords(),...this.#resetInvestigation(),
      ...(preserveEvidence?{evidenceWriteIntent:preserveEvidence,evidenceWritePhase:'unknown' as const,
        evidenceWriteMessage:'The same patient is being rechecked. The earlier evidence write remains uncertain; reload its case authority before exact receipt recovery.'}:{})});
    if(!this.#token){this.#publish({message:'Connect an authorized synthetic credential first.'});return;}
    if(!boundedKey(id)){this.#publish({phase:'error',message:'Use an opaque patient ID, not a name or URL.'});return;}
    const control=new AbortController();this.#controllers.add(control);
    const current=()=>scope===this.#scope && request===this.#read;
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({phase:'reading',message:'Checking the current patient grant…'});
    try{
      const res=await this.transport('/v1/patients/'+encodeURIComponent(id),this.#init(control));
      if(!current())return;
      if(res.status!==200){
        // A temporary recheck failure cannot establish the earlier write's
        // outcome. Explicit patient denial does withdraw this shared scope.
        if([403,404].includes(res.status))this.#publish(this.#resetInvestigation());
        this.#httpError(res.status);return;
      }
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
    const retainedCase=this.#state.reviewReturnIntent?.case_id,
      retainedFollowthroughCase=this.#state.followthroughIntent?.case_id??Object.values(this.#state.followthroughDrafts)[0]?.case_id,
      retainedEvidenceCase=this.#state.evidenceLinkIntent?.case_id,
      retainedAuthoredEvidenceCase=this.#state.evidenceWriteIntent?.case_id;
    const scope=this.#scope,read=this.#read,request=++this.#records;
    const current=()=>scope===this.#scope && read===this.#read &&
      request===this.#records && this.#state.patient?.patient_id===patientId;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({...emptyIntake(),...emptyWorld(),...this.#resetInvestigation(retainedCase,retainedFollowthroughCase,retainedEvidenceCase,retainedAuthoredEvidenceCase),cases:null,sourceIndex:null,recordsPhase:'loading-cases',recordMessage:'Checking current case mapping permissions…'});
    try{
      const res=await this.transport('/v1/patients/'+encodeURIComponent(patientId)+'/case-bindings',this.#init(control));
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status!==200){
        this.#publish({cases:null,sourceIndex:null,recordsPhase:'error',
          ...([403,404].includes(res.status)?{...this.#resetReview(),...this.#resetFollowthrough(),...this.#resetEvidence(),...this.#evidenceSession.reset()}:{}),
          recordMessage:'Case mappings unavailable or permission changed. No records are shown.'});
        return;
      }
      const mappings=parseCaseBindingList(await json(res),patientId);
      if(!current())return;
      const pendingCase=this.#state.followthroughIntent?.case_id??Object.values(this.#state.followthroughDrafts)[0]?.case_id;
      this.#publish({...((pendingCase&&!mappings.some(item=>item.case_id===pendingCase&&item.status==='active'))?this.#resetFollowthrough():{}),
        ...(retainedEvidenceCase&&!mappings.some(item=>item.case_id===retainedEvidenceCase&&item.status==='active')?this.#resetEvidence():{}),
        ...(retainedAuthoredEvidenceCase&&!mappings.some(item=>item.case_id===retainedAuthoredEvidenceCase&&item.status==='active')?this.#evidenceSession.reset():{}),
        cases:mappings,sourceIndex:null,recordsPhase:'ready',
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
          ...([403,404].includes(res.status)?{...this.#resetReview(),...this.#resetFollowthrough(),...this.#resetEvidence(),...this.#evidenceSession.reset()}:{}),
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
    if(this.#state.followthroughCaseId&&this.#state.followthroughCaseId!==caseId)this.#publish(this.#resetFollowthrough(caseId));
    const evidenceCase=this.#state.evidenceLinkIntent?.case_id??(this.#state.evidenceQuestionId?this.#state.questionsCaseId:null);
    if(evidenceCase&&evidenceCase!==caseId)this.#publish(this.#resetEvidence());
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

  /** Recheck an exact original quotation before starting a question from Records.
   *
   * The cached source index only supplies an anchor, never permission or
   * an executable clinical context. The canonical World Model is fetched again.
   * A changed/amended source cannot silently become a new question's source.
   */
  async beginQuestionFromSourceReading(caseId:string,sourceId:string,sourceLine:number):Promise<boolean>{
    if(this.#savingQuestion||this.#state.questionSavePhase==='saving'||
       this.#state.questionSaveMessage.startsWith('Save outcome unknown.')){
      this.#publish({worldMessage:'Resolve the earlier uncertain question save in Investigations before changing its source.'});
      return false;
    }
    if(this.#state.questionDraft&&this.#state.questionSavePhase!=='saved'){
      this.#publish({worldMessage:'An unfinished question draft exists. Finish or discard it in Investigations before starting a different one.'});
      return false;
    }
    const index=this.#state.sourceIndex,patientId=this.#state.patient?.patient_id;
    const source=index?.sources.find(s=>s.source_id===sourceId&&s.state==='current');
    const finding=index?.source_reported_assertions.find(f=>f.source_id===sourceId&&f.source_line===sourceLine);
    if(!index||index.case_id!==caseId||!patientId||this.#state.phase!=='ready'||
       this.#state.recordsPhase!=='ready'||this.#state.worldPhase==='loading'||
       !source||!finding||!this.#state.cases?.some(c=>c.case_id===caseId&&c.status==='active')){
      this.#publish({worldMessage:'This statement is not a current, authorized source anchor. Recheck Records before asking a question.'});
      return false;
    }
    const scope=this.#scope,priorWorldRead=this.#worldRead;
    await this.loadWorldModel(caseId);
    const model=this.#state.worldModel;
    // A concurrent patient/case/source refresh invalidates this user intent.
    if(scope!==this.#scope||priorWorldRead+1!==this.#worldRead||
       this.#state.patient?.patient_id!==patientId||this.#state.sourceIndex!==index||
       this.#state.worldPhase!=='ready'||!model||model.case_id!==caseId)return false;
    const currentSource=model.current_sources.find(s=>s.source_id===sourceId);
    const quotation=model.observations.filter(o=>o.source_id===sourceId&&o.source_line===sourceLine);
    if(!currentSource||currentSource.sha256!==source.sha256||
       currentSource.version!==source.version||quotation.length!==1||
       quotation[0].document_id!==source.document_id||
       quotation[0].document_version!==source.version||
       quotation[0].source_sha256!==source.sha256||
       quotation[0].source_statement!==finding.source_statement||
       quotation[0].finding_key!==finding.finding_key||
       quotation[0].reported_state!==finding.reported_state){
      this.#resetWorld(caseId);
      this.#publish({worldPhase:'error',worldMessage:'The source quotation or version changed during the handoff. No question draft was created. Recheck Records.'});
      return false;
    }
    this.chooseQuestionDraft(sourceId,sourceLine);
    return this.#state.questionDraft?.source_id===sourceId&&
      this.#state.questionDraft.source_line===sourceLine;
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
        this.#publish({...emptyWorld(),...([403,404].includes(response.status)?{...this.#resetReview(),...this.#resetFollowthrough(),...this.#resetEvidence(),...this.#evidenceSession.reset()}:{}),worldPhase:'error',
          worldMessage:'World Model source scope unavailable or revoked. Previous snapshot cleared.'});
        return;
      }
      const model=parseSourceWorldModel(await json(response,1048576),patientId,caseId);
      if(!current())return;
      this.#publish({worldModel:model,worldPhase:'ready',
        followthroughDrafts:Object.freeze(Object.fromEntries(Object.entries(this.#state.followthroughDrafts)
          .filter(([,draft])=>draft.patient_id===patientId&&draft.case_id===caseId&&
            draft.source_snapshot_sha256===model.snapshot_fingerprint))),
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
        'Select an authorized current source statement and valid q…21912 tokens truncated…rue;
}"""


def navigate(cd, section):
    cd.evaluate("[...document.querySelectorAll('nav button')].find(e=>e.textContent.startsWith("
                + json.dumps(section) + ")).click()")
    selectors = {'Investigations': '[data-view=investigations]',
                 'Journey': '[data-view=journey]', 'Records': '[data-testid=records-workspace]',
                 'Overview': '[data-testid=patient-card]', 'Review': '[data-testid=review-workspace]'}
    cd.wait('Boolean(document.querySelector(' + json.dumps(selectors[section]) + '))',
            section + ' workspace for follow-through')


def fill(cd, selector, value):
    cd.evaluate("(()=>{const e=document.querySelector(" + json.dumps(selector) + ");"
                "if(!e)throw Error('Missing task input');"
                "const p=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;"
                "Object.getOwnPropertyDescriptor(p,'value').set.call(e," + json.dumps(value) + ");"
                "e.dispatchEvent(new Event('input',{bubbles:true}));})()")


def click(cd, selector):
    # An earlier real request may still be settling after workspace navigation.
    # Use the harness's bounded wait, including disabled ancestor fieldsets.
    cd.wait('(()=>{const e=document.querySelector(' + json.dumps(selector)
            + ");return Boolean(e)&&!e.matches(':disabled');})()", 'enabled task control ' + selector)
    cd.evaluate('document.querySelector(' + json.dumps(selector) + ').click()')


def select_case(cd, case_id):
    expression = ("[...document.querySelectorAll('.world-cases li')].find(e=>"
                  "e.querySelector('code')?.textContent===" + json.dumps(case_id) + ")")
    cd.wait('(()=>{const e=' + expression
            + ";const button=e?.querySelector('[data-testid=world-load]');"
            + "return Boolean(button)&&!button.matches(':disabled');})()",
            'enabled authorized case ' + case_id)
    cd.evaluate(expression + ".querySelector('[data-testid=world-load]').click()")
    cd.wait("document.querySelector('[data-testid=world-projection] > p code')?.textContent==="
            + json.dumps(case_id), 'current case World Model')


def artifacts_directory():
    root = Path(__file__).resolve().parents[3]
    path = Path(os.environ.get('OI_WEB_ARTIFACT_DIR', root / 'apps/web/.evidence'))
    path.mkdir(parents=True, exist_ok=True)
    return path


def capture_failure(cd, name):
    """Bounded synthetic-only diagnostics; never serialize input values or headers."""
    try:
        path = artifacts_directory()
        image = cd.command('Page.captureScreenshot', {'format': 'png'})
        (path / (name + '.png')).write_bytes(base64.b64decode(image['data']))
        info = cd.evaluate("({text:document.querySelector('main')?.textContent.slice(0,16000),"
                           "writes:window.__oiFollowthroughChecks?.writes.map(x=>({path:x.path,status:x.status})),"
                           "reads:window.__oiFollowthroughChecks?.reads.map(x=>({path:x.path,status:x.status}))})")
        (path / (name + '.json')).write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    except Exception:
        print('Follow-through failure capture unavailable; original failure retained.')


class FollowthroughChecks:
    def __init__(self, cd, patient_id, case_id, question_id, source_id):
        self.cd, self.patient_id, self.case_id = cd, patient_id, case_id
        self.question_id, self.source_id = question_id, source_id
        self.task_ids = {}
        self.before_amendment = None
        self.first_write = None
        self.draft_checks = {}

    def row(self, task_id):
        return '[data-testid=followthrough-task][data-task-id="' + task_id + '"]'

    def wait_task(self, task_id, status, revision):
        selector = self.row(task_id)
        self.cd.wait('document.querySelector(' + json.dumps(selector) + ')?.dataset.status==='
                     + json.dumps(status) + ' && document.querySelector(' + json.dumps(selector)
                     + ')?.dataset.revision===' + json.dumps(str(revision)),
                     'real task ' + status + ' revision ' + str(revision))

    def projection(self):
        value = self.cd.evaluate('window.__oiFollowthroughChecks.reads.at(-1)')
        assert value['status'] == 200
        payload = value['payload']
        assert payload['contract'] == 'oi.pg-question-followthrough/1'
        assert (payload['patient_id'], payload['case_id']) == (self.patient_id, self.case_id)
        assert payload['synthetic'] is True
        assert payload['clinical_approval'] is False
        assert payload['external_notification_sent'] is False
        assert payload['evaluated_on'] == datetime.now(timezone.utc).date().isoformat()
        return payload

    def refresh(self, expected_count=3):
        previous = self.cd.evaluate('window.__oiFollowthroughChecks.reads.length')
        click(self.cd, '[data-testid=followthrough-refresh]')
        self.cd.wait('window.__oiFollowthroughChecks.reads.length===' + str(previous + 1)
                     + " && document.querySelector('[data-testid=followthrough-status]')?.dataset.phase==='ready'"
                     + " && document.querySelectorAll('[data-testid=followthrough-task]').length==="
                     + str(expected_count), 'fresh authorized task projection')
        return self.projection()

    def create(self, title, *, lose_delivery=False):
        selector = '.question-items li[data-question-id="' + self.question_id + '"] [data-testid=followthrough-open-create]'
        click(self.cd, selector)
        fields = {'title': title, 'detail': 'Collect the existing fictional source references.',
                  'owner': '', 'due-date': (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat(),
                  'trigger': 'When another source arrives', 'reason': 'Recorded for the fictional discussion.'}
        for name, value in fields.items():
            fill(self.cd, '[data-testid=followthrough-' + name + ']', value)
        before = self.cd.evaluate('window.__oiFollowthroughChecks.writes.length')
        if lose_delivery:
            self.cd.evaluate('window.__oiFollowthroughChecks.dropNextWrite=true')
        click(self.cd, '[data-testid=followthrough-create]')
        self.cd.wait('window.__oiFollowthroughChecks.writes.length===' + str(before + 1),
                     'actual create response observed')
        first = self.cd.evaluate('window.__oiFollowthroughChecks.writes.at(-1)')
        assert first['status'] == 201 and first['payload']['duplicate'] is False
        assert first['body']['synthetic'] is True
        assert first['body']['source_snapshot_contract'] == 'oi.pg-source-world-model/1'
        assert first['payload']['question_id'] == self.question_id
        if lose_delivery:
            self.cd.wait("document.querySelector('[data-testid=followthrough-write-status]')?.dataset.phase==='unknown'",
                         'committed response loss has explicit uncertain outcome')
            assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-receipt]')")
            assert self.cd.evaluate("document.querySelectorAll('[data-testid=followthrough-task]').length===0")
            assert title in self.cd.evaluate("document.querySelector('[data-testid=followthrough-recovery]').textContent")
            assert self.cd.evaluate("[...document.querySelectorAll('[data-testid=followthrough-title]')].every(e=>e.matches(':disabled'))")
            click(self.cd, '[data-testid=followthrough-retry]')
            self.cd.wait('window.__oiFollowthroughChecks.writes.length===' + str(before + 2),
                         'same write retried against actual server')
            replay = self.cd.evaluate('window.__oiFollowthroughChecks.writes.at(-1)')
            assert replay['body'] == first['body'] and replay['path'] == first['path']
            assert replay['status'] == 200
            assert replay['payload'] == {**first['payload'], 'duplicate': True}
            self.first_write = first
        task_id = first['payload']['task_id']
        self.wait_task(task_id, 'created', 1)
        visible_receipt = self.cd.evaluate("document.querySelector('[data-testid=followthrough-receipt]').textContent")
        assert task_id in visible_receipt and first['payload']['event_id'] in visible_receipt
        assert self.cd.evaluate("document.querySelector('[data-testid=followthrough-receipt]').dataset.duplicate") == str(lose_delivery).lower()
        rows = self.projection()['tasks']
        assert len([row for row in rows if row['task_id'] == task_id]) == 1
        assert next(row for row in rows if row['task_id'] == task_id)['history'][0]['event_id'] == first['payload']['event_id']
        self.task_ids[title] = task_id
        return task_id

    def transition(self, task_id, status, revision, owner=''):
        selector = self.row(task_id)
        fill(self.cd, selector + ' [data-testid=followthrough-transition-reason]',
             'Recorded fictional work status: ' + status + '.')
        if status == 'assigned':
            fill(self.cd, selector + ' [data-testid=followthrough-transition-owner]', owner)
        action = {'assigned': 'assign', 'acknowledged': 'acknowledge', 'completed': 'complete', 'deferred': 'defer'}[status]
        click(self.cd, selector + ' [data-testid=followthrough-' + action + ']')
        self.wait_task(task_id, status, revision)
        write = self.cd.evaluate('window.__oiFollowthroughChecks.writes.at(-1)')
        assert write['status'] == 201 and write['body']['synthetic'] is True
        assert write['body']['expected_revision'] == revision - 1
        assert write['payload']['revision'] == revision

    def start(self, credentials, write_grants):
        navigate(self.cd, 'Investigations')
        click(self.cd, '[data-testid=load-source-questions]')
        self.cd.wait("document.querySelector('[data-testid=source-question-history]')?.textContent.includes("
                     + json.dumps(self.question_id) + ")", 'existing saved question remains canonical')
        completed = self.create(TITLE_DONE, lose_delivery=True)
        assert self.cd.evaluate('!document.querySelector(' + json.dumps(self.row(completed)
                                + ' [data-testid=followthrough-complete]') + ')')
        # A saved transition belongs to the existing task. It must not consume
        # another, unsaved task draft attached to the same canonical question.
        question = '.question-items li[data-question-id="' + self.question_id + '"]'
        draft_title = 'Unsaved second fictional coordination task'
        draft_detail = 'Keep these authored notes while the existing fictional task changes status.'
        click(self.cd, question + ' [data-testid=followthrough-open-create]')
        fill(self.cd, question + ' [data-testid=followthrough-title]', draft_title)
        fill(self.cd, question + ' [data-testid=followthrough-detail]', draft_detail)
        before_transitions = self.cd.evaluate('window.__oiFollowthroughChecks.writes.length')

        # Leaving the question to inspect its source must not discard an unsent
        # coordination draft or silently record it. These are real UI inputs.
        draft_fields = {'title': draft_title, 'detail': draft_detail,
                        'owner': 'Fictional navigation coordinator',
                        'due-date': '2026-12-09',
                        'trigger': 'After inspecting the fictional original',
                        'reason': 'Keep the exact unsent coordination plan.'}
        for name, value in draft_fields.items():
            fill(self.cd, question + ' [data-testid=followthrough-' + name + ']', value)
        for section in ('Journey', 'Records', 'Overview', 'Review'):
            navigate(self.cd, section)
            navigate(self.cd, 'Investigations')
            self.cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))')
            for name, expected in draft_fields.items():
                actual = self.cd.evaluate('document.querySelector(' + json.dumps(
                    question + ' [data-testid=followthrough-' + name + ']') + ')?.value')
                assert actual == expected, 'Same-case navigation discarded unsent follow-up ' + name
            assert self.cd.evaluate('window.__oiFollowthroughChecks.writes.length') == before_transitions

        # Actually reload the original source index and the same World Model,
        # then obtain a fresh authorized question read before restoring inputs.
        navigate(self.cd, 'Records')
        self.cd.evaluate("[...document.querySelectorAll('[data-testid=load-sources]')].find(e=>"
                         "e.closest('li').textContent.includes(" + json.dumps(self.case_id) + ")).click()")
        self.cd.wait("Boolean(document.querySelector('[data-testid=source-index]'))", 'fresh source index')
        navigate(self.cd, 'Investigations')
        select_case(self.cd, self.case_id)
        click(self.cd, '[data-testid=load-source-questions]')
        self.cd.wait('Boolean(document.querySelector(' + json.dumps(question + ' [data-testid=followthrough-title]')
                     + '))', 'same-source unsent task restored after fresh reads')
        for name, expected in draft_fields.items():
            assert self.cd.evaluate('document.querySelector(' + json.dumps(
                question + ' [data-testid=followthrough-' + name + ']') + ').value') == expected
        assert self.cd.evaluate('window.__oiFollowthroughChecks.writes.length') == before_transitions

        # Separate task access denial clears the retained form; permission
        # restoration must not bring the discarded input back.
        credentials[0]['actions'].remove('followthrough_read')
        write_grants()
        click(self.cd, '[data-testid=followthrough-refresh]')
        self.cd.wait("document.querySelector('[data-testid=followthrough-status]')?.dataset.phase==='error'",
                     'fresh denied task read clears unsent fields')
        assert self.cd.evaluate('!document.querySelector(' + json.dumps(question + ' [data-testid=followthrough-title]') + ')')
        credentials[0]['actions'].append('followthrough_read')
        write_grants()
        self.refresh(expected_count=1)
        click(self.cd, question + ' [data-testid=followthrough-open-create]')
        assert self.cd.evaluate('document.querySelector(' + json.dumps(question + ' [data-testid=followthrough-title]') + ').value') == ''
        for name, value in draft_fields.items():
            fill(self.cd, question + ' [data-testid=followthrough-' + name + ']', value)
        self.draft_checks = {'same_case_navigation': True, 'fresh_source_question_reads': True,
                             'denied_read_cleared_draft': True, 'navigation_writes': 0}
        self.cd.evaluate('document.querySelector(' + json.dumps(question + ' [data-testid=followthrough-create-form]')
                         + ").scrollIntoView({block:'center'})")
        image = self.cd.command('Page.captureScreenshot', {'format': 'png'})
        (artifacts_directory() / 'h1-followthrough-unsent-draft.png').write_bytes(base64.b64decode(image['data']))

        def assert_creation_draft_survives(status):
            # Let committed receipt rendering and its React effects settle;
            # an eventually closed form must not accidentally pass this check.
            self.cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))')
            form = question + ' [data-testid=followthrough-create-form]'
            assert self.cd.evaluate('Boolean(document.querySelector(' + json.dumps(form) + '))'), (
                'Successful existing-task ' + status + ' discarded the unsaved second-task creation form')
            for name, expected in (('title', draft_title), ('detail', draft_detail)):
                selector = question + ' [data-testid=followthrough-' + name + ']'
                assert self.cd.evaluate('document.querySelector(' + json.dumps(selector) + ').value') == expected, (
                    'Successful existing-task ' + status + ' changed the unsaved creation ' + name)

        self.transition(completed, 'assigned', 2, 'Fictional coordinator')
        assert_creation_draft_survives('assignment')
        assert self.cd.evaluate('!document.querySelector(' + json.dumps(self.row(completed)
                                + ' [data-testid=followthrough-complete]') + ')')
        self.transition(completed, 'acknowledged', 3)
        assert_creation_draft_survives('acknowledgment')
        click(self.cd, question + ' [data-testid=followthrough-cancel]')
        self.cd.wait('!document.querySelector(' + json.dumps(question + ' [data-testid=followthrough-create-form]')
                     + ')', 'explicit cancellation clears only the unsaved second-task draft')
        assert self.cd.evaluate('window.__oiFollowthroughChecks.writes.length') == before_transitions + 2
        assert len(self.projection()['tasks']) == 1, 'An unsaved draft must not create a task'
        self.transition(completed, 'completed', 4)
        self.create(TITLE_OPEN)
        deferred = self.create(TITLE_DEFERRED)
        self.transition(deferred, 'deferred', 2)
        self.transition(deferred, 'assigned', 3, 'Fictional later coordinator')
        self.transition(deferred, 'deferred', 4)
        self.before_amendment = {row['task_id']: row for row in self.projection()['tasks']}
        assert len(self.before_amendment) == 3
        for row in self.before_amendment.values():
            assert (row['question_id'], row['source_id'], row['source_line'], row['source_version']) == (
                self.question_id, self.source_id, 8, 1)
            assert row['source_context_state'] == 'current_unreviewed_question'
            assert row['needs_recheck'] is False and row['clinical_approval'] is False
            assert all(event['actor_label'] == 'ACTOR-0' for event in row['history'])
            selector = self.row(row['task_id']) + ' [data-testid=followthrough-history]'
            assert self.cd.evaluate('document.querySelector(' + json.dumps(selector) + ').children.length') == row['revision']
            history = self.cd.evaluate('document.querySelector(' + json.dumps(selector) + ').textContent')
            assert all(event['event_id'] in history and event['reason'] in history for event in row['history'])
        assert self.before_amendment[self.task_ids[TITLE_OPEN]]['is_overdue'] is True
        click(self.cd, question + ' [data-testid=followthrough-open-create]')
        fill(self.cd, question + ' [data-testid=followthrough-title]', 'Draft bound to the original fictional source')

    def after_amendment(self, replacement_source_id):
        navigate(self.cd, 'Investigations')
        select_case(self.cd, self.case_id)
        self.assert_amendment(replacement_source_id)
        navigate(self.cd, 'Records')

    def assert_amendment(self, replacement_source_id):
        value = self.refresh()
        assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-create-form]')"), 'Amendment must clear source-bound unsent task fields'
        for row in value['tasks']:
            before = self.before_amendment[row['task_id']]
            for field in ('source_id', 'source_line', 'source_sha256', 'source_version', 'question_id',
                          'source_snapshot_contract', 'source_snapshot_sha256', 'preflight_sha256',
                          'title', 'detail', 'owner_label', 'due_date', 'review_trigger', 'status', 'revision', 'history'):
                assert row[field] == before[field], field
            assert row['source_id'] != replacement_source_id
            assert row['source_context_state'] == 'source_reassessment_required'
            assert row['needs_recheck'] is (row['status'] == 'created')
            selector = self.row(row['task_id'])
            text = self.cd.evaluate('document.querySelector(' + json.dumps(selector) + ').textContent')
            assert self.source_id in text and self.question_id in text
            assert row['source_sha256'] in text
            assert row['needs_recheck'] == self.cd.evaluate('Boolean(document.querySelector('
                + json.dumps(selector + ' [data-testid=followthrough-recheck]') + '))')
        return value

    def assert_attention_filters(self):
        """Filter actual authorized tasks without writes, reads or discarded form state."""
        self.cd.wait("Boolean(document.querySelector('[data-testid=followthrough-attention]'))",
                     'source-bound work attention filters')
        counts = {'all': 3, 'recheck': 1, 'overdue': 1, 'unassigned': 1, 'history': 2}
        for key, count in counts.items():
            selector = '[data-testid=followthrough-filter-' + key + ']'
            assert self.cd.evaluate('document.querySelector(' + json.dumps(selector) + ').dataset.count') == str(count)
        current = self.task_ids[TITLE_OPEN]
        reason = 'Keep this fictional transition note while filtering recorded work.'
        owner = 'Fictional proposed owner'
        fill(self.cd, self.row(current) + ' [data-testid=followthrough-transition-reason]', reason)
        fill(self.cd, self.row(current) + ' [data-testid=followthrough-transition-owner]', owner)
        calls = self.cd.evaluate('({reads:window.__oiFollowthroughChecks.reads.length,writes:window.__oiFollowthroughChecks.writes.length})')
        for key, expected in (
                ('recheck', [current]), ('overdue', [current]), ('unassigned', [current]),
                ('history', [self.task_ids[TITLE_DONE], self.task_ids[TITLE_DEFERRED]]),
                ('all', list(self.task_ids.values()))):
            selector = '[data-testid=followthrough-filter-' + key + ']'
            click(self.cd, selector)
            self.cd.wait('document.querySelector(' + json.dumps(selector) + ").getAttribute('aria-pressed')==='true'",
                         'selected operational filter ' + key)
            visible = self.cd.evaluate("[...document.querySelectorAll('[data-testid=followthrough-task]')].filter(e=>e.getClientRects().length>0).map(e=>e.dataset.taskId)")
            assert sorted(visible) == sorted(expected), (key, visible, expected)
            # Even a hidden task remains mounted with the exact authored draft.
            for name, value in (('reason', reason), ('owner', owner)):
                control = self.row(current) + ' [data-testid=followthrough-transition-' + name + ']'
                assert self.cd.evaluate('document.querySelector(' + json.dumps(control) + ').value') == value
            assert self.cd.evaluate('({reads:window.__oiFollowthroughChecks.reads.length,writes:window.__oiFollowthroughChecks.writes.length})') == calls
        # A real response with a new receipt resets the filter; it is not an effect-time stale frame.
        click(self.cd, '[data-testid=followthrough-filter-history]')
        self.refresh()
        assert self.cd.evaluate("document.querySelector('[data-testid=followthrough-filter-all]').getAttribute('aria-pressed')") == 'true'
        assert self.cd.evaluate("[...document.querySelectorAll('[data-testid=followthrough-task]')].filter(e=>e.getClientRects().length>0).length") == 3
        # Keyboard activation uses an actual input event rather than calling click().
        self.cd.evaluate("document.querySelector('[data-testid=followthrough-filter-recheck]').focus()")
        self.cd.command('Input.dispatchKeyEvent', {'type': 'rawKeyDown', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
        self.cd.command('Input.dispatchKeyEvent', {'type': 'char', 'text': '\r', 'unmodifiedText': '\r', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
        self.cd.command('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13})
        self.cd.wait("document.querySelector('[data-testid=followthrough-filter-recheck]').getAttribute('aria-pressed')==='true'",
                     'keyboard-select source-changed work')
        assert self.cd.evaluate("document.activeElement.dataset.testid") == 'followthrough-filter-recheck'
        print('PASS FOLLOWTHROUGH ATTENTION: actual source-amended task flags; overlapping counts; exact historical rows; no filter HTTP calls; preserved transition drafts; new-receipt reset; keyboard activation.')

    def assert_timestamp_rejection(self):
        """A corrupted copy of a real read cannot retain actionable task history."""
        original_tasks = self.projection()['tasks']
        writes = self.cd.evaluate('window.__oiFollowthroughChecks.writes.length')
        for field, value in (('created_at', '2026-02-30T10:00:00Z'),
                             ('recorded_at', '2026-11-03T24:00:00Z'),
                             ('recorded_at', '2026-11-03T10:00:00.1234567Z')):
            self.cd.evaluate('window.__oiFollowthroughChecks.corruptNextTimestamp='
                             + json.dumps({'field': field, 'value': value}))
            click(self.cd, '[data-testid=followthrough-refresh]')
            self.cd.wait("document.querySelector('[data-testid=followthrough-status]')?.dataset.phase==='error'",
                         'invalid timestamp removes actionable task history')
            assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-task]')")
            assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-attention]')")
            assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-history]')")
            assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-transition-reason]')")
            assert self.cd.evaluate('window.__oiFollowthroughChecks.writes.length') == writes
            assert self.projection()['tasks'] == original_tasks
            restored = self.refresh()
            assert restored['tasks'] == original_tasks
            for task in original_tasks:
                self.wait_task(task['task_id'], task['status'], task['revision'])
                selector = self.row(task['task_id'])
                displayed = self.cd.evaluate("[...document.querySelector(" + json.dumps(selector)
                    + ").querySelectorAll('[data-testid=followthrough-history] time')].map(e=>"
                      "({dateTime:e.getAttribute('datetime'),text:e.textContent}))")
                assert displayed == [{'dateTime': event['recorded_at'], 'text': event['recorded_at']}
                                     for event in task['history']]
                text = self.cd.evaluate('document.querySelector(' + json.dumps(selector) + ').textContent')
                assert all(task[field] in text for field in ('source_id', 'source_sha256', 'question_id'))
            assert self.cd.evaluate('window.__oiFollowthroughChecks.writes.length') == writes
        print('PASS FOLLOWTHROUGH TIMESTAMPS: three explicitly corrupted copies of real authorized reads '
              'withhold task history, counts and transition controls; fresh valid reads restore exact '
              'original tasks and timestamps without writes or grant changes.')

    def finish(self, replacement_source_id, credentials, write_grants, screenshots):
        navigate(self.cd, 'Investigations')
        value = self.assert_amendment(replacement_source_id)
        self.assert_attention_filters()
        self.assert_timestamp_rejection()
        # A failed fresh read must remove old task text and transition controls.
        credentials[0]['actions'].remove('followthrough_read')
        write_grants()
        click(self.cd, '[data-testid=followthrough-refresh]')
        self.cd.wait("document.querySelector('[data-testid=followthrough-status]')?.textContent.includes('unavailable')",
                     'independent task-read denial clears prior view')
        assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-task]')")
        assert self.cd.evaluate("!document.querySelector('[data-testid=followthrough-attention]')")
        credentials[0]['actions'].append('followthrough_read')
        write_grants()
        self.refresh()
        click(self.cd, '[data-testid=followthrough-filter-recheck]')
        screenshots.mkdir(parents=True, exist_ok=True)
        for width, height, suffix in ((1440, 1100, 'desktop'), (390, 844, 'mobile')):
            self.cd.command('Emulation.setDeviceMetricsOverride', {
                'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': False})
            self.cd.wait('window.innerWidth===' + str(width), 'task viewport')
            assert self.cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
            self.cd.evaluate('document.querySelector(' + json.dumps(self.row(self.task_ids[TITLE_OPEN]))
                             + ").scrollIntoView({block:'center'})")
            image = self.cd.command('Page.captureScreenshot', {'format': 'png'})
            (screenshots / ('h1-followthrough-' + suffix + '.png')).write_bytes(base64.b64decode(image['data']))
            self.cd.evaluate("document.querySelector('[data-testid=followthrough-attention]').scrollIntoView({block:'start'})")
            image = self.cd.command('Page.captureScreenshot', {'format': 'png'})
            (screenshots / ('h1-followthrough-attention-' + suffix + '.png')).write_bytes(base64.b64decode(image['data']))
        self.cd.command('Emulation.setDeviceMetricsOverride', {
            'width': 1440, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': False})
        (screenshots / 'h1-followthrough-receipts.json').write_text(json.dumps({
            'patient_id': self.patient_id, 'case_id': self.case_id, 'question_id': self.question_id,
            'first_create_receipt': self.first_write['payload'],
            'unsent_draft_checks': self.draft_checks,
            'timestamp_fault_injection': self.cd.evaluate('window.__oiFollowthroughChecks.timestampFaults'),
            'task_summary': [{'task_id': row['task_id'], 'status': row['status'], 'revision': row['revision'],
                              'source_id': row['source_id'], 'needs_recheck': row['needs_recheck'],
                              'history_events': [event['event_id'] for event in row['history']]} for row in value['tasks']],
            'synthetic': True, 'clinical_approval': False,
        }, indent=2) + '\n', encoding='utf-8')
        navigate(self.cd, 'Journey')
        print('PASS FOLLOWTHROUGH DRAFTS: six literal fields survive four same-case workspace round trips '
              'and fresh source/question reads without writes; denied access clears retained input; '
              'existing-task transitions preserve it; explicit clear and source amendment remove it.')
        print('PASS FOLLOWTHROUGH: actual saved question to PostgreSQL tasks; lost committed response '
              'recovered with the exact request and one receipt; assignment, acknowledgment, completion, '
              'deferral and reassignment history; a second-task draft survives existing-task assignment '
              'and acknowledgment until explicit cancellation; source amendment flags only open work and retains '
              'original source/hash/history; independent read denial clears content; desktop/mobile capture.')


@contextmanager
def exercise(cd, patient_id, case_id, question_id, source_id, credentials, write_grants):
    previous = list(credentials[0]['actions'])
    try:
        credentials[0]['actions'] = sorted(set(previous) | READ_ACTIONS | WRITE_ACTIONS)
        write_grants()
        cd.evaluate('(' + _OBSERVE + ')()')
        checks = FollowthroughChecks(cd, patient_id, case_id, question_id, source_id)
        checks.start(credentials, write_grants)
        yield checks
    except Exception:
        capture_failure(cd, 'h1-followthrough-failure')
        raise
    finally:
        try:
            cd.evaluate('window.__oiFollowthroughChecks?.restore()')
        finally:
            credentials[0]['actions'] = previous
            write_grants()


def exercise_case_switch(cd, patient_id, case_id, second_case_id, credentials, write_grants, screenshots,
                         *, current_question_id):
    """Run after existing record-intake checks have created the second case."""
    previous = list(credentials[0]['actions'])
    try:
        credentials[0]['actions'] = sorted(set(previous) | READ_ACTIONS)
        write_grants()
        cd.evaluate('(' + _OBSERVE + ')()')
        navigate(cd, 'Investigations')
        click(cd, '[data-testid=world-load-cases]')
        select_case(cd, case_id)
        checks = FollowthroughChecks(cd, patient_id, case_id, '', '')
        value = checks.refresh()
        assert {row['title'] for row in value['tasks']} == {TITLE_DONE, TITLE_OPEN, TITLE_DEFERRED}
        # An actual unsaved current-question draft must also disappear on switch.
        click(cd, '[data-testid=load-source-questions]')
        # Several saved questions share v2. Use the exact question returned by
        # the connected upstream journey, never whichever row sorts first.
        current = ('.question-items li[data-question-id="' + current_question_id
                   + '"] [data-testid=followthrough-open-create]:not(:disabled)')
        cd.wait('Boolean(document.querySelector(' + json.dumps(current) + '))', 'current second-version question')
        click(cd, current)
        draft_title = 'Unsaved fictional Alpha coordination draft'
        fill(cd, '[data-testid=followthrough-title]', draft_title)
        cd.evaluate('window.__oiFollowthroughChecks.holdNextRead=true')
        click(cd, '[data-testid=followthrough-refresh]')
        cd.wait('window.__oiFollowthroughChecks.held', 'real first-case read held before client delivery')
        select_case(cd, second_case_id)
        assert cd.evaluate("!document.querySelector('[data-testid=followthrough-task]')")
        assert cd.evaluate("!document.querySelector('[data-testid=followthrough-receipt]')")
        cd.evaluate('window.__oiFollowthroughChecks.release()')
        cd.wait('window.__oiFollowthroughChecks.released===1', 'delayed first-case response released')
        cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))')
        assert cd.evaluate("!document.querySelector('[data-testid=followthrough-task]')")
        checks.case_id = second_case_id
        empty = checks.refresh(expected_count=0)
        assert empty['tasks'] == []
        panel = cd.evaluate("document.querySelector('[data-testid=followthrough-panel]').textContent")
        for row in value['tasks']:
            assert row['task_id'] not in panel and row['title'] not in panel
        assert draft_title not in panel
        assert cd.evaluate("!document.querySelector('[data-testid=followthrough-title]') && "
                           "!document.querySelector('[data-testid=followthrough-retry]')")
        assert cd.evaluate('window.__oiFollowthroughChecks.writes.length===0')
        select_case(cd, case_id)
        click(cd, '[data-testid=load-source-questions]')
        cd.wait('Boolean(document.querySelector(' + json.dumps(current) + '))', 'original question reloaded after case round trip')
        assert cd.evaluate("!document.querySelector('[data-testid=followthrough-title]')"), 'Case round trip must not resurrect an unsent task'
        click(cd, current)
        assert cd.evaluate("document.querySelector('[data-testid=followthrough-title]').value") == ''
        click(cd, '[data-testid=followthrough-cancel]')
        assert cd.evaluate('localStorage.length===0 && sessionStorage.length===0')
        (screenshots / 'h1-followthrough-case-switch.json').write_text(json.dumps({
            'patient_id': patient_id, 'first_case_id': case_id, 'second_case_id': second_case_id,
            'unsaved_draft_question_id': current_question_id,
            'case_roundtrip_draft_cleared': True, 'browser_storage_empty': True,
            'delayed_real_read_discarded': True, 'second_case_tasks': empty['tasks'],
        }, indent=2) + '\n', encoding='utf-8')
        navigate(cd, 'Overview')
        print('PASS FOLLOWTHROUGH CASE SWITCH: actual second-case selection clears prior task content, '
              'receipts and drafts; a delayed authorized first-case response cannot restore them; '
              'second-case API list remains empty; no extra case or source fixture introduced.')
    except Exception:
        capture_failure(cd, 'h1-followthrough-case-switch-failure')
        raise
    finally:
        try:
            cd.evaluate('window.__oiFollowthroughChecks?.restore()')
        finally:
            credentials[0]['actions'] = previous
            write_grants()
