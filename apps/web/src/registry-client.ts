import {PermissionConsole,PermissionHttpError} from './patient-permissions.js';
import {createEncounterChart, EncounterHttpError, type EncounterChart} from './encounter-client.js';
import {readLaboratoryCitationReport} from './laboratory-citation-report.js';
import {emptySuspension,readSuspensionReceipt,type SuspensionState} from './patient-suspension.js';
/** Transient UI state over the canonical patient API; never an authority or ledger. */
export {patientContinuity} from './patient-continuity.js';
import {parseCaseBindingList, parseSourceIndex, parseSourceHistory, receiptMicros} from './source-contracts.js';
import {decodeQuestionSourcePacket} from './source-quote-review-packet.js';
import type {QuestionSourceReviewPacket} from './source-quote-review-packet.js';
import type {CaseBinding, SourceIndex} from './source-contracts.js';
import {prepareSource,parseImportReceipt,verifyOriginal} from './source-intake.js';
import type {ImportReceipt,OriginalSource} from './source-intake.js';
import {emptyLaboratory,prepareLaboratoryFile,parseLaboratoryReceipt} from './laboratory-fhir.js';
import {LABORATORY_PREVIEW_REJECTED,LaboratoryPreviewRejected,readLaboratoryPreview} from './laboratory-preview.js';
import type {LaboratoryFile,LaboratoryImportState,LaboratoryIntent} from './laboratory-fhir.js';
import {readLabPreparation,validLabQuestion,emptyLabQuestions,readLabQuestionList} from './laboratory-question.js';
import type {LabPreparation,LabQuestionView} from './laboratory-question.js';
import {parseSourceWorldModel,parseSourceHistory} from './source-world-model.js';
import type {SourceWorldModel,SourceHistory} from './source-world-model.js';
import {decodeComposerPreflight,DEFAULT_SOURCE_QUESTION} from './composer-preflight-view.js';
import type {ComposerPreflight} from './composer-preflight-view.js';
import {decodeSavedQuestion,decodeSourceQuestions,questionSaveBlocksSourceChange} from './source-questions-view.js';
import type {SavedQuestion,SourceQuestion} from './source-questions-view.js';
import {decodeReviewQueue,decodeReviewReturnResult,decodeEvidenceRunReturn,openedReviewArtifacts,validReturnReason,FICTIONAL_RETURN_REASON,type ReviewArtifacts} from './review-queue-view.js';
import type {ReviewQueue,ReviewReturnResult} from './review-queue-view.js';
import {canPrepareSourceBrief,decodeSourceBrief} from './source-brief.js';
import type {SourceBrief} from './source-brief.js';
import {canRetryRun, readRunReceipt, readRunResult, readRunStatus} from './background-brief.js';
import type {BackgroundBrief, RunAction} from './background-brief.js';
import {projectFollowthroughAttention,currentFollowthroughQuestion,followthroughLaboratoryAnchor,matchesFollowthroughDraft,FOLLOWTHROUGH_V2_MEDIA,decodeFollowthrough,decodeFollowthroughReceipt,
  validFollowthroughDraft,validFollowthroughTransition,followthroughTransitionContext,FOLLOWTHROUGH_TRANSITIONS} from './followthrough-view.js';
import type {FollowthroughTask,FollowthroughFamily,FollowthroughDraft,FollowthroughUnsentDraft,FollowthroughIntent,FollowthroughList,
  FollowthroughReceipt,FollowthroughTransition,FollowthroughTransitionFields,FollowthroughUnsentTransition} from './followthrough-view.js';
import {decodeQuestionEvidenceSearch,decodeQuestionEvidenceLinks,decodeQuestionEvidenceReceipt,
  laboratoryEvidenceAnchor,matchesLaboratoryEvidenceAnchor,unwrapLaboratoryEvidence,validEvidenceQuery} from './question-evidence-view.js';
import type {QuestionEvidenceSearch,QuestionEvidenceLinks,QuestionEvidenceIntent,
  QuestionEvidenceReceipt} from './question-evidence-view.js';
import {QuestionEvidenceSession,emptyEvidenceState} from './authored-evidence-session.js';
import {decodeSourceImages,readSourceImageOriginal,readSourceImagePreview,emptySourceImages} from './source-images.js';
import type {SourceImagesState} from './source-images.js';
import type {EvidenceState,EvidenceDraftPatch} from './authored-evidence-session.js';
import type {ContentItem,Permissions,Relation,Applicability} from './authored-evidence.js';
export type Patient = Readonly<{
  patient_id: string; origin_org: string; created_at: string;
  status: 'active' | 'suspended'; revision: number;
}>;
export type CreatedPatient = Readonly<{patient_id: string; duplicate: boolean}>;
export type ReviewReturnIntent=Readonly<{
  patient_id:string;case_id:string;question_id:string;queue_fingerprint:string;reason:string;artifacts?:ReviewArtifacts;
}>;
export type QuestionDraft = Readonly<{case_id:string;source_id:string;source_line:number;
  snapshot_fingerprint:string;question:string}>;
