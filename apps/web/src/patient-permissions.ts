/** Transient permission console; persisted policy belongs exclusively to the API. */
export type PermissionGrant={grant_id:string;actor:string;purpose:'operations'|'research';actions:string[];
  relationship:string;authority_ref:string;granted_by:string;created_at:string;expires_at:string;
  revoked_at:string|null;revoked_by:string|null;revocation_ref:string|null;status:'active'|'expired'|'revoked';revision:1|2};
export type PermissionPage={patient_id:string;grants:PermissionGrant[];next_after:string|null;
  enforcement:'synthetic_fixture'|'persisted_grants';available_actions:string[];operator_expires_at:string};
export type PermissionScope={patientId:string;active:()=>boolean;request:(suffix:string,body?:string)=>Promise<unknown>};
export class PermissionHttpError extends Error{constructor(readonly status:number){super('Permission request unavailable');}}
export const permissionKey=(v:unknown):v is string=>typeof v==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$/.test(v);
const grantId=(v:unknown):v is string=>typeof v==='string'&&/^GRANT-[A-F0-9]{32}$/.test(v);
const object=(v:unknown):v is Record<string,unknown>=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const instant=(v:unknown)=>typeof v==='string'&&v.length<50&&Number.isFinite(Date.parse(v))&&/(Z|[+-]\d\d:\d\d)$/.test(v);
export function readPermissionPage(value:unknown,patient:string):PermissionPage{
  if(!object(value)||value.patient_id!==patient||!['persisted_grants','synthetic_fixture'].includes(String(value.enforcement))||
    !Array.isArray(value.grants)||value.grants.length>25||!(value.next_after===null||grantId(value.next_after))||
    !Array.isArray(value.available_actions)||value.available_actions.length>64||!value.available_actions.every(permissionKey)||
    value.available_actions.some(a=>['patient_create','patient_permissions_manage','patient_permissions_read'].includes(a))||
    !instant(value.operator_expires_at))throw Error('Invalid permission page');
  const ids=new Set<string>();
  for(const row of value.grants){
    if(!object(row)||!grantId(row.grant_id)||ids.has(row.grant_id)||!permissionKey(row.actor)||!permissionKey(row.granted_by)||!permissionKey(row.authority_ref)||
      !['operations','research'].includes(String(row.purpose))||!['patient','guardian','animal_owner','care_team','research_delegate'].includes(String(row.relationship))||
      !Array.isArray(row.actions)||!row.actions.length||row.actions.length>64||!row.actions.every(permissionKey)||
      !instant(row.created_at)||!instant(row.expires_at)||!['active','expired','revoked'].includes(String(row.status))||
      row.revision!==(row.status==='revoked'?2:1)||
      (row.status==='revoked'?(!instant(row.revoked_at)||!permissionKey(row.revoked_by)||!permissionKey(row.revocation_ref)):
        row.revoked_at!==null||row.revoked_by!==null||row.revocation_ref!==null))throw Error('Invalid permission history');
    ids.add(row.grant_id);
  }
  return value as PermissionPage;
}
export class PermissionConsole{
  page:PermissionPage|null=null;
  pending:{suffix:string;body:string;grantId?:string;uncertain:boolean}|null=null;
  busy=false;
  message='Check the current permission history.';
  #generation=0;
  constructor(readonly scope:PermissionScope,private readonly changed:()=>void=()=>{}){}
  clear(){this.#generation++;this.page=null;this.pending=null;this.busy=false;}
  async read(after=''){
    if(this.busy||this.pending||!this.scope.active())return;
    const generation=++this.#generation;this.busy=true;this.page=null;this.changed();
    try{
      const value=await this.scope.request(after?'?after='+encodeURIComponent(after):'');
      if(generation!==this.#generation||!this.scope.active())return;
      this.page=readPermissionPage(value,this.scope.patientId);this.message='Permission history checked.';
    }catch{if(generation===this.#generation)this.message='Permission history unavailable. Recheck operator access.';}
    finally{if(generation===this.#generation){this.busy=false;this.changed();}}
  }
  async command(payload:Record<string,unknown>,grant?:string){
    if(this.busy||this.pending||!this.scope.active()||(grant!==undefined&&!grantId(grant)))return;
    this.pending={suffix:grant?'/'+grant+'/revocations':'',body:JSON.stringify(payload),grantId:grant,uncertain:false};
    await this.retry();
  }
  async retry(){
    const pending=this.pending;if(!pending||this.busy||!this.scope.active())return;
    const generation=++this.#generation;this.busy=true;this.page=null;this.changed();
    try{
      const value=await this.scope.request(pending.suffix,pending.body);
      if(generation!==this.#generation||!this.scope.active())return;
      if(!object(value)||Object.keys(value).length!==3||value.patient_id!==this.scope.patientId||!grantId(value.grant_id)||
        typeof value.duplicate!=='boolean'||(pending.grantId&&pending.grantId!==value.grant_id))throw Error('Invalid receipt');
      this.pending=null;this.message='Permission change recorded. Check history to see current access.';
    }catch(error){
      if(generation!==this.#generation||!this.scope.active())return;
      if(!pending.uncertain&&error instanceof PermissionHttpError&&[401,403,404,409,413,422].includes(error.status)){
        this.pending=null;this.message='Permission change refused. Recheck current access and intent.';
      }else{
        pending.uncertain=true;
        this.message='The outcome is unknown. Retry the exact saved change to recover its receipt.';
      }
    }finally{if(generation===this.#generation){this.busy=false;this.changed();}}
  }
}
