/** Bounded original-text intake, not clinical parsing, identity or permission. */
import type {SourceVersion} from './source-contracts.js';
export type PreparedSource = Readonly<{text:string;declaredCase:string;byteLength:number}>;
export type ImportReceipt = Readonly<{
  result:'imported'|'duplicate'|'quarantined';duplicate:boolean;source_id:string|null;version:number|null;
}>;
export type OriginalSource = Readonly<{
  source_id:string;case_id:string;document_id:string;version:number;state:'current'|'superseded';
  sha256:string;original_text:string;synthetic:true;clinical_review_state:'not_established';
}>;
function exact(v:unknown,keys:string[]):v is Record<string,unknown>{
  return v!==null && typeof v==='object' && !Array.isArray(v) &&
    Object.keys(v).length===keys.length && keys.every(k=>Object.hasOwn(v,k));
}
export function prepareSource(bytes:Uint8Array,name:string):PreparedSource{
  if(typeof name!=='string'||!name.toLowerCase().endsWith('.txt'))throw Error('Choose an original fictional .txt report; PDF and scans are not connected to this H1 intake.');
  if(!(bytes instanceof Uint8Array)||bytes.byteLength<1||bytes.byteLength>65536)throw Error('The original must contain 1–65,536 bytes.');
  let text:string;
  try{text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes);}catch(_){throw Error('Invalid UTF-8. No content was normalized or uploaded.');}
  if(!text.startsWith('OI-SYNTHETIC-REPORT/1\n')||text.includes('\r')||text.includes('\0'))throw Error('Use the authored synthetic report format with LF line endings, no BOM or NUL. Nothing was rewritten.');
  const encoded=new TextEncoder().encode(text);
  if(encoded.length!==bytes.length||encoded.some((v,i)=>v!==bytes[i]))throw Error('Source bytes did not round-trip unchanged.');
  const headers=text.split('\n').filter(line=>line.startsWith('Patient:'));
  if(headers.length!==1||!/^Patient: CASE-[A-Z0-9-]{1,35}$/.test(headers[0]))throw Error('One exact fictional Patient: CASE-… header is required.');
  return Object.freeze({text,declaredCase:headers[0].slice(9),byteLength:bytes.length});
}
export function parseImportReceipt(v:unknown):ImportReceipt{
  if(!exact(v,['result','duplicate','source_id','version'])||typeof v.duplicate!=='boolean')throw Error('contract');
  if(v.result==='quarantined'){
    if(v.source_id!==null||v.version!==null)throw Error('contract');
  }else{
    if(!['imported','duplicate'].includes(String(v.result))||v.duplicate!==(v.result==='duplicate')||
      typeof v.source_id!=='string'||!/^SRC-[0-9A-F]{32}$/.test(v.source_id)||
      typeof v.version!=='number'||!Number.isSafeInteger(v.version)||v.version<1)throw Error('contract');
  }
  return Object.freeze(v as ImportReceipt);
}
export async function verifyOriginal(v:unknown,caseId:string,source:SourceVersion):Promise<OriginalSource>{
  if(!exact(v,['source_id','case_id','document_id','version','state','sha256','original_text','synthetic','clinical_review_state'])||
     v.source_id!==source.source_id||v.case_id!==caseId||v.document_id!==source.document_id||
     v.version!==source.version||v.state!==source.state||v.sha256!==source.sha256||
     v.synthetic!==true||v.clinical_review_state!=='not_established'||typeof v.original_text!=='string')throw Error('contract');
  const bytes=new TextEncoder().encode(v.original_text);
  const prepared=prepareSource(bytes,'original.txt');
  if(prepared.declaredCase!==caseId||prepared.text!==v.original_text)throw Error('contract');
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
  if(hash!==source.sha256)throw Error('contract');
  return Object.freeze(v as OriginalSource);
}
