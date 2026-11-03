/** Exact, read-only decoder of the existing H1 PostgreSQL record-request owner.
 * No external institution contact, new authority, patient inference or storage.
 */
export type ReceiptState =
  'not_received' | 'source_current_unreviewed' |
  'source_superseded_reconciliation_required' | 'binding_revoked_not_usable';
export type ReceiptReference=Readonly<{
  case_id:string;source_id:string;version:number;sha256:string;
}>;
export type RecordRequest=Readonly<{
  request_id:string;patient_id:string;kind:string;record_label:string;
  source_organization:string;status:'requested'|'received'|'cancelled';
  revision:number;created_at:string;updated_at:string;
  receipt_status:ReceiptState;source_reference:ReceiptReference|null;
  external_request_sent:false;
}>;
export type RecordRequestIndex=Readonly<{
  patient_id:string;requests:ReadonlyArray<RecordRequest>;
  synthetic:true;external_request_sent:false;source_receipts_enabled:true;
}>;
const PATIENT=/^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$/;
const REQUEST=/^RECORD-[0-9A-F]{32}$/;
const CASE=/^CASE-[A-Z0-9-]{1,35}$/;
const SOURCE=/^SRC-[0-9A-F]{32}$/;
const SHA=/^[a-f0-9]{64}$/;
const KINDS=new Set(['clinical','pathology','laboratory','imaging','molecular','other']);
const RECEIPTS=new Set<ReceiptState>([
  'not_received','source_current_unreviewed',
  'source_superseded_reconciliation_required','binding_revoked_not_usable'
]);
function fail():never{throw Error('record-request-contract');}
function exact(value:unknown,keys:readonly string[]):value is Record<string,unknown>{
  return value!==null && typeof value==='object' && !Array.isArray(value) &&
    Object.keys(value).length===keys.length &&
    keys.every(key=>Object.hasOwn(value,key));
}
function text(value:unknown,max:number):value is string{
  return typeof value==='string' && value.length>0 && value.length<=max &&
    !/[\u0000-\u001f\u007f]/.test(value);
}
function time(value:unknown):value is string{
  return text(value,80) &&
    /^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
    Number.isFinite(Date.parse(value));
}
function positive(value:unknown):value is number{
  return typeof value==='number' && Number.isSafeInteger(value) && value>0;
}
export function parseRecordRequests(raw:unknown,expectedPatient:string):RecordRequestIndex{
  if(!PATIENT.test(expectedPatient) ||
     !exact(raw,['patient_id','requests','synthetic','external_request_sent','source_receipts_enabled']) ||
     raw.patient_id!==expectedPatient || raw.synthetic!==true ||
     raw.external_request_sent!==false || raw.source_receipts_enabled!==true ||
     !Array.isArray(raw.requests) || raw.requests.length>128) return fail();
  const seen=new Set<string>();
  const requests:RecordRequest[]=[];
  for(const entry of raw.requests){
    if(!exact(entry,[
      'request_id','patient_id','kind','record_label','source_organization',
      'status','revision','created_at','updated_at','receipt_status',
      'source_reference','external_request_sent'
    ]) || typeof entry.request_id!=='string' || !REQUEST.test(entry.request_id) ||
      seen.has(entry.request_id) || entry.patient_id!==expectedPatient ||
      !KINDS.has(String(entry.kind)) || !text(entry.record_label,140) ||
      !text(entry.source_organization,100) ||
      !['requested','received','cancelled'].includes(String(entry.status)) ||
      !positive(entry.revision) || !time(entry.created_at) || !time(entry.updated_at) ||
      !RECEIPTS.has(entry.receipt_status as ReceiptState) ||
      entry.external_request_sent!==false) return fail();

    // A receipt is an original immutable journal event. Never invent an
    // original source link for a request still pending or cancelled.
    if((entry.status==='received')===(entry.receipt_status==='not_received'))return fail();

    let source_reference:ReceiptReference|null=null;
    if(entry.source_reference!==null){
      const v=entry.source_reference;
      if(!exact(v,['case_id','source_id','version','sha256']) ||
         typeof v.case_id!=='string'||!CASE.test(v.case_id)||
         typeof v.source_id!=='string'||!SOURCE.test(v.source_id)||
         !positive(v.version) || typeof v.sha256!=='string'||!SHA.test(v.sha256) ||
         entry.status!=='received' || entry.receipt_status==='binding_revoked_not_usable')
        return fail();
      source_reference=Object.freeze({
        case_id:v.case_id,source_id:v.source_id,
        version:v.version,sha256:v.sha256
      });
    }
    seen.add(entry.request_id);
    requests.push(Object.freeze({
      request_id:entry.request_id,patient_id:expectedPatient,
      kind:entry.kind as string,record_label:entry.record_label,
      source_organization:entry.source_organization,
      status:entry.status as RecordRequest['status'],
      revision:entry.revision,created_at:entry.created_at,updated_at:entry.updated_at,
      receipt_status:entry.receipt_status as ReceiptState,
      source_reference,external_request_sent:false as const
    }));
  }
  return Object.freeze({
    patient_id:expectedPatient,requests:Object.freeze(requests),
    synthetic:true,external_request_sent:false,source_receipts_enabled:true
  });
}
