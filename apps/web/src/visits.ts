/** Patient-scoped encounter and note contracts from the first-party EHR API. */
export const visitKinds = ['outpatient','inpatient','telehealth','telephone','procedure','other'] as const;
export const noteKinds = ['history_and_physical','consultation','progress','procedure','operative','discharge','referral','nursing','other'] as const;
export type VisitKind = typeof visitKinds[number];
export type NoteKind = typeof noteKinds[number];
export type VisitStatus = 'scheduled'|'in_progress'|'completed'|'cancelled';
export type Target = Exclude<VisitStatus,'scheduled'>;
export type Visit = {id:number; external_key:string; kind:VisitKind; service_date:string; status:VisitStatus; revision:number};
export type Note = {id:number; note_key:string; latest_version:number};
export type Version = {version:number; body:string; status:string; sha256:string; authored_by:string; created_at:string;
  note_kind:NoteKind|null; facility_id:string|null; department_id:string|null; amendment_reason:string|null; hasNewer:boolean};
export type Page<T> = {items:T[]; next:number|null};
export type VisitCommand = (
  |{type:'schedule'; externalKey:string; kind:VisitKind; date:string}
  |{type:'move'; visitId:number; target:Target; expected:number}
  |{type:'save'; visitId:number; noteKey:string; expected:number; body:string; kind:NoteKind|null}
) & {requestKey:string};
export const pageSize=10;

export class VisitHttpError extends Error {
  constructor(readonly status:number){super('Visit request failed');}
}
function check(condition:unknown):asserts condition {if(!condition)throw Error('Invalid visit response');}
function object(value:unknown):Record<string,unknown>{
  check(value && typeof value==='object' && !Array.isArray(value));
  return value as Record<string,unknown>;
}
function integer(value:unknown,min=1):value is number{return typeof value==='number'&&Number.isSafeInteger(value)&&value>=min;}
function key(value:unknown):value is string{return typeof value==='string' && /^[A-Z][A-Z0-9-]{1,39}$/.test(value)&&!/[\r\n]/.test(value);}
function label(value:unknown,max=100):value is string{return typeof value==='string'&&value.length>0&&value.length<=max&&!value.includes('\0');}
function oneOf<T extends string>(value:unknown,allowed:readonly T[]):value is T{return allowed.some(item=>item===value);}
function dateTime(value:unknown):value is string{return typeof value==='string'&&/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value)&&Number.isFinite(Date.parse(value));}
function dateOnly(value:unknown):value is string{
  if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))return false;
  const ms=Date.parse(value);return Number.isFinite(ms)&&new Date(ms).toISOString().slice(0,10)===value;
}
async function digest(text:string){
  const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));
  return [...new Uint8Array(bytes)].map(x=>x.toString(16).padStart(2,'0')).join('');
}
function page<T extends {id:number}>(items:T[],next:unknown,after:number):Page<T>{
  check(items.length<=pageSize && items.every((v,i)=>v.id>(i?items[i-1].id:after)));
  check(next===null || (integer(next)&&items.length===pageSize&&next===items.at(-1)?.id));
  return {items,next};
}

