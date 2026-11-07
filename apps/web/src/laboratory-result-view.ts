import type {WorldLaboratoryObservation} from './source-world-model.js';

export type LaboratoryFilters=Readonly<{code:string;context:string;status:string}>;
export type LaboratoryLayout='cards'|'table';
export const LABORATORY_PAGE_SIZE=25;
export const emptyLaboratoryFilters:LaboratoryFilters=Object.freeze({code:'',context:'',status:''});

// Bundle-local references do not establish specimen identity across originals.
export const laboratoryContextKey=(result:WorldLaboratoryObservation):string=>
  JSON.stringify([result.source_id,result.specimen_reference]);

/** Presentation only: preserve server order and source strings; never interpret values. */
export function selectLaboratoryResults(
  results:readonly WorldLaboratoryObservation[],filters:LaboratoryFilters,requestedPage:number,
){
  const matchingIndices:number[]=[];
  const reports=new Set<string>(),testCodes=new Set<string>();
  let reported=0,absent=0;
  results.forEach((result,index)=>{
    reports.add(result.source_id);testCodes.add(result.loinc_code);
    if(result.status==='reported_value')reported++;
    else if(result.status==='reported_absent')absent++;
    if((!filters.code||result.loinc_code===filters.code)&&
       (!filters.context||laboratoryContextKey(result)===filters.context)&&
       (!filters.status||result.status===filters.status))matchingIndices.push(index);
  });
  const matching=matchingIndices.length;
  const lastPage=Math.max(0,Math.ceil(matching/LABORATORY_PAGE_SIZE)-1);
  const page=Math.min(lastPage,Number.isFinite(requestedPage)?Math.max(0,Math.floor(requestedPage)):0);
  const start=page*LABORATORY_PAGE_SIZE,end=Math.min(start+LABORATORY_PAGE_SIZE,matching);
  return {
    indices:matchingIndices.slice(start,end),matching,page,start,end,
    summary:{results:results.length,reports:reports.size,testCodes:testCodes.size,reported,absent},
  };
}
