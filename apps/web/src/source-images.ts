/** Read projections of the existing source-image custody API, not a second image owner. */
import type {SourceVersion} from './source-contracts.js';

export type SourceImage=Readonly<{
 image_id:string;source_id:string;case_id:string;sha256:string;byte_count:number;
 study_uid:string;series_uid:string;sop_uid:string;modality:'CT'|'MR';study_date:string;
}>;
export type SourceImageIndex=Readonly<{
 patient_id:string;case_id:string;source_id:string;images:readonly SourceImage[];
 access_receipt_id:string;synthetic:true;source_identity_verified:false;
}>;
export type SourceImageDownload=Readonly<{
 patient_id:string;case_id:string;source_id:string;image_id:string;sha256:string;
 byte_count:number;access_receipt_id:string;
}>;
export type SourceImagesState=Readonly<{
 sourceImages:SourceImageIndex|null;sourceImagesSourceId:string|null;
 sourceImagesPhase:'idle'|'loading'|'ready'|'error';sourceImagesMessage:string;
 sourceImageDownload:SourceImageDownload|null;
 sourceImageDownloadPhase:'idle'|'loading'|'ready'|'error';sourceImageDownloadMessage:string;
}>;
export const emptySourceImages=():SourceImagesState=>({sourceImages:null,sourceImagesSourceId:null,
 sourceImagesPhase:'idle',sourceImagesMessage:'Inspect linked original images for a current imaging report.',
 sourceImageDownload:null,sourceImageDownloadPhase:'idle',sourceImageDownloadMessage:''});
const IMAGE=/^IMG-[0-9A-F]{32}$/,RECEIPT=/^ACCESS-[0-9A-F]{32}$/,SHA=/^[0-9a-f]{64}$/;
const MAX_BYTES=2_097_152;
function exact(value:unknown,keys:readonly string[]):value is Record<string,unknown>{
 return value!==null&&typeof value==='object'&&!Array.isArray(value)&&
  Object.keys(value).length===keys.length&&keys.every(key=>Object.hasOwn(value,key));
}
function uid(value:unknown):value is string{
 return typeof value==='string'&&value.length<=64&&/^(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+$/.test(value);
}
function day(value:unknown):value is string{
 if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))return false;
 const date=new Date(value+'T00:00:00.000Z');
 return Number.isFinite(date.getTime())&&date.toISOString().slice(0,10)===value;
}
export function decodeSourceImages(value:unknown,patientId:string,caseId:string,source:SourceVersion):SourceImageIndex{
 if(source.kind!=='imaging'||source.state!=='current'||
  !exact(value,['patient_id','case_id','source_id','images','access_receipt_id','synthetic','source_identity_verified'])||
  value.patient_id!==patientId||value.case_id!==caseId||value.source_id!==source.source_id||
  typeof value.access_receipt_id!=='string'||!RECEIPT.test(value.access_receipt_id)||
  value.synthetic!==true||value.source_identity_verified!==false||!Array.isArray(value.images)||value.images.length>256)throw Error('image index');
 const images:SourceImage[]=[],seen=new Set<string>();let total=0;
 const hierarchy = new Map<string, string>();
 function bindUid(uid: string, owner: string) {
  const previous = hierarchy.get(uid);
  if (previous !== undefined && previous !== owner) throw Error('image hierarchy');
  hierarchy.set(uid, owner);
 }
 for(const raw of value.images){
  if(!exact(raw,['image_id','source_id','case_id','sha256','byte_count','study_uid','series_uid','sop_uid','modality','study_date'])||
   typeof raw.image_id!=='string'||!IMAGE.test(raw.image_id)||seen.has(raw.image_id)||
   raw.source_id!==source.source_id||raw.case_id!==caseId||typeof raw.sha256!=='string'||!SHA.test(raw.sha256)||
   typeof raw.byte_count!=='number'||!Number.isSafeInteger(raw.byte_count)||raw.byte_count<132||raw.byte_count>MAX_BYTES||
   !uid(raw.study_uid)||!uid(raw.series_uid)||!uid(raw.sop_uid)||(raw.modality!=='CT'&&raw.modality!=='MR')||
   !day(raw.study_date)||raw.study_date!==source.event_date)throw Error('image index');
  bindUid(raw.study_uid, 'study');
  bindUid(raw.series_uid, 'series:' + raw.study_uid + ':' + raw.modality);
  bindUid(raw.sop_uid, 'instance:' + raw.image_id);
  total+=raw.byte_count;if(total>67_108_864)throw Error('image index');
  seen.add(raw.image_id);images.push(Object.freeze({...raw} as SourceImage));
 }
 return Object.freeze({...value,images:Object.freeze(images)} as SourceImageIndex);
}

/** Exact bytes only: no pixel decoding, clinical interpretation or retained binary cache. */
export async function readSourceImageOriginal(response:Response,expected:SourceImage):Promise<{
 bytes:Uint8Array<ArrayBuffer>;accessReceiptId:string;
}>{
 if(!/^application\/dicom$/i.test(response.headers.get('Content-Type')??''))throw Error('image type');
 const accessReceiptId=response.headers.get('X-OI-Access-Receipt');
 if(!accessReceiptId||!RECEIPT.test(accessReceiptId))throw Error('image receipt');
 const declared=response.headers.get('Content-Length');
 if(declared!==null&&(!/^\d+$/.test(declared)||Number(declared)!==expected.byte_count||Number(declared)>MAX_BYTES))throw Error('image bound');
 const reader=response.body?.getReader();if(!reader)throw Error('image body');
 const parts:Uint8Array[]= [];let size=0;
 try{
  while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;
   if(size>MAX_BYTES||size>expected.byte_count){await reader.cancel();throw Error('image bound');}parts.push(value);}
 }finally{reader.releaseLock();}
 if(size!==expected.byte_count)throw Error('image length');
 const bytes=new Uint8Array(size);let offset=0;for(const part of parts){bytes.set(part,offset);offset+=part.length;}
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),byte=>byte.toString(16).padStart(2,'0')).join('');
 if(digest!==expected.sha256)throw Error('image digest');
 return {bytes,accessReceiptId};
}
