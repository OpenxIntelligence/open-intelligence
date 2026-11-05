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
