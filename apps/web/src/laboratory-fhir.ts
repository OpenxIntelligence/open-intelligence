/** Local original inspection and receipt validation; the server owns FHIR validation. */
export type LaboratoryFile=Readonly<{text:string;byteCount:number;sha256:string}>;
export type LaboratoryReceipt=Readonly<{source_id:string;version:number;duplicate:boolean;
  original_sha256:string;observation_count:number}>;
export type LaboratoryIntent=Readonly<{patient_id:string;case_id:string;body:string;sha256:string}>;
export type LaboratoryImportState=Readonly<{
  laboratoryPhase:'idle'|'sending'|'unknown'|'saved'|'error';
  laboratoryIntent:LaboratoryIntent|null;laboratoryReceipt:LaboratoryReceipt|null;laboratoryMessage:string;
}>;
export const emptyLaboratory=():LaboratoryImportState=>({laboratoryPhase:'idle',laboratoryIntent:null,
  laboratoryReceipt:null,laboratoryMessage:''});

export async function prepareLaboratoryFile(bytes:Uint8Array,name:string):Promise<LaboratoryFile>{
  if(!/\.json$/i.test(name)||bytes.byteLength<1||bytes.byteLength>65536)
    throw Error('Choose an independently authored fictional JSON file up to 64 KiB.');
  let text:string;
  try{text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes);}
  catch(_){throw Error('The file must be valid UTF-8. Nothing was rewritten or sent.');}
  const encoded=new TextEncoder().encode(text);
  if(encoded.length!==bytes.length||encoded.some((v,i)=>v!==bytes[i])||text.startsWith('\uFEFF'))
    throw Error('The original UTF-8 bytes cannot be preserved. Nothing was sent.');
  // Inspect only the envelope. Clinical values are never normalized or interpreted here.
  let value:unknown;
  try{value=JSON.parse(text);}catch(_){throw Error('The selected file is not JSON. Nothing was sent.');}
  if(!value||typeof value!=='object'||Array.isArray(value)||
     (value as {resourceType?:unknown}).resourceType!=='Bundle')
    throw Error('Select a fictional FHIR laboratory Bundle. The server checks its supported profile.');
  const sha256=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new Uint8Array(bytes))),
    b=>b.toString(16).padStart(2,'0')).join('');
  return Object.freeze({text,byteCount:bytes.length,sha256});
}

export function parseLaboratoryReceipt(value:unknown,sha256:string,status:number):LaboratoryReceipt{
  if(!value||typeof value!=='object'||Array.isArray(value))throw Error('laboratory-receipt');
  const v=value as Record<string,unknown>;
  const keys=['source_id','version','duplicate','original_sha256','observation_count'];
  if(Object.keys(v).length!==keys.length||keys.some(k=>!Object.hasOwn(v,k))||
     typeof v.source_id!=='string'||!/^SRC-[A-F0-9]{32}$/.test(v.source_id)||
     typeof v.version!=='number'||!Number.isSafeInteger(v.version)||v.version<1||
     typeof v.duplicate!=='boolean'||v.duplicate!==(status===200)||![200,201].includes(status)||
     v.original_sha256!==sha256||!/^[a-f0-9]{64}$/.test(sha256)||
     typeof v.observation_count!=='number'||!Number.isSafeInteger(v.observation_count)||
     v.observation_count<1||v.observation_count>16)throw Error('laboratory-receipt');
  return Object.freeze(v as LaboratoryReceipt);
}

export type SourceIdentity=Readonly<{identity_id:string;source_organization:string;source_system:string;
  source_subject_ref:string;review_ref:string;created_by:string;created_at:string;
  status:'linked'|'quarantined';primary_identity:boolean}>;
export function readSourceIdentities(value:unknown,patientId:string,caseId:string):readonly SourceIdentity[]{
  if(!value||typeof value!=='object'||Array.isArray(value))throw Error('Source identities unavailable');
  const v=value as Record<string,unknown>;
  if(Object.keys(v).length!==3||v.patient_id!==patientId||v.case_id!==caseId||
     !Array.isArray(v.identities)||v.identities.length<1||v.identities.length>64)throw Error('Source identity scope');
  const seen=new Set<string>();let primary=0;
  const rows=v.identities.map((raw:unknown)=>{
    if(!raw||typeof raw!=='object'||Array.isArray(raw))throw Error('Source identity');
    const r=raw as Record<string,unknown>;
    const keys=['identity_id','source_organization','source_system','source_subject_ref','review_ref','created_by','created_at','status','primary_identity'];
    if(Object.keys(r).length!==keys.length||keys.some(k=>!Object.hasOwn(r,k))||
       typeof r.identity_id!=='string'||!/^IDENT-[0-9A-F]{32}$/.test(r.identity_id)||seen.has(r.identity_id)||
       ['source_organization','source_system','source_subject_ref','review_ref','created_by'].some(k=>
         typeof r[k]!=='string'||!/^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$/.test(r[k] as string))||
       typeof r.created_at!=='string'||!Number.isFinite(Date.parse(r.created_at))||
       !['linked','quarantined'].includes(r.status as string)||typeof r.primary_identity!=='boolean'||
       (r.primary_identity&&r.status!=='linked'))throw Error('Source identity');
    seen.add(r.identity_id);if(r.primary_identity)primary++;
    return Object.freeze(r as SourceIdentity);
  });
  if(primary!==1)throw Error('Primary source identity unavailable');
  return Object.freeze(rows);
}
