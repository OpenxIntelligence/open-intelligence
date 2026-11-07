/** Bounded original-text intake, not clinical parsing, identity or permission. */
import type {SourceVersion} from './source-contracts.js';
export type PreparedSource = Readonly<{text:string;declaredCase:string;byteLength:number}>;
export type ImportReceipt = Readonly<{
  result:'imported'|'duplicate'|'quarantined';duplicate:boolean;source_id:string|null;version:number|null;
}>;
export type OriginalSource = Readonly<{
  source_id:string;case_id:string;access_receipt_id:string;document_id:string;version:number;state:'current'|'superseded';
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
  if(!/^OI-SYNTHETIC-REPORT\/[12]\n/.test(text)||text.includes('\r')||text.includes('\0'))throw Error('Use the authored synthetic report format with LF line endings, no BOM or NUL. Nothing was rewritten.');
  if(text.startsWith('OI-SYNTHETIC-REPORT/2\n')&&/[\u000b\u000c\u001c-\u001e\u0085\u2028\u2029]/.test(text))throw Error('Version 2 reports require LF line separators.');
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
/** Recognize the supported saved lab modality and its source anchors only.
 * Full FHIR validation and authorization remain with the canonical server owner.
 * JSON is never reserialized; the exact original bytes must match the source hash.
 */
function verifyLaboratoryOriginal(text:string,source:SourceVersion,expectedSubject:string|undefined,reportReference?:string):void{
  if(source.kind!=='laboratory'||typeof expectedSubject!=='string'||
     !/^Patient\/[A-Za-z0-9.-]{1,64}$/.test(expectedSubject))throw Error('contract');
  const bundle:unknown=JSON.parse(text);
  if(!exact(bundle,['resourceType','type','entry'])||bundle.resourceType!=='Bundle'||
     bundle.type!=='collection'||!Array.isArray(bundle.entry)||
     bundle.entry.length<4||bundle.entry.length>19)throw Error('contract');
  const resources=new Map<string,Record<string,unknown>>(),bundleIds=new Map<string,string>();
  for(const entry of bundle.entry){
    if(!exact(entry,['fullUrl','resource'])||typeof entry.fullUrl!=='string'||
       !/^urn:uuid:[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(entry.fullUrl)||
       bundleIds.has(entry.fullUrl)||entry.resource===null||typeof entry.resource!=='object'||Array.isArray(entry.resource))throw Error('contract');
    const item=entry.resource as Record<string,unknown>;
    if(typeof item.resourceType!=='string'||!['Patient','Specimen','Observation','DiagnosticReport'].includes(item.resourceType)||
       typeof item.id!=='string'||! /^[A-Za-z0-9.-]{1,64}$/.test(item.id))throw Error('contract');
    const ref=item.resourceType+'/'+item.id;
    if(resources.has(ref))throw Error('contract');
    resources.set(ref,item);bundleIds.set(entry.fullUrl,ref);
  }
  const ofKind=(kind:string)=>[...resources].filter(([ref])=>ref.startsWith(kind+'/'));
  const patients=ofKind('Patient'),specimens=ofKind('Specimen'),reports=ofKind('DiagnosticReport'),observations=ofKind('Observation');
  if(patients.length!==1||patients[0][0]!==expectedSubject||
     specimens.length!==1||specimens[0][0]!=='Specimen/'+source.specimen_id||
     reports.length!==1||reports[0][0]!==(reportReference??'DiagnosticReport/'+source.document_id)||
     observations.length<1||observations.length>16)throw Error('contract');
  const resolveReference = (value: unknown): string => {
    if (!exact(value, ['reference']) || typeof value.reference !== 'string') throw Error('contract');
    return bundleIds.get(value.reference) ?? value.reference;
  };
  const report=reports[0][1],specimen=specimens[0][1],specimenRef=specimens[0][0];
  if(resolveReference(specimen.subject)!==expectedSubject||resolveReference(report.subject)!==expectedSubject||
     report.status!=='final'||typeof report.effectiveDateTime!=='string'||
     report.effectiveDateTime.slice(0,10)!==source.event_date||typeof report.issued!=='string'||
     report.issued.slice(0,10)!==source.issued_at||!Array.isArray(report.specimen)||
     report.specimen.length!==1||resolveReference(report.specimen[0])!==specimenRef||
     !Array.isArray(report.result)||report.result.length!==observations.length)throw Error('contract');
  const resultRefs=new Set<string>();
  for(const result of report.result){
    const ref = resolveReference(result);
    if(!resources.has(ref)||!ref.startsWith('Observation/')||resultRefs.has(ref))throw Error('contract');
    resultRefs.add(ref);
  }
  for(const [,observation] of observations){
    if(observation.status!=='final'||resolveReference(observation.subject)!==expectedSubject||
       resolveReference(observation.specimen)!==specimenRef)throw Error('contract');
  }
}
export async function verifyOriginal(v:unknown,caseId:string,source:SourceVersion,expectedSubject?:string,reportReference?:string):Promise<OriginalSource>{
  if(!exact(v,['source_id','case_id','access_receipt_id','document_id','version','state','sha256','original_text','synthetic','clinical_review_state'])||
     v.source_id!==source.source_id||v.case_id!==caseId||v.document_id!==source.document_id||
     v.version!==source.version||v.state!==source.state||v.sha256!==source.sha256||
     typeof v.access_receipt_id!=='string'||!/^ACCESS-[0-9A-F]{32}$/.test(v.access_receipt_id)||
     v.synthetic!==true||v.clinical_review_state!=='not_established'||typeof v.original_text!=='string')throw Error('contract');
  const bytes=new TextEncoder().encode(v.original_text);
  if(bytes.length<1||bytes.length>65536)throw Error('contract');
  if(/^OI-SYNTHETIC-REPORT\/[12]\n/.test(v.original_text)){
    const prepared=prepareSource(bytes,'original.txt');
    if(prepared.declaredCase!==caseId||prepared.text!==v.original_text)throw Error('contract');
  }else{
    verifyLaboratoryOriginal(v.original_text,source,expectedSubject,reportReference);
  }
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
  if(hash!==source.sha256)throw Error('contract');
  return Object.freeze(v as OriginalSource);
}
