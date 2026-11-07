import type {ViewState} from './registry-client.js';
import {decodeFollowthrough,projectFollowthroughAttention} from './followthrough-view.js';
import type {FollowthroughTask} from './followthrough-view.js';
import {amendmentAction,decodeAmendmentInbox,decodeAmendmentReceipt,decodeAmendmentReview,validAmendmentReason,validDisposition} from './laboratory-amendment.js';
import type {AmendmentDetail,AmendmentIntent,AmendmentItem,AmendmentReceipt,AmendmentScope,Disposition} from './laboratory-amendment.js';

type Target=Readonly<{task:FollowthroughTask;selection:AmendmentItem|null}>;
type Command=Readonly<{target:Target;body:AmendmentIntent}>;
export type AmendmentState=Readonly<{
 scope:AmendmentScope|null;mode:'patient'|'review'|null;inbox:readonly AmendmentItem[]|null;target:Target|null;
 detail:AmendmentDetail|null;phase:'idle'|'loading'|'ready'|'saving'|'unknown'|'error';
 command:Command|null;message:string;
}>;
export const emptyAmendment=():AmendmentState=>({scope:null,mode:null,inbox:null,target:null,detail:null,phase:'idle',command:null,message:''});
type Reply=Readonly<{status:number;value:unknown}>;
type Exchange=(scope:AmendmentScope,path:string,signal:AbortController,body?:AmendmentIntent)=>Promise<Reply>;
const unavailable='The comparison or its access could not be verified. Reopen it to check again.';
const unknown='The write outcome is uncertain. Retry the exact request to recover its receipt, or abandon recovery and check the history.';
function active(state:ViewState,scope:AmendmentScope):boolean{
 return state.connected&&state.phase==='ready'&&state.patient?.status==='active'&&state.patient.patient_id===scope.patient_id&&
  !!state.cases?.some(c=>c.case_id===scope.case_id&&c.patient_id===scope.patient_id&&c.status==='active');
}
function taskPath(task:FollowthroughTask){return '/followthrough/'+task.task_id+'/laboratory-amendment-review';}
function locked(s:AmendmentState){return s.command!==null;}

