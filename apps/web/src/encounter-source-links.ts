import type {SourceIndex, SourceVersion} from './source-contracts.js';

export type SourceLink = Readonly<{id:number; source:SourceVersion}>;
export type LinkPage = Readonly<{links:readonly SourceLink[]; next:number|null}>;
export type LinkIntent = Readonly<{caseId:string; encounterId:number; body:string}>;

function fields(value:unknown, names:string[]):value is Record<string,unknown> {
  return value!==null && typeof value==='object' && !Array.isArray(value) &&
    Object.keys(value).length===names.length && names.every(name=>Object.hasOwn(value,name));
}
function positive(value:unknown):value is number {
  return typeof value==='number' && Number.isSafeInteger(value) && value>0;
}

export function parseLinkedSources(value:unknown, index:SourceIndex, encounterId:number, after:number):LinkPage {
  const invalid=()=>new Error('Refresh the case records and visit links to verify their source versions.');
  if(!positive(encounterId) || !Number.isSafeInteger(after) || after<0 ||
      !fields(value,['patient_id','case_id','encounter_id','links','next_after_id','access_receipt_id']) ||
      value.patient_id!==index.patient_id || value.case_id!==index.case_id || value.encounter_id!==encounterId ||
      typeof value.access_receipt_id!=='string' || !/^ACCESS-[A-F0-9]{32}$/.test(value.access_receipt_id) ||
      value.access_receipt_id.length!==39 || !Array.isArray(value.links) || value.links.length>25) throw invalid();
  let last=after;
  const seen=new Set<string>();
  const links=value.links.map((row:unknown)=>{
    if(!fields(row,['id','patient_id','case_id','encounter_id','source_id','version','sha256','source_state']) ||
        !positive(row.id) || row.id<=last || row.patient_id!==index.patient_id ||
        row.case_id!==index.case_id || row.encounter_id!==encounterId) throw invalid();
    const source=index.sources.find(item=>item.source_id===row.source_id);
    if(!source || seen.has(source.source_id) || source.sha256!==row.sha256 ||
        source.state!==row.source_state || source.version!==row.version) throw invalid();
    last=row.id;
    seen.add(source.source_id);
    return Object.freeze({id:row.id,source});
  });
  const next=value.next_after_id;
  if(next!==null && (links.length!==25 || next!==last)) throw invalid();
  return Object.freeze({links:Object.freeze(links),next:next===null?null:last});
}

export function prepareSourceLink(index:SourceIndex, encounterId:number, sourceId:string):LinkIntent {
  const source=index.sources.find(item=>item.source_id===sourceId && item.state==='current');
  if(!positive(encounterId) || !source) throw Error('Select a visit and a current source version.');
  return Object.freeze({caseId:index.case_id,encounterId,body:JSON.stringify({synthetic:true,
    request_key:crypto.randomUUID(),source_id:source.source_id,
    expected_version:source.version,expected_sha256:source.sha256})});
}

export function parseLinkReceipt(value:unknown):Readonly<{id:number;duplicate:boolean}> {
  if(!fields(value,['id','duplicate']) || !positive(value.id) || typeof value.duplicate!=='boolean') {
    throw Error('Unknown source link outcome.');
  }
  return Object.freeze({id:value.id,duplicate:value.duplicate});
}
