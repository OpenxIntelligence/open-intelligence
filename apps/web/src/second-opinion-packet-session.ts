/** Packet operations share RegistrySession's credential, cancellation and authority scope. */
import type {ViewState} from './registry-client.js';
import {decodeSecondOpinionList,decodeSecondOpinionReceipt,packetInputs,activePacketDraft,validPacketPatch,canSavePacket} from './second-opinion-packets.js';
import type {SecondOpinionList,PacketReceipt,PacketDraft,PacketDraftPatch,PacketIntent} from './second-opinion-packets.js';
export type SecondOpinionState={
 secondOpinionPackets:SecondOpinionList|null;secondOpinionPhase:'idle'|'loading'|'ready'|'error';secondOpinionMessage:string;
 secondOpinionDraft:PacketDraft|null;secondOpinionIntent:PacketIntent|null;secondOpinionReceipt:PacketReceipt|null;
 secondOpinionWritePhase:'idle'|'saving'|'saved'|'error'|'unknown';secondOpinionWriteMessage:string;
};
export const emptySecondOpinion=():SecondOpinionState=>({secondOpinionPackets:null,secondOpinionPhase:'idle',
 secondOpinionMessage:'Saved packets have not been checked for this case.',secondOpinionDraft:null,secondOpinionIntent:null,
 secondOpinionReceipt:null,secondOpinionWritePhase:'idle',secondOpinionWriteMessage:'Select exact records and questions. Nothing is sent to a care team.'});
type Host={snapshot:()=>ViewState;publish:(patch:Partial<ViewState>)=>void;scope:()=>string;
 request:(url:string,controller:AbortController,body?:string)=>Promise<Response>;json:(response:Response,limit?:number)=>Promise<unknown>;
 add:(control:AbortController)=>void;remove:(control:AbortController)=>void;expire:()=>void};