function questionCommand(prepared:ComposerPreflight){
  return {question:prepared.question,source_id:prepared.selected_source.source_id,
    source_line:prepared.selected_source.line,expected_source_snapshot_sha256:prepared.source_snapshot_sha256,
    expected_preflight_sha256:prepared.preflight_sha256};
}
export type ViewState = Readonly<EvidenceState & SourceImagesState & LaboratoryImportState & LabQuestionView & SuspensionState & {
  manualPassageDraftQuestionIds:readonly string[];
  connected: boolean; phase: 'disconnected' | 'idle' | 'reading' | 'creating' | 'ready' | 'error';
  patient: Patient | null; created: CreatedPatient | null; message: string;
  cases: ReadonlyArray<CaseBinding> | null; sourceIndex: SourceIndex | null;
  recordsPhase: 'idle' | 'loading-cases' | 'loading-sources' | 'loading-original' | 'ready' | 'error';
  original:OriginalSource|null; importReceipt:ImportReceipt|null;
  importOutcome:'idle'|'sending'|'confirmed'|'rejected'|'unknown'; importMessage:string;
  recordMessage: string;
  sourceHistory:SourceHistory|null;historyPhase:'idle'|'loading'|'ready'|'error';historyMessage:string;
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
  backgroundBrief:BackgroundBrief|null;
  sourceBrief:SourceBrief|null;briefPhase:'idle'|'loading'|'ready'|'error';briefMessage:string;
  followthrough:FollowthroughList|null;followthroughCaseId:string|null;
  followthroughDrafts:Readonly<Record<string,FollowthroughUnsentDraft>>;
  followthroughTransitionDrafts:Readonly<Record<string,FollowthroughUnsentTransition>>;
  followthroughPhase:'idle'|'loading'|'ready'|'error';followthroughMessage:string;
  followthroughReceipt:FollowthroughReceipt|null;followthroughIntent:FollowthroughIntent|null;
  followthroughWritePhase:'idle'|'saving'|'saved'|'unknown'|'error';followthroughWriteMessage:string;
  sourceQuotePacket:QuestionSourceReviewPacket|null;
  sourceQuotePhase:'idle'|'loading'|'ready'|'error';sourceQuoteMessage:string;
  evidenceQuestionId:string|null;evidenceGeneration:number;evidenceFamily:'text'|'laboratory'|null;
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
const emptyHistory=()=>({sourceHistory:null,historyPhase:'idle' as const,historyMessage:''});
const emptyWorld=()=>({...emptyHistory(),worldModel:null,worldPhase:'idle' as const,worldMessage:'Choose an authorized active fictional case to inspect its source-derived World Model.'});
const emptyReview=()=>({reviewQueue:null,reviewPhase:'idle' as const,
  reviewMessage:'Open the current patient case to inspect saved questions and verification returns.',
  reviewReturn:null,reviewReturnPhase:'idle' as const,reviewReturnIntent:null,
  reviewReturnMessage:'No return action is in progress.'});
const emptyBrief=()=>({backgroundBrief:null,sourceBrief:null,briefPhase:'idle' as const,
  briefMessage:'Prepare a source-linked brief from a current saved question. Each download checks permission again.'});
const emptyFollowthrough=()=>({followthrough:null,followthroughCaseId:null,followthroughPhase:'idle' as const,
  followthroughDrafts:Object.freeze({}) as Readonly<Record<string,FollowthroughUnsentDraft>>,
  followthroughTransitionDrafts:Object.freeze({}) as Readonly<Record<string,FollowthroughUnsentTransition>>,
  followthroughMessage:'Choose an authorized case to inspect work recorded for its saved questions.',
  followthroughReceipt:null,followthroughIntent:null,followthroughWritePhase:'idle' as const,
  followthroughWriteMessage:'No follow-up action is in progress.'});
const emptyEvidenceMetadata=()=>({evidenceSearch:null,evidenceSearchPhase:'idle' as const,
  evidenceSearchMessage:'Enter your own terms to search the original fictional catalog.',
  evidenceLinks:null,evidenceLinksPhase:'idle' as const,
  evidenceLinksMessage:'Refresh saved citations to check their current availability.'});
const emptyEvidence=()=>({...emptyEvidenceMetadata(),evidenceQuestionId:null,evidenceFamily:null,evidenceLinkIntent:null,evidenceLinkReceipt:null,
  evidenceLinkPhase:'idle' as const,evidenceLinkMessage:'No citation link is being saved.'});
const emptyInvestigation=()=>({questionDraft:null,composerPreview:null,composerPhase:'idle' as const,
  composerMessage:'Select an exact current source observation to prepare a non-executing context.',
  savedQuestion:null,questionSavePhase:'idle' as const,
  questionSaveMessage:'Save a verified preflight to create one unreviewed source-linked question.',
  questions:null,questionsAccessReceiptId:null,questionsCaseId:null,questionListPhase:'idle' as const,
  questionListMessage:'Open an authorized case to inspect saved source questions.',
  ...emptyEvidenceState(),...emptyBrief(),sourceQuotePacket:null,sourceQuotePhase:'idle' as const,
  sourceQuoteMessage:'Select a saved question to inspect its source quotation and evidence gaps.'});
const unconfirmedLabQuestion = {labQuestionWritePhase:'unknown',labQuestionWriteMessage:
  'The earlier save is unconfirmed. Retry its unchanged request after reopening this case.'} as const;

const fresh = (): ViewState => Object.freeze({evidenceGeneration:0,...emptySuspension(),...emptyLabQuestions(),manualPassageDraftQuestionIds:Object.freeze([]),connected:false,phase:'disconnected',patient:null,created:null,message:'Connect a local synthetic credential to use the patient registry.',cases:null,sourceIndex:null,recordsPhase:'idle',recordMessage:'Open an authorized fictional patient in Overview first.',...emptyIntake(),...emptyLaboratory(),...emptyWorld(),...emptyInvestigation(),...emptyReview(),...emptyFollowthrough(),...emptyEvidence(),...emptySourceImages()});
const emptyRecords=()=>({...emptyIntake(),...emptyLaboratory(),...emptyWorld(),...emptySourceImages(),cases:null,sourceIndex:null,recordsPhase:'idle' as const,recordMessage:'Load the current authorized case mappings to inspect original source metadata.'});
function exact(value: unknown, fields: string[]): value is Record<string,unknown> {
  return value !== null && typeof value==='object' && !Array.isArray(value) &&
    Object.keys(value).length===fields.length && fields.every(k=>Object.hasOwn(value,k));
}
function boundedKey(value: unknown): value is string { return typeof value==='string' && KEY.test(value); }
async function json(response: Response, limit=65536, alternateMediaType?:string): Promise<unknown> {
  const type=response.headers.get('Content-Type')??'';
  if(!/^application\/json(?:\s*;|$)/i.test(type)&&
     (!alternateMediaType||type.split(';',1)[0].trim().toLowerCase()!==alternateMediaType))throw Error('contract');
  return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(await boundedBytes(response,limit)));
}
async function boundedBytes(response:Response,limit:number):Promise<Uint8Array>{
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
  return all;
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
  // Exact reference-only commands survive a transient panel or evidence refresh.
  // Scope checks withhold recovery controls from another patient/case/question;
  // explicit disconnect clears this in-memory session just like other drafts.
  #manualPassageIntents=new Map<string,string>();
  #manualPassageDrafts=new Map<string,import('./question-passages').ManualSelectionDraft>();
  #manualDraftEpoch=0;
  #manualDraftCase:string|null=null;
  #clearManualDrafts(preserveCase?:string){
    // Invalidate old panel callbacks on every reset. Same-case refresh may keep
    // references, but never quotations or permission to display them.
    this.#manualDraftEpoch++;
    if(!preserveCase||this.#manualDraftCase!==preserveCase){this.#manualPassageDrafts.clear();this.#manualDraftCase=null;}
  }
  manualPassageDraftStore=(scope:import('./question-passages').PassageScope):import('./question-passages').ManualDraftStore=>{
    const key=JSON.stringify([scope.patient_id,scope.case_id,scope.question_id]),epoch=this.#manualDraftEpoch,session=this.#scope;
    const current=()=>epoch===this.#manualDraftEpoch&&session===this.#scope&&this.#state.connected&&
      this.#state.patient?.patient_id===scope.patient_id&&this.#state.questionsCaseId===scope.case_id&&this.#state.questionListPhase==='ready'&&
      Boolean(this.#state.questions?.some(q=>q.question_id===scope.question_id&&q.case_id===scope.case_id&&q.patient_id===scope.patient_id));
    return {read:()=>current()?this.#manualPassageDrafts.get(key)??null:null,
      write:draft=>{if(!current())return;if(draft===null)this.#manualPassageDrafts.delete(key);else{this.#manualDraftCase=scope.case_id;this.#manualPassageDrafts.set(key,draft);}this.#publish({});}};
  };
  manualPassageIntentStore=(scope:import('./question-passages').PassageScope):import('./question-passages').ManualIntentStore=>{
    const key=JSON.stringify([scope.patient_id,scope.case_id,scope.question_id]);
    const current=()=>this.#state.patient?.patient_id===scope.patient_id&&this.#state.questionsCaseId===scope.case_id&&
      Boolean(this.#state.questions?.some(q=>q.question_id===scope.question_id&&q.case_id===scope.case_id&&q.patient_id===scope.patient_id));
    return {read:()=>current()?this.#manualPassageIntents.get(key)??null:null,
      write:body=>{if(body===null)this.#manualPassageIntents.delete(key);else if(current())this.#manualPassageIntents.set(key,body);}};
  };
  /** A report is a fresh protected read, not retained in the session or browser storage. */
  async readLaboratoryCitationReport(questionId:string,signal:AbortSignal){
    if(signal.aborted||this.#savingEvidence||this.#state.evidenceLinkPhase==='unknown')throw Error('Finish the citation save first');
    this.#focusSavedQuestion(questionId);
    this.dismissEvidenceMetadata();
    const generation=this.#evidenceRead,scope=this.#scope,patient=this.#state.patient?.patient_id;
    const model=this.#state.worldModel,subject=this.#catalogSubject(questionId,'laboratory');
    if(!patient||!model||!subject?.laboratory||!this.#token)throw Error('Reopen authorized saved questions');
    const question=subject.laboratory;
    const control=new AbortController();this.#controllers.add(control);
    const stop=()=>control.abort();signal.addEventListener('abort',stop,{once:true});
    const timeout=setTimeout(stop,10000);
    const current=()=>generation===this.#evidenceRead&&scope===this.#scope&&this.#state.worldModel===model&&
      this.#state.patient?.patient_id===patient&&this.#inspectionQuestionId===questionId&&
      this.#catalogSubject(questionId,'laboratory')?.row===question&&!signal.aborted;
    try{
      const res=await this.transport(this.#catalogPath(patient,model.case_id,questionId,true)+'/source-citation-report',this.#init(control));
      if(!current()){void res.body?.cancel().catch(()=>{});throw Error('Report scope changed');}
      if(res.status!==200){
        if(res.status===401)this.#httpError(401);
        else if(res.status===403||res.status===404)this.#denyLaboratoryQuestionAccess('evidence');
        void res.body?.cancel().catch(()=>{});
        throw Error('Report unavailable');
      }
      if(control.signal.aborted)throw Error('Report timed out');
      const report=readLaboratoryCitationReport(await json(res,512000),model,question);
      if(!current()||control.signal.aborted)throw Error('Report scope changed');
      return {report,generation};
    }finally{signal.removeEventListener('abort',stop);clearTimeout(timeout);this.#controllers.delete(control);}
  }
  #permissions:PermissionConsole|null=null;
  currentPermissions=()=>this.#permissions?.scope.active()?this.#permissions:null;
  permissionChangePending=()=>Boolean(this.currentPermissions()?.pending||this.currentPermissions()?.busy);
  #hasPendingPatientWrite(patientId:string|undefined){
    return this.#creating||this.#uploading||this.#savingQuestion||this.#savingReview||
       this.#savingFollowthrough||this.#savingEvidence||this.#laboratoryWriting||
       this.#questionRetryKeys.size>0||Boolean(this.#labPending)||
       [...this.#manualPassageIntents.keys()].some(key=>!patientId||JSON.parse(key)[0]===patientId)||
       [this.#state.importOutcome,this.#state.laboratoryPhase,this.#state.reviewReturnPhase,
        this.#state.followthroughWritePhase,this.#state.evidenceWritePhase,this.#state.evidenceLinkPhase,
        this.#state.labQuestionWritePhase].some(p=>['sending','saving','unknown'].includes(p));
  }
  managePatientPermissions(patientId:string){
    if(this.permissionChangePending()||!this.#token||!KEY.test(patientId)||this.#suspensionIntent)return;
    if(this.#hasPendingPatientWrite(this.#state.patient?.patient_id)){
      this.#publish({message:'Resolve the pending patient write before managing permissions. Its recovery request is preserved.'});return;
    }
    this.#clearPatientSessionData();
    const scope=this.#scope;
    const active=()=>scope===this.#scope&&this.#permissions!==null&&!!this.#token&&this.#state.connected;
    this.#permissions=new PermissionConsole({patientId,active,request:async(suffix,body)=>{
      if(!active()||!/^$|^\?after=GRANT-[A-F0-9]{32}$|^\/GRANT-[A-F0-9]{32}\/revocations$/.test(suffix))throw Error('Reopen permission management');
      const control=new AbortController();this.#controllers.add(control);
      const timer=setTimeout(()=>control.abort(),10000);
      try{
        const response=await this.transport('/v1/patients/'+encodeURIComponent(patientId)+'/permissions'+suffix,this.#init(control,body));
        if(!active()||control.signal.aborted){void response.body?.cancel().catch(()=>{});throw Error();}
        if(response.status!==200){void response.body?.cancel().catch(()=>{});if(response.status===401)this.#httpError(401);throw new PermissionHttpError(response.status);}
        const value=await json(response,131072);if(!active()||control.signal.aborted)throw Error();return value;
      }finally{clearTimeout(timer);this.#controllers.delete(control);}
    }},()=>this.#publish({}));
    this.#publish({connected:true,phase:'idle',message:'Patient records cleared for permission management.'});
  }
  #encounterScope(patientId:string){
    const scope=this.#scope,read=this.#read,patient=this.#state.patient;
    return ()=>scope===this.#scope&&read===this.#read&&!!this.#token&&this.#state.connected&&
      this.#state.phase==='ready'&&patient?.status==='active'&&patient.patient_id===patientId&&this.#state.patient===patient;
  }
  /** A chart handle belongs to one successful patient selection, including when an ID is reopened. */
  encounterChart(patientId:string):EncounterChart{
    const current=this.#encounterScope(patientId);
    return createEncounterChart(patientId,(suffix,body,limit,decode)=>
      this.#encounterRequest(patientId,suffix,current,body,limit,decode));
  }
  async encounterSourceRequest(patientId:string,id:number,caseId:string,after:number|null,body?:string):Promise<unknown>{
    const patientCurrent=this.#encounterScope(patientId),index=this.#state.sourceIndex,records=this.#records;
    const current=()=>patientCurrent()&&records===this.#records&&index!==null&&this.#state.sourceIndex===index&&
      index.patient_id===patientId&&index.case_id===caseId&&this.#state.recordsPhase==='ready';
    if(!current()||!Number.isSafeInteger(id)||id<1||!/^CASE-[A-Z0-9-]{1,35}$/.test(caseId)||
      (body===undefined?after===null||!Number.isSafeInteger(after)||after<0:after!==null))throw Error('Recheck patient and case access');
    if(body!==undefined){
      let intent:unknown;try{intent=body.length<=1024?JSON.parse(body):null;}catch{intent=null;}
      if(!exact(intent,['synthetic','request_key','source_id','expected_version','expected_sha256'])||intent.synthetic!==true||
        typeof intent.request_key!=='string'||!/^[A-Za-z0-9_.:-]{8,100}$/.test(intent.request_key)||
        !index?.sources.some(s=>s.source_id===intent.source_id&&s.version===intent.expected_version&&s.sha256===intent.expected_sha256))
        throw Error('Recheck the exact source version');
    }
    const suffix='/'+id+'/cases/'+encodeURIComponent(caseId)+'/source-links'+(after===null?'':'?after_id='+after+'&limit=25');
    return this.#encounterRequest(patientId,suffix,current,body,65536,x=>x,body!==undefined);
  }
  async sourceHistory(index:SourceIndex,cutoff:string,signal:AbortSignal):Promise<import('./source-contracts.js').SourceHistory>{
    const patientCurrent=this.#encounterScope(index.patient_id),records=this.#records;
    const current=()=>patientCurrent()&&records===this.#records&&this.#state.sourceIndex===index&&this.#state.recordsPhase==='ready';
    receiptMicros(cutoff);
    if(!current()||signal.aborted)throw Error('Recheck patient and case access');
    const control=new AbortController(),stop=()=>control.abort();
    signal.addEventListener('abort',stop,{once:true});this.#controllers.add(control);
    const timer=setTimeout(stop,10000),live=()=>current()&&!control.signal.aborted;
    try{
      const path='/v1/patients/'+encodeURIComponent(index.patient_id)+'/cases/'+encodeURIComponent(index.case_id)+
        '/source-history?received_through='+encodeURIComponent(cutoff);
      const response=await this.transport(path,this.#init(control));
      if(!live()){void response.body?.cancel().catch(()=>{});throw Error();}
      if(response.status!==200){
        void response.body?.cancel().catch(()=>{});
        if(response.status===401)this.#httpError(401);
        else if(response.status===403||response.status===404){
          this.#clearPatientSessionData();
          this.#publish({connected:true,phase:'error',message:'Source history access is unavailable. Reopen the patient to check current access.'});
        }
        throw Error();
      }
      const value=await json(response,512000);if(!live())throw Error();
      return parseSourceHistory(value,index,cutoff);
    }catch{throw Error('Source history could not be verified. Refresh records and check current access.');}
    finally{clearTimeout(timer);signal.removeEventListener('abort',stop);this.#controllers.delete(control);}
  }
  async #encounterRequest<T>(patientId:string,suffix:string,current:()=>boolean,body:string|undefined,limit:number,
      decode:(data:unknown)=>T|Promise<T>,allowCreated=false):Promise<T>{
    if(!current())throw Error('Reopen the authorized patient');
    const control=new AbortController();this.#controllers.add(control);
    const timer=setTimeout(()=>control.abort(),10000);
    const live=()=>current()&&!control.signal.aborted;
    try{
      const response=await this.transport('/v1/patients/'+encodeURIComponent(patientId)+'/encounters'+suffix,this.#init(control,body));
      if(!live()){void response.body?.cancel().catch(()=>{});throw Error();}
      if(response.status!==200&&!(allowCreated&&response.status===201)){
        void response.body?.cancel().catch(()=>{});
        if(response.status===401)this.#httpError(401);
        else if(response.status===403||response.status===404){
          this.#clearPatientSessionData();
          this.#publish({connected:true,phase:'error',message:'Visit access is unavailable. Reopen the patient to check current access.'});
        }
        throw new EncounterHttpError(response.status);
      }
      const data=await json(response,limit);if(!live())throw Error();
      const verified=await decode(data);if(!live())throw Error();
      return verified;
    }catch(error){
      if(error instanceof EncounterHttpError)throw error;
      // Network exceptions and invalid JSON may include credentials or response excerpts.
      throw Error('Encounter response unavailable or could not be verified');
    }finally{clearTimeout(timer);this.#controllers.delete(control);}
  }
  async documentRequest(caseId:string,path:string,body?:string,questionId?:string):Promise<import('./reviewed-documents').DocumentReply>{
    if(!/^CASE-[A-Z0-9-]{1,35}$/.test(caseId)||!/^$|^\/preview$|^\/SRC-[A-F0-9]{32}(?:\/(?:original|annotations)|\/selections\/ANN-[A-F0-9]{32}\/[a-z][a-z0-9_-]{0,59})?$/.test(path))throw Error('Invalid document path');
    if(questionId!==undefined&&!/^QUESTION-[A-F0-9]{32}$/.test(questionId))throw Error('Invalid question scope');
    return this.#caseContentRequest(caseId,'/documents'+path,body,questionId);
  }
  async questionPassageRequest(caseId:string,questionId:string,body?:string):Promise<import('./reviewed-documents').DocumentReply>{
    if(!/^CASE-[A-Z0-9-]{1,35}$/.test(caseId)||!/^QUESTION-[A-F0-9]{32}$/.test(questionId))throw Error('Invalid question passage path');
    const q=this.#state.questions?.find(q=>q.question_id===questionId&&q.case_id===caseId);
    if(!q||q.patient_id!==this.#state.patient?.patient_id)throw Error('Recheck current question access');
    return this.#caseContentRequest(caseId,'/questions/'+questionId+'/manual-passages',body,questionId);
  }
  async #caseContentRequest(caseId:string,path:string,body?:string,questionId?:string):Promise<import('./reviewed-documents').DocumentReply>{
    const scope=this.#scope,read=this.#read,records=this.#records,patient=this.#state.patient?.patient_id;
    const caseContext=()=>questionId!==undefined?
      this.#state.questionListPhase==='ready'&&this.#state.questionsCaseId===caseId&&this.#state.worldPhase==='ready'&&this.#state.worldModel?.case_id===caseId&&
       Boolean(this.#state.questions?.some(q=>q.question_id===questionId&&q.case_id===caseId&&q.patient_id===patient)):
      this.#state.sourceIndex?.case_id===caseId;
    const labPreview=path==='/laboratory/fhir-r4/preview';
    const selectedIndex=this.#state.sourceIndex;
    // Closing an unrelated original must not suppress a denial for the selected case.
    const current=()=>scope===this.#scope && read===this.#read && patient===this.#state.patient?.patient_id &&
      (labPreview ? selectedIndex===this.#state.sourceIndex : records===this.#records) && caseContext();
    if(!patient||!this.#token||!current())throw Error('Recheck patient and case access');
    const control=new AbortController();this.#controllers.add(control);
    const timeout=questionId!==undefined||labPreview?setTimeout(()=>control.abort(),10000):undefined;
    try{
      const response=await this.transport('/v1/patients/'+encodeURIComponent(patient)+'/cases/'+encodeURIComponent(caseId)+path,this.#init(control,body));
      if(!current()){
        void response.body?.cancel().catch(()=>{});
        throw Error('Patient or case changed');
      }
      // A denied endpoint cannot leave the shared case looking authorized.
      // Status is authoritative even when a proxy returns a non-JSON body.
      if([401,403,404].includes(response.status)){
        if(response.status===401)this.#httpError(401);
        else this.#publish(this.#resetDeniedCaseSources(labPreview?'Laboratory preview access unavailable. Reload case permissions.':'Document access unavailable or mapping changed. Reload case permissions.'));
        void response.body?.cancel().catch(()=>{});
        return{status:response.status,body:null,headers:response.headers};
      }
      let value:unknown;
      if(path.endsWith('/original')&&response.status===200){
        value=await boundedBytes(response,65536);
      }else{
        // 64 revisions × 30 quotes × 1200 code points × at most 12 JSON bytes
        // (escaped surrogate pairs), plus bounded findings metadata and 64 KiB rendition.
        // 32 MiB covers the complete permitted history; streaming still limits bad peers.
        value=await json(response,labPreview?65536:32*1024*1024);
      }
      if(!current())throw Error('Patient or case changed');
      const contentScope=path.includes('/selections/')&&value&&typeof value==='object'?(value as {anchor?:unknown}).anchor:value;
      if(body===undefined&&response.status===200&&path!=='/documents/preview'&&!path.endsWith('/original')&&
        (!contentScope||typeof contentScope!=='object'||(contentScope as {patient_id?:string}).patient_id!==patient||(contentScope as {case_id?:string}).case_id!==caseId))throw Error('Wrong document scope');
      return{status:response.status,body:value,headers:response.headers};
    }finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }
  #historyRead=0;
  #token=''; #scope=0; #read=0; #records=0; #state:ViewState=fresh();
  #suspensionIntent:{target:Patient;body:string;uncertain:boolean}|null=null;
  #worldRead=0; #composerRead=0; #questionRead=0; #questionWrite=0; #briefRead=0;
  #questionKey=''; #questionFingerprint=''; #savingQuestion=false;
  // An interrupted write may already have committed. Only a freshly authorized,
  // byte-identical command in this credential/patient/case may recover its key.
  #questionRetryKeys=new Map<string,string>();
  #reviewRead=0; #reviewWrite=0; #reviewKey=''; #reviewIntent=''; #savingReview=false;
  #followRead=0; #followWrite=0; #savingFollowthrough=false;
  #evidenceRead=0; #evidenceWrite=0; #savingEvidence=false;
  #quoteRead=0;
  #imageRead=0; #imageDownload=0; #imagePreview=0;
  #labDrafts=new WeakMap<LabPreparation,{model:SourceWorldModel;question:string;source:string;reference:string;key:string}>();
  #labPending:{patient:string;caseId:string;body:string}|null=null;
  #labSave=0;#labList=0;
  #laboratoryWrite=0; #laboratoryWriting=false;
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
  prepareEvidenceReport=(questionId:string,assessmentIds:readonly string[],manualContextSha256?:string)=>this.#evidenceSession.prepareReport(questionId,assessmentIds,manualContextSha256);
  readEvidenceReport=(questionId:string,reportId:string)=>this.#evidenceSession.readReport(questionId,reportId);
  loadEvidenceOriginal=(questionId:string,evidenceId:string)=>this.#evidenceSession.original(questionId,evidenceId);
  retryEvidenceWrite=()=>this.#evidenceSession.retry();
  snapshot=():ViewState=>this.#state;
  subscribe=(listener:()=>void):(()=>void)=>{this.#listeners.add(listener);return()=>this.#listeners.delete(listener);};
  #publish(patch:Partial<ViewState>){
    let next={...this.#state,...patch};
    if(next.worldModel!==this.#state.worldModel||next.worldPhase!=='ready'||
       next.patient!==this.#state.patient||!next.connected||next.phase!=='ready'){
      this.#historyRead++;next={...next,...emptyHistory()};
    }
    const prior=this.#state.laboratoryIntent,intent=next.laboratoryIntent;
    let invalidated=prior!==null&&intent===null;
    if(intent&&(next.patient!==null&&next.patient.patient_id!==intent.patient_id||
       next.sourceIndex!==null&&next.sourceIndex.case_id!==intent.case_id||
       next.cases!==null&&!next.cases.some(row=>row.case_id===intent.case_id&&row.status==='active'))){
      next={...next,...emptyLaboratory()};invalidated=true;
    }else if(intent&&next.laboratoryPhase==='sending'&&patch.recordsPhase?.startsWith('loading')){
      // A metadata refresh can interrupt the read of a write's response, not undo its commit.
      next={...next,laboratoryPhase:'unknown',laboratoryReceipt:null,
        laboratoryMessage:'Import outcome unknown after context refresh. Reopen this case and retry the exact saved request.'};
      invalidated=true;
    }else if(this.#state.laboratoryPhase==='sending'&&next.laboratoryPhase==='unknown'){
      invalidated=true;
    }
    if(invalidated){this.#laboratoryWrite++;
      if(this.#laboratoryWriting){this.#laboratoryWriting=false;this.#uploading=false;}}
    const patient=next.patient?.patient_id,caseId=next.questionsCaseId;
    const scoped=next.connected&&next.phase==='ready'&&next.patient?.status==='active'&&next.questionListPhase==='ready'&&
      next.worldPhase==='ready'&&next.worldModel?.patient_id===patient&&next.worldModel?.case_id===caseId&&
      next.cases?.some(c=>c.patient_id===patient&&c.case_id===caseId&&c.status==='active');
    const ids=scoped?(next.questions??[]).filter(q=>q.patient_id===patient&&q.case_id===caseId&&
      this.#manualPassageDrafts.has(JSON.stringify([patient,caseId,q.question_id]))).map(q=>q.question_id):[];
    if(this.#labPending&&next.cases!==null&&!next.cases.some(c=>c.patient_id===this.#labPending?.patient&&c.case_id===this.#labPending?.caseId&&c.status==='active'))next={...next,...this.#resetLabQuestions()};
    this.#state=Object.freeze({...next,evidenceGeneration:this.#evidenceRead,manualPassageDraftQuestionIds:Object.freeze(ids)});
    for(const listener of this.#listeners)listener();
  }
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
    const transitionDrafts=Object.freeze(Object.fromEntries(Object.entries(this.#state.followthroughTransitionDrafts)
      .filter(([,draft])=>draft.patient_id===this.#state.patient?.patient_id&&draft.case_id===preserveCase)));
    if(intent&&intent.patient_id===this.#state.patient?.patient_id&&intent.case_id===preserveCase&&
       ['saving','unknown'].includes(this.#state.followthroughWritePhase)){
      return {...emptyFollowthrough(),followthroughDrafts:drafts,followthroughTransitionDrafts:transitionDrafts,
        followthroughCaseId:preserveCase,followthroughIntent:intent,
        followthroughWritePhase:'unknown' as const,followthroughWriteMessage:
          'The earlier write outcome is uncertain. Retry its exact recorded intent to recover the receipt, or explicitly abandon recovery.'};
    }
    return {...emptyFollowthrough(),followthroughDrafts:drafts,followthroughTransitionDrafts:transitionDrafts,followthroughCaseId:preserveCase??null};
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
  #resetLabQuestions(preserveCase?:string):LabQuestionView{
    this.#labSave++;this.#labList++;this.#labDrafts=new WeakMap();
    if(this.#labPending&&preserveCase===this.#labPending.caseId&&this.#state.patient?.patient_id===this.#labPending.patient){
      return {...emptyLabQuestions(),...unconfirmedLabQuestion};
    }
    this.#labPending=null;return emptyLabQuestions();
  }
  #resetInvestigation(preserveReviewCase?:string,preserveFollowthroughCase=preserveReviewCase,preserveEvidenceCase=preserveReviewCase,preserveAuthoredEvidenceCase=preserveReviewCase,preserveManualCase=preserveReviewCase,preserveLabCase=preserveReviewCase){
    this.#clearManualDrafts(preserveManualCase);
    this.#inspectionQuestionId=null;
    this.#worldRead++;this.#composerRead++;this.#questionRead++;this.#questionWrite++;this.#briefRead++;this.#quoteRead++;
    this.#questionKey='';this.#questionFingerprint='';this.#savingQuestion=false;
    return {...emptyInvestigation(),...this.#resetLabQuestions(preserveLabCase),...this.#resetSourceImages(),...this.#resetReview(preserveReviewCase),...this.#resetFollowthrough(preserveFollowthroughCase),
      ...this.#resetEvidence(preserveEvidenceCase),...this.#evidenceSession.reset(preserveAuthoredEvidenceCase)};
  }
  #resetWorld(preserveReviewCase?:string){
    this.#publish({...emptyWorld(),...this.#resetInvestigation(preserveReviewCase)});
  }
  #resetDeniedCaseSources(recordMessage='Source access must be rechecked. Reload case permissions to reopen records.'){
    this.#records++;
    return {...emptyRecords(),...this.#resetInvestigation(),recordsPhase:'error' as const,recordMessage};
  }
  // A question endpoint combines source_read with an action-specific grant. Hide
  // both views immediately, then restore independent actions only from fresh reads.
  async #recheckQuestionDenial(caseId:string,control:AbortController,restore:'case'|'world'|'questions',failure:Partial<ViewState>){
    const patientId=this.#state.patient?.patient_id;
    const hadWorld=this.#state.worldModel?.case_id===caseId;
    const hadIndex=this.#state.sourceIndex?.case_id===caseId&&this.#state.sourceIndex.patient_id===patientId;
    const reset=this.#resetDeniedCaseSources();
    const scope=this.#scope,records=this.#records,questions=this.#questionRead,quotes=this.#quoteRead,brief=this.#briefRead;
    const current=()=>scope===this.#scope&&records===this.#records&&questions===this.#questionRead&&
      quotes===this.#quoteRead&&brief===this.#briefRead&&this.#state.patient?.patient_id===patientId;
    this.#publish(reset);
    if(!patientId||!current())return;
    const read=async(url:string,limit:number)=>{
      if(!current()||control.signal.aborted)throw Error('scope changed');
      const response=await this.transport(url,this.#init(control));
      if(!current()||control.signal.aborted||response.status!==200){
        void response.body?.cancel().catch(()=>{});
        if(current()&&response.status===401)this.#httpError(401);
        throw Error('access unavailable');
      }
      const result=await json(response,limit);
      if(!current()||control.signal.aborted)throw Error('scope changed');
      return result;
    };
    const patientPath='/v1/patients/'+encodeURIComponent(patientId);
    const casePath=patientPath+'/cases/'+encodeURIComponent(caseId);
    try{
      const model=parseSourceWorldModel(await read(casePath+'/world-model',1048576),patientId,caseId);
      const cases=parseCaseBindingList(await read(patientPath+'/case-bindings',65536),patientId);
      if(!cases.some(item=>item.case_id===caseId&&item.status==='active'))throw Error('case unavailable');
      const sourceIndex=hadIndex?parseSourceIndex(await read(casePath+'/sources',65536),patientId,caseId):null;
      const patch:Partial<ViewState>={cases,sourceIndex,recordsPhase:'ready',recordMessage:sourceIndex?
        'Original source metadata rechecked. Open an original to inspect its bytes.':'Case access rechecked. Select the case to reopen Records.'};
      const world=hadWorld&&restore!=='case'?{worldModel:model,worldPhase:'ready' as const,
        worldMessage:'Source-derived snapshot verified at last read.'}:{};
      if(restore==='questions'){
        const history=decodeSourceQuestions(await read(casePath+'/questions',1048576),patientId,caseId);
        if(current())this.#publish({...patch,...world,questions:history.questions,questionsAccessReceiptId:history.access_receipt_id,
          questionsCaseId:caseId,questionListPhase:'ready',questionListMessage:'Saved question access rechecked.',...failure});
      }else if(current())this.#publish({...patch,...world,...failure});
    }catch{
      if(current())this.#publish(failure);
    }
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
  #clearPatientSessionData(preserveOtherManualIntents=false){
    this.#permissions?.clear();this.#permissions=null;
    this.#suspensionIntent=null;
    this.#questionRetryKeys.clear();
    if(!preserveOtherManualIntents)this.#manualPassageIntents.clear();
    this.#laboratoryWrite++;this.#laboratoryWriting=false;
    this.#scope++;this.#read++;this.#records++;this.#creating=false;this.#uploading=false;
    this.#resetInvestigation();
    for(const c of this.#controllers)c.abort();this.#controllers.clear();
    this.#state=fresh();
  }
  disconnect=()=>{
    this.#token='';
    this.#clearPatientSessionData();
    for(const listener of this.#listeners)listener();
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
    if(this.permissionChangePending()){this.#publish({message:"Resolve the pending permission change first."});return;}
    this.#permissions?.clear();this.#permissions=null;
    if(this.#suspensionIntent)return;
    this.#publish(emptySuspension());
    if(this.#state.patient?.patient_id!==id)this.#questionRetryKeys.clear();
    const scope=this.#scope, request=++this.#read;
    const lab=this.#state.laboratoryIntent;
    const preserveLaboratory=lab?.patient_id===id&&['sending','unknown'].includes(this.#state.laboratoryPhase)?lab:null;
    const pendingEvidence=this.#state.evidenceWriteIntent;
    const preserveEvidence=pendingEvidence?.patient_id===id&&
      ['saving','unknown'].includes(this.#state.evidenceWritePhase)?pendingEvidence:null;
    // Invalidate the earlier response and every displayed source. Retain only the
    // exact command for this patient until its case can be authorized again.
    const pendingLabQuestion=this.#labPending?.patient===id?this.#labPending:null;
    const pendingCitation=this.#state.evidenceLinkIntent?.patient_id===id&&
      ['saving','unknown'].includes(this.#state.evidenceLinkPhase)?this.#state.evidenceLinkIntent:null;
    const clearedInvestigation=this.#resetInvestigation();
    this.#labPending=pendingLabQuestion;
    this.#records++;this.#publish({patient:null,...emptyRecords(),...clearedInvestigation,
      ...(pendingLabQuestion?unconfirmedLabQuestion:{}),
      ...(pendingCitation?{evidenceLinkIntent:pendingCitation,evidenceLinkPhase:'unknown' as const,
        evidenceLinkMessage:'Reopen the question to check the original citation save.'}:{}),
      ...(preserveLaboratory?{laboratoryIntent:preserveLaboratory,laboratoryPhase:'unknown' as const,
        laboratoryMessage:'The earlier laboratory import remains uncertain. Recheck this case, then retry its exact saved request.'}:{}),
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
        if([403,404].includes(res.status))this.#publish({...this.#resetInvestigation(),...emptyLaboratory()});
        this.#httpError(res.status);return;
      }
      const value=patient(await json(res),id); if(!current())return;
      this.#publish({patient:value,phase:'ready',message:'Patient identity read from the canonical registry. No clinical record is loaded.'});
    }catch(_){if(current())this.#publish({patient:null,phase:'error',message:'The patient response could not be verified. No cached patient is shown.'});}
    finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }
  async create(requestKey:string,confirmed:boolean):Promise<void>{
    if(this.permissionChangePending())return;
    this.#permissions?.clear();this.#permissions=null;
    if(this.#suspensionIntent)return;
    if(this.#creating)return;
    if(!this.#token){this.#publish({message:'Connect an authorized synthetic credential first.'});return;}
    if(confirmed!==true || !boundedKey(requestKey)){this.#publish({phase:'error',message:'Confirm fictional identity creation and use a valid request key.'});return;}
    // A new creation is a new selection intent; an older read cannot restore it.
    this.#read++;this.#records++;
    const scope=this.#scope,control=new AbortController();this.#controllers.add(control);this.#creating=true;
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({phase:'creating',patient:null,created:null,...emptySuspension(),...emptyRecords(),...this.#resetInvestigation(),message:'Creating a fictional identity; reading it will still need an explicit grant…'});
    try{
      const res=await this.transport('/v1/patients',this.#init(control,JSON.stringify({synthetic:true,request_key:requestKey})));
      if(scope!==this.#scope)return;
      if(![200,201].includes(res.status)){this.#httpError(res.status);return;}
      const value=created(await json(res));if(scope!==this.#scope)return;
      this.#publish({phase:'idle',created:value,message:value.duplicate?'Original creation receipt recovered. No duplicate identity was created.':'Identity created. Ask the operator for its exact read grant before opening it.'});
    }catch(_){if(scope===this.#scope)this.#publish({phase:'error',message:'Creation outcome is unknown. Retry with the same request key to avoid duplication.'});}
    finally{clearTimeout(timeout);this.#controllers.delete(control);if(scope===this.#scope)this.#creating=false;}
  }

  /** The canonical registry owns suspension and its receipt. Clear every clinical
   * reader before sending; even a lost response may mean access is suspended. */
  async suspendPatient(confirmed:boolean):Promise<void>{
    const target=this.#state.patient;
    if(this.#suspensionIntent||!this.#token||this.#state.phase!=='ready'||
       !target||target.status!=='active'||confirmed!==true)return;
    if(this.#hasPendingPatientWrite(target.patient_id)){
      this.#publish({suspensionPhase:'rejected',suspensionMessage:
        'Resolve the pending patient write before suspending access. Its recovery request is preserved.'});return;
    }
    if(!Number.isSafeInteger(target.revision+1))return;
    const intent={target,body:JSON.stringify({synthetic:true,request_key:crypto.randomUUID(),
      expected_revision:target.revision}),uncertain:false};
    this.#clearPatientSessionData(true);
    this.#suspensionIntent=intent;
    this.#publish({connected:true,phase:'idle',suspensionTarget:{patient_id:target.patient_id,revision:target.revision},
      message:'Patient content and unsaved drafts cleared for the suspension request.'});
    await this.#sendSuspension();
  }
  retryPatientSuspension=async():Promise<void>=>{
    if(this.#state.suspensionPhase==='unknown')await this.#sendSuspension();
  };
  leaveSuspensionRecovery=()=>{
    if(this.#state.suspensionPhase!=='unknown')return;
    this.#clearPatientSessionData(true);
    this.#publish({connected:!!this.#token,phase:'idle',message:
      'Local recovery cleared. This does not reverse or cancel a suspension. Recheck the patient registry before continuing.'});
  };
  async #sendSuspension():Promise<void>{
    const intent=this.#suspensionIntent;
    if(!intent||!this.#token||this.#state.suspensionPhase==='sending')return;
    const scope=this.#scope,control=new AbortController();this.#controllers.add(control);
    const current=()=>scope===this.#scope&&this.#suspensionIntent===intent;
    const uncertain=()=>{intent.uncertain=true;this.#publish({suspensionPhase:'unknown',suspensionReceipt:null,
      suspensionMessage:'Suspension outcome is unknown. Patient content remains cleared. Retry the unchanged request to recover its receipt.'});};
    this.#publish({suspensionPhase:'sending',suspensionMessage:'Checking authority and suspending patient access…'});
    const timeout=setTimeout(()=>control.abort(),10000);
    try{
      const response=await this.transport('/v1/patients/'+encodeURIComponent(intent.target.patient_id)+'/suspensions',
        this.#init(control,intent.body));
      if(!current())return;
      if(response.status===401){this.#httpError(401);return;}
      if([403,404,409,422].includes(response.status)){
        // A refusal of the retry cannot tell us whether an earlier request committed.
        if(intent.uncertain){uncertain();return;}
        this.#suspensionIntent=null;
        this.#publish({suspensionPhase:'rejected',suspensionMessage:response.status===409?
          'The registry revision changed. Reopen the patient before making a new decision.':
          'Suspension was refused. Check current patient access and the independent suspension grant.'});return;
      }
      if(response.status!==200){uncertain();return;}
      const receipt=readSuspensionReceipt(await json(response),intent.target);
      if(!current())return;
      this.#suspensionIntent=null;
      this.#publish({patient:Object.freeze({...intent.target,...receipt}),phase:'ready',suspensionPhase:'confirmed',
        suspensionReceipt:receipt,suspensionMessage:'Suspension confirmed by the registry. Patient content remains cleared.',
        message:'Patient access is suspended. Historical records and work remain in the canonical services.'});
    }catch{if(current())uncertain();}
    finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }

  /** Explicit, permission-checked metadata read; never create a second patient/case ledger. */
  async loadCases():Promise<void>{
    const patientId=this.#state.patient?.patient_id;
    if(!this.#token || !patientId || this.#state.phase!=='ready'){
      this.#publish({...emptyRecords(),...this.#resetInvestigation(),recordsPhase:'error',recordMessage:'Open an authorized fictional patient in Overview first.',...emptyIntake()});
      return;
    }
    const retainedCase=this.#state.reviewReturnIntent?.case_id,
      retainedFollowthroughCase=this.#state.followthroughIntent?.case_id??Object.values(this.#state.followthroughDrafts)[0]?.case_id??
        Object.values(this.#state.followthroughTransitionDrafts)[0]?.case_id,
      retainedEvidenceCase=this.#state.evidenceLinkIntent?.case_id,
      retainedAuthoredEvidenceCase=this.#state.evidenceWriteIntent?.case_id,
      retainedManualCase=this.#manualDraftCase??undefined;
    const scope=this.#scope,read=this.#read,request=++this.#records;
    const current=()=>scope===this.#scope && read===this.#read &&
      request===this.#records && this.#state.patient?.patient_id===patientId;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({...emptyIntake(),...emptyWorld(),...this.#resetInvestigation(retainedCase,retainedFollowthroughCase,retainedEvidenceCase,retainedAuthoredEvidenceCase,retainedManualCase,this.#labPending?.caseId),cases:null,sourceIndex:null,recordsPhase:'loading-cases',recordMessage:'Checking current case mapping permissions…'});
    try{
      const res=await this.transport('/v1/patients/'+encodeURIComponent(patientId)+'/case-bindings',this.#init(control));
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status!==200){
        if([403,404].includes(res.status))this.#clearManualDrafts();
        this.#publish({cases:null,sourceIndex:null,recordsPhase:'error',
          ...([403,404].includes(res.status)?{...emptyLaboratory(),...this.#resetLabQuestions(),...this.#resetReview(),...this.#resetFollowthrough(),...this.#resetEvidence(),...this.#evidenceSession.reset()}:{}),
          recordMessage:'Case mappings unavailable or permission changed. No records are shown.'});
        return;
      }
      const mappings=parseCaseBindingList(await json(res),patientId);
      if(!current())return;
      if(retainedManualCase&&!mappings.some(item=>item.case_id===retainedManualCase&&item.status==='active'))this.#clearManualDrafts();
      const pendingCase=this.#state.followthroughIntent?.case_id??Object.values(this.#state.followthroughDrafts)[0]?.case_id??
        Object.values(this.#state.followthroughTransitionDrafts)[0]?.case_id;
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
  async loadSources(caseId:string,taskOriginal?:FollowthroughTask):Promise<void>{
    if(taskOriginal&&(taskOriginal.case_id!==caseId||taskOriginal.source_line!==null||
       !projectFollowthroughAttention(this.#state)?.list.tasks.includes(taskOriginal))){
      this.#records++;
      this.#publish({original:null,recordsPhase:'error',recordMessage:'Refresh recorded work before inspecting its original laboratory report.'});
      return;
    }
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
        if([403,404].includes(res.status))this.#clearManualDrafts();
        this.#publish({cases:null,sourceIndex:null,recordsPhase:'error',
          ...([403,404].includes(res.status)?{...emptyLaboratory(),...this.#resetLabQuestions(),...this.#resetReview(),...this.#resetFollowthrough(),...this.#resetEvidence(),...this.#evidenceSession.reset()}:{}),
          recordMessage:'Sources unavailable, denied or mapping revoked. Reload case permissions.'});
        return;
      }
      const index=parseSourceIndex(await json(res),patientId,caseId);
      if(!current())return;
      if(taskOriginal&&!index.sources.some(source=>source.kind==='laboratory'&&source.source_id===taskOriginal.source_id&&
         source.version===taskOriginal.source_version&&source.sha256===taskOriginal.source_sha256)){
        this.#publish({sourceIndex:index,recordsPhase:'error',
          recordMessage:'The source versions available for this case do not match the laboratory report recorded on this task.'});
        return;
      }
      this.#publish({sourceIndex:index,recordsPhase:'ready',
        recordMessage:'Exact original source metadata read. Extracted statements are not clinical assessments.'});
      if(taskOriginal&&current())await this.loadOriginal(taskOriginal.source_id,taskOriginal.observation_reference);
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
    await this.returnReviewQuestion(intent.question_id,intent.queue_fingerprint,intent.reason,Boolean(intent.artifacts));
  }

  async returnReviewQuestion(questionId:string,fingerprint:string,
                             reason:string=FICTIONAL_RETURN_REASON,includeArtifacts=false):Promise<void>{
    if(this.#savingReview)return;
    const patientId=this.#state.patient?.patient_id;
    const previous=this.#state.reviewReturnIntent;
    const recovering=this.#state.reviewReturnPhase==='unknown'&&previous!==null&&this.#reviewKey!=='';
    if(recovering&&(previous.question_id!==questionId||previous.queue_fingerprint!==fingerprint||previous.reason!==reason||Boolean(previous.artifacts)!==includeArtifacts)){
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
    const artifacts=recovering?previous.artifacts:includeArtifacts&&item?
      openedReviewArtifacts(item,this.#state.backgroundBrief,this.#state.evidenceReport):null;
    if(includeArtifacts&&!artifacts){
      this.#publish({reviewReturnPhase:'error',reviewReturnMessage:'Reopen the completed brief and current comparison report for this question.'});return;
    }
    const intent=JSON.stringify([patientId,caseId,questionId,fingerprint,reason,artifacts??null]);
    if(this.#reviewIntent!==intent||!this.#reviewKey){this.#reviewKey=crypto.randomUUID();this.#reviewIntent=intent;}
    const requestKey=this.#reviewKey,query=++this.#reviewWrite,scope=this.#scope,selection=this.#read;
    const captured=Object.freeze({patient_id:patientId,case_id:caseId,question_id:questionId,queue_fingerprint:fingerprint,reason,...(artifacts?{artifacts}:{})});
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
        '/questions/'+encodeURIComponent(questionId)+(artifacts?'/evidence-reports/'+encodeURIComponent(artifacts.report_id)+
          '/runs/'+encodeURIComponent(artifacts.run_id):'')+'/return-for-verification';
      const res=await this.transport(url,this.#init(control,JSON.stringify({synthetic:true,
        request_key:requestKey,expected_queue_fingerprint:fingerprint,reason,...(artifacts?{
          expected_result_sha256:artifacts.result_sha256,expected_report_snapshot_sha256:artifacts.report_snapshot_sha256}:{})})));
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status===408||res.status>=500){uncertain();return;}
      if(res.status!==200&&res.status!==201){
        if(artifacts){
          this.#briefRead++;
          const message=res.status===409?'The selected brief, comparison or review request changed. Reopen both documents before returning them.':
            'The brief and comparison report were closed because the return could not be authorized.';
          this.#publish({...emptyBrief(),...this.#evidenceSession.reset(caseId),briefPhase:'error',briefMessage:message});
          if(recovering){
            this.#publish({...this.#resetReview(caseId),reviewReturnMessage:
              'The earlier return is still uncertain. Its original request can be retried after access is restored.'});return;
          }
        }
        this.#publish({...this.#resetReview(),reviewReturnPhase:'error',reviewReturnMessage:res.status===409?
          'The source or return intent is no longer current. Refresh the inbox; no new request was created.':
          'Return permission or source context is unavailable. Prior review content is cleared.'});
        return;
      }
      const value=await json(res);
      const saved=artifacts?decodeEvidenceRunReturn(value,questionId,artifacts,res.status):decodeReviewReturnResult(value,questionId);
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
    if(this.#savingQuestion||questionSaveBlocksSourceChange(this.#state)){
      this.#publish({worldMessage:'Resolve the earlier uncertain question save in Investigations before changing its source.'});
      return false;
    }
    if(this.#state.questionDraft&&this.#state.questionSavePhase!=='saved'){
      this.#publish({worldMessage:'An unfinished question draft exists. Finish or discard it in Investigations before starting a different one.'});
      return false;
    }
    const index=this.#state.sourceIndex,patientId=this.#state.patient?.patient_id;
    const source=index?.sources.find(s=>s.source_id===sourceId&&s.state==='current');
    const findings=index?.source_reported_assertions.filter(f=>f.source_id===sourceId&&f.source_line===sourceLine);
    const finding=findings?.length===1?findings[0]:undefined;
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
       quotation[0].reported_state!==finding.reported_state||
       quotation[0].oncology?.role!==finding.oncology?.role||
       quotation[0].oncology?.episode_id!==finding.oncology?.episode_id){
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
      this.#clearManualDrafts();
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
        if(response.status===403||response.status===404){
          const message='World Model source scope unavailable or revoked. Reload case permissions before reopening sources.';
          this.#publish({...this.#resetDeniedCaseSources(message),worldPhase:'error',worldMessage:message});
        }else this.#publish({...emptyWorld(),worldPhase:'error',
          worldMessage:'World Model is unavailable. Retry to check the current snapshot.'});
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

  dismissSourceHistory=()=>{this.#historyRead++;this.#publish(emptyHistory());};

  async loadSourceHistory(cutoff:string):Promise<void>{
    const model=this.#state.worldModel;
    if(!model||this.#state.worldPhase!=='ready'||!this.#token||this.#uploading||
       ![...model.current_sources,...model.history].some(s=>s.received_at===cutoff))return;
    const scope=this.#scope,read=this.#read,generation=++this.#historyRead;
    const current=()=>scope===this.#scope&&read===this.#read&&generation===this.#historyRead&&
      model===this.#state.worldModel&&this.#state.worldPhase==='ready';
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({...emptyHistory(),historyPhase:'loading',historyMessage:'Checking historical sources and current access…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(model.patient_id)+'/cases/'+encodeURIComponent(model.case_id)+
        '/world-model/history?received_through='+encodeURIComponent(cutoff);
      const response=await this.transport(url,this.#init(control));
      if(!current())return;
      if(response.status===401){this.#httpError(401);return;}
      if(response.status===403||response.status===404){
        this.#publish(this.#resetDeniedCaseSources('Historical source access unavailable. Recheck patient and case permissions.'));return;
      }
      if(response.status!==200)throw Error('Historical view unavailable');
      const history=parseSourceHistory(await json(response,1048576),model.patient_id,model.case_id,cutoff);
      if(current())this.#publish({sourceHistory:history,historyPhase:'ready',historyMessage:'Historical source context checked under current access.'});
    }catch(_){
      if(current())this.#publish({...emptyHistory(),historyPhase:'error',historyMessage:'Historical context could not be verified. Retry to check access and sources again.'});
    }finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }

  /** A question draft belongs to one current source and World Model snapshot.
   * Never persist editable text, credentials or preflight data outside memory.
   */
  chooseQuestionDraft(sourceId:string,sourceLine:number):void{
    if(this.#savingQuestion||questionSaveBlocksSourceChange(this.#state)){
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

  /** Preparation is a scoped source read. This path never calls question save. */
  async prepareLabQuestion(model:SourceWorldModel, source:string, reference:string,
                           question:string, signal:AbortSignal):Promise<LabPreparation|null>{
    if(questionSaveBlocksSourceChange(this.#state)||this.#labPending)return null;
    const scope=this.#scope, patientRead=this.#read, worldRead=this.#worldRead, questionWrite=this.#questionWrite, labEpoch=this.#labSave;
    // An older laboratory read must never clear a later question save or its retry key.
    const current=()=>scope===this.#scope && patientRead===this.#read && worldRead===this.#worldRead &&
      questionWrite===this.#questionWrite && labEpoch===this.#labSave &&
      !signal.aborted && this.#state.worldModel===model && this.#state.worldPhase==='ready' &&
      this.#state.phase==='ready' && this.#state.patient?.status==='active' &&
      this.#state.patient.patient_id===model.patient_id &&
      this.#state.cases?.some(c=>c.case_id===model.case_id && c.patient_id===model.patient_id && c.status==='active');
    const item=model.laboratory_observations.find(o=>o.source_id===source && o.observation_reference===reference);
    if(!this.#token || !current() || !item || !validLabQuestion(question))return null;
    const controller=new AbortController(), abort=()=>controller.abort();
    signal.addEventListener('abort',abort,{once:true});this.#controllers.add(controller);
    const timer=setTimeout(abort,10000);
    const withhold=(message:string,preserveCase?:string)=>{
      this.#resetWorld(preserveCase);
      this.#publish({worldPhase:'error',worldMessage:message});
    };
    try{
      const url='/v1/patients/'+encodeURIComponent(model.patient_id)+'/cases/'+encodeURIComponent(model.case_id)+'/composer/laboratory-preflight';
      const res=await this.transport(url,this.#init(controller,JSON.stringify({synthetic:true,source_id:source,
        observation_reference:reference,question,expected_source_snapshot_sha256:model.snapshot_fingerprint})));
      if(!current())return null;
      if(res.status===401){this.#httpError(401);return null;}
      if(res.status===403||res.status===404){this.#denyLaboratoryQuestionAccess('prepare');return null;}
      if(res.status!==200){
        withhold(res.status===409?'The laboratory report changed. Reopen the case to select a current result.':
          'Laboratory question preparation is unavailable. Recheck access to this case.',
          model.case_id);return null;
      }
      const receipt=readLabPreparation(await json(res),model,item,question);
      if(!current()||controller.signal.aborted)return null;
      this.#labDrafts.set(receipt,{model,source,reference,question,key:crypto.randomUUID()});
      return receipt;
    }catch{
      if(current())withhold('The laboratory question response could not be verified. Reopen the case before trying again.',model.case_id);
      return null;
    }finally{clearTimeout(timer);signal.removeEventListener('abort',abort);this.#controllers.delete(controller);}
  }

  #canReadLabModel(model:SourceWorldModel):boolean{
    return !!this.#token&&this.#state.connected&&this.#state.phase==='ready'&&this.#state.patient?.status==='active'&&
      this.#state.patient.patient_id===model.patient_id&&this.#state.worldModel===model&&this.#state.worldPhase==='ready'&&
      !!this.#state.cases?.some(c=>c.patient_id===model.patient_id&&c.case_id===model.case_id&&c.status==='active');
  }
  async saveLabQuestion(model:SourceWorldModel,receipt:LabPreparation):Promise<void>{
    const draft=this.#labDrafts.get(receipt);
    if(!draft||draft.model!==model||!this.#canReadLabModel(model)||this.#labPending||questionSaveBlocksSourceChange(this.#state))return;
    this.#labDrafts.delete(receipt);
    this.#labPending={patient:model.patient_id,caseId:model.case_id,body:JSON.stringify({synthetic:true,
      request_key:draft.key,source_id:draft.source,observation_reference:draft.reference,question:draft.question,
      expected_source_snapshot_sha256:model.snapshot_fingerprint,expected_preflight_sha256:receipt.fingerprint})};
    await this.#sendLabQuestion(model);
  }
  async retryLabQuestion(model:SourceWorldModel):Promise<void>{
    if(this.#state.labQuestionWritePhase==='unknown'&&this.#canReadLabModel(model)&&!questionSaveBlocksSourceChange(this.#state))await this.#sendLabQuestion(model);
  }
  #denyLaboratoryQuestionAccess(operation:'prepare'|'save'|'history'|'evidence'){
    // A 403/404 can represent lost patient or case authority. Invalidate all
    // patient data and outstanding responses before permitting another read.
    this.#clearPatientSessionData();
    const message='Laboratory question access is unavailable. Reopen the patient in Overview to check current access.';
    this.#publish({connected:true,phase:'error',message,worldPhase:'error',worldMessage:message,
      recordsPhase:'error',recordMessage:message,
      ...(operation==='save'?{labQuestionWritePhase:'error' as const,labQuestionWriteMessage:message}:{}),
      ...(operation==='history'?{labQuestionListPhase:'error' as const,labQuestionListMessage:message}:{})});
  }
  async #sendLabQuestion(model:SourceWorldModel):Promise<void>{
    const intent=this.#labPending;
    if(!intent||intent.caseId!==model.case_id||intent.patient!==model.patient_id||this.#state.labQuestionWritePhase==='saving')return;
    const epoch=++this.#labSave,current=()=>epoch===this.#labSave&&this.#labPending===intent&&this.#canReadLabModel(model);
    this.#labList++;
    this.#dismissLabCitations(model.case_id);
    this.#publish({...emptyLabQuestions(),labQuestionWritePhase:'saving',labQuestionWriteMessage:'Saving the prepared question…'});
    const control=new AbortController();this.#controllers.add(control);const timer=setTimeout(()=>control.abort(),10000);
    try{
      const path='/v1/patients/'+encodeURIComponent(intent.patient)+'/cases/'+encodeURIComponent(intent.caseId)+'/composer/laboratory-questions';
      const response=await this.transport(path,this.#init(control,intent.body));
      if(!current())return;
      if(response.status===401){this.#httpError(401);return;}
      if(response.status===403||response.status===404){this.#denyLaboratoryQuestionAccess('save');return;}
      if([409,413,422].includes(response.status)){
        this.#labPending=null;this.#labDrafts=new WeakMap();this.#publish({...emptyLabQuestions(),labQuestionWritePhase:'error',
          labQuestionWriteMessage:response.status===409?'A changed report, conflicting request or full history can prevent a save. Reopen the saved questions and check the current report.':'Question save unavailable. Recheck access and prepare the question again.'});return;
      }
      if(![200,201].includes(response.status))throw Error('unknown');
      const saved=decodeSavedQuestion(await json(response));
      if(saved.duplicate!==(response.status===200))throw Error('unknown');
      if(!current())return;
      this.#labPending=null;this.#publish({labQuestionWritePhase:'saved',labQuestionSavedId:saved.question_id,
        labQuestionWriteMessage:saved.duplicate?'Original save receipt recovered.':'Laboratory question saved.'});
    }catch{if(current())this.#publish({labQuestionWritePhase:'unknown',labQuestionWriteMessage:'Save outcome unknown. Retry the exact request to recover its receipt.'});}
    finally{clearTimeout(timer);this.#controllers.delete(control);}
  }
  async loadLabQuestions(model:SourceWorldModel):Promise<void>{
    if(!this.#canReadLabModel(model)||questionSaveBlocksSourceChange(this.#state)||this.#labPending)return;
    const epoch=++this.#labList,current=()=>epoch===this.#labList&&this.#canReadLabModel(model);
    this.#dismissLabCitations(model.case_id);
    this.#publish({labQuestionHistory:null,labQuestionListPhase:'loading',labQuestionListMessage:'Checking access to saved laboratory questions…'});
    const control=new AbortController();this.#controllers.add(control);const timer=setTimeout(()=>control.abort(),10000);
    try{
      const path='/v1/patients/'+encodeURIComponent(model.patient_id)+'/cases/'+encodeURIComponent(model.case_id)+'/composer/laboratory-questions';
      const response=await this.transport(path,this.#init(control));if(!current())return;
      if(response.status===401){this.#httpError(401);return;}
      if(response.status===403||response.status===404){this.#denyLaboratoryQuestionAccess('history');return;}
      if(response.status!==200)throw Error('unavailable');
      const history=readLabQuestionList(await json(response,1048576),model);if(!current())return;
      this.#publish({labQuestionHistory:history,labQuestionListPhase:'ready',
        followthroughDrafts:Object.freeze(Object.fromEntries(Object.entries(this.#state.followthroughDrafts)
          .filter(([id,draft])=>draft.patient_id===model.patient_id&&draft.case_id===model.case_id&&
            (!draft.laboratoryAnchor||history.questions.some(row=>row.question_id===id&&matchesFollowthroughDraft(draft,row)))))),
        labQuestionListMessage:'Saved questions checked against current access.'});
    }catch{if(current())this.#publish({...this.#resetLabQuestions(),labQuestionListPhase:'error',labQuestionListMessage:'Saved questions are unavailable or the source changed. Refresh Journey and check access again.'});}
    finally{clearTimeout(timer);this.#controllers.delete(control);}
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
        const failure={composerPhase:'error' as const,composerMessage:res.status===409?
          'The original source changed. Refresh Investigations before preparing a new context.':
          'Composer context unavailable under current authority. Source observations were cleared.'};
        if(res.status===403||res.status===404)await this.#recheckQuestionDenial(model.case_id,control,'case',failure);
        else{this.#resetWorld(model.case_id);this.#publish(failure);}
        return;
      }
      const prepared=decodeComposerPreflight(await json(res),model,observation,question);
      const commandBytes=new TextEncoder().encode(JSON.stringify([patientId,model.case_id,questionCommand(prepared)]));
      const digest=await crypto.subtle.digest('SHA-256',commandBytes);
      const fingerprint=Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('');
      if(!current())return;
      if(this.#questionFingerprint!==fingerprint){
        this.#questionFingerprint=fingerprint;
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
    const command=questionCommand(prepared);
    const intent=this.#questionFingerprint;
    const earlierKey=this.#questionRetryKeys.get(intent);
    const key=earlierKey??this.#questionKey,query=++this.#questionWrite;
    this.#questionKey=key;
    this.#questionRetryKeys.set(intent,key);
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
      const body=JSON.stringify({synthetic:true,request_key:key,...command});
      const res=await this.transport(url,this.#init(control,body));
      if(!current())return;
      if(res.status===401){this.#httpError(res.status);return;}
      if(![200,201].includes(res.status)){
        if(![403,404,409,413,422].includes(res.status))throw Error('unconfirmed');
        // A refusal on a retry cannot establish the first attempt's outcome.
        if(!earlierKey)this.#questionRetryKeys.delete(intent);
        if(res.status===409){
          // Refresh stale source context while keeping this case's outstanding
          // commands recoverable with their original idempotency keys.
          this.#resetWorld(prepared.case_id);
          this.#publish({questionSavePhase:'error',questionSaveMessage:
            'Source/version or request intent changed. Refresh current originals and saved questions.'});
        }else{
          const failure={questionSavePhase:'error' as const,questionSaveMessage:
            'Question save refused by current authorization. No successful save is assumed.'};
          if(res.status===403||res.status===404)await this.#recheckQuestionDenial(prepared.case_id,control,'case',failure);
          else this.#publish(failure);
        }
        return;
      }
      const value=decodeSavedQuestion(await json(res));
      if(!current())return;
      this.#questionRetryKeys.delete(intent);
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
        const denied=res.status===403||res.status===404;
        const failure={sourceQuotePacket:null,sourceQuotePhase:'error' as const,
          sourceQuoteMessage:'Source quote packet unavailable or not authorized. Previous quote cleared.'};
        if(denied)await this.#recheckQuestionDenial(caseId,controller,'questions',failure);
        else this.#publish(failure);
        return;
      }
      const currentWorld=this.#state.worldModel?.case_id===caseId?this.#state.worldModel:undefined;
      const packet=await decodeQuestionSourcePacket(
        await json(res,1048576),question,caseId,pid,currentWorld);
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
    if(this.#manualDraftCase!==null&&this.#manualDraftCase!==caseId)this.#clearManualDrafts();
    if(this.#state.followthroughCaseId&&this.#state.followthroughCaseId!==caseId)this.#publish(this.#resetFollowthrough(caseId));
    this.#publish(this.#resetEvidence(caseId));
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
        const failure={questions:null,questionListPhase:'error' as const,questionListMessage:'Saved questions unavailable under current authority.'};
        if(res.status===403||res.status===404)await this.#recheckQuestionDenial(caseId,controller,'world',
          {...failure,reviewPhase:'error',reviewMessage:'Question or source access is unavailable. Previous review content is cleared.'});
        else this.#publish(failure);
        return;
      }
      const history=decodeSourceQuestions(await json(res,1048576),patientId,caseId);
      if(!current())return;
      const pendingEvidence=this.#state.evidenceLinkIntent;
      this.#publish({questions:history.questions,questionsAccessReceiptId:history.access_receipt_id,
        followthroughDrafts:Object.freeze(Object.fromEntries(Object.entries(this.#state.followthroughDrafts)
          .filter(([id,draft])=>draft.patient_id===patientId&&draft.case_id===caseId&&
            (draft.laboratoryAnchor||history.questions.some(item=>item.question_id===id&&matchesFollowthroughDraft(draft,item)))))),
        ...(pendingEvidence&&!pendingEvidence.laboratoryAnchor&&!history.questions.some(item=>item.question_id===pendingEvidence.question_id)?this.#resetEvidence():{}),
        questionsCaseId:caseId,questionListPhase:'ready',
        questionListMessage:history.questions.length?
          'Authorized source-linked questions, including any reopened reassessment needs.':
          'No saved source questions are available under this grant.'});
    }catch(_){
      if(current())this.#publish({questions:null,questionListPhase:'error',
        questionListMessage:'Question history could not be verified; no cached questions are shown.'});
    }finally{clearTimeout(timeout);this.#controllers.delete(controller);}
  }

  #dismissLabCitations(caseId:string){
    if(this.#state.evidenceFamily==='laboratory'||this.#state.evidenceLinkIntent?.laboratoryAnchor)
      this.#publish(this.#resetEvidence(caseId));
  }
  #catalogSubject(questionId:string,family:'text'|'laboratory'){
    const st=this.#state, model=st.worldModel;
    if(family==='laboratory'){
      const row=st.labQuestionHistory?.questions.find(q=>q.question_id===questionId);
      return model&&this.#canReadLabModel(model)&&st.labQuestionListPhase==='ready'&&row?
        {caseId:model.case_id,row,laboratory:row,canSearch:row.source_context_state==='current_unreviewed_question',
          canSave:row.source_context_state==='current_unreviewed_question'&&row.source_snapshot_sha256===model.snapshot_fingerprint}:null;
    }
    const row=st.questions?.find(q=>q.question_id===questionId);
    return row&&st.questionListPhase==='ready'&&row.case_id===st.questionsCaseId&&row.patient_id===st.patient?.patient_id?
      {caseId:row.case_id,row,laboratory:null,canSearch:true,canSave:canPrepareSourceBrief(row,model)}:null;
  }
  #catalogPath(patient:string,caseId:string,question:string,laboratory:boolean){
    return '/v1/patients/'+encodeURIComponent(patient)+'/cases/'+encodeURIComponent(caseId)+
      (laboratory?'/composer/laboratory-questions/':'/questions/')+encodeURIComponent(question);
  }

  /** Catalog queries are manually supplied; no patient-derived text is sent. */
  async searchQuestionEvidence(questionId:string,query:string,family:'text'|'laboratory'='text'):Promise<void>{
    if(this.#savingEvidence)return;
    if(this.#state.evidenceLinkPhase==='unknown'){
      this.#publish({evidenceLinkMessage:'Resolve the earlier uncertain citation save before searching for or saving another citation.'});return;
    }
    await this.#readQuestionEvidence(questionId,family,query);
  }

  async loadQuestionEvidenceLinks(questionId:string,family:'text'|'laboratory'='text'):Promise<void>{
    if(this.#savingEvidence)return;
    await this.#readQuestionEvidence(questionId,family);
  }

  async #readQuestionEvidence(questionId:string,family:'text'|'laboratory',query?:string):Promise<void>{
    this.#focusSavedQuestion(questionId);
    const patientId=this.#state.patient?.patient_id,subject=this.#catalogSubject(questionId,family),caseId=subject?.caseId;
    const search=query!==undefined;
    const read=++this.#evidenceRead,scope=this.#scope,selection=this.#read,
      questionRead=this.#questionRead,worldRead=this.#worldRead;
    // Both readers share this barrier. A rights-restricted refresh must also
    // erase an earlier search title and prevent its delayed response returning.
    this.#publish({...emptyEvidenceMetadata(),evidenceQuestionId:questionId,evidenceFamily:family});
    const failed=(message:string)=>this.#publish(search?{evidenceSearchPhase:'error',evidenceSearchMessage:message}:
      {evidenceLinksPhase:'error',evidenceLinksMessage:message});
    if(!this.#token||!patientId||!caseId||!subject||this.#state.phase!=='ready'||this.#uploading||
       !this.#state.cases?.some(item=>item.case_id===caseId&&item.status==='active')||
       (search&&(!subject.canSearch||!validEvidenceQuery(query)))){
      failed(search?'Choose an authorized saved question and enter 1–200 visible characters without surrounding spaces.':
        'Refresh the authorized case and saved questions before reading citation links.');return;
    }
    const current=()=>read===this.#evidenceRead&&scope===this.#scope&&selection===this.#read&&
      questionRead===this.#questionRead&&worldRead===this.#worldRead&&this.#state.patient?.patient_id===patientId&&
      this.#inspectionQuestionId===questionId&&this.#catalogSubject(questionId,family)?.row===subject.row;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish(search?{evidenceSearchPhase:'loading',evidenceSearchMessage:'Checking permission and searching fictional catalog metadata…'}:
      {evidenceLinksPhase:'loading',evidenceLinksMessage:'Rechecking saved citation versions and current metadata permissions…'});
    try{
      const base=this.#catalogPath(patientId,caseId,questionId,!!subject.laboratory);
      const res=await this.transport(base+(search?'/evidence-search':'/evidence-links'),
        this.#init(control,search?JSON.stringify({synthetic:true,query}):undefined));
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status!==200){
        if([403,404].includes(res.status)){
          if(subject.laboratory){this.#denyLaboratoryQuestionAccess('evidence');return;}
          const receipt=this.#state.evidenceLinkPhase==='saved'?this.#state.evidenceLinkReceipt:null;
          // A metadata-read denial cannot resolve a separately authorized write.
          // Keep only its opaque exact intent; retry rechecks link permission.
          this.#publish({...this.#resetEvidence(caseId),evidenceQuestionId:questionId,evidenceFamily:family,
            ...(receipt?{evidenceLinkReceipt:receipt,evidenceLinkPhase:'saved' as const,
              evidenceLinkMessage:'The citation save receipt is recorded. Current metadata access is unavailable.'}:{})});
        }
        failed('Evidence metadata is unavailable under current permissions or service state. No previous titles or links are shown.');return;
      }
      if(control.signal.aborted)throw Error('evidence timeout');
      const raw=await json(res,1048576),value=subject.laboratory?unwrapLaboratoryEvidence(raw,subject.laboratory,search):raw;
      const result=search?decodeQuestionEvidenceSearch(value,patientId,caseId,questionId,query):
        decodeQuestionEvidenceLinks(value,patientId,caseId,questionId);
      if(!current())return;if(control.signal.aborted)throw Error('evidence timeout');
      if(search){const found=result as QuestionEvidenceSearch;
        this.#publish({evidenceSearch:found,evidenceSearchPhase:'ready',evidenceSearchMessage:found.records.length?
          'Fictional metadata found. Inspect its exact citation and rights before saving a link.':
          'No fictional catalog metadata matched these terms. No conclusion follows from an empty search.'});
      }else{const found=result as QuestionEvidenceLinks;
        this.#publish({evidenceLinks:found,evidenceLinksPhase:'ready',evidenceLinksMessage:found.links.length?
          'Saved citation links read from the server. Availability is checked on every refresh.':
          'No citation links are currently recorded for this question.'});
      }
    }catch(_){if(current())failed('The evidence response could not be verified. No previous metadata is shown.');}
    finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }

  async saveQuestionEvidence(questionId:string,citation:string,family:'text'|'laboratory'='text'):Promise<void>{
    if(this.#savingEvidence)return;
    if(this.#state.evidenceLinkPhase==='unknown'){
      this.#publish({evidenceLinkMessage:'Retry the exact uncertain citation save or explicitly abandon recovery before recording another link.'});return;
    }
    const patientId=this.#state.patient?.patient_id,model=this.#state.worldModel,search=this.#state.evidenceSearch;
    const subject=this.#catalogSubject(questionId,family),question=subject?.row;
    const record=search?.records.find(item=>item.citation===citation);
    if(!this.#token||!patientId||!model||!subject||!question||!record||!search||this.#uploading||
       this.#state.phase!=='ready'||this.#state.worldPhase!=='ready'||this.#state.evidenceFamily!==family||
       this.#state.evidenceSearchPhase!=='ready'||this.#state.evidenceQuestionId!==questionId||search.question_id!==questionId||
       search.patient_id!==patientId||search.case_id!==model.case_id||subject.caseId!==model.case_id||
       search.source_context_state!=='current_unreviewed_question'||!subject.canSave||
       !this.#state.cases?.some(item=>item.case_id===model.case_id&&item.status==='active')){
      this.#publish({evidenceLinkReceipt:null,evidenceLinkPhase:'error',evidenceLinkMessage:
        'Inspect a current fictional search result for this exact saved question before saving. Changed source context requires reassessment.'});return;
    }
    const body=Object.freeze({synthetic:true as const,request_key:crypto.randomUUID(),citation:record.citation,
      expected_metadata_sha256:record.metadata_sha256,source_snapshot_contract:'oi.pg-source-world-model/1' as const,
      expected_source_snapshot_sha256:question.source_snapshot_sha256,expected_preflight_sha256:question.preflight_sha256});
    await this.#writeQuestionEvidence(Object.freeze({patient_id:patientId,case_id:model.case_id,question_id:questionId,body,
      ...(subject.laboratory?{laboratoryAnchor:laboratoryEvidenceAnchor(subject.laboratory)}:{})}));
  }

  async retryQuestionEvidenceLink():Promise<void>{
    const intent=this.#state.evidenceLinkIntent;
    if(this.#savingEvidence||this.#state.evidenceLinkPhase!=='unknown'||!intent)return;
    this.#focusSavedQuestion(intent.question_id);
    await this.#writeQuestionEvidence(intent,true);
  }

  abandonQuestionEvidenceLink=()=>{
    if(this.#savingEvidence||this.#state.evidenceLinkPhase!=='unknown')return;
    this.#evidenceWrite++;
    this.#publish({evidenceLinkIntent:null,evidenceLinkReceipt:null,evidenceLinkPhase:'idle',evidenceLinkMessage:
      'Recovery abandoned. This does not cancel or undo a save that may have committed. Refresh saved citations before starting another link.'});
  };

  async #writeQuestionEvidence(intent:QuestionEvidenceIntent,recovering=false):Promise<void>{
    const family=intent.laboratoryAnchor?'laboratory':'text';
    const subject=intent.laboratoryAnchor?this.#catalogSubject(intent.question_id,'laboratory'):null;
    if(!this.#token||this.#state.patient?.patient_id!==intent.patient_id||this.#state.phase!=='ready'||this.#uploading||
       (intent.laboratoryAnchor&&(!subject?.laboratory||subject.caseId!==intent.case_id||
         !matchesLaboratoryEvidenceAnchor(intent.laboratoryAnchor,subject.laboratory)))||
       !this.#state.cases?.some(item=>item.case_id===intent.case_id&&item.status==='active')){
      this.#publish({evidenceLinkMessage:'Recheck the authorized case before retrying. The exact earlier citation intent remains saved.'});return;
    }
    const write=++this.#evidenceWrite,scope=this.#scope,selection=this.#read;
    this.#evidenceRead++;this.#savingEvidence=true;
    const current=()=>write===this.#evidenceWrite&&scope===this.#scope&&selection===this.#read&&
      this.#state.patient?.patient_id===intent.patient_id&&this.#state.evidenceLinkIntent===intent&&
      this.#state.evidenceQuestionId===intent.question_id;
    const uncertain=()=>this.#publish({...emptyEvidenceMetadata(),evidenceLinkReceipt:null,evidenceLinkPhase:'unknown',
      evidenceLinkMessage:'Citation save outcome uncertain. Retry this exact intent to recover its original receipt. A new save is blocked until recovery or explicit abandonment.'});
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({...emptyEvidenceMetadata(),evidenceQuestionId:intent.question_id,evidenceFamily:family,evidenceLinkIntent:intent,
      evidenceLinkReceipt:null,evidenceLinkPhase:'saving',evidenceLinkMessage:recovering?
        'Recovering the exact earlier citation save under current permissions…':
        'Checking independent link permission and saving this exact metadata version…'});
    try{
      const url=this.#catalogPath(intent.patient_id,intent.case_id,intent.question_id,!!intent.laboratoryAnchor)+'/evidence-links';
      const res=await this.transport(url,this.#init(control,JSON.stringify(intent.body)));
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if(intent.laboratoryAnchor&&[403,404].includes(res.status)){this.#denyLaboratoryQuestionAccess('evidence');return;}
      if([400,403,404,409,413,422].includes(res.status)){
        if(recovering){
          uncertain();
          this.#publish({evidenceLinkMessage:
            'This retry was refused under current permissions or source/input state. The earlier save outcome is still uncertain. Recheck access and retry this exact intent, or explicitly abandon recovery.'});
          return;
        }
        this.#publish({...this.#resetEvidence(),evidenceQuestionId:intent.question_id,evidenceFamily:family,evidenceLinkPhase:'error',
          evidenceLinkMessage:res.status===409?
            'The metadata, source context or request intent changed. Refresh the question and catalog before a new save.':
            'The citation save was refused by the current permission or input contract. No successful link is assumed.'});return;
      }
      if(![200,201].includes(res.status)||control.signal.aborted){uncertain();return;}
      const receipt=decodeQuestionEvidenceReceipt(await json(res),intent);
      if(!current())return;if(control.signal.aborted){uncertain();return;}
      if((res.status===200)!==receipt.duplicate)throw Error('evidence receipt status');
      this.#publish({evidenceLinkReceipt:receipt,evidenceLinkIntent:null,evidenceLinkPhase:'saved',evidenceLinkMessage:receipt.duplicate?
        'Original citation receipt recovered. The same request was not saved twice.':
        'Citation link saved. Its content was not appraised, no model ran, and no clinical approval was created.'});
      this.#savingEvidence=false;
      await this.loadQuestionEvidenceLinks(intent.question_id,family);
    }catch(_){if(current())uncertain();}
    finally{clearTimeout(timeout);this.#controllers.delete(control);
      if(write===this.#evidenceWrite&&scope===this.#scope)this.#savingEvidence=false;}
  }

  /** A fresh task projection requires its own grant. A patient read never grants it. */
  async loadFollowthrough(caseId:string):Promise<void>{
    if(this.#savingFollowthrough)return;
    if(this.#state.followthroughCaseId!==caseId)this.#publish(this.#resetFollowthrough(caseId));
    const query=++this.#followRead,scope=this.#scope,selection=this.#read;
    const patientId=this.#state.patient?.patient_id;
    this.#publish({followthrough:null,followthroughPhase:'idle',followthroughMessage:'Checking current follow-up access…'});
    // Temporary metadata loss neither authorizes another read nor discards an
    // uncertain write captured for this same patient and case.
    const intent=this.#state.followthroughIntent;
    if(this.#token&&patientId&&this.#state.phase==='ready'&&this.#state.cases===null&&
       intent?.patient_id===patientId&&intent.case_id===caseId&&this.#state.followthroughWritePhase==='unknown'){
      this.#publish({followthroughPhase:'error',followthroughMessage:
        'Recheck authorized cases before refreshing recorded work. The exact earlier write remains saved.'});return;
    }
    if(!this.#token||!patientId||this.#state.phase!=='ready'||this.#uploading||
       !/^CASE-[A-Z0-9-]{1,35}$/.test(caseId)||
       !this.#state.cases?.some(item=>item.case_id===caseId&&item.status==='active')){
      this.#publish({...this.#resetFollowthrough(),followthroughPhase:'error',
        followthroughMessage:'Open an authorized patient and active case before reading recorded work.'});return;
    }
    const current=()=>query===this.#followRead&&scope===this.#scope&&selection===this.#read&&
      this.#state.patient?.patient_id===patientId&&this.#state.followthroughCaseId===caseId;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({followthroughPhase:'loading',followthroughMessage:'Checking separate task, question and source permissions…'});
    try{
      const url='/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+encodeURIComponent(caseId)+'/followthrough';
      const init=this.#init(control);init.headers={...init.headers,Accept:FOLLOWTHROUGH_V2_MEDIA+', application/json;q=0.9'};
      const res=await this.transport(url,init);
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status!==200){
        this.#publish({...([403,404].includes(res.status)?this.#resetFollowthrough():{}),followthrough:null,
          followthroughPhase:'error',followthroughMessage:'Recorded work is unavailable under current permissions. Prior task content is cleared.'});return;
      }
      if(control.signal.aborted)throw Error('task timeout');
      const value=decodeFollowthrough(await json(res,4194304,FOLLOWTHROUGH_V2_MEDIA),patientId,caseId);
      if(!current())return;if(control.signal.aborted)throw Error('task timeout');
      this.#publish({followthrough:value,followthroughPhase:'ready',
        followthroughTransitionDrafts:Object.freeze(Object.fromEntries(Object.entries(this.#state.followthroughTransitionDrafts)
          .filter(([id,draft])=>draft.patient_id===patientId&&draft.case_id===caseId&&value.tasks.some(task=>
            task.task_id===id&&draft.context===followthroughTransitionContext(task))))),
        followthroughMessage:value.tasks.length?
        'Recorded work and attributed history, checked at this read. Source changes do not approve a new conclusion.':
        'No follow-up tasks are visible for this case.'});
    }catch(_){if(current())this.#publish({followthrough:null,followthroughPhase:'error',
      followthroughMessage:'The task response could not be verified. Earlier task content and controls are unavailable.'});}
    finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }

  #followthroughBlocked():boolean{
    if(this.#savingFollowthrough)return true;
    if(this.#state.followthroughWritePhase==='unknown'){
      this.#publish({followthroughWriteMessage:'Resolve the uncertain write using Retry exact write or explicitly abandon recovery before editing or recording different work.'});
      return true;
    }
    return false;
  }

  /** Memory only; no command or request key is allocated until explicit submission. */
  editFollowthroughDraft(questionId:string,fields:FollowthroughDraft,family:FollowthroughFamily='text'):void{
    if(this.#followthroughBlocked())return;
    const model=this.#state.worldModel,question=currentFollowthroughQuestion(this.#state,questionId,family);
    if(!this.#token||this.#uploading||!model||!question)return;
    const draft=Object.freeze({patient_id:model.patient_id,case_id:model.case_id,
      source_snapshot_sha256:question.source_snapshot_sha256,preflight_sha256:question.preflight_sha256,
      ...('observation_reference' in question?{laboratoryAnchor:followthroughLaboratoryAnchor(question)}:{}),
      fields:Object.freeze({...fields})});
    this.#publish({followthroughCaseId:model.case_id,
      followthroughDrafts:Object.freeze({...this.#state.followthroughDrafts,[questionId]:draft})});
  }

  clearFollowthroughDraft(questionId:string):void{
    if(this.#followthroughBlocked())return;
    const drafts={...this.#state.followthroughDrafts};delete drafts[questionId];
    this.#publish({followthroughDrafts:Object.freeze(drafts)});
  }

  async createFollowthrough(questionId:string,draft:FollowthroughDraft,family:FollowthroughFamily='text'):Promise<void>{
    if(this.#followthroughBlocked())return;
    const model=this.#state.worldModel,question=currentFollowthroughQuestion(this.#state,questionId,family);
    if(!this.#token||this.#uploading||!model||!question||!validFollowthroughDraft(draft)){
      this.#publish({followthroughWritePhase:'error',followthroughReceipt:null,followthroughWriteMessage:
        'Use a current saved question, a 3–160 character title, a 3–600 character reason, and a valid due date or review trigger.'});return;
    }
    const body=Object.freeze({synthetic:true as const,request_key:crypto.randomUUID(),title:draft.title,
      detail:draft.detail,owner_label:draft.owner_label,due_date:draft.due_date,review_trigger:draft.review_trigger,
      reason:draft.reason,source_snapshot_contract:'oi.pg-source-world-model/1' as const,
      expected_source_snapshot_sha256:question.source_snapshot_sha256,expected_preflight_sha256:question.preflight_sha256});
    await this.#writeFollowthrough(Object.freeze({kind:'create',patient_id:model.patient_id,case_id:model.case_id,question_id:questionId,body}));
  }

  editFollowthroughTransitionDraft(taskId:string,fields:FollowthroughTransitionFields):void{
    if(this.#followthroughBlocked())return;
    const patientId=this.#state.patient?.patient_id,list=this.#state.followthrough;
    const task=list?.tasks.find(item=>item.task_id===taskId);
    if(!this.#token||!patientId||this.#state.phase!=='ready'||this.#uploading||
       this.#state.followthroughPhase!=='ready'||!list||list.patient_id!==patientId||!task||
       FOLLOWTHROUGH_TRANSITIONS[task.status].length===0||
       !this.#state.cases?.some(row=>row.case_id===list.case_id&&row.status==='active'))return;
    const draft=Object.freeze({patient_id:patientId,case_id:list.case_id,
      context:followthroughTransitionContext(task),fields:Object.freeze({...fields})});
    this.#publish({followthroughTransitionDrafts:Object.freeze({...this.#state.followthroughTransitionDrafts,[taskId]:draft})});
  }

  clearFollowthroughTransitionDraft(taskId:string):void{
    if(this.#followthroughBlocked())return;
    const drafts={...this.#state.followthroughTransitionDrafts};delete drafts[taskId];
    this.#publish({followthroughTransitionDrafts:Object.freeze(drafts)});
  }

  async transitionFollowthrough(taskId:string,draft:FollowthroughTransition):Promise<void>{
    if(this.#followthroughBlocked())return;
    const patientId=this.#state.patient?.patient_id,list=this.#state.followthrough;
    const task=list?.tasks.find(item=>item.task_id===taskId);
    if(!patientId||!this.#token||this.#state.phase!=='ready'||this.#uploading||
       this.#state.followthroughPhase!=='ready'||!list||list.patient_id!==patientId||!task||
       !validFollowthroughTransition(task,draft)||
       !this.#state.cases?.some(row=>row.case_id===list.case_id&&row.status==='active')){
      this.#publish({followthroughWritePhase:'error',followthroughReceipt:null,followthroughWriteMessage:
        'Refresh recorded work and choose a legal next status with a reason. Assignment requires an owner; completion requires acknowledgment.'});return;
    }
    const body=Object.freeze({synthetic:true as const,request_key:crypto.randomUUID(),expected_revision:task.revision,
      status:draft.status,owner_label:draft.status==='assigned'?draft.owner_label:'',reason:draft.reason});
    await this.#writeFollowthrough(Object.freeze({kind:'transition',patient_id:patientId,case_id:list.case_id,
      question_id:task.question_id,task_id:taskId,body}));
  }

  async retryFollowthroughWrite():Promise<void>{
    const intent=this.#state.followthroughIntent;
    if(this.#savingFollowthrough||this.#state.followthroughWritePhase!=='unknown'||!intent)return;
    await this.#writeFollowthrough(intent,true);
  }

  abandonFollowthroughWrite=()=>{
    if(this.#state.followthroughWritePhase!=='unknown'||this.#savingFollowthrough)return;
    this.#followWrite++;
    this.#publish({followthroughIntent:null,followthroughReceipt:null,followthroughWritePhase:'idle',
      followthroughWriteMessage:'Recovery abandoned. This does not cancel or undo a write that may have committed. Check current task history before recording new work.'});
  };

  async #writeFollowthrough(intent:FollowthroughIntent,recovering=false):Promise<void>{
    if(!this.#token||this.#state.patient?.patient_id!==intent.patient_id||this.#state.phase!=='ready'||this.#uploading||
       !this.#state.cases?.some(row=>row.case_id===intent.case_id&&row.status==='active'))return;
    const query=++this.#followWrite,scope=this.#scope,selection=this.#read;
    this.#followRead++;this.#savingFollowthrough=true;
    const current=()=>query===this.#followWrite&&scope===this.#scope&&selection===this.#read&&
      this.#state.patient?.patient_id===intent.patient_id&&this.#state.followthroughIntent===intent&&
      this.#state.followthroughCaseId===intent.case_id;
    const uncertain=()=>this.#publish({followthrough:null,followthroughReceipt:null,followthroughPhase:'idle',
      followthroughWritePhase:'unknown',followthroughWriteMessage:
        'Write outcome uncertain. Retry the exact recorded intent to recover its receipt without creating another request. Edits are blocked until recovery or explicit abandonment.'});
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);
    this.#publish({followthrough:null,followthroughCaseId:intent.case_id,followthroughPhase:'idle',
      followthroughReceipt:null,followthroughIntent:intent,followthroughWritePhase:'saving',
      followthroughWriteMessage:recovering?'Recovering the exact earlier write under current permissions…':
        'Checking independent write permission and exact source context or task revision…'});
    try{
      const base='/v1/patients/'+encodeURIComponent(intent.patient_id)+'/cases/'+encodeURIComponent(intent.case_id);
      const url=base+(intent.kind==='create'?'/questions/'+encodeURIComponent(intent.question_id)+'/followthrough':
        '/followthrough/'+encodeURIComponent(intent.task_id)+'/transitions');
      const res=await this.transport(url,this.#init(control,JSON.stringify(intent.body)));
      if(!current())return;
      if(res.status===401){this.#httpError(401);return;}
      if([400,403,404,409,413,422].includes(res.status)){
        const drafts=this.#state.followthroughDrafts,transitionDrafts=this.#state.followthroughTransitionDrafts;
        this.#publish({...this.#resetFollowthrough(),...(![403,404].includes(res.status)?
          {followthroughDrafts:drafts,followthroughTransitionDrafts:transitionDrafts}:{}),
          followthroughCaseId:intent.case_id,followthroughWritePhase:'error',followthroughWriteMessage:res.status===409?
          'The saved source context, task revision or request intent changed. Refresh the case and recorded work before a new action.':
          'This write was refused by the current grant or input contract. No successful action is assumed.'});return;
      }
      if(![200,201].includes(res.status)||control.signal.aborted){uncertain();return;}
      const saved=decodeFollowthroughReceipt(await json(res),intent);
      if(!current())return;if(control.signal.aborted){uncertain();return;}
      if((res.status===200)!==saved.duplicate)throw Error('task receipt status');
      const drafts={...this.#state.followthroughDrafts},transitionDrafts={...this.#state.followthroughTransitionDrafts};
      if(intent.kind==='create')delete drafts[intent.question_id];
      else delete transitionDrafts[intent.task_id];
      this.#publish({followthroughDrafts:Object.freeze(drafts),followthroughTransitionDrafts:Object.freeze(transitionDrafts),
        followthroughReceipt:saved,followthroughIntent:null,followthroughWritePhase:'saved',followthroughWriteMessage:saved.duplicate?
        'Original task receipt recovered. The same request was not recorded twice.':
        'Follow-up work recorded. No clinical approval, order or external notification was created.'});
      this.#savingFollowthrough=false;
      await this.loadFollowthrough(intent.case_id);
    }catch(_){if(current())uncertain();}
    finally{clearTimeout(timeout);this.#controllers.delete(control);
      if(query===this.#followWrite&&scope===this.#scope)this.#savingFollowthrough=false;}
  }

  async backgroundBriefAction(questionId: string, action: RunAction): Promise<void> {
    this.#focusSavedQuestion(questionId);
    const world = this.#state.worldModel;
    const question = this.#state.questions?.find(item => item.question_id === questionId);
    const view = this.#state.backgroundBrief;
    const previous = view?.questionId === questionId ? view.status : null;
    if (!world || !question || !this.#token || this.#state.phase !== 'ready' || this.#state.worldPhase !== 'ready' ||
        this.#state.questionListPhase !== 'ready' || this.#state.questionsCaseId !== world.case_id ||
        this.#state.patient?.patient_id !== world.patient_id || question.patient_id !== world.patient_id ||
        question.case_id !== world.case_id || question.source_snapshot_contract !== 'oi.pg-source-world-model/1' ||
        view?.busy || this.#uploading || this.#savingQuestion) return;
    const enqueue = action === 'enqueue' || action === 'retry';
    if ((action !== 'enqueue' && action !== 'latest' && !previous) ||
        (action === 'retry' && (!previous || !canRetryRun(previous.state))) ||
        (action === 'cancel' && previous?.state !== 'queued' && previous?.state !== 'running') ||
        (action === 'result' && previous?.state !== 'completed') ||
        ((action === 'result' || enqueue) && !canPrepareSourceBrief(question, world))) return;

    const query = ++this.#briefRead;
    const scope = this.#scope;
    const patientRead = this.#read;
    const current = () => query === this.#briefRead && scope === this.#scope && patientRead === this.#read &&
      this.#state.worldModel === world && this.#state.questions?.find(q => q.question_id === questionId) === question;
    const control = new AbortController();
    this.#controllers.add(control);
    const timeout = setTimeout(() => control.abort(), 10000);
    const pending = {questionId, status: previous, result: null, busy: true, message: 'Checking current access…'};
    this.#publish({...emptyBrief(), backgroundBrief: pending});
    try {
      const base = '/v1/patients/' + encodeURIComponent(question.patient_id) + '/cases/' +
        encodeURIComponent(question.case_id) + '/questions/' + encodeURIComponent(questionId) + '/runs';
      // The server scopes this key to the actor, organization and purpose. Reopening after a
      // lost response or reload repeats the exact intent without retaining any patient data locally.
      let path = base;
      let body: string | undefined;
      if (enqueue) {
        body = JSON.stringify({synthetic: true, request_key: 'web-brief-v1-' +
          (action === 'retry' ? previous!.run_id : questionId),
          source_snapshot_contract: question.source_snapshot_contract,
          expected_source_snapshot_sha256: question.source_snapshot_sha256,
          expected_preflight_sha256: question.preflight_sha256});
      } else if (action !== 'latest') {
        path += '/' + previous!.run_id;
        if (action === 'cancel') { path += '/cancel'; body = JSON.stringify({synthetic: true}); }
        if (action === 'result') path += '/result';
      }
      const response = await this.transport(path, this.#init(control, body));
      if (!current()) { void response.body?.cancel().catch(() => {}); return; }
      if (response.status === 401) { this.#httpError(401); return; }
      if (response.status === 403 || response.status === 404) {
        if (action === 'latest') {
          await this.#recheckQuestionDenial(world.case_id, control, 'questions', {
            briefPhase: 'error', briefMessage: 'No previous background run is visible under current access.'});
        } else {
          await this.#recheckQuestionDenial(world.case_id, control, 'case', {
            briefPhase: 'error', briefMessage: 'Background brief unavailable under current access. Reopen the case to check again.'});
        }
        return;
      }
      if (response.status === 409) {
        this.#resetWorld(world.case_id);
        this.#publish({briefPhase: 'error', briefMessage: 'The source or run changed. Refresh the case before reopening the brief.'});
        return;
      }
      if (control.signal.aborted || (enqueue ? ![200, 201].includes(response.status) : response.status !== 200))
        throw Error('Run unavailable');
      const value = await json(response, 73728);
      const result = action === 'result' ? await readRunResult(value, previous!, world, question) : null;
      const status = enqueue ? readRunReceipt(value, response.status, question) :
        result ? previous! : readRunStatus(value, question, action === 'latest' ? undefined : previous!);
      if (action === 'cancel' && (status.state === 'queued' || status.state === 'running'))
        throw Error('Cancellation returned active work');
      if (action === 'retry' && status.run_id === previous!.run_id) throw Error('Replacement returned its predecessor');
      if (!current()) return;
      if (control.signal.aborted) throw Error('Run request timed out');
      this.#publish({backgroundBrief: {questionId, status, result, busy: false, message: ''}});
    } catch {
      if (current()) this.#publish({backgroundBrief: {...pending, busy: false, message: enqueue ?
        'Queue outcome unknown. Repeat the same action to recover its receipt.' :
        'The latest response could not be verified. Check the run again.'}});
    } finally {
      clearTimeout(timeout);
      this.#controllers.delete(control);
    }
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
        const failure={briefPhase:'error' as const,briefMessage:res.status===409?
          'The source changed. Refresh Investigations and use a current saved question before preparing a new brief.':
          'Source brief unavailable under current authority. No earlier preview can be downloaded.'};
        if(res.status===403||res.status===404)await this.#recheckQuestionDenial(model.case_id,control,'case',failure);
        else{this.#resetWorld(model.case_id);this.#publish(failure);}
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
  #resetSourceImages(){this.#imageRead++;this.#imageDownload++;this.#imagePreview++;return emptySourceImages();}
  dismissSourceImages=()=>this.#publish(this.#resetSourceImages());
  async loadSourceImages(sourceId:string):Promise<void>{
    const patientId=this.#state.patient?.patient_id,index=this.#state.sourceIndex;
    const source=index?.sources.find(item=>item.source_id===sourceId);
    this.#publish(this.#resetSourceImages());
    if(!this.#token||!patientId||this.#state.phase!=='ready'||!index||!source||
       source.kind!=='imaging'||source.state!=='current'||this.#uploading||
       !this.#state.cases?.some(item=>item.case_id===index.case_id&&item.status==='active')){
      this.#publish({sourceImagesPhase:'error',sourceImagesMessage:'Choose a current imaging report in the authorized case first.'});return;
    }
    const scope=this.#scope,read=this.#read,request=this.#imageRead,caseId=index.case_id;
    const current=()=>scope===this.#scope&&read===this.#read&&request===this.#imageRead&&
      this.#state.patient?.patient_id===patientId&&this.#state.sourceIndex===index;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>{control.abort();if(current())this.#publish({sourceImages:null,
      sourceImagesPhase:'error',sourceImagesMessage:'Image metadata request timed out. Recheck the source and try again.'});},10000);
    this.#publish({sourceImagesSourceId:sourceId,sourceImagesPhase:'loading',sourceImagesMessage:'Checking linked image metadata and its current permission…'});
    try{
      const res=await this.transport('/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+encodeURIComponent(caseId)+'/sources/'+encodeURIComponent(sourceId)+'/images',this.#init(control));
      if(!current()||control.signal.aborted)return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status!==200){this.#publish({sourceImages:null,sourceImagesPhase:'error',sourceImagesMessage:'Linked images unavailable or permission denied. No earlier image list is retained.'});return;}
      const sourceImages=decodeSourceImages(await json(res,524288),patientId,caseId,source);
      if(!current()||control.signal.aborted)return;
      this.#publish({sourceImages,sourceImagesPhase:'ready',sourceImagesMessage:'Linked original metadata checked for this source. Original bytes require a separate fresh read; images have not been interpreted.'});
    }catch(_){if(current()&&!control.signal.aborted)this.#publish({sourceImages:null,sourceImagesPhase:'error',sourceImagesMessage:'Image metadata could not be verified or the service is unavailable. Recheck the source before retrying.'});}
    finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }
  async downloadSourceImage(sourceId:string,imageId:string):Promise<void>{
    const patientId=this.#state.patient?.patient_id,index=this.#state.sourceIndex,images=this.#state.sourceImages;
    const source=index?.sources.find(item=>item.source_id===sourceId),image=images?.images.find(item=>item.image_id===imageId);
    const request=++this.#imageDownload;
    this.#publish({sourceImageDownload:null,sourceImageDownloadPhase:'idle',sourceImageDownloadMessage:''});
    if(!this.#token||!patientId||this.#state.phase!=='ready'||!index||!source||
       source.kind!=='imaging'||source.state!=='current'||!images||!image||this.#uploading||
       images.patient_id!==patientId||images.case_id!==index.case_id||images.source_id!==sourceId||
       this.#state.sourceImagesPhase!=='ready'||!this.#state.cases?.some(item=>item.case_id===index.case_id&&item.status==='active')){
      this.#publish({sourceImageDownloadPhase:'error',sourceImageDownloadMessage:'Inspect the exact current source image list before requesting original bytes.'});return;
    }
    const scope=this.#scope,read=this.#read,imageRead=this.#imageRead,caseId=index.case_id;
    const current=()=>scope===this.#scope&&read===this.#read&&request===this.#imageDownload&&imageRead===this.#imageRead&&
      this.#state.patient?.patient_id===patientId&&this.#state.sourceIndex===index&&this.#state.sourceImages===images;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>{control.abort();if(current())this.#publish({sourceImageDownload:null,
      sourceImageDownloadPhase:'error',sourceImageDownloadMessage:'Original image request timed out. Nothing was downloaded. Recheck and try again.'});},10000);
    this.#publish({sourceImageDownloadPhase:'loading',sourceImageDownloadMessage:'Rechecking original-image permission and exact bytes before download…'});
    try{
      const init=this.#init(control);init.headers={...init.headers,Accept:'application/dicom'};
      const res=await this.transport('/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+encodeURIComponent(caseId)+'/sources/'+encodeURIComponent(sourceId)+'/images/'+encodeURIComponent(imageId),init);
      if(!current()||control.signal.aborted)return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status===403||res.status===404)this.dismissSourceImagePreview();
      if(res.status!==200){this.#publish({sourceImageDownload:null,sourceImageDownloadPhase:'error',sourceImageDownloadMessage:'Original image unavailable or permission denied. No cached bytes were downloaded.'});return;}
      const verified=await readSourceImageOriginal(res,image);
      if(!current()||control.signal.aborted)return;
      const url=URL.createObjectURL(new Blob([verified.bytes],{type:'application/dicom'}));
      try{const link=document.createElement('a');link.href=url;link.download='open-intelligence-original-'+imageId+'.dcm';
        document.body.append(link);link.click();link.remove();}
      finally{URL.revokeObjectURL(url);}
      this.#publish({sourceImageDownload:Object.freeze({patient_id:patientId,case_id:caseId,source_id:sourceId,image_id:imageId,
        sha256:image.sha256,byte_count:image.byte_count,access_receipt_id:verified.accessReceiptId}),sourceImageDownloadPhase:'ready',
        sourceImageDownloadMessage:'Exact original bytes verified and offered for download. This read receipt is not continuing access or clinical approval.'});
    }catch(_){if(current()&&!control.signal.aborted)this.#publish({sourceImageDownload:null,sourceImageDownloadPhase:'error',sourceImageDownloadMessage:'Original image failed byte verification or could not be downloaded. No previous original is reused.'});}
    finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }
  dismissSourceImagePreview=()=>{
    this.#imagePreview++;
    this.#publish({sourceImagePreview:null,sourceImagePreviewPhase:'idle',sourceImagePreviewMessage:''});
  };
  async previewSourceImage(sourceId:string,imageId:string):Promise<void>{
    const patientId=this.#state.patient?.patient_id,index=this.#state.sourceIndex,images=this.#state.sourceImages;
    const source=index?.sources.find(item=>item.source_id===sourceId),image=images?.images.find(item=>item.image_id===imageId);
    const request=++this.#imagePreview;
    this.#publish({sourceImagePreview:null,sourceImagePreviewPhase:'idle',sourceImagePreviewMessage:''});
    if(!this.#token||!patientId||this.#state.phase!=='ready'||!index||!source||
       source.kind!=='imaging'||source.state!=='current'||!images||!image||this.#uploading||
       images.patient_id!==patientId||images.case_id!==index.case_id||images.source_id!==sourceId||
       this.#state.sourceImagesPhase!=='ready'||!this.#state.cases?.some(item=>item.case_id===index.case_id&&item.status==='active')){
      this.#publish({sourceImagePreviewPhase:'error',sourceImagePreviewMessage:'Inspect the exact current source image list before requesting a preview.'});return;
    }
    const scope=this.#scope,read=this.#read,imageRead=this.#imageRead,caseId=index.case_id;
    const current=()=>scope===this.#scope&&read===this.#read&&request===this.#imagePreview&&imageRead===this.#imageRead&&
      this.#state.patient?.patient_id===patientId&&this.#state.sourceIndex===index&&this.#state.sourceImages===images;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>{control.abort();if(current())this.#publish({sourceImagePreview:null,
      sourceImagePreviewPhase:'error',sourceImagePreviewMessage:'Preview request timed out. No image is shown; recheck and try again.'});},10000);
    this.#publish({sourceImagePreviewPhase:'loading',sourceImagePreviewMessage:'Rechecking original-image permission and generating a bounded non-diagnostic preview…'});
    try{
      const init=this.#init(control);init.headers={...init.headers,Accept:'image/png'};
      const res=await this.transport('/v1/patients/'+encodeURIComponent(patientId)+'/cases/'+encodeURIComponent(caseId)+
        '/sources/'+encodeURIComponent(sourceId)+'/images/'+encodeURIComponent(imageId)+'/preview',init);
      if(!current()||control.signal.aborted)return;
      if(res.status===401){this.#httpError(401);return;}
      if(res.status===403||res.status===404){
        this.#imageDownload++;
        this.#publish({sourceImageDownload:null,sourceImageDownloadPhase:'idle',sourceImageDownloadMessage:''});
      }
      if(res.status!==200){this.#publish({sourceImagePreview:null,sourceImagePreviewPhase:'error',
        sourceImagePreviewMessage:'Preview unavailable or permission denied. No earlier pixels are reused.'});return;}
      const verified=await readSourceImagePreview(res,image);
      if(!current()||control.signal.aborted)return;
      this.#publish({sourceImagePreview:Object.freeze({patient_id:patientId,case_id:caseId,source_id:sourceId,image_id:imageId,
        original_sha256:image.sha256,access_receipt_id:verified.accessReceiptId,png_bytes:verified.bytes}),
        sourceImagePreviewPhase:'ready',
        sourceImagePreviewMessage:'Non-diagnostic preview generated from the freshly authorized original. It is not a clinical display or interpretation.'});
    }catch(_){if(current()&&!control.signal.aborted)this.#publish({sourceImagePreview:null,sourceImagePreviewPhase:'error',
      sourceImagePreviewMessage:'Preview failed verification or could not be generated. No previous pixels are reused.'});}
    finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }

  dismissOriginal=()=>{
    this.#records++;
    this.#publish({...(this.#state.worldPhase==='loading'?emptyWorld():{}),original:null,recordsPhase:'ready'});
  };
  async loadOriginal(sourceId:string,expectedObservation?:string):Promise<void>{
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
      const subject=this.#state.cases?.find(item=>item.case_id===caseId&&item.status==='active')?.source_subject_ref;
      const original=await verifyOriginal(await json(res,524288),caseId,source,subject?'Patient/'+subject:undefined,expectedObservation);
      if(!current())return;
      this.#publish({original,recordsPhase:'ready',recordMessage:'Exact original bytes verified against the selected source hash. Clinical review remains not established.'});
    }catch(_){if(current())this.#publish({original:null,recordsPhase:'error',recordMessage:'Original failed verification or service unavailable. Reload metadata before trying again.'});}
    finally{clearTimeout(timeout);this.#controllers.delete(control);}
  }
  async previewLaboratory(caseId:string,file:LaboratoryFile) {
    const index=this.#state.sourceIndex;
    const binding=this.#state.cases?.find(row=>row.case_id===caseId && row.status==='active');
    if(!index || index.case_id!==caseId || !binding || binding.patient_id!==this.#state.patient?.patient_id ||
       index.patient_id!==binding.patient_id) throw Error('Recheck patient and case access');
    const reply=await this.#caseContentRequest(caseId,'/laboratory/fhir-r4/preview',
      JSON.stringify({synthetic:true,bundle_json:file.text}));
    if(reply.status===422) throw new LaboratoryPreviewRejected(LABORATORY_PREVIEW_REJECTED);
    if(reply.status!==200 || this.#state.sourceIndex!==index) throw Error('Laboratory preview unavailable.');
    return readLaboratoryPreview(reply.body,file,binding);
  }
  /** Preserve one exact in-memory command until its receipt is known or this patient/case is withdrawn. */
  async importLaboratory(caseId:string,text:string,confirmed:boolean,previousSourceId:string|null=null):Promise<void>{
    if(this.#laboratoryWriting||this.#uploading)return;
    if(this.#state.laboratoryPhase==='unknown'){
      this.#publish({laboratoryMessage:'Resolve the uncertain import with Retry exact import before choosing another original.'});return;
    }
    const patientId=this.#state.patient?.patient_id,index=this.#state.sourceIndex;
    if(!patientId||!this.#token||this.#state.phase!=='ready'||index?.case_id!==caseId||
       !this.#state.cases?.some(row=>row.case_id===caseId&&row.status==='active')||confirmed!==true||
       (previousSourceId!==null&&!index.sources.some(row=>row.source_id===previousSourceId&&row.kind==='laboratory'&&row.state==='current'))){
      this.#publish({laboratoryPhase:'error',laboratoryReceipt:null,laboratoryMessage:'Choose the authorized case, inspect the fictional original and confirm its source version.'});return;
    }
    const scope=this.#scope,read=this.#read,records=this.#records,preparing=++this.#laboratoryWrite;
    this.#laboratoryWriting=true;
    try{
      const file=await prepareLaboratoryFile(new TextEncoder().encode(text),'original.json');
      if(file.text!==text)throw Error('changed bytes');
      if(preparing!==this.#laboratoryWrite||scope!==this.#scope||read!==this.#read||records!==this.#records||this.#state.sourceIndex!==index)return;
      const body=JSON.stringify({synthetic:true,request_key:crypto.randomUUID(),
        expected_previous_source_id:previousSourceId,bundle_json:file.text});
      if(new TextEncoder().encode(body).length>524288)throw Error('envelope');
      const intent=Object.freeze({patient_id:patientId,case_id:caseId,body,sha256:file.sha256});
      this.#laboratoryWriting=false;
      await this.#sendLaboratory(intent);
    }catch(_){if(scope===this.#scope&&read===this.#read&&records===this.#records)
      this.#publish({laboratoryPhase:'error',laboratoryReceipt:null,laboratoryMessage:'Unsupported original JSON. Nothing was sent.'});}
    finally{if(preparing===this.#laboratoryWrite&&scope===this.#scope)this.#laboratoryWriting=false;}
  }
  async retryLaboratoryImport():Promise<void>{
    if(this.#state.laboratoryPhase!=='unknown'||!this.#state.laboratoryIntent)return;
    await this.#sendLaboratory(this.#state.laboratoryIntent);
  }
  async #sendLaboratory(intent:LaboratoryIntent):Promise<void>{
    if(this.#laboratoryWriting||this.#uploading)return;
    if(!this.#token||this.#state.phase!=='ready'||this.#state.patient?.patient_id!==intent.patient_id||
       this.#state.sourceIndex?.case_id!==intent.case_id||
       !this.#state.cases?.some(row=>row.case_id===intent.case_id&&row.status==='active')){
      this.#publish({laboratoryMessage:'Recheck this patient and case before recovering the exact import.'});return;
    }
    const write=++this.#laboratoryWrite,scope=this.#scope,read=this.#read;
    this.#records++;
    // The command's generation and selected scope govern its response. A blocked
    // World Model read can advance the metadata counter without changing this command.
    const current=()=>write===this.#laboratoryWrite&&scope===this.#scope&&read===this.#read&&
      this.#state.patient?.patient_id===intent.patient_id&&this.#state.sourceIndex?.case_id===intent.case_id;
    const control=new AbortController();this.#controllers.add(control);
    const timeout=setTimeout(()=>control.abort(),10000);this.#laboratoryWriting=true;this.#uploading=true;
    this.#publish({...emptyWorld(),...this.#resetInvestigation(intent.case_id),original:null,
      laboratoryPhase:'sending',laboratoryIntent:intent,laboratoryReceipt:null,
      laboratoryMessage:'Saving the exact fictional laboratory original under current source-import permission…'});
    const uncertain=()=>this.#publish({laboratoryPhase:'unknown',laboratoryReceipt:null,
      laboratoryMessage:'Import outcome unknown. It may have been saved. Retry the exact saved request to recover its receipt; nothing was automatically retried.'});
    try{
      const response=await this.transport('/v1/patients/'+encodeURIComponent(intent.patient_id)+'/cases/'+
        encodeURIComponent(intent.case_id)+'/laboratory/fhir-r4/sources',this.#init(control,intent.body));
      if(!current())return;
      if(response.status===401){this.#httpError(401);return;}
      if([403,404].includes(response.status)){
        this.#publish({...emptyRecords(),...this.#resetInvestigation(),recordsPhase:'error',
          recordMessage:'Laboratory import permission or case binding unavailable. Reload current access.'});return;
      }
      if([409,413,422].includes(response.status)){
        this.#publish({laboratoryPhase:'error',laboratoryIntent:null,laboratoryReceipt:null,
          laboratoryMessage:'This request was rejected. Inspect the supported format and current predecessor before a new import.'});return;
      }
      if(![200,201].includes(response.status)){uncertain();return;}
      const receipt=parseLaboratoryReceipt(await json(response),intent.sha256,response.status);
      if(!current())return;
      this.#publish({laboratoryPhase:'saved',laboratoryReceipt:receipt,
        laboratoryMessage:receipt.duplicate?'Original import receipt recovered; no duplicate source version was created.':
          'Laboratory original saved. Results remain source-reported and unreviewed.'});
      // A new original invalidates cached clinical context. Refresh only the same live case.
      await this.loadSources(intent.case_id);
    }catch(_){if(current())uncertain();}
    finally{clearTimeout(timeout);this.#controllers.delete(control);
      if(write===this.#laboratoryWrite&&scope===this.#scope){this.#laboratoryWriting=false;this.#uploading=false;}}
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
        if([403,404].includes(res.status))this.#clearManualDrafts();
        this.#publish({cases:null,sourceIndex:null,original:null,recordsPhase:'error',importOutcome:'rejected',
          ...([403,404].includes(res.status)?{...emptyLaboratory(),...this.#resetLabQuestions(),...this.#resetReview(),...this.#resetFollowthrough(),...this.#resetEvidence(),...this.#evidenceSession.reset()}:{}),
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
