/** Transient manual context; source originals and canonical questions stay server-owned. */
import {canonicalEvidenceJson} from './authored-evidence.js';
import {authoredEvidenceTimestamp} from './evidence-timestamp.js';
import type {DocumentReply} from './reviewed-documents.js';

export type PassageScope=Readonly<{patient_id:string;case_id:string;question_id:string}>;
export type PassageReference=Readonly<{source_id:string;annotation_revision_id:string;selection_key:string;anchor_sha256:string}>;
export type ManualAnchor=Readonly<PassageScope & {
 source_id:string;document_id:string;source_version:number;original_sha256:string;extraction_method:'utf8-plain-text-v1'|'pypdf-text-v1';
 extraction_sha256:string|null;annotation_revision_id:string;annotation_revision:number;review_sha256:string;selected_by:string;selected_at:string;
 selection_key:string;selected_state:string;quote:string;line:number;page:number|null;classification_origin:'user_selected';clinical_review:'not_performed';
}>;
// The source anchor has patient/case scope; question ownership belongs to the enclosing context.
export type ResolvedPassage=Readonly<{anchor:Omit<ManualAnchor,'question_id'>;anchor_sha256:string;source_state:'current'|'superseded';
 latest_annotation_revision_id:string;selection_state:'current_unreviewed_selection'|'selection_reassessment_required'}>;
export type ManualContext=Readonly<PassageScope & {contract:'oi.question-manual-passages/1';revision_id:string|null;revision:number;
 attached_by:string|null;attached_at:string|null;passages:readonly ResolvedPassage[];state:'current_unreviewed'|'reassessment_required';context_sha256:string}>;