/** All reads and explicit writes use the case owner. Only an uncertain immutable command survives a matching navigation. */
export class AmendmentSession{
 private operation:AbortController|null=null;
 constructor(private readonly snapshot:()=>ViewState,private readonly publish:(s:AmendmentState)=>void,private readonly exchange:Exchange){}
 private get state(){return this.snapshot().amendment;}
 reset(preserveCase?:string):AmendmentState{
  this.operation?.abort();this.operation=null;
  const s=this.state;
  if(s.command&&s.scope&&s.scope.case_id===preserveCase&&s.scope.patient_id===this.snapshot().patient?.patient_id)
   return {...emptyAmendment(),scope:s.scope,mode:s.mode,command:s.command,phase:'unknown',message:unknown};
  return emptyAmendment();
 }
 dismiss(){this.publish(this.reset(this.state.scope?.case_id));}
 abandon(){if(this.state.phase==='unknown')this.publish(this.reset());}
 private start(){
  this.operation?.abort();const control=new AbortController();this.operation=control;return control;
 }
 private current(control:AbortController,scope:AmendmentScope){
  return this.operation===control&&active(this.snapshot(),scope);
 }
 private async read(scope:AmendmentScope,path:string,control:AbortController){
  const reply=await this.exchange(scope,path,control);
  if(reply.status!==200||control.signal.aborted||!this.current(control,scope))throw Error('Protected read unavailable');
  return reply.value;
 }
 async loadInbox(caseId:string){
  const patient=this.snapshot().patient?.patient_id;if(!patient||locked(this.state))return;
  const scope={patient_id:patient,case_id:caseId};if(!active(this.snapshot(),scope))return;
  const control=this.start();
  this.publish({...emptyAmendment(),scope,mode:'review',phase:'loading',message:'Checking pending verification requests…'});
  try{
   const value=await this.read(scope,'/laboratory-amendment-requests',control);
   const inbox=decodeAmendmentInbox(value,scope);
   if(this.current(control,scope))this.publish({...this.state,inbox,phase:'ready',message:''});
  }catch{if(this.current(control,scope))this.publish({...emptyAmendment(),scope,mode:'review',phase:'error',message:'The verification inbox is unavailable. Recheck case access.'});}
 }
 async openRequest(item:AmendmentItem){
  const {scope,inbox}=this.state;if(!scope||!inbox?.includes(item)||locked(this.state)||!active(this.snapshot(),scope))return;
  const control=this.start();
  this.publish({...emptyAmendment(),scope,mode:'review',inbox,phase:'loading',message:'Checking the selected request and its original task…'});
  try{
   const list=decodeFollowthrough(await this.read(scope,'/followthrough',control),scope.patient_id,scope.case_id);
   const task=list.tasks.find(t=>t.task_id===item.task_id&&t.question_id===item.question_id&&t.source_line===null);
   if(!task)throw Error('Missing task');
   await this.show(scope,{task,selection:item},control);
  }catch{this.failRead(control,scope,'review');}
 }
 async openTask(task:FollowthroughTask){
  if(locked(this.state)||task.source_line!==null||task.source_context_state!=='source_reassessment_required'||
     !projectFollowthroughAttention(this.snapshot())?.list.tasks.includes(task))return;
  const scope={patient_id:task.patient_id,case_id:task.case_id},control=this.start();
  const target={task,selection:null};
  this.publish({...emptyAmendment(),scope,mode:'patient',phase:'loading',target,message:'Checking the original report and its current successor…'});
  try{await this.show(scope,target,control);}
  catch{this.failRead(control,scope,'patient');}
 }
 private failRead(control:AbortController,scope:AmendmentScope,mode:'patient'|'review'){
  if(this.current(control,scope))this.publish({...emptyAmendment(),scope,mode,phase:'error',message:unavailable});
 }
 private async show(scope:AmendmentScope,target:Target,control:AbortController,saved?:{receipt:AmendmentReceipt;body:AmendmentIntent}){
  const detail=decodeAmendmentReview(await this.read(scope,taskPath(target.task),control),target.task,target.selection);
  if(saved&&!detail.entries.some(e=>e.entry_id===saved.receipt.entry_id&&e.request_id===saved.receipt.request_id&&
     e.action===saved.body.action&&e.reason===saved.body.reason&&e.latest_source_id===saved.body.expected_latest_source_id&&
     e.latest_sha256===saved.body.expected_latest_sha256&&e.disposition===(saved.body.disposition??null)))throw Error('Receipt absent from history');
  if(this.current(control,scope))this.publish({...this.state,target,detail,command:null,phase:'ready',
   message:saved?(saved.receipt.duplicate?'Original receipt recovered.':'Recorded and checked against the history.') : ''});
 }
 async submit(detail:AmendmentDetail,reason:string,disposition?:Disposition){
  const {scope,target}=this.state;
  if(!scope||!target||this.state.detail!==detail||this.state.phase!=='ready'||locked(this.state)||
     !active(this.snapshot(),scope)||!validAmendmentReason(reason))return;
  const action=amendmentAction(detail,target.selection);
  if(!action||(action==='respond'?!validDisposition(disposition):disposition!==undefined))return;
  const body=Object.freeze({synthetic:true as const,request_key:crypto.randomUUID(),action,reason,
   expected_latest_source_id:detail.latest.source_id,expected_latest_sha256:detail.latest.sha256,
   ...(action==='respond'?{request_id:target.selection!.request_id,disposition}:{})});
  await this.write(scope,Object.freeze({target,body}));
 }
 async retry(){
  const {scope,command,phase}=this.state;
  if(phase==='unknown'&&scope&&command&&active(this.snapshot(),scope))await this.write(scope,command);
 }
 private async write(scope:AmendmentScope,command:Command){
  const control=this.start(),{target,body}=command,mode=target.selection?'review':'patient';
  this.publish({...emptyAmendment(),scope,mode,phase:'saving',command,message:'Recording the exact verification action…'});
  let receipt:AmendmentReceipt;
  try{
   const res=await this.exchange(scope,taskPath(target.task),control,body);
   if(!this.current(control,scope))return;
   if([400,403,404,409,413,422].includes(res.status)){
    this.publish({...emptyAmendment(),scope,mode,phase:'error',message:res.status===409?
     'The request or report version changed. Reopen the comparison before recording a new action.':
     'This action was refused. Recheck access, the selected request and the independent reviewer.'});return;
   }
   if(control.signal.aborted)throw Error('Uncertain write');
   receipt=decodeAmendmentReceipt(res.value,body,res.status);
  }catch{
   if(this.current(control,scope))this.publish({...emptyAmendment(),scope,mode,command,phase:'unknown',message:unknown});
   return;
  }
  this.publish({...emptyAmendment(),scope,mode,phase:'loading',message:'Receipt received. Checking the recorded history…'});
  try{await this.show(scope,target,control,{receipt,body});}
  catch{if(this.current(control,scope))this.publish({...emptyAmendment(),scope,mode,phase:'error',
   message:'Receipt received. History could not be verified. Reopen the comparison to check the recorded action.'});}
 }
}