export class VisitClient{
  constructor(private readonly patientId:string,private readonly request:(suffix:string,body?:string)=>Promise<unknown>){}
  private async read(path:string,visitId?:number){
    const value=object(await this.request(path));
    check(value.patient_id===this.patientId && typeof value.access_receipt_id==='string'&&/^ACCESS-[A-F0-9]{32}$/.test(value.access_receipt_id));
    if(visitId!==undefined)check(value.encounter_id===visitId);
    return value;
  }
  async list(after:number):Promise<Page<Visit>>{
    check(integer(after,0));
    const data=await this.read(`?after_id=${after}&limit=${pageSize}`);
    check(Array.isArray(data.encounters));
    const items=data.encounters.map(raw=>{
      const r=object(raw);
      check(r.patient_id===this.patientId && integer(r.id)&&integer(r.revision)&&key(r.external_key)&&oneOf(r.kind,visitKinds)
        &&dateOnly(r.service_date)&&dateTime(r.created_at)&&dateTime(r.updated_at)&&oneOf(r.status,['scheduled','in_progress','completed','cancelled'] as const));
      return {id:r.id,external_key:r.external_key,kind:r.kind,service_date:r.service_date,status:r.status,revision:r.revision};
    });
    return page(items,data.next_after_id,after);
  }
  async notes(visitId:number,after:number):Promise<Page<Note>>{
    check(integer(visitId)&&integer(after,0));
    const data=await this.read(`/${visitId}/notes?after_id=${after}&limit=${pageSize}`,visitId);
    check(Array.isArray(data.notes));
    const items=data.notes.map(raw=>{
      const r=object(raw);check(integer(r.id)&&key(r.note_key)&&integer(r.latest_version));
      return {id:r.id,note_key:r.note_key,latest_version:r.latest_version};
    });
    check(new Set(items.map(n=>n.note_key)).size===items.length);
    return page(items,data.next_after_id,after);
  }
  async version(visitId:number,noteKey:string,number:number):Promise<Version>{
    check(integer(visitId)&&key(noteKey)&&integer(number));
    const data=await this.read(`/${visitId}/notes/${noteKey}/versions?after_version=${number-1}&limit=1`,visitId);
    check(data.note_key===noteKey && Array.isArray(data.versions)&&data.versions.length===1 && (data.next_after_version===null||data.next_after_version===number));
    const r=object(data.versions[0]);
    check(r.version===number && integer(r.id) && oneOf(r.status,['draft','draft_correction','attested','attested_correction'])
      && typeof r.body==='string'&&r.body.length>0&&[...r.body].length<=20000 && typeof r.sha256==='string' && r.sha256===await digest(r.body)
      && label(r.authored_by)&&dateTime(r.created_at)&&(r.note_kind===null||oneOf(r.note_kind,noteKinds))
      && (r.facility_id===null||label(r.facility_id))&&(r.department_id===null||label(r.department_id))&&(r.amendment_reason===null||label(r.amendment_reason,1000)));
    return {version:number,body:r.body,sha256:r.sha256,status:r.status,authored_by:r.authored_by,created_at:r.created_at,note_kind:r.note_kind,
      facility_id:r.facility_id,department_id:r.department_id,amendment_reason:r.amendment_reason,hasNewer:data.next_after_version!==null};
  }
  async submit(c:VisitCommand){
    const common={synthetic:true,request_key:c.requestKey};
    check(/^[A-Za-z0-9_.:-]{8,100}$/.test(c.requestKey));
    if(c.type==='schedule'){
      check(key(c.externalKey)&&oneOf(c.kind,visitKinds)&&dateOnly(c.date));
      const r=object(await this.request('',JSON.stringify({...common,external_key:c.externalKey,kind:c.kind,service_date:c.date})));
      check(integer(r.encounter_id)&&r.status==='scheduled'&&r.revision===1);return r.encounter_id;
    }
    check(integer(c.visitId));
    if(c.type==='move'){
      check(integer(c.expected)&&oneOf(c.target,['in_progress','completed','cancelled']));
      const r=object(await this.request(`/${c.visitId}/transitions`,JSON.stringify({...common,target:c.target,expected_revision:c.expected})));
      check(r.encounter_id===c.visitId&&r.revision===c.expected+1&&r.status===c.target);return c.visitId;
    }
    check(key(c.noteKey)&&integer(c.expected,0)&&c.body.trim().length>0&&[...c.body].length<=20000&&!c.body.includes('\0')&&(c.kind===null||oneOf(c.kind,noteKinds)));
    const body=c.body.trim();
    const r=object(await this.request(`/${c.visitId}/notes/${c.noteKey}/versions`,
      JSON.stringify({...common,expected_version:c.expected,body,note_kind:c.kind})));
    check(integer(r.note_id)&&r.note_key===c.noteKey&&r.version===c.expected+1&&oneOf(r.status,['draft','draft_correction'])&&r.sha256===await digest(body));
    return r.note_id;
  }
}
