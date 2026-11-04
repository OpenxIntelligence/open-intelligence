/** Transient evidence operations within RegistrySession's existing request scope. */
import type {ViewState} from './registry-client.js';
import type {SourceQuestion} from './source-questions-view.js';
import {decodeEvidencePacket,decodeEvidenceReport,decodeEvidenceOriginal,decodeEvidenceReceipt,
 canonicalEvidenceJson,visibleLine} from './authored-evidence.js';
import type {EvidencePacket,EvidenceReport,EvidenceOriginal,EvidenceWriteIntent,EvidenceReceipt,
 EvidenceWriteKind,ContentItem,Permissions,Relation,Applicability} from './authored-evidence.js';

export type EvidenceComparisonDraft=Readonly<{
 patient_id:string;case_id:string;question_id:string;
 source_snapshot_sha256:string;preflight_sha256:string;
 evidence_id:string;evidence_sha256:string;rights_sha256:string;
 evidence_key:string;evidence_version:number;statement_line:number;content_item:ContentItem;
 quote:string;relation:Relation;applicability:Applicability;rationale:string;dirty:boolean;
}>;
export type EvidenceDraftPatch=Readonly<Partial<Pick<EvidenceComparisonDraft,
 'quote'|'relation'|'applicability'|'rationale'>>>;
const emptyComparisonDraft=(message='No unfinished evidence comparison.')=>({
 evidenceComparisonDraft:null as EvidenceComparisonDraft|null,
 evidenceRejectedFields:Object.freeze([]) as readonly ('quote'|'rationale')[],
 evidenceDraftMessage:message,
});

/** A retained draft is not disclosure authority. Only a fresh matching packet
 * may expose its input fields or permit editing/submission. */
export function activeComparisonDraft(state:ViewState):EvidenceComparisonDraft|null{
 const draft=state.evidenceComparisonDraft,packet=state.evidencePacket;
 if(!draft||!packet||!state.connected||state.phase!=='ready'||state.evidencePhase!=='ready'||
    state.patient?.patient_id!==draft.patient_id||state.patient.status!=='active'||
    state.questionListPhase!=='ready'||state.questionsCaseId!==draft.case_id||
    !state.cases?.some(c=>c.patient_id===draft.patient_id&&c.case_id===draft.case_id&&c.status==='active')||
    state.worldPhase!=='ready'||state.worldModel?.patient_id!==draft.patient_id||
    state.worldModel.case_id!==draft.case_id||state.worldModel.snapshot_fingerprint!==draft.source_snapshot_sha256||
    packet.patient_id!==draft.patient_id||packet.case_id!==draft.case_id||
    packet.question.question_id!==draft.question_id||
    packet.question.source_context_state!=='current_unreviewed_question'||
    packet.source_snapshot_sha256!==draft.source_snapshot_sha256||
    packet.question.source_snapshot_sha256!==draft.source_snapshot_sha256||
    packet.question.preflight_sha256!==draft.preflight_sha256)return null;
 const evidence=packet.evidence.find(e=>e.evidence_id===draft.evidence_id);
 return evidence?.state==='current'&&evidence.statement!==null&&
   evidence.sha256===draft.evidence_sha256&&evidence.rights_sha256===draft.rights_sha256&&
   evidence.evidence_key===draft.evidence_key&&evidence.version===draft.evidence_version&&
   evidence.statement_line===draft.statement_line&&evidence.content_item===draft.content_item?draft:null;
}

/** UI selection is not action authority. Historical question context may still
 * select a current evidence family for the separately authorized withdrawal
 * path, but it must never create or reactivate a comparison draft. */
