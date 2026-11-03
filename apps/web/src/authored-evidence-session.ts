/** Transient evidence operations within RegistrySession's existing request scope. */
import type {ViewState} from './registry-client.js';
import type {SourceQuestion} from './source-questions-view.js';
import {decodeEvidencePacket,decodeEvidenceReport,decodeEvidenceOriginal,decodeEvidenceReceipt,
 canonicalEvidenceJson,visibleLine} from './authored-evidence.js';
import type {EvidencePacket,EvidenceReport,EvidenceOriginal,EvidenceWriteIntent,EvidenceReceipt,
 EvidenceWriteKind,ContentItem,Permissions,Relation,Applicability} from './authored-evidence.js';

export type EvidenceState={
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
export const emptyEvidenceState=():EvidenceState=>({...emptyEvidenceDisclosure(),evidenceWriteIntent:null,evidenceReceipt:null,evidenceWritePhase:'idle',evidenceWriteMessage:'No evidence change is in progress.'});
type Host={
 snapshot:()=>ViewState;publish:(patch:Partial<ViewState>)=>void;
 scope:()=>string;request:(url:string,controller:AbortController,body?:string)=>Promise<Response>;
 json:(response:Response,limit?:number)=>Promise<unknown>;
 add:(control:AbortController)=>void;remove:(control:AbortController)=>void;expire:()=>void;
};
export class QuestionEvidenceSession{
 #read=0;#reportRead=0;#originalRead=0;#write=0;
 constructor(private host:Host){}
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
  this.host.publish({...emptyEvidenceDisclosure(),...(saving?{evidenceWritePhase:'unknown' as const,evidenceWriteMessage:'The in-flight evidence write may have committed. Retry its exact stored intent before changing it.'}:{})});
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
   if(response.status!==200){this.host.publish({evidencePhase:'error',evidenceMessage:'Evidence unavailable under current authority. No earlier evidence view is retained.'});return;}
   const value=await decodeEvidencePacket(await this.host.json(response,524288),q);
   if(!current()||control.signal.aborted)return;
   this.host.publish({evidencePacket:value,evidencePhase:'ready',evidenceMessage:value.question.source_context_state==='current_unreviewed_question'?'Case evidence and human-authored proposals. Scientific appraisal and clinical review have not been performed.':'Source changed. Earlier proposals remain historical; create a current source question before new comparisons.'});
  }catch(_){if(current())this.host.publish({evidencePhase:'error',evidenceMessage:'Evidence response could not be verified. Refresh before trying again.'});}
  finally{done();}
 }
 async readReport(questionId:string,reportId:string):Promise<EvidenceReport|null>{
  const q=this.#question(questionId),state=this.host.snapshot(),packet=state.evidencePacket;
  const summary=packet?.question.question_id===questionId?packet.reports.find(r=>r.report_id===reportId):undefined;
  const stamp=this.host.scope(),read=++this.#reportRead,evidenceRead=this.#read;
  this.host.publish({evidenceReport:null,evidenceReportPhase:'loading',evidenceReportMessage:'Rechecking report export authority and current family rights…'});
  if(!q||!summary||!packet||state.evidencePhase!=='ready'){
   this.host.publish({evidenceReportPhase:'error',evidenceReportMessage:'Inspect this question’s report history before opening the exact report.'});return null;
  }
  const current=()=>read===this.#reportRead&&evidenceRead===this.#read&&stamp===this.host.scope()&&this.host.snapshot().evidencePacket===packet;
  const {control,done}=this.#controller();
  try{
   const response=await this.host.request(this.#path(q)+'/evidence-reports/'+encodeURIComponent(reportId),control);if(!current())return null;
   if(response.status===401){this.host.expire();return null;}
   if(response.status!==200){this.host.publish({...emptyEvidenceDisclosure(),evidenceReportPhase:'error',evidenceReportMessage:'Report unavailable under current authority. No previous body can be downloaded.'});return null;}
   const value=await decodeEvidenceReport(await this.host.json(response,524288),q,reportId,summary);
   if(!current()||control.signal.aborted)return null;
   this.host.publish({...(value.state==='content_withheld'?emptyEvidenceDisclosure():{}),evidenceReport:value,evidenceReportPhase:'ready',evidenceReportMessage:value.state==='content_withheld'?'Current content permissions withhold this report. Its immutable preparation references remain. Refresh evidence to inspect current permissions.':value.state==='historical_reassessment_required'?'Historical preparation. Source or evidence changed; this report is not a current comparison.':'Immutable human-authored comparison report verified. Each download rechecks authority and content rights.'});
   return value;
  }catch(_){if(current())this.host.publish({evidenceReportPhase:'error',evidenceReportMessage:'Report bytes or provenance failed verification. No cached body can be downloaded.'});return null;}
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
   if(response.status!==200){this.host.publish({...emptyEvidenceDisclosure(),evidencePhase:'error',evidenceMessage:'Original evidence unavailable under current authority. Nothing was downloaded.'});return null;}
   const value=await decodeEvidenceOriginal(await this.host.json(response,524288),q,selected);
   if(!current()||control.signal.aborted)return null;
   this.host.publish({evidenceOriginal:value,evidenceMessage:'Exact original evidence bytes verified. This is an authored fictional record.'});return value;
  }catch(_){if(current())this.host.publish({evidenceMessage:'Original evidence failed verification. Nothing was downloaded.'});return null;}
  finally{done();}
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
  if(typeof originalText!=='string'||bytes.length<1||bytes.length>32768||new TextDecoder('utf-8',{fatal:true}).decode(bytes)!==originalText||!originalText.startsWith('OI-SYNTHETIC-EVIDENCE/1\n')||/[\r\0]/.test(originalText)||!['abstract','api_output','full_text'].includes(contentItem)){
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
  await this.#send(intent);
 };
 async #send(intent:EvidenceWriteIntent):Promise<void>{
  const stamp=this.host.scope(),write=++this.#write;
  this.#read++;this.#reportRead++;this.#originalRead++;
  this.host.publish({...emptyEvidenceDisclosure(),evidenceWriteIntent:intent,evidenceReceipt:null,evidenceWritePhase:'saving',evidenceWriteMessage:'Saving this exact fictional evidence intent. The server rechecks source and content authority.'});
  const current=()=>write===this.#write&&stamp===this.host.scope()&&this.host.snapshot().patient?.patient_id===intent.patient_id;
  const {control,done}=this.#controller();
  try{
   const response=await this.host.request(intent.path,control,intent.body);if(!current())return;
   if(response.status===401){this.host.expire();return;}
   if([403,404,409,413,422].includes(response.status)){
    this.host.publish({evidenceWriteIntent:null,evidenceWritePhase:'error',evidenceWriteMessage:response.status===409?'Source, evidence or request context changed. Refresh and explicitly reassess; no success is claimed.':'Evidence action was refused under current scope or permissions. No success is claimed.'});return;
   }
   if(![200,201].includes(response.status))throw Error('uncertain evidence write');
   const evidenceId=intent.kind==='withdrawal'?decodeURIComponent(intent.path.split('/').at(-2)!):undefined;
   const receipt=decodeEvidenceReceipt(await this.host.json(response),intent.kind,intent.question_id,evidenceId);
   if(!current()||control.signal.aborted)return;
   this.host.publish({evidenceWriteIntent:null,evidenceReceipt:receipt,evidenceWritePhase:'saved',evidenceWriteMessage:receipt.duplicate?'Original evidence receipt recovered. No duplicate intent was created.':'Evidence intent saved with immutable provenance. No clinical approval occurred.'});
   await this.load(intent.question_id);
  }catch(_){if(current())this.host.publish({evidenceWritePhase:'unknown',evidenceWriteMessage:'Evidence write outcome unknown. It may have committed. Retry this exact intent to recover its original receipt.'});}
  finally{done();}
 }
}
