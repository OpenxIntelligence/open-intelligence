/** Patient-scoped views of canonical EHR records. This client holds no authority or credentials. */
export const encounterKinds = ['outpatient','inpatient','telehealth','telephone','procedure','other'] as const;
export const noteKinds = ['history_and_physical','consultation','progress','procedure','operative',
  'discharge','referral','nursing','other'] as const;
const states = ['scheduled','in_progress','completed','cancelled'] as const;
const noteStates = ['draft','attested','draft_correction','attested_correction'] as const;
export type EncounterKind = typeof encounterKinds[number];
export type VisitState = typeof states[number];
export type NoteKind = typeof noteKinds[number];
type NoteState = typeof noteStates[number];

export type Encounter = {id:number;patient_id:string;external_key:string;kind:EncounterKind;
  service_date:string;status:VisitState;revision:number;created_at:string;updated_at:string};
export type EncounterPage = {patient_id:string;encounters:Encounter[];next_after_id:number|null;access_receipt_id:string};
export type NoteHeader = {id:number;note_key:string;latest_version:number};
export type NotesPage = {patient_id:string;encounter_id:number;notes:NoteHeader[];next_after_id:number|null;access_receipt_id:string};
export type NoteVersion = {id:number;version:number;status:NoteState;body:string;sha256:string;authored_by:string;
  created_at:string;supersedes_id:number|null;amendment_reason:string|null;facility_id:string|null;
  department_id:string|null;note_kind:NoteKind|null};
export type NoteHistory = {patient_id:string;encounter_id:number;note_key:string;versions:NoteVersion[];
  next_after_version:number|null;access_receipt_id:string};
type Command = {synthetic:true;request_key:string};
export type ScheduleCommand = Command & {external_key:string;kind:EncounterKind;service_date:string};
export type TransitionCommand = Command & {target:Exclude<VisitState,'scheduled'>;expected_revision:number};
export type DraftNoteCommand = Command & {expected_version:number;body:string;note_kind?:NoteKind|null;
  facility_id?:string|null;department_id?:string|null};
export type EncounterReceipt = {encounter_id:number;status:VisitState;revision:number};
export type NoteReceipt = {note_id:number;note_key:string;version:number;status:'draft'|'draft_correction';sha256:string};
export interface EncounterChart {
  visits(after?:number):Promise<EncounterPage>;
  notes(id:number,after?:number):Promise<NotesPage>;
  versions(id:number,key:string,after?:number):Promise<NoteHistory>;
  schedule(command:ScheduleCommand):Promise<EncounterReceipt>;
  transition(id:number,command:TransitionCommand):Promise<EncounterReceipt>;
  saveNote(id:number,key:string,command:DraftNoteCommand):Promise<NoteReceipt>;
}
export class EncounterHttpError extends Error {
  constructor(readonly status:number){super('Encounter request returned HTTP '+status);this.name='EncounterHttpError';}
}
export class EncounterInputError extends Error {
  constructor(){super('Check the encounter command before sending');this.name='EncounterInputError';}
}
const invalid=():never=>{throw new EncounterInputError();};
type Request = <T>(suffix:string,body:string|undefined,maxBytes:number,
  decode:(data:unknown)=>T|Promise<T>)=>Promise<T>;
const limit=25, intMax=2147483647;
const fail=():never=>{throw Error('Encounter data could not be verified');};
function fields(value:unknown,required:string[],optional:string[]=[]):value is Record<string,unknown>{
  return value!==null&&typeof value==='object'&&!Array.isArray(value)&&required.every(k=>Object.hasOwn(value,k))&&
    Object.keys(value).every(k=>required.includes(k)||optional.includes(k));
}
const int=(x:unknown,min=1,max=Number.MAX_SAFE_INTEGER):x is number=>
  typeof x==='number'&&Number.isSafeInteger(x)&&x>=min&&x<=max;
const matches=(x:unknown,re:RegExp):x is string=>typeof x==='string'&&re.test(x);
const member=<T extends string>(x:unknown,options:readonly T[]):x is T=>options.some(v=>v===x);
const key=(x:unknown)=>matches(x,/^[A-Z][A-Z0-9-]{1,39}$/);
const opaque=(x:unknown)=>matches(x,/^[A-Za-z0-9_.:-]{8,100}$/);
const access=(x:unknown)=>matches(x,/^ACCESS-[A-F0-9]{32}$/);
const hash=(x:unknown)=>matches(x,/^[a-f0-9]{64}$/);
function date(x:unknown):x is string{
  if(!matches(x,/^\d{4}-\d{2}-\d{2}$/)||x.startsWith('0000'))return false;
  const parsed=new Date(x+'T00:00:00Z');
  return Number.isFinite(parsed.valueOf())&&parsed.toISOString().slice(0,10)===x;
}
const instant=(x:unknown)=>matches(x,/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/)&&
  date(x.slice(0,10))&&Number.isFinite(Date.parse(x));
