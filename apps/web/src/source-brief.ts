/** Literal source-only export; never a clinical report or stored client record. */
export type SourceBrief=Readonly<{
 contract:'oi.synthetic-source-brief/1';synthetic:true;patient_id:string;case_id:string;
 source_snapshot_sha256:string;prepared_at:string;media_type:'text/plain;charset=utf-8';
 body:string;body_sha256:string;clinical_approval:false;
}>;
const fields=['contract','synthetic','patient_id','case_id','source_snapshot_sha256',
 'prepared_at','media_type','body','body_sha256','clinical_approval'];
export async function decodeSourceBrief(value:unknown,patientId:string,caseId:string,
 fingerprint:string):Promise<SourceBrief>{
 if(!value||typeof value!=='object'||Array.isArray(value))throw Error('brief contract');
 const v=value as Record<string,unknown>;
 if(Object.keys(v).length!==fields.length||!fields.every(k=>Object.hasOwn(v,k))||
  v.contract!=='oi.synthetic-source-brief/1'||v.synthetic!==true||v.patient_id!==patientId||
  v.case_id!==caseId||v.source_snapshot_sha256!==fingerprint||
  v.media_type!=='text/plain;charset=utf-8'||v.clinical_approval!==false||
  typeof v.prepared_at!=='string'||v.prepared_at.length>64||
  !/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(v.prepared_at)||
  !Number.isFinite(Date.parse(v.prepared_at))||typeof v.body!=='string'||
  v.body.length===0||new TextEncoder().encode(v.body).byteLength>65536||
  typeof v.body_sha256!=='string'||v.body_sha256.length!==64||
  !/^[0-9a-f]{64}$/.test(v.body_sha256))throw Error('brief contract');
 const bytes=new TextEncoder().encode(v.body);
 const digest=await crypto.subtle.digest('SHA-256',bytes);
 const actual=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');
 if(actual!==v.body_sha256)throw Error('brief integrity');
 // Do not freeze a provider-owned object, even on a valid response.
 return Object.freeze({...v}) as SourceBrief;
}
