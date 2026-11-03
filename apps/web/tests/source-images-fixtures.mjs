import {patientId,caseId,sourceId,questionId,reportId,token,response,patient,cases,world,history,
 packet,report,hash,digest,time} from './authored-evidence-fixtures.mjs';
export {patientId,caseId,sourceId,questionId,reportId,token,response};
export const imageId='IMG-'+'C'.repeat(32),accessId='ACCESS-'+'C'.repeat(32);
// Byte-integrity fixture only. Actual DICOM parsing is covered by the existing
// API/real-browser fixture; this deliberately does not claim a medical image.
export const original=Buffer.alloc(160);original.write('DICM',128);original.write('fictional',132);
export const image=()=>({image_id:imageId,source_id:sourceId,case_id:caseId,sha256:digest(original),
 byte_count:original.length,study_uid:'2.25.101',series_uid:'2.25.102',sop_uid:'2.25.103',
 modality:'CT',study_date:'2026-01-10'});
export const images=()=>({patient_id:patientId,case_id:caseId,source_id:sourceId,
 images:[image()],access_receipt_id:accessId,synthetic:true,source_identity_verified:false});
export function sourceIndex(caseName=caseId){
 const source={...world().current_sources[0],kind:'imaging',specimen_id:null};
 return {contract:'oi.synthetic-original-sources/1',patient_id:patientId,case_id:caseName,
  access_receipt_id:accessId,sources:[source],source_reported_assertions:[{source_id:sourceId,
   finding_key:'marker',reported_state:'not-reported',source_statement:'Fictional source statement remains unresolved.',
   source_line:8,clinical_review_state:'not_established'}],synthetic:true,
  clinical_interpretation:false,research_review_invalidation_integrated:false};
}
export const imageReport=()=>{
 const r=report();r.snapshot.selected_source.kind='imaging';r.snapshot.selected_source.specimen_id=null;
 r.snapshot_sha256=hash(r.snapshot);return r;
};
export const evidencePacket=()=>{
 const p=packet();p.reports[0].snapshot_sha256=imageReport().snapshot_sha256;return p;
};
export const metadataLinks=()=>({contract:'oi.pg-question-evidence-links/1',patient_id:patientId,
 case_id:caseId,question_id:questionId,source_context_state:'current_unreviewed_question',
 source_access_receipt_id:'ACCESS-'+'D'.repeat(32),links:[],synthetic:true,model_executed:false,
 content_appraised:false,clinical_approval:false});
export function binary(bytes=original,headers={}){
 return new Response(bytes,{headers:{'Content-Type':'application/dicom',
  'Content-Length':String(bytes.length),'X-OI-Access-Receipt':accessId,...headers}});
}
export function transportForImages(handler=()=>undefined,source=sourceIndex){
 return (url,init)=>{
  const handled=handler(url,init);if(handled!==undefined)return handled;
  if(url.endsWith('/case-bindings'))return response(cases());
  if(url.endsWith('/sources'))return response(source(url.includes('/CASE-BETA/')?'CASE-BETA':caseId));
  if(url.endsWith('/world-model')){
   const model=world();model.current_sources[0].kind='imaging';model.current_sources[0].specimen_id=null;
   model.observations[0].source_kind='imaging';model.observations[0].specimen_id=null;return response(model);
  }
  if(url.endsWith('/questions'))return response(history());
  if(url.endsWith('/evidence-links'))return response(metadataLinks());
  if(url.includes('/evidence-reports/'))return response(imageReport());
  if(url.endsWith('/evidence'))return response(evidencePacket());
  if(url.endsWith('/images'))return response(images());
  if(url.endsWith('/images/'+imageId))return binary();
  return response(patient(url.endsWith('PAT-EXAMPLE-002')?'PAT-EXAMPLE-002':patientId));
 };
}
export async function readyImages(session,{evidence=false}={}){
 session.connect(token);await session.read(patientId);await session.loadCases();await session.loadSources(caseId);
 if(evidence){await session.loadWorldModel(caseId);await session.loadSavedQuestions(caseId);
  await session.loadQuestionEvidence(questionId);await session.readEvidenceReport(questionId,reportId);
  await session.loadQuestionEvidenceLinks(questionId);}
}
export async function captureDownload(run){
 const savedDocument=globalThis.document,savedCreate=URL.createObjectURL,savedRevoke=URL.revokeObjectURL;
 const blobs=[],links=[],revoked=[];
 globalThis.document={body:{append(){}},createElement(){const link={click(){links.push({name:this.download,href:this.href});},remove(){}};return link;}};
 URL.createObjectURL=blob=>{blobs.push(blob);return 'blob:fictional-source-image';};
 URL.revokeObjectURL=url=>revoked.push(url);
 try{await run();return {blobs,links,revoked};}
 finally{globalThis.document=savedDocument;URL.createObjectURL=savedCreate;URL.revokeObjectURL=savedRevoke;}
}