// The canonical domain strips Python whitespace before persisting or hashing a draft.
const white=/[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/;
function strip(s:string){
  let first=0,last=s.length;
  while(first<last&&white.test(s[first]))first++;
  while(last>first&&white.test(s[last-1]))last--;
  return s.slice(first,last);
}
const validText=(x:unknown,max:number):x is string=>typeof x==='string'&&x.length>0&&x.length<=2*max&&
  !/[\u0000\ud800-\udfff]/u.test(x)&&Array.from(x).length<=max&&strip(x).length>0;
async function digest(body:string){
  const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(body));
  return Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('');
}
const query=(after:number,name='after_id')=>int(after,0)?'?'+name+'='+after+'&limit='+limit:invalid();
const visitPath=(id:number)=>int(id)?'/'+id:invalid();
const historyPath=(id:number,k:string)=>key(k)?visitPath(id)+'/notes/'+k+'/versions':invalid();

function checkPage<T>(rows:T[],next:unknown,after:number,cursor:(r:T)=>number){
  if(rows.length>limit)return fail();
  let last=after;
  for(const row of rows){const n=cursor(row);if(!int(n)||n<=last)return fail();last=n;}
  if(next!==null&&(rows.length!==limit||next!==last))return fail();
}
function visit(row:unknown,patientId:string):Encounter{
  if(!fields(row,['id','patient_id','external_key','kind','service_date','status','revision','created_at','updated_at'])||
    !int(row.id)||row.patient_id!==patientId||!key(row.external_key)||!member(row.kind,encounterKinds)||
    !date(row.service_date)||!member(row.status,states)||!int(row.revision)||!instant(row.created_at)||!instant(row.updated_at))return fail();
  return row as Encounter;
}
function header(row:unknown):NoteHeader{
  if(!fields(row,['id','note_key','latest_version'])||!int(row.id)||!key(row.note_key)||!int(row.latest_version,1,intMax))return fail();
  return row as NoteHeader;
}
type Anchor = Pick<NoteVersion,'id'|'version'|'sha256'|'status'>;
function noteVersion(row:unknown,prior:Anchor|null):NoteVersion{
  if(!fields(row,['id','version','status','body','sha256','authored_by','created_at','supersedes_id','amendment_reason','facility_id','department_id','note_kind'])||
    !int(row.id)||!int(row.version,1,intMax)||!member(row.status,noteStates)||!validText(row.body,20000)||strip(row.body)!==row.body||!hash(row.sha256)||
    !matches(row.authored_by,/^[A-Za-z0-9_.:-]{3,100}$/)||!instant(row.created_at)||
    !(row.note_kind===null||member(row.note_kind,noteKinds))||!(row.facility_id===null||opaque(row.facility_id))||
    !(row.department_id===null||opaque(row.department_id))||row.version!==(prior?.version??0)+1||
    row.supersedes_id!==(prior?.id??null)||row.id<=(prior?.id??0))return fail();
  const correction=row.status==='draft_correction'||row.status==='attested_correction';
  if(correction?!validText(row.amendment_reason,500):row.amendment_reason!==null)return fail();
  if(!prior){if(row.status!=='draft')return fail();}
  else if(row.status==='attested'||row.status==='attested_correction'){
    if(prior.status!==(correction?'draft_correction':'draft')||prior.sha256!==row.sha256)return fail();
  }else if((row.status==='draft')!==(prior.status==='draft'))return fail();
  return row as NoteVersion;
}
function encounterReceipt(x:unknown,status:VisitState,revision:number,id?:number):EncounterReceipt{
  if(!fields(x,['encounter_id','status','revision'])||!int(x.encounter_id)||(id!==undefined&&x.encounter_id!==id)||
    x.status!==status||x.revision!==revision||!int(x.revision))return fail();
  return x as EncounterReceipt;
}
const commandOK=(c:Command)=>c.synthetic===true&&opaque(c.request_key);