export type ManualPacket=ManualContext & Readonly<{access_receipt_id:string}>;
const contextFields=['contract','patient_id','case_id','question_id','revision_id','revision','attached_by','attached_at','passages','state','context_sha256'];
const anchorFields=['patient_id','case_id','source_id','document_id','source_version','original_sha256','extraction_method','extraction_sha256','annotation_revision_id','annotation_revision','review_sha256','selected_by','selected_at','selection_key','selected_state','quote','line','page','classification_origin','clinical_review'];
const passageFields=['anchor','anchor_sha256','source_state','latest_annotation_revision_id','selection_state'];
const key=/^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$/;
const hex=(v:unknown):v is string=>typeof v==='string'&&/^[0-9a-f]{64}$/.test(v);
const id=(v:unknown,prefix:string):v is string=>typeof v==='string'&&new RegExp('^'+prefix+'-[A-F0-9]{32}$').test(v);
const integer=(v:unknown,min:number,max:number):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=min&&v<=max;
const exact=(v:unknown,keys:readonly string[]):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
export async function manualHash(v:unknown):Promise<string>{
 const text=canonicalEvidenceJson(v),bytes=new TextEncoder().encode(text);
 if(new TextDecoder('utf-8',{fatal:true}).decode(bytes)!==text)throw Error('Invalid manual context bytes');
 return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
}
export function passageReference(p:ResolvedPassage):PassageReference{
 return Object.freeze({source_id:p.anchor.source_id,annotation_revision_id:p.anchor.annotation_revision_id,selection_key:p.anchor.selection_key,anchor_sha256:p.anchor_sha256});
}
async function decodePassage(value:unknown,scope:Pick<PassageScope,'patient_id'|'case_id'>):Promise<ResolvedPassage>{
 if(!exact(value,passageFields)||!exact(value.anchor,anchorFields)||!hex(value.anchor_sha256)||!id(value.latest_annotation_revision_id,'ANN'))throw Error('Invalid manual passage');
 const a=value.anchor,pdf=a.extraction_method==='pypdf-text-v1';
 if(a.patient_id!==scope.patient_id||a.case_id!==scope.case_id||!id(a.source_id,'SRC')||!id(a.annotation_revision_id,'ANN')||
    typeof a.document_id!=='string'||!/^[A-Z][A-Z0-9-]{1,39}$/.test(a.document_id)||!integer(a.source_version,1,2147483647)||!hex(a.original_sha256)||
    !['utf8-plain-text-v1','pypdf-text-v1'].includes(String(a.extraction_method))||(pdf?(!hex(a.extraction_sha256)||!integer(a.page,1,20)):(a.extraction_sha256!==null||a.page!==null))||
    !integer(a.annotation_revision,1,64)||!hex(a.review_sha256)||typeof a.selected_by!=='string'||!key.test(a.selected_by)||!authoredEvidenceTimestamp(a.selected_at)||
    typeof a.selection_key!=='string'||!/^[a-z][a-z0-9_-]{0,59}$/.test(a.selection_key)||!['reported','negative','pending','indeterminate','not-reported','not-assessed','conflicting'].includes(String(a.selected_state))||
    typeof a.quote!=='string'||Array.from(a.quote).length<1||Array.from(a.quote).length>1200||!integer(a.line,1,512)||a.classification_origin!=='user_selected'||a.clinical_review!=='not_performed'||
    !['current','superseded'].includes(String(value.source_state))||!['current_unreviewed_selection','selection_reassessment_required'].includes(String(value.selection_state)))throw Error('Invalid manual provenance');
 if((value.selection_state==='current_unreviewed_selection')!==(value.source_state==='current'&&value.latest_annotation_revision_id===a.annotation_revision_id)||await manualHash(a)!==value.anchor_sha256)throw Error('Manual freshness or anchor digest differs');
 return Object.freeze({...value,anchor:Object.freeze({...a})}) as ResolvedPassage;
}
export async function decodeSelection(value:unknown,scope:Pick<PassageScope,'patient_id'|'case_id'>,reference:Omit<PassageReference,'anchor_sha256'>):Promise<ResolvedPassage>{
 if(!exact(value,[...passageFields,'contract','synthetic','clinical_approval','model_execution','access_receipt_id'])||value.contract!=='oi.reviewed-document-selection/1'||value.synthetic!==true||value.clinical_approval!==false||value.model_execution!==false||!id(value.access_receipt_id,'ACCESS'))throw Error('Invalid selection receipt');
 const p=await decodePassage(Object.fromEntries(passageFields.map(k=>[k,value[k]])),scope);
 if(p.anchor.source_id!==reference.source_id||p.anchor.annotation_revision_id!==reference.annotation_revision_id||p.anchor.selection_key!==reference.selection_key)throw Error('Different selection returned');
 return p;
}
export async function decodeManualContext(value:unknown,scope:PassageScope,packet=false):Promise<ManualContext|ManualPacket>{
 if(!exact(value,packet?[...contextFields,'access_receipt_id']:contextFields)||value.contract!=='oi.question-manual-passages/1'||
    value.patient_id!==scope.patient_id||value.case_id!==scope.case_id||value.question_id!==scope.question_id||!id(value.question_id,'QUESTION')||
    !integer(value.revision,0,64)||!hex(value.context_sha256)||!Array.isArray(value.passages)||value.passages.length>20||
    !['current_unreviewed','reassessment_required'].includes(String(value.state))||(packet&&!id(value.access_receipt_id,'ACCESS')))throw Error('Invalid question passage context');
 if(value.revision===0?(value.revision_id!==null||value.attached_by!==null||value.attached_at!==null||value.passages.length!==0):
    (!id(value.revision_id,'PASSAGES')||typeof value.attached_by!=='string'||!key.test(value.attached_by)||!authoredEvidenceTimestamp(value.attached_at)))throw Error('Invalid attachment provenance');
 const passages=await Promise.all(value.passages.map(p=>decodePassage(p,scope))),identities=passages.map(p=>[p.anchor.source_id,p.anchor.annotation_revision_id,p.anchor.selection_key].join(':'));
 if(new Set(identities).size!==passages.length||(value.state==='current_unreviewed')!==passages.every(p=>p.selection_state==='current_unreviewed_selection'))throw Error('Invalid selected context');
 const contents=Object.fromEntries(contextFields.filter(k=>k!=='context_sha256').map(k=>[k,value[k]]));
 if(await manualHash(contents)!==value.context_sha256)throw Error('Manual context digest differs');
 return Object.freeze({...value,passages:Object.freeze(passages)}) as ManualContext|ManualPacket;
}

type Request=(body?:string)=>Promise<DocumentReply>;
type State=Readonly<{phase:'idle'|'loading'|'saving'|'uncertain'|'error';packet:ManualPacket|null;pending:string|null;message:string;
 chosen:readonly ResolvedPassage[];draftStatus:'none'|'unverified'|'ready'|'conflict'}>;
