/** Read projections of the existing source-image custody API, not a second image owner. */
import type {SourceVersion} from './source-contracts.js';

export type SourceImage=Readonly<{
 image_id:string;source_id:string;case_id:string;sha256:string;byte_count:number;
 study_uid:string;series_uid:string;sop_uid:string;modality:'CT';study_date:string;
}>;
export type SourceImageIndex=Readonly<{
 patient_id:string;case_id:string;source_id:string;images:readonly SourceImage[];
 access_receipt_id:string;synthetic:true;source_identity_verified:false;
}>;
export type SourceImageDownload=Readonly<{
 patient_id:string;case_id:string;source_id:string;image_id:string;sha256:string;
 byte_count:number;access_receipt_id:string;
}>;
export type SourceImagePreview=Readonly<{
 patient_id:string;case_id:string;source_id:string;image_id:string;original_sha256:string;
 access_receipt_id:string;png_bytes:Uint8Array<ArrayBuffer>;
}>;
export type SourceImagesState=Readonly<{
 sourceImages:SourceImageIndex|null;sourceImagesSourceId:string|null;
 sourceImagesPhase:'idle'|'loading'|'ready'|'error';sourceImagesMessage:string;
 sourceImageDownload:SourceImageDownload|null;
 sourceImageDownloadPhase:'idle'|'loading'|'ready'|'error';sourceImageDownloadMessage:string;
 sourceImagePreview:SourceImagePreview|null;
 sourceImagePreviewPhase:'idle'|'loading'|'ready'|'error';sourceImagePreviewMessage:string;
}>;
export const emptySourceImages=():SourceImagesState=>({sourceImages:null,sourceImagesSourceId:null,
 sourceImagesPhase:'idle',sourceImagesMessage:'Inspect linked original images for a current imaging report.',
 sourceImageDownload:null,sourceImageDownloadPhase:'idle',sourceImageDownloadMessage:'',
 sourceImagePreview:null,sourceImagePreviewPhase:'idle',sourceImagePreviewMessage:''});
const IMAGE=/^IMG-[0-9A-F]{32}$/,RECEIPT=/^ACCESS-[0-9A-F]{32}$/,SHA=/^[0-9a-f]{64}$/;
const MAX_BYTES=2_097_152;
function exact(value:unknown,keys:readonly string[]):value is Record<string,unknown>{
 return value!==null&&typeof value==='object'&&!Array.isArray(value)&&
  Object.keys(value).length===keys.length&&keys.every(key=>Object.hasOwn(value,key));
}
function uid(value:unknown):value is string{
 return typeof value==='string'&&value.length<=64&&/^(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))*$/.test(value);
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
 for(const raw of value.images){
  if(!exact(raw,['image_id','source_id','case_id','sha256','byte_count','study_uid','series_uid','sop_uid','modality','study_date'])||
   typeof raw.image_id!=='string'||!IMAGE.test(raw.image_id)||seen.has(raw.image_id)||
   raw.source_id!==source.source_id||raw.case_id!==caseId||typeof raw.sha256!=='string'||!SHA.test(raw.sha256)||
   typeof raw.byte_count!=='number'||!Number.isSafeInteger(raw.byte_count)||raw.byte_count<132||raw.byte_count>MAX_BYTES||
   !uid(raw.study_uid)||!uid(raw.series_uid)||!uid(raw.sop_uid)||raw.modality!=='CT'||
   !day(raw.study_date)||raw.study_date!==source.event_date)throw Error('image index');
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


const MAX_PREVIEW_BYTES=1_200_000;
const PNG_SIGNATURE=[0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a];
function uint32(bytes:Uint8Array,offset:number):number{
 return ((bytes[offset]*0x1000000)+(bytes[offset+1]<<16)+(bytes[offset+2]<<8)+bytes[offset+3])>>>0;
}

/** Bounded derivative of the same fresh original read; not a diagnostic image contract. */
export async function readSourceImagePreview(response:Response,expected:SourceImage):Promise<{
 bytes:Uint8Array<ArrayBuffer>;accessReceiptId:string;
}>{
 if(!/^image\/png$/i.test(response.headers.get('Content-Type')??''))throw Error('preview type');
 const accessReceiptId=response.headers.get('X-OI-Access-Receipt');
 if(!accessReceiptId||!RECEIPT.test(accessReceiptId))throw Error('preview receipt');
 if(response.headers.get('X-OI-Original-SHA256')!==expected.sha256)throw Error('preview source');
 if(response.headers.get('X-OI-Preview-Mode')!=='synthetic-ct-minmax-8bit-nondiagnostic')throw Error('preview mode');
 const declared=response.headers.get('Content-Length');
 if(declared!==null&&(!/^\d+$/.test(declared)||Number(declared)<33||Number(declared)>MAX_PREVIEW_BYTES))throw Error('preview bound');
 const reader=response.body?.getReader();if(!reader)throw Error('preview body');
 const parts:Uint8Array[]=[];let size=0;
 try{
  while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;
   if(size>MAX_PREVIEW_BYTES){await reader.cancel();throw Error('preview bound');}parts.push(value);}
 }finally{reader.releaseLock();}
 if(size<58||(declared!==null&&Number(declared)!==size))throw Error('preview size');
 const bytes=new Uint8Array(size);let offset=0;for(const part of parts){bytes.set(part,offset);offset+=part.length;}
 if(!PNG_SIGNATURE.every((value,index)=>bytes[index]===value)||
    uint32(bytes,8)!==13||String.fromCharCode(...bytes.slice(12,16))!=='IHDR')throw Error('preview png');
 const width=uint32(bytes,16),height=uint32(bytes,20);
 if(width<1||height<1||width>1024||height>1024||width*height>1_048_576||
    bytes[24]!==8||bytes[25]!==0||bytes[26]!==0||bytes[27]!==0||bytes[28]!==0)throw Error('preview png');
 // The first-party renderer emits one IDAT followed by an empty IEND.
 const imageDataLength=uint32(bytes,33);
 const endOffset=45+imageDataLength;
 if(imageDataLength===0||endOffset+12!==size||
    String.fromCharCode(...bytes.subarray(37,41))!=='IDAT'||
    uint32(bytes,endOffset)!==0||String.fromCharCode(...bytes.subarray(endOffset+4,endOffset+8))!=='IEND')throw Error('preview png');
 return{bytes,accessReceiptId};
}