export function createEncounterChart(patientId:string,request:Request):EncounterChart{
  // Retain only continuation identities, never a cached version body or permission.
  const continuations=new Map<string,Anchor>();
  return {
    async visits(after=0){
      return request(query(after),undefined,65536,x=>{
        if(!fields(x,['patient_id','encounters','next_after_id','access_receipt_id'])||x.patient_id!==patientId||
          !access(x.access_receipt_id)||!Array.isArray(x.encounters)||x.encounters.length>limit)return fail();
        const rows=x.encounters.map(r=>visit(r,patientId));checkPage(rows,x.next_after_id,after,r=>r.id);
        if(new Set(rows.map(r=>r.external_key)).size!==rows.length)return fail();
        return x as EncounterPage;
      });
    },
    async notes(id,after=0){
      return request(visitPath(id)+'/notes'+query(after),undefined,65536,x=>{
        if(!fields(x,['patient_id','encounter_id','notes','next_after_id','access_receipt_id'])||x.patient_id!==patientId||
          x.encounter_id!==id||!access(x.access_receipt_id)||!Array.isArray(x.notes)||x.notes.length>limit)return fail();
        const rows=x.notes.map(header);checkPage(rows,x.next_after_id,after,r=>r.id);
        if(new Set(rows.map(r=>r.note_key)).size!==rows.length)return fail();
        return x as NotesPage;
      });
    },
    async versions(id,k,after=0){
      const path=historyPath(id,k),suffix=path+query(after,'after_version');
      const prior=after===0?null:continuations.get(path);
      if(prior===undefined||(prior&&prior.version!==after))return fail();
      // 25 × (20k body + 500 reason) code points, up to 12 bytes per JSON-escaped
      // supplementary character, plus bounded attribution fields and envelope.
      return request(suffix,undefined,7*1024*1024,async x=>{
        if(!fields(x,['patient_id','encounter_id','note_key','versions','next_after_version','access_receipt_id'])||
          x.patient_id!==patientId||x.encounter_id!==id||x.note_key!==k||!access(x.access_receipt_id)||
          !Array.isArray(x.versions)||x.versions.length>limit||(prior&&x.versions.length===0))return fail();
        let prev=prior;
        for(const raw of x.versions){const row=noteVersion(raw,prev);if(await digest(row.body)!==row.sha256)return fail();prev=row;}
        checkPage(x.versions as NoteVersion[],x.next_after_version,after,r=>r.version);
        if(x.next_after_version!==null&&prev){
          const {id,version,status,sha256}=prev;continuations.set(path,{id,version,status,sha256});
        }else continuations.delete(path);
        return x as NoteHistory;
      });
    },
    async schedule(c){
      if(!fields(c,['synthetic','request_key','external_key','kind','service_date'])||!commandOK(c)||!key(c.external_key)||
        !member(c.kind,encounterKinds)||!date(c.service_date))return invalid();
      return request('',JSON.stringify(c),4096,x=>encounterReceipt(x,'scheduled',1));
    },
    async transition(id,c){
      if(!fields(c,['synthetic','request_key','target','expected_revision'])||!commandOK(c)||!member(c.target,['in_progress','completed','cancelled'])||
        !int(c.expected_revision,1,Number.MAX_SAFE_INTEGER-1))return invalid();
      const {target,expected_revision}=c;
      return request(visitPath(id)+'/transitions',JSON.stringify(c),4096,x=>encounterReceipt(x,target,expected_revision+1,id));
    },
    async saveNote(id,k,c){
      if(!fields(c,['synthetic','request_key','expected_version','body'],['note_kind','facility_id','department_id'])||!commandOK(c)||
        !int(c.expected_version,0,intMax-1)||!validText(c.body,20000)||!(c.note_kind==null||member(c.note_kind,noteKinds))||
        !(c.facility_id==null||opaque(c.facility_id))||!(c.department_id==null||opaque(c.department_id)))return invalid();
      const {expected_version,body}=c;
      return request(historyPath(id,k),JSON.stringify(c),4096,async x=>{
        if(!fields(x,['note_id','note_key','version','status','sha256'])||!int(x.note_id)||x.note_key!==k||
          x.version!==expected_version+1||!(x.status==='draft'||(expected_version>0&&x.status==='draft_correction'))||
          x.sha256!==await digest(strip(body)))return fail();
        return x as NoteReceipt;
      });
    }
  };
}