export type ManualIntentStore=Readonly<{read:()=>string|null;write:(body:string|null)=>void}>;
export type ManualSelectionDraft=Readonly<{expected_context_sha256:string;references:readonly PassageReference[]}>;
export type ManualDraftStore=Readonly<{read:()=>ManualSelectionDraft|null;write:(draft:ManualSelectionDraft|null)=>void}>;
export function manualReportBinding(packet:ManualPacket|null,chosen:readonly ResolvedPassage[],phase:State['phase'],draftStatus:State['draftStatus']='none'):Readonly<{context:ManualContext|null;blocked:boolean;dirty:boolean}>{
 const identities=(rows:readonly ResolvedPassage[])=>rows.map(p=>canonicalEvidenceJson(passageReference(p))).sort();
 const dirty=packet!==null&&canonicalEvidenceJson(identities(packet.passages))!==canonicalEvidenceJson(identities(chosen));
 const blocked=dirty||phase==='saving'||phase==='uncertain'||draftStatus==='unverified'||draftStatus==='conflict';
 return {context:phase==='idle'&&!blocked?packet:null,blocked,dirty};
}
export type ManualPanelStatus=Readonly<{scope:PassageScope;context:ManualContext|null;blocked:boolean}>;
export class QuestionPassageClient{
 #generation=0;#listeners=new Set<()=>void>();
 #state:State={phase:'idle',packet:null,pending:null,message:'Inspect the saved manual context for this question.',chosen:[],draftStatus:'none'};
 constructor(private scope:PassageScope,private request:Request,private intentStore?:ManualIntentStore,
  private draftStore?:ManualDraftStore,private resolveSelection?:(reference:PassageReference)=>Promise<DocumentReply>){
  const pending=intentStore?.read();
  if(pending)this.#state={...this.#state,phase:'uncertain',pending,message:'An earlier passage save has an unknown outcome. Retry its exact intent after rechecking this question.'};
  else if(draftStore?.read())this.#state={...this.#state,draftStatus:'unverified',message:'Unsent passage changes retained. Rechecking their exact sources before resuming.'};
 }
 snapshot=()=>this.#state;
 subscribe=(fn:()=>void)=>{this.#listeners.add(fn);return()=>{this.#listeners.delete(fn);};};
 #publish(patch:Partial<State>){
  if(Object.hasOwn(patch,'pending'))this.intentStore?.write(patch.pending??null);
  this.#state=Object.freeze({...this.#state,...patch});this.#listeners.forEach(fn=>fn());
 }
 dispose(){this.#generation++;this.#listeners.clear();this.#state={phase:'idle',packet:null,pending:null,message:'',chosen:[],draftStatus:'none'};}
 #edit(chosen:readonly ResolvedPassage[]):boolean{
  const {packet,phase,draftStatus}=this.#state;if(!packet||phase!=='idle'||draftStatus==='conflict'||chosen.length>20)return false;
  const dirty=manualReportBinding(packet,chosen,phase).dirty;
  this.draftStore?.write(dirty?Object.freeze({expected_context_sha256:packet.context_sha256,references:Object.freeze(chosen.map(passageReference))}):null);
  this.#publish({chosen:Object.freeze([...chosen]),draftStatus:dirty?'ready':'none'});return true;
 }
 choose(passage:ResolvedPassage):boolean{
  if(passage.anchor.patient_id!==this.scope.patient_id||passage.anchor.case_id!==this.scope.case_id||passage.selection_state!=='current_unreviewed_selection')return false;
  return this.#edit(this.#state.chosen.some(p=>p.anchor_sha256===passage.anchor_sha256)?this.#state.chosen:[...this.#state.chosen,passage]);
 }
 remove(anchorSha:string):boolean{return this.#edit(this.#state.chosen.filter(p=>p.anchor_sha256!==anchorSha));}
 async discardDraft(){
  if(['loading','saving','uncertain'].includes(this.#state.phase))return;
  this.draftStore?.write(null);this.#publish({chosen:[],draftStatus:'none'});await this.load();
 }
 async load(){
  if(['saving','uncertain'].includes(this.#state.phase))return;
  const generation=++this.#generation,draft=this.draftStore?.read();
  this.#publish({phase:'loading',packet:null,chosen:[],draftStatus:draft?'unverified':'none',message:'Checking question, original-read permission and exact saved passages…'});
  try{const reply=await this.request();if(generation!==this.#generation)return;
   if(reply.status!==200){if([401,403,404].includes(reply.status))this.draftStore?.write(null);throw Error('Manual context unavailable. Recheck case permissions.');}
   const packet=await decodeManualContext(reply.body,this.scope,true) as ManualPacket;if(generation!==this.#generation)return;
   let chosen=packet.passages;
   if(draft){
    if(this.draftStore?.read()!==draft)throw Error('Draft scope changed. Recheck this question.');
    if(draft.expected_context_sha256!==packet.context_sha256){
     this.#publish({phase:'idle',packet,chosen:[],draftStatus:'conflict',message:'The saved passage set changed while you were away. Unsent selections are withheld. Discard them and select from the current context.'});return;
    }
    const resolved:ResolvedPassage[]=[];
    for(const reference of draft.references){
     if(!this.resolveSelection)throw Error('Reopen the question to verify retained selections.');
     const selected=await this.resolveSelection(reference);if(generation!==this.#generation)return;
     if([401,403,404].includes(selected.status))this.draftStore?.write(null);
     if(selected.status!==200)throw Error('Retained passage unavailable. Recheck source permissions.');
     const passage=await decodeSelection(selected.body,this.scope,reference);if(generation!==this.#generation)return;
     if(this.draftStore?.read()!==draft)throw Error('Draft scope changed. Recheck this question.');
     if(passage.anchor_sha256!==reference.anchor_sha256||passage.selection_state!=='current_unreviewed_selection'){
      this.#publish({phase:'idle',packet,chosen:[],draftStatus:'conflict',message:'A retained selection changed. Unsent quotations are withheld. Discard these changes and choose current passages.'});return;
     }
     resolved.push(passage);
    }
    if(this.draftStore?.read()!==draft)throw Error('Draft scope changed. Recheck this question.');
    chosen=Object.freeze(resolved);
   }
   this.#publish({phase:'idle',packet,chosen,draftStatus:draft?'ready':'none',message:draft?'Unsent passage changes restored after fresh source checks. Save explicitly or discard them.':packet.state==='current_unreviewed'?'Manual context inspected. Selections remain unreviewed.':'Manual context changed. Replace or remove stale passages before preparing a new report.'});
  }catch(e){if(generation===this.#generation)this.#publish({phase:'error',packet:null,chosen:[],draftStatus:this.draftStore?.read()?'unverified':'none',message:e instanceof Error?e.message:'Manual context unavailable.'});}
 }
 async replace(references:readonly PassageReference[]){
  if(!this.#state.packet||this.#state.phase!=='idle'||this.#state.draftStatus==='conflict'||references.length>20)return;
  const body=canonicalEvidenceJson({synthetic:true,request_key:'PASSAGES-'+crypto.randomUUID(),expected_context_sha256:this.#state.packet.context_sha256,references});
  await this.#send(body);
 }
 async retry(){if(this.#state.phase==='uncertain'&&this.#state.pending)await this.#send(this.#state.pending);}
 async #send(body:string){
  const recovering=this.#state.phase==='uncertain';
  const generation=++this.#generation;this.#publish({phase:'saving',pending:body,chosen:[],draftStatus:'none',message:'Saving the exact selected reference set…'});
  this.draftStore?.write(null);
  try{const reply=await this.request(body);if(generation!==this.#generation)return;
   if([400,401,403,404,409,422].includes(reply.status)){
    this.#publish(recovering?{phase:'uncertain',packet:null,pending:body,message:'Recovery was denied. The earlier outcome remains unknown; restore permission and retry this exact intent.'}:
     {phase:'error',packet:null,pending:null,message:reply.status===409?'The inspected context changed. Refresh before selecting again.':'Manual context save denied. Recheck current permissions.'});return;
   }
   if(![200,201].includes(reply.status)||!exact(reply.body,['revision_id','question_id','duplicate'])||!id(reply.body.revision_id,'PASSAGES')||reply.body.question_id!==this.scope.question_id||typeof reply.body.duplicate!=='boolean'||reply.body.duplicate!==(reply.status===200))throw Error('Uncertain receipt');
   this.#publish({phase:'idle',packet:null,pending:null,message:'Saved exact manual context.'});await this.load();
  }catch(_){if(generation===this.#generation)this.#publish({phase:'uncertain',packet:null,pending:body,message:'The save may have committed. Retry the exact intent to recover its receipt.'});}
 }
}