export class SecondOpinionPacketSession{
 #read=0;#write=0;#writeScope='';
 constructor(private host:Host){}
 reset(preserveCase?:string):SecondOpinionState{
  this.#read++;this.#write++;
  const state=this.host.snapshot(),intent=state.secondOpinionIntent,draft=state.secondOpinionDraft;
  const same=(value:{patient_id:string;case_id:string}|null)=>!!value&&value.patient_id===state.patient?.patient_id&&value.case_id===preserveCase;
  return {...emptySecondOpinion(),...(same(draft)?{secondOpinionDraft:draft}:{}),
   ...(same(intent)&&['saving','unknown'].includes(state.secondOpinionWritePhase)?{secondOpinionIntent:intent,
    secondOpinionWritePhase:'unknown' as const,secondOpinionWriteMessage:'Earlier packet save may have committed. Recheck the case, then retry the exact captured command.'}:{})};
 }
 /** Suppress stale disclosures on shared-reader failures; retained intent is not read authority. */
 reconcile(state:ViewState):Partial<SecondOpinionState>{
  const patch:Partial<SecondOpinionState>={};
  if(!packetInputs(state)){
   if(state.secondOpinionPackets)patch.secondOpinionPackets=null;
   if(['ready','loading'].includes(state.secondOpinionPhase))patch.secondOpinionPhase='idle';
  }else if(state.secondOpinionDraft&&!activePacketDraft(state)){
   patch.secondOpinionDraft=null;
   if(!state.secondOpinionIntent)patch.secondOpinionWriteMessage='The selected source context changed. Choose records and questions again; no selection was retargeted.';
  }
  if(state.secondOpinionWritePhase==='saving'&&this.#writeScope!==this.host.scope()){
   patch.secondOpinionWritePhase='unknown';patch.secondOpinionWriteMessage='Context was refreshed during saving. The earlier command may have committed; retry that exact command after checking access.';
  }
  if(state.questionListPhase==='error')patch.secondOpinionDraft=null;
  return patch;
 }
 #controller(){const control=new AbortController();this.host.add(control);const timer=setTimeout(()=>control.abort(),10000);
  return {control,done:()=>{clearTimeout(timer);this.host.remove(control);}};}
 #path(scope:{patient_id:string;case_id:string}){return '/v1/patients/'+encodeURIComponent(scope.patient_id)+'/cases/'+encodeURIComponent(scope.case_id)+'/second-opinion-packets';}
 #locked(){return ['saving','unknown'].includes(this.host.snapshot().secondOpinionWritePhase);}
 edit(patch:PacketDraftPatch):boolean{
  const state=this.host.snapshot(),input=packetInputs(state);
  if(!input||this.#locked()||!validPacketPatch(patch))return false;
  const previous=activePacketDraft(state)??{patient_id:input.patient_id,case_id:input.case_id,snapshot_sha256:input.snapshot_sha256,title:'',source_ids:[],question_ids:[]};
  const draft={...previous,...patch};
  if(!draft.source_ids.every(id=>input.sources.some(s=>s.source_id===id))||!draft.question_ids.every(id=>input.questions.some(q=>q.question_id===id)))return false;
  this.host.publish({secondOpinionDraft:Object.freeze({...draft,source_ids:Object.freeze([...draft.source_ids]),question_ids:Object.freeze([...draft.question_ids])}),
   secondOpinionReceipt:null,secondOpinionWritePhase:'idle',secondOpinionWriteMessage:'Unsaved selection in this tab only. Save explicitly; navigation does not send it.'});return true;
 }
 clear():boolean{if(this.#locked())return false;this.host.publish({secondOpinionDraft:null,secondOpinionReceipt:null,secondOpinionWritePhase:'idle',
  secondOpinionWriteMessage:'Unsent selection cleared. No saved packet was deleted.'});return true;}
 async load(caseId:string):Promise<void>{
  if(this.host.snapshot().secondOpinionWritePhase==='saving')return;
  const input=packetInputs(this.host.snapshot()),stamp=this.host.scope(),read=++this.#read;
  this.host.publish({secondOpinionPackets:null,secondOpinionPhase:'loading',secondOpinionMessage:'Checking packet access and current source context…'});
  if(!input||input.case_id!==caseId){this.host.publish({secondOpinionPhase:'error',secondOpinionMessage:'Open this patient case and check saved questions first.'});return;}
  const current=()=>read===this.#read&&stamp===this.host.scope()&&packetInputs(this.host.snapshot())?.case_id===caseId;
  const {control,done}=this.#controller();
  try{
   const response=await this.host.request(this.#path(input),control);if(!current())return;
   if(response.status===401){this.host.expire();return;}
   if(response.status!==200)throw Error('packet access unavailable');
   const value=decodeSecondOpinionList(await this.host.json(response,4194304),input.patient_id,caseId);
   if(!current())return;if(control.signal.aborted)throw Error('packet timeout');
   this.host.publish({secondOpinionPackets:value,secondOpinionPhase:'ready',secondOpinionMessage:'Saved preparation packets from the latest authorized read. No referral or transmission occurred.'});
  }catch(_){if(current())this.host.publish({secondOpinionPackets:null,secondOpinionPhase:'error',secondOpinionMessage:'Saved packets are unavailable or failed verification. No previous packet details are shown.'});}
  finally{done();}
 }
 async save(confirmed:boolean):Promise<void>{
  const state=this.host.snapshot();if(this.#locked())return;
  if(confirmed!==true||!canSavePacket(state)){this.host.publish({secondOpinionWriteMessage:'Enter a title, explicitly select records and questions with their source records, and confirm fictional preparation.'});return;}
  const draft=activePacketDraft(state)!;
  const intent=Object.freeze({patient_id:draft.patient_id,case_id:draft.case_id,body:JSON.stringify({synthetic:true,request_key:crypto.randomUUID(),title:draft.title,
   source_snapshot_contract:'oi.pg-source-world-model/1',expected_source_snapshot_sha256:draft.snapshot_sha256,
   source_ids:draft.source_ids,question_ids:draft.question_ids})});
  await this.#send(intent);
 }
 async retry():Promise<void>{
  const state=this.host.snapshot(),intent=state.secondOpinionIntent,input=packetInputs(state);
  if(state.secondOpinionWritePhase!=='unknown'||!intent||!input||input.patient_id!==intent.patient_id||input.case_id!==intent.case_id)return;
  await this.#send(intent,true);
 }
 abandon():boolean{
  if(this.host.snapshot().secondOpinionWritePhase==='saving')return false;
  this.#write++;this.host.publish({secondOpinionIntent:null,secondOpinionDraft:null,secondOpinionReceipt:null,secondOpinionWritePhase:'idle',
   secondOpinionWriteMessage:'Local recovery abandoned. This does not undo a possibly committed packet. Check saved packets before preparing another.'});return true;
 }
 async #send(intent:PacketIntent,recovering=false):Promise<void>{
  const write=++this.#write,stamp=this.host.scope();this.#writeScope=stamp;this.#read++;
  const current=()=>write===this.#write&&stamp===this.host.scope();
  const {control,done}=this.#controller();
  this.host.publish({secondOpinionIntent:intent,secondOpinionReceipt:null,secondOpinionWritePhase:'saving',secondOpinionPackets:null,secondOpinionPhase:'idle',
   secondOpinionWriteMessage:'Saving the exact preparation selection. No external request is being sent.'});
  try{
   const response=await this.host.request(this.#path(intent),control,intent.body);if(!current())return;
   if(response.status===401){this.host.expire();return;}
   if([400,403,404,409,413,422].includes(response.status)){
    if(recovering){this.host.publish({secondOpinionWritePhase:'unknown',secondOpinionWriteMessage:'This retry was refused. The earlier save outcome remains unknown; recheck access and retry that exact command or explicitly abandon local recovery.'});return;}
    this.host.publish({secondOpinionIntent:null,secondOpinionWritePhase:'error',secondOpinionWriteMessage:'Packet save was refused. Recheck permissions and current records before preparing again.'});return;
   }
   const receipt=decodeSecondOpinionReceipt(await this.host.json(response),response.status);
   if(!current())return;if(control.signal.aborted)throw Error('save timeout');
   this.host.publish({secondOpinionIntent:null,secondOpinionDraft:null,secondOpinionReceipt:receipt,secondOpinionWritePhase:'saved',
    secondOpinionWriteMessage:receipt.duplicate?'Original packet receipt recovered. No duplicate packet was created.':'Packet saved. Reopen saved packets to check its current source status. Nothing was sent externally.'});
  }catch(_){if(current())this.host.publish({secondOpinionWritePhase:'unknown',secondOpinionReceipt:null,
   secondOpinionWriteMessage:'Packet save outcome is unknown. Retry the exact command to recover its receipt; do not create a replacement.'});}
  finally{done();}
 }
}