export function evidenceSelectionMode(state:ViewState,evidenceId:string):'comparison'|'withdrawal_only'|null{
 const packet=state.evidencePacket;
 if(!packet||!state.connected||state.phase!=='ready'||state.evidencePhase!=='ready'||
    ['saving','unknown'].includes(state.evidenceWritePhase)||
    state.patient?.patient_id!==packet.patient_id||state.patient.status!=='active'||
    state.questionListPhase!=='ready'||state.questionsCaseId!==packet.case_id||
    !state.questions?.some(q=>q.question_id===packet.question.question_id&&
      q.patient_id===packet.patient_id&&q.case_id===packet.case_id)||
    !state.cases?.some(c=>c.patient_id===packet.patient_id&&c.case_id===packet.case_id&&c.status==='active'))return null;
 const evidence=packet.evidence.find(row=>row.evidence_id===evidenceId);
 if(!evidence||evidence.state!=='current')return null;
 return evidence.statement!==null&&packet.question.source_context_state==='current_unreviewed_question'&&
   state.worldPhase==='ready'&&state.worldModel?.patient_id===packet.patient_id&&
   state.worldModel.case_id===packet.case_id&&
   state.worldModel.snapshot_fingerprint===packet.source_snapshot_sha256?'comparison':'withdrawal_only';
}

