/** Memory-only consent management over the canonical patient journal. */
import {PermissionHttpError,permissionKey,type PermissionScope} from './patient-permissions.js';
import {citationEvidenceTimestamp as instant} from './evidence-timestamp.js';
const administrative=new Set(['patient_create','patient_suspend','patient_permissions_read','patient_permissions_manage','data_use_read','data_use_manage','consent_read','consent_manage']);
const object=(v:unknown):v is Record<string,unknown>=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const positive=(v:unknown):v is number=>Number.isSafeInteger(v)&&Number(v)>0;
const actions=(v:unknown):v is string[]=>Array.isArray(v)&&v.length<=64&&v.every(x=>permissionKey(x)&&!administrative.has(x))&&new Set(v).size===v.length;
export type ConsentRow={event_id:number;revision:number;actor:string;target_purpose:'operations'|'research';state:'granted'|'withdrawn';
  actions:string[];decision_maker:string;basis:string;authority_ref:string;valid_from:string|null;expires_at:string|null;
  recorded_at:string;recorded_by:string;status:'active'|'scheduled'|'expired'|'withdrawn'|'superseded'};
export type ConsentPage={patient_id:string;decisions:ConsentRow[];next_before:number|null;available_actions:string[];
  operator_expires_at:string;enforcement:'required'|'recorded_decisions_only';authority_verified:false;data_scope:'patient_record'};
export function readConsentPage(v:unknown,patient:string):ConsentPage{
  if(!object(v)||v.patient_id!==patient||v.authority_verified!==false||v.data_scope!=='patient_record'||
    !['required','recorded_decisions_only'].includes(String(v.enforcement))||!actions(v.available_actions)||!instant(v.operator_expires_at)||
    !(v.next_before===null||positive(v.next_before))||!Array.isArray(v.decisions)||v.decisions.length>25)throw Error('Invalid consent history');
  let previous=Infinity;
  for(const r of v.decisions){
    if(!object(r)||!positive(r.event_id)||r.event_id>=previous||!positive(r.revision)||!permissionKey(r.actor)||
      !permissionKey(r.decision_maker)||!permissionKey(r.recorded_by)||!permissionKey(r.authority_ref)||!instant(r.recorded_at)||
      !['operations','research'].includes(String(r.target_purpose))||!['self','guardian','animal_owner','authorized_representative'].includes(String(r.basis))||
      !['granted','withdrawn'].includes(String(r.state))||!['active','scheduled','expired','withdrawn','superseded'].includes(String(r.status))||!actions(r.actions))throw Error('Invalid consent decision');
    if(r.state==='granted'?(!r.actions.length||!instant(r.valid_from)||!instant(r.expires_at)||Date.parse(r.valid_from)>=Date.parse(r.expires_at)||r.status==='withdrawn'):
      (r.actions.length!==0||r.valid_from!==null||r.expires_at!==null||!['withdrawn','superseded'].includes(String(r.status))))throw Error('Invalid consent validity');
    previous=r.event_id;
  }
  if(v.next_before!==null&&(v.decisions.length!==25||v.next_before!==previous))throw Error('Invalid consent page cursor');
  return v as ConsentPage;
}

export class ConsentConsole{
  page:ConsentPage|null=null;
  pending:{body:string;intent:Record<string,unknown>;uncertain:boolean}|null=null;
  busy=false;message='Check the current consent decision history.';#generation=0;
  constructor(readonly scope:PermissionScope,private readonly changed:()=>void=()=>{}){}
  clear(){this.#generation++;this.page=null;this.pending=null;this.busy=false;}
  async read(before=0){
    if(this.busy||this.pending||!this.scope.active()||!Number.isSafeInteger(before)||before<0)return;
    const generation=++this.#generation;this.busy=true;this.page=null;this.changed();
    try{const value=await this.scope.request(before?'?before='+before:'');
      if(generation!==this.#generation||!this.scope.active())return;
      this.page=readConsentPage(value,this.scope.patientId);this.message='Consent history checked. Recorded declarations do not verify legal authority.';
    }catch{if(generation===this.#generation)this.message='Consent history unavailable. Recheck operator access.';}
    finally{if(generation===this.#generation){this.busy=false;this.changed();}}
  }
  async command(payload:Record<string,unknown>){
    if(this.busy||this.pending||!this.scope.active())return;
    const body=JSON.stringify(payload);this.pending={body,intent:JSON.parse(body),uncertain:false};await this.retry();
  }
  async retry(){
    const p=this.pending;if(!p||this.busy||!this.scope.active())return;
    const generation=++this.#generation;this.busy=true;this.page=null;this.changed();
    try{const value=await this.scope.request('',p.body);
      if(generation!==this.#generation||!this.scope.active())return;
      if(!object(value)||Object.keys(value).length!==8||value.patient_id!==this.scope.patientId||!positive(value.event_id)||
        value.revision!==Number(p.intent.expected_revision)+1||typeof value.duplicate!=='boolean'||
        ['actor','target_purpose','state','request_key'].some(key=>value[key]!==p.intent[key]))throw Error('Invalid consent receipt');
      this.pending=null;this.message='Consent decision recorded. Check history for the current decision.';
    }catch(error){if(generation!==this.#generation||!this.scope.active())return;
      if(!p.uncertain&&error instanceof PermissionHttpError&&[401,403,404,409,413,422].includes(error.status)){
        this.pending=null;this.message='Consent decision refused. Refresh history and recheck the intended revision.';
      }else{p.uncertain=true;this.message='The outcome is unknown. Retry the exact saved consent decision to recover its receipt.';}
    }finally{if(generation===this.#generation){this.busy=false;this.changed();}}
  }
}
