/** Verify an existing source-owner original, never interpret it.
 * Exact source_id/version/hash/state must match the last authorized index;
 * a later amendment requires explicitly refreshing that index.
 */
import type {SourceIndex} from './source-contracts.js';

export type ExactOriginal = Readonly<{
  source_id:string; case_id:string; document_id:string; version:number;
  state:'current'|'superseded'; sha256:string; original_text:string;
}>;

export async function parseExactOriginal(value:unknown,index:SourceIndex,sourceId:string):Promise<ExactOriginal>{
  if(!/^SRC-[0-9A-F]{32}$/.test(sourceId)||
     value===null||typeof value!=='object'||Array.isArray(value))throw Error('original-contract');
  const raw=value as Record<string,unknown>;
  const fields=['source_id','case_id','document_id','version','state',
    'sha256','original_text','synthetic','clinical_review_state'];
  if(Object.keys(raw).length!==fields.length||
     fields.some(key=>!Object.hasOwn(raw,key)))throw Error('original-contract');
  const selected=index.sources.find(s=>s.source_id===sourceId);
  if(!selected||raw.source_id!==sourceId||raw.case_id!==index.case_id||
     raw.document_id!==selected.document_id||raw.version!==selected.version||
     raw.state!==selected.state||raw.sha256!==selected.sha256||
     raw.synthetic!==true||raw.clinical_review_state!=='not_established'||
     typeof raw.original_text!=='string')throw Error('original-contract');
  const encoded=new TextEncoder().encode(raw.original_text);
  if(encoded.byteLength<1||encoded.byteLength>65_536)throw Error('original-size');
  // Index metadata is insufficient to establish document custody: verify actual bytes.
  if(!crypto.subtle?.digest)throw Error('digest-unavailable');
  const computed=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',encoded)))
    .map(v=>v.toString(16).padStart(2,'0')).join('');
  if(computed!==selected.sha256)throw Error('original-hash-mismatch');
  return Object.freeze({
    source_id:sourceId,case_id:index.case_id,document_id:selected.document_id,
    version:selected.version,state:selected.state,sha256:computed,
    original_text:raw.original_text,
  });
}