export type EvidenceState={
 evidenceComparisonDraft:EvidenceComparisonDraft|null;
 evidenceRejectedFields:readonly ('quote'|'rationale')[];evidenceDraftMessage:string;
 evidencePacket:EvidencePacket|null;evidencePhase:'idle'|'loading'|'ready'|'error';evidenceMessage:string;
 evidenceReport:EvidenceReport|null;evidenceReportPhase:'idle'|'loading'|'ready'|'error';evidenceReportMessage:string;
 evidenceOriginal:EvidenceOriginal|null;
 evidenceWriteIntent:EvidenceWriteIntent|null;evidenceReceipt:EvidenceReceipt|null;
 evidenceWritePhase:'idle'|'saving'|'saved'|'error'|'unknown';evidenceWriteMessage:string;
};
export const emptyEvidenceDisclosure=()=>({
 evidencePacket:null,evidencePhase:'idle' as const,evidenceMessage:'Select a saved question to inspect case-owned fictional evidence.',
 evidenceReport:null,evidenceReportPhase:'idle' as const,evidenceReportMessage:'Open a saved comparison report with a fresh permission check.',evidenceOriginal:null,
});
export const emptyEvidenceState=():EvidenceState=>({...emptyEvidenceDisclosure(),...emptyComparisonDraft(),evidenceWriteIntent:null,evidenceReceipt:null,evidenceWritePhase:'idle',evidenceWriteMessage:'No evidence change is in progress.'});
type Host={
 snapshot:()=>ViewState;publish:(patch:Partial<ViewState>)=>void;
 scope:()=>string;selectedQuestion:()=>string|null;request:(url:string,controller:AbortController,body?:string)=>Promise<Response>;
 json:(response:Response,limit?:number)=>Promise<unknown>;
 add:(control:AbortController)=>void;remove:(control:AbortController)=>void;expire:()=>void;
};
export class QuestionEvidenceSession{
 #read=0;#reportRead=0;#originalRead=0;#write=0;
 constructor(private host:Host){}
 #clearDisclosure(patch:Partial<EvidenceState>,preserveDraft=false):void{
  // Invalidate parallel dependent readers too. Only a verified freshness change
  // may retain a hidden draft; failed access still clears it. Neither resolves
  // uncertain writes, whose commit outcome is independent of a read.
  this.#read++;this.#reportRead++;this.#originalRead++;
  this.host.publish({...emptyEvidenceDisclosure(),
   ...(preserveDraft?{evidenceDraftMessage:'The source or comparison basis changed. Unfinished comparison retained; recheck evidence before resuming.'}:
    emptyComparisonDraft('Comparison draft cleared because current evidence access could not be verified.')),...patch});
 }
 reset(preserveCase?:string):EvidenceState{
  this.#read++;this.#reportRead++;this.#originalRead++;this.#write++;
  const state=this.host.snapshot(),intent=state.evidenceWriteIntent;
  if(intent&&intent.patient_id===state.patient?.patient_id&&intent.case_id===preserveCase&&['saving','unknown'].includes(state.evidenceWritePhase))return {...emptyEvidenceState(),evidenceWriteIntent:intent,evidenceWritePhase:'unknown',evidenceWriteMessage:'Earlier evidence write outcome is uncertain. Retry its exact stored intent to recover the receipt.'};
  return emptyEvidenceState();
 }
 dismiss=():void=>{
  this.#read++;this.#reportRead++;this.#originalRead++;
  const state=this.host.snapshot(),saving=state.evidenceWritePhase==='saving';
  if(saving)this.#write++;
  this.host.publish({...emptyEvidenceDisclosure(),...(state.evidenceComparisonDraft?{evidenceDraftMessage:'Unfinished comparison retained in memory. Reopen its question for a fresh access check.'}:{}),...(saving?{evidenceWritePhase:'unknown' as const,evidenceWriteMessage:'The in-flight evidence write may have committed. Retry its exact stored intent before changing it.'}:{})});
 };
 #question(id:string):SourceQuestion|null{
  const state=this.host.snapshot(),q=state.questions?.find(q=>q.question_id===id);
  return state.connected&&state.phase==='ready'&&state.questionListPhase==='ready'&&q&&state.patient?.patient_id===q.patient_id&&state.questionsCaseId===q.case_id&&state.cases?.some(c=>c.case_id===q.case_id&&c.status==='active')?q:null;
 }
 #path(q:Pick<SourceQuestion,'patient_id'|'case_id'|'question_id'>):string{return '/v1/patients/'+encodeURIComponent(q.patient_id)+'/cases/'+encodeURIComponent(q.case_id)+'/questions/'+encodeURIComponent(q.question_id);}
 #controller():{control:AbortController;done:()=>void}{
  const control=new AbortController();this.host.add(control);const timeout=setTimeout(()=>control.abort(),10000);
  return {control,done:()=>{clearTimeout(timeout);this.host.remove(control);}};
 }
 async load(questionId:string):Promise<void>{
  const q=this.#question(questionId),stamp=this.host.scope(),read=++this.#read;
  this.#reportRead++;this.#originalRead++;
  this.host.publish({...emptyEvidenceDisclosure(),evidencePhase:'loading',evidenceMessage:'Checking exact question, case evidence and current content permissions…'});
  if(!q){this.host.publish({evidencePhase:'error',evidenceMessage:'Open the current patient case and saved question first.'});return;}
  const current=()=>read===this.#read&&stamp===this.host.scope()&&this.#question(questionId)!==null;
  const {control,done}=this.#controller();
  try{
   const response=await this.host.request(this.#path(q)+'/evidence',control);if(!current())return;
   if(response.status===401){this.host.expire();return;}
   if(response.status!==200){this.#clearDisclosure({evidencePhase:'error',evidenceMessage:'Evidence unavailable under current authority. No earlier evidence view is retained.'});return;}
   const value=await decodeEvidencePacket(await this.host.json(response,524288),q);
   if(!current())return;if(control.signal.aborted)throw Error('evidence timeout');
   const state=this.host.snapshot(),draft=state.evidenceComparisonDraft;
   let draftPatch:Partial<EvidenceState>={};
   if(draft){
    const evidence=value.evidence.find(e=>e.evidence_id===draft.evidence_id);
    if(value.patient_id!==draft.patient_id||value.case_id!==draft.case_id||
       !evidence||evidence.statement===null||evidence.state==='withdrawn'){
     draftPatch=emptyComparisonDraft('Comparison draft cleared because its evidence is no longer available under current permissions.');
    }else{
     const active=activeComparisonDraft({...state,evidencePacket:value,evidencePhase:'ready'});
     draftPatch={evidenceDraftMessage:active?'Unfinished comparison restored after a fresh matching source and rights check.':
       value.question.question_id!==draft.question_id?'An unfinished comparison belongs to another question. Resume it or explicitly discard it.':
       'The captured source, evidence or rights changed. This draft cannot be applied to the new context; explicitly discard it before starting again.'};
    }
   }
   this.host.publish({...draftPatch,evidencePacket:value,evidencePhase:'ready',evidenceMessage:value.question.source_context_state==='current_unreviewed_question'?'Case evidence and human-authored proposals. Scientific appraisal and clinical review have not been performed.':'Source changed. Earlier proposals remain historical; create a current source question before new comparisons.'});
  }catch(_){if(current())this.#clearDisclosure({evidencePhase:'error',evidenceMessage:'Evidence response could not be verified. Refresh before trying again.'});}
  finally{done();}
 }
 async readReport(questionId:string,reportId:string):Promise<EvidenceReport|null>{
  const q=this.#question(questionId),state=this.host.snapshot(),packet=state.evidencePacket;
  // A newly historical report invalidates its older evidence packet. Its verified
  // immutable references still identify this exact report for another authorized
  // read, including download; they never authorize comparison actions.
  const retained=state.evidenceReportPhase==='ready'&&state.evidenceReport?.question_id===questionId&&
   state.evidenceReport.report_id===reportId?state.evidenceReport:undefined;
  const summary=packet?.question.question_id===questionId?packet.reports.find(r=>r.report_id===reportId):
   !packet?retained:undefined;
  const stamp=this.host.scope(),read=++this.#reportRead,evidenceRead=this.#read;
  this.host.publish({evidenceReport:null,evidenceReportPhase:'loading',evidenceReportMessage:'Rechecking report export authority and current family rights…'});
  if(!q||!summary||(packet&&state.evidencePhase!=='ready')){
   this.host.publish({evidenceReportPhase:'error',evidenceReportMessage:'Inspect this question’s report history before opening the exact report.'});return null;
  }
  const current=()=>read===this.#reportRead&&evidenceRead===this.#read&&stamp===this.host.scope()&&this.host.snapshot().evidencePacket===packet;
  const {control,done}=this.#controller();
  try{
   const response=await this.host.request(this.#path(q)+'/evidence-reports/'+encodeURIComponent(reportId),control);if(!current())return null;
   if(response.status===401){this.host.expire();return null;}
   if(response.status!==200){this.#clearDisclosure({evidenceReportPhase:'error',evidenceReportMessage:'Report unavailable under current authority. No previous body can be downloaded.'});return null;}
   const value=await decodeEvidenceReport(await this.host.json(response,524288),q,reportId,summary);
   if(!current())return null;if(control.signal.aborted)throw Error('report timeout');
   const patch={evidenceReport:value,evidenceReportPhase:'ready' as const,evidenceReportMessage:value.state==='content_withheld'?'Current content permissions withhold this report. Its immutable preparation references remain. Refresh evidence to inspect current permissions.':value.state==='historical_reassessment_required'?'Historical preparation. Source or evidence changed; this report is not a current comparison.':'Immutable human-authored comparison report verified. Each download rechecks authority and content rights.'};
   if(value.state==='content_withheld')this.#clearDisclosure(patch);
   else if(value.state==='historical_reassessment_required'&&summary.state==='current_unreviewed'){
    this.#clearDisclosure({...patch,evidenceMessage:'The report check found changed source or comparison context. Refresh evidence and rights before continuing comparisons.'},true);
   }else this.host.publish(patch);
   return value;
  }catch(_){if(current())this.#clearDisclosure({evidenceReportPhase:'error',evidenceReportMessage:'Report bytes or provenance failed verification. No cached body can be downloaded.'});return null;}
  finally{done();}
 }
 async original(questionId:string,evidenceId:string):Promise<EvidenceOriginal|null>{
  const q=this.#question(questionId),state=this.host.snapshot(),packet=state.evidencePacket;
  const selected=packet?.question.question_id===questionId?packet.evidence.find(e=>e.evidence_id===evidenceId):undefined;
  const stamp=this.host.scope(),read=++this.#originalRead,evidenceRead=this.#read;
  this.host.publish({evidenceOriginal:null});
  if(!q||!selected||selected.statement===null||state.evidencePhase!=='ready')return null;
  const current=()=>read===this.#originalRead&&evidenceRead===this.#read&&stamp===this.host.scope()&&this.host.snapshot().evidencePacket===packet;
  const {control,done}=this.#controller();
  try{
   const response=await this.host.request(this.#path(q)+'/evidence/'+encodeURIComponent(evidenceId)+'/original',control);if(!current())return null;
   if(response.status===401){this.host.expire();return null;}
   if(response.status!==200){this.#clearDisclosure({evidencePhase:'error',evidenceMessage:'Original evidence unavailable under current authority. Nothing was downloaded.'});return null;}
   const value=await decodeEvidenceOriginal(await this.host.json(response,524288),q,selected);
   if(!current())return null;if(control.signal.aborted)throw Error('original timeout');
   this.host.publish({evidenceOriginal:value,evidenceMessage:'Exact original evidence bytes verified. This is an authored fictional record.'});return value;
  }catch(_){if(current())this.#clearDisclosure({evidencePhase:'error',evidenceMessage:'Original evidence failed verification. Nothing was downloaded.'});return null;}
  finally{done();}
 }
 #draftLocked():boolean{return ['saving','unknown'].includes(this.host.snapshot().evidenceWritePhase);}
 beginComparison(questionId:string,evidenceId:string):boolean{
  const scope=this.#canStart(questionId);if(!scope)return false;
  const {question:q,packet}=scope,e=packet.evidence.find(row=>row.evidence_id===evidenceId);
  if(q.source_context_state!=='current_unreviewed_question'||packet.source_snapshot_sha256!==q.source_snapshot_sha256||
     q.source_snapshot_sha256!==this.host.snapshot().worldModel?.snapshot_fingerprint||
     !e||e.state!=='current'||e.statement===null){
   this.host.publish({evidenceDraftMessage:'Inspect current question context and readable evidence before starting a comparison.'});return false;
  }
  const existing=this.host.snapshot().evidenceComparisonDraft;
  if(existing&&activeComparisonDraft(this.host.snapshot())===existing&&existing.evidence_id===evidenceId)return true;
  if(existing?.dirty){
   this.host.publish({evidenceDraftMessage:'An unfinished comparison is bound to its original question and evidence. Resume it or explicitly discard it first.'});return false;
  }
  const draft:EvidenceComparisonDraft=Object.freeze({patient_id:q.patient_id,case_id:q.case_id,question_id:q.question_id,
   source_snapshot_sha256:q.source_snapshot_sha256,preflight_sha256:q.preflight_sha256,
   evidence_id:e.evidence_id,evidence_sha256:e.sha256,rights_sha256:e.rights_sha256,
   evidence_key:e.evidence_key,evidence_version:e.version,statement_line:e.statement_line,content_item:e.content_item,
   quote:Array.from(e.statement).slice(0,400).join(''),relation:'unknown',applicability:'unknown',rationale:'',dirty:false});
  this.host.publish({evidenceComparisonDraft:draft,evidenceRejectedFields:Object.freeze([]),
   evidenceDraftMessage:'Unsaved comparison. Its exact source, evidence and rights are captured; nothing has been submitted.'});return true;
 }
 editComparison(patch:EvidenceDraftPatch):boolean{
  const draft=activeComparisonDraft(this.host.snapshot());
  if(!draft||this.#draftLocked())return false;
  if(!patch||typeof patch!=='object'||Array.isArray(patch))return false;
  const validText=(v:unknown,max:number)=>typeof v==='string'&&Array.from(v).length<=max&&
   new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(new TextEncoder().encode(v))===v;
  for(const [key,value] of Object.entries(patch)){
   if(key==='quote'&&!validText(value,400)||key==='rationale'&&!validText(value,600)){
    const field=key as 'quote'|'rationale',state=this.host.snapshot();
    const rejected=Object.freeze([...new Set([...state.evidenceRejectedFields,field])]);
    this.host.publish({evidenceRejectedFields:rejected,
     evidenceDraftMessage:`The ${field==='quote'?'passage':'rationale'} edit was rejected. The previous accepted text is still shown; correct the field or explicitly keep the previous text before saving.`});
    return false;
   }
   if(key==='relation'?!['supports','contradicts','context','unknown'].includes(value as string):
      key==='applicability'?!['applicable','limited','not_applicable','unknown'].includes(value as string):
      key!=='quote'&&key!=='rationale')return false;
  }
  const state=this.host.snapshot(),cleared=Object.keys(patch).filter(key=>key==='quote'||key==='rationale');
  const rejected=Object.freeze(state.evidenceRejectedFields.filter(field=>!cleared.includes(field)));
  if(!Object.entries(patch).some(([key,value])=>draft[key as keyof EvidenceComparisonDraft]!==value)&&rejected.length===state.evidenceRejectedFields.length)return true;
  this.host.publish({evidenceComparisonDraft:Object.freeze({...draft,...patch,dirty:true}),evidenceRejectedFields:rejected,
   evidenceDraftMessage:'Unfinished comparison retained in this session only. Save explicitly or discard it.'});return true;
 }
 acknowledgeRejectedField(field:'quote'|'rationale'):boolean{
  const state=this.host.snapshot(),draft=activeComparisonDraft(state);
  if(!draft||this.#draftLocked()||!state.evidenceRejectedFields.includes(field))return false;
  this.host.publish({evidenceRejectedFields:Object.freeze(state.evidenceRejectedFields.filter(value=>value!==field)),
   evidenceDraftMessage:`Kept the previous accepted ${field==='quote'?'passage':'rationale'}. Review the comparison before saving.`});return true;
 }
 discardComparison():boolean{
  if(this.#draftLocked()){
   this.host.publish({evidenceDraftMessage:'Resolve the pending or uncertain write using its exact intent before discarding the comparison.'});return false;
  }
  this.host.publish(emptyComparisonDraft('Unfinished comparison discarded. This local action made no server request.'));return true;
 }
 async saveComparison():Promise<void>{
  const draft=activeComparisonDraft(this.host.snapshot());
  if(!draft||this.#draftLocked()){
   this.host.publish({evidenceDraftMessage:'A fresh matching question, source, evidence and rights check is required before submitting this draft.'});return;
  }
  if(this.host.snapshot().evidenceRejectedFields.length){
   this.host.publish({evidenceDraftMessage:'Resolve or explicitly acknowledge the rejected comparison edit before saving. The earlier accepted text will not be submitted silently.'});return;
  }
  await this.assess(draft.question_id,draft.evidence_id,draft.quote,draft.relation,draft.applicability,draft.rationale);
 }
 #completedComparison(intent:EvidenceWriteIntent):Partial<EvidenceState>{
  const draft=this.host.snapshot().evidenceComparisonDraft;
  if(!draft||intent.kind!=='assessment'||intent.patient_id!==draft.patient_id||
     intent.case_id!==draft.case_id||intent.question_id!==draft.question_id)return {};
  const body=JSON.parse(intent.body) as Record<string,unknown>;
  if(['evidence_id','evidence_sha256','rights_sha256','quote','relation','applicability','rationale']
      .some(key=>body[key]!==draft[key as keyof EvidenceComparisonDraft])||
      body.expected_source_snapshot_sha256!==draft.source_snapshot_sha256||
      body.expected_preflight_sha256!==draft.preflight_sha256)return {};
  return emptyComparisonDraft('Comparison saved with its original captured context. No clinical approval occurred.');
 }
 #canStart(questionId:string):{question:SourceQuestion;packet:EvidencePacket}|null{
  const state=this.host.snapshot(),q=this.#question(questionId),packet=state.evidencePacket;
  if(state.evidenceWriteIntent&&['saving','unknown'].includes(state.evidenceWritePhase)){
   this.host.publish({evidenceWriteMessage:'Resolve the uncertain write using its exact retry before changing evidence intent.'});return null;
  }
  if(!q||!packet||state.evidencePhase!=='ready'||packet.question.question_id!==questionId){
   this.host.publish({evidenceWritePhase:'error',evidenceWriteMessage:'Inspect this question’s current evidence before changing it.'});return null;
  }
  return {question:q,packet};
 }
 #invalid(message:string):void{this.host.publish({evidenceWritePhase:'error',evidenceWriteMessage:message});}
 async import(questionId:string,originalText:string,contentItem:ContentItem,permissions:Permissions):Promise<void>{
  const scope=this.#canStart(questionId);if(!scope)return;
  const bytes=new TextEncoder().encode(originalText);
  if(typeof originalText!=='string'||bytes.length<1||bytes.length>32768||new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes)!==originalText||!originalText.startsWith('OI-SYNTHETIC-EVIDENCE/1\n')||/[\r\0]/.test(originalText)||!['abstract','api_output','full_text'].includes(contentItem)){
   this.#invalid('Choose a valid independently authored evidence file, at most 32 KiB, and its declared content class.');return;
  }
  await this.#start(scope.question,'import','/evidence',{original_text:originalText,content_item:contentItem,permissions});
 }
 async assess(questionId:string,evidenceId:string,quote:string,relation:Relation,applicability:Applicability,rationale:string):Promise<void>{
  const scope=this.#canStart(questionId);if(!scope)return;
  const {question:q,packet}=scope,e=packet.evidence.find(e=>e.evidence_id===evidenceId);
  if(packet.question.source_context_state!=='current_unreviewed_question'||packet.source_snapshot_sha256!==this.host.snapshot().worldModel?.snapshot_fingerprint||!e||e.state!=='current'||e.statement===null||typeof quote!=='string'||Array.from(quote).length<1||Array.from(quote).length>400||!e.statement.includes(quote)||e.statement.indexOf(quote)!==e.statement.lastIndexOf(quote)||!['supports','contradicts','context','unknown'].includes(relation)||!['applicable','limited','not_applicable','unknown'].includes(applicability)||relation==='supports'&&applicability==='not_applicable'||!visibleLine(rationale)){
   this.#invalid('Use current source and evidence, one exact unique quote, a consistent proposed relation, and a visible 10–600 character rationale.');return;
  }
  await this.#start(q,'assessment','/evidence-assessments',{evidence_id:evidenceId,evidence_sha256:e.sha256,rights_sha256:e.rights_sha256,expected_source_snapshot_sha256:q.source_snapshot_sha256,expected_preflight_sha256:q.preflight_sha256,quote,relation,applicability,rationale});
 }
 async withdraw(questionId:string,evidenceId:string,reason:string):Promise<void>{
  const scope=this.#canStart(questionId);if(!scope)return;
  if(!scope.packet.evidence.some(e=>e.evidence_id===evidenceId&&e.state==='current')||!visibleLine(reason)){
   this.#invalid('Choose the latest current evidence version and provide a visible 10–600 character withdrawal reason.');return;
  }
  await this.#start(scope.question,'withdrawal','/evidence/'+encodeURIComponent(evidenceId)+'/withdraw',{reason});
 }
 async prepareReport(questionId:string,assessmentIds:readonly string[]):Promise<void>{
  const scope=this.#canStart(questionId);if(!scope)return;
  const ids=[...assessmentIds].sort();
  if(scope.packet.question.source_context_state!=='current_unreviewed_question'||scope.packet.source_snapshot_sha256!==this.host.snapshot().worldModel?.snapshot_fingerprint||ids.length<1||ids.length>20||new Set(ids).size!==ids.length||ids.some(id=>!scope.packet.assessments.some(a=>a.assessment_id===id&&a.state==='current_unreviewed'))){
   this.#invalid('Select 1–20 current human-authored comparisons from the inspected question.');return;
  }
  await this.#start(scope.question,'report','/evidence-reports',{expected_packet_sha256:scope.packet.packet_sha256,assessment_ids:ids});
 }
 async #start(q:SourceQuestion,kind:EvidenceWriteKind,suffix:string,fields:Record<string,unknown>):Promise<void>{
  const body=canonicalEvidenceJson({synthetic:true,request_key:'EVIDENCE-REQUEST-'+crypto.randomUUID(),...fields});
  if(new TextEncoder().encode(body).length>72000){this.#invalid('Evidence request exceeds the bounded transport size. Nothing was sent.');return;}
  const intent=Object.freeze({patient_id:q.patient_id,case_id:q.case_id,question_id:q.question_id,kind,path:this.#path(q)+suffix,body});
  await this.#send(intent);
 }
 retry=async():Promise<void>=>{
  const state=this.host.snapshot(),intent=state.evidenceWriteIntent;
  if(!intent||state.evidenceWritePhase!=='unknown'||!state.connected||state.phase!=='ready'||state.patient?.patient_id!==intent.patient_id||!state.cases?.some(c=>c.case_id===intent.case_id&&c.status==='active'))return;
  await this.#send(intent,true);
 };
 async #send(intent:EvidenceWriteIntent,recovering=false):Promise<void>{
  const stamp=this.host.scope(),write=++this.#write;
  this.#read++;this.#reportRead++;this.#originalRead++;
  this.host.publish({...emptyEvidenceDisclosure(),evidenceWriteIntent:intent,evidenceReceipt:null,evidenceWritePhase:'saving',evidenceWriteMessage:'Saving this exact fictional evidence intent. The server rechecks source and content authority.'});
  const current=()=>write===this.#write&&stamp===this.host.scope()&&this.host.snapshot().patient?.patient_id===intent.patient_id;
  const {control,done}=this.#controller();
  try{
   const response=await this.host.request(intent.path,control,intent.body);if(!current())return;
   if(response.status===401){this.host.expire();return;}
   if([403,404,409,413,422].includes(response.status)){
    if(response.status===403||response.status===404)this.host.publish(emptyComparisonDraft('Comparison draft cleared because current authority could not be verified.'));
    if(recovering){
     this.host.publish({evidenceWritePhase:'unknown',evidenceWriteMessage:'Receipt recovery was refused. The earlier write may still have committed; retain and retry this exact intent when current authority permits.'});
    }else{
     this.host.publish({evidenceWriteIntent:null,evidenceWritePhase:'error',evidenceWriteMessage:response.status===409?'Source, evidence or request context changed. Refresh and explicitly reassess; no success is claimed.':'Evidence action was refused under current scope or permissions. No success is claimed.'});
    }
    return;
   }
   if(![200,201].includes(response.status))throw Error('uncertain evidence write');
   const evidenceId=intent.kind==='withdrawal'?decodeURIComponent(intent.path.split('/').at(-2)!):undefined;
   const receipt=decodeEvidenceReceipt(await this.host.json(response),intent.kind,intent.question_id,evidenceId);
   if(!current())return;if(control.signal.aborted)throw Error('write timeout');
   // A success-shaped body is not confirmation when its replay flag contradicts
   // the wire status. Keep the exact intent (and draft) for explicit recovery.
   if((response.status===200)!==receipt.duplicate)throw Error('evidence receipt status');
   this.host.publish({...this.#completedComparison(intent),evidenceWriteIntent:null,evidenceReceipt:receipt,evidenceWritePhase:'saved',evidenceWriteMessage:receipt.duplicate?'Original evidence receipt recovered. No duplicate intent was created.':'Evidence intent saved with immutable provenance. No clinical approval occurred.'});
   // Recovering an old question is receipt recovery, not a new selection.
   // The host owns question focus across source briefs, packets and evidence.
   if(this.host.selectedQuestion()===intent.question_id)await this.load(intent.question_id);
  }catch(_){if(current())this.host.publish({evidenceWritePhase:'unknown',evidenceWriteMessage:'Evidence write outcome unknown. It may have committed. Retry this exact intent to recover its original receipt.'});}
  finally{done();}
 }
}
