/** Strict, source-owned H1 read projections. Not clinical interpretations. */
export type ReceiptState =
  'not_received' | 'source_current_unreviewed' |
  'source_superseded_reconciliation_required' | 'binding_revoked_not_usable';
export type ReceivedReference = Readonly<{
  case_id:string; source_id:string; version:number; sha256:string;
}>;
export type RecordRequest = Readonly<{
  request_id:string; patient_id:string; kind:string; record_label:string;
  source_organization:string; status:'requested'|'received'|'cancelled';
  revision:number; created_at:string; updated_at:string;
  receipt_status:ReceiptState; source_reference:ReceivedReference|null;
  external_request_sent:false;
}>;
export type OriginalSource = Readonly<{
  source_id:string; case_id:string; document_id:string; version:number;
  state:'current'|'superseded'; sha256:string; original_text:string;
  synthetic:true; clinical_review_state:'not_established';
}>;

const ID=/^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$/;
const CASE=/^CASE-[A-Z0-9-]{1,35}$/;
const SOURCE=/^SRC-[0-9A-F]{32}$/;
const HASH=/^[0-9a-f]{64}$/;
const KINDS=['clinical','pathology','laboratory','imaging','molecular','other'];
const RECEIPTS=['not_received','source_current_unreviewed',
  'source_superseded_reconciliation_required','binding_revoked_not_usable'];
const FIELDS=['request_id','patient_id','kind','record_label','source_organization',
  'status','revision','created_at','updated_at','receipt_status',
  'source_reference','external_request_sent'];

function object(value:unknown, fields:string[]): value is Record<string,unknown> {
  return value!==null && typeof value==='object' && !Array.isArray(value) &&
    Object.keys(value).length===fields.length && fields.every(k=>Object.hasOwn(value,k));
}
function validDate(value:unknown):value is string {
  return typeof value==='string' &&
    /^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
    Number.isFinite(Date.parse(value));
}
function text(value:unknown,max:number):value is string {
  return typeof value==='string' && value.length>=1 && value.length<=max &&
    !/[\u0000-\u001f\u007f]/.test(value);
}
function reference(value:unknown):ReceivedReference|null {
  if(value===null)return null;
  if(!object(value,['case_id','source_id','version','sha256']) ||
    typeof value.case_id!=='string' || !CASE.test(value.case_id) ||
    typeof value.source_id!=='string' || !SOURCE.test(value.source_id) ||
    !Number.isSafeInteger(value.version) || Number(value.version)<1 ||
    typeof value.sha256!=='string' || !HASH.test(value.sha256)) throw Error('contract');
  return Object.freeze(value as ReceivedReference);
}
export function decodeRecordRequests(value:unknown,patientId:string):readonly RecordRequest[] {
  if(!object(value,['patient_id','requests','synthetic','external_request_sent','source_receipts_enabled']) ||
    value.patient_id!==patientId || value.synthetic!==true ||
    value.external_request_sent!==false || value.source_receipts_enabled!==true ||
    !Array.isArray(value.requests) || value.requests.length>250) throw Error('contract');
  const seen=new Set<string>();
  return Object.freeze(value.requests.map((row:unknown)=>{
    if(!object(row,FIELDS) ||
      typeof row.request_id!=='string' || !ID.test(row.request_id) ||
      row.patient_id!==patientId || typeof row.kind!=='string' || !KINDS.includes(row.kind) ||
      !text(row.record_label,140) || !text(row.source_organization,100) ||
      !['requested','received','cancelled'].includes(String(row.status)) ||
      !Number.isSafeInteger(row.revision) || Number(row.revision)<1 ||
      !validDate(row.created_at) || !validDate(row.updated_at) ||
      typeof row.receipt_status!=='string' || !RECEIPTS.includes(row.receipt_status) ||
      row.external_request_sent!==false || seen.has(row.request_id)) throw Error('contract');
    seen.add(row.request_id);
    const source=reference(row.source_reference);
    if((row.status==='received')===(row.receipt_status==='not_received') ||
      (row.status!=='received' && source!==null) ||
      (row.receipt_status==='binding_revoked_not_usable' && source!==null)) throw Error('contract');
    return Object.freeze({...row,source_reference:source} as RecordRequest);
  }));
}
export async function decodeOriginal(value:unknown,expected:ReceivedReference):Promise<OriginalSource> {
  if(!object(value,['source_id','case_id','document_id','version','state','sha256',
                    'original_text','synthetic','clinical_review_state']) ||
     value.source_id!==expected.source_id || value.case_id!==expected.case_id ||
     value.version!==expected.version || value.sha256!==expected.sha256 ||
     typeof value.document_id!=='string' || !/^[A-Z][A-Z0-9-]{1,39}$/.test(value.document_id) ||
     !['current','superseded'].includes(String(value.state)) ||
     value.synthetic!==true || value.clinical_review_state!=='not_established' ||
     typeof value.original_text!=='string' || value.original_text.length>65536 ||
     !value.original_text.startsWith('OI-SYNTHETIC-REPORT/1\n')) throw Error('contract');
  // Verify the exact UTF-8 content against the independently selected receipt
  // fingerprint. Do not trust an unexpected HTTP response or a copied hash.
  if(!globalThis.crypto?.subtle)throw Error('contract');
  const raw=new TextEncoder().encode(value.original_text);
  if(raw.byteLength>65536)throw Error('contract');
  const digest=await globalThis.crypto.subtle.digest('SHA-256',raw);
  const actual=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');
  if(actual!==expected.sha256)throw Error('contract');
  return Object.freeze(value as OriginalSource);
}
