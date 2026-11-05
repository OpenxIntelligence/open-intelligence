import {codedResultLabel,CodingProvenance} from './laboratory-coding-view';
import {useState} from 'react';
import type {ReactElement,ReactNode} from 'react';
import type {WorldLaboratoryObservation} from './source-world-model';

type Result=WorldLaboratoryObservation;
type ResultRowProps={result:Result;children?:ReactNode};
type Filters={code:string;context:string;status:string};
const initialFilters:Filters={code:'',context:'',status:''};
const PAGE_SIZE=25;

// Specimen references are local to each original. Displaying two equal reference
// strings never establishes that they identify the same specimen across reports.
const laboratoryContextKey=(result:Result)=>JSON.stringify([result.source_id,result.specimen_reference]);
function matchesLaboratoryFilters(result:Result,filters:Filters):boolean{
  return (!filters.code||result.loinc_code===filters.code)&&
    (!filters.context||laboratoryContextKey(result)===filters.context)&&
    (!filters.status||result.status===filters.status);
}

/** Receives result rows in the order of the already validated server timeline. */
export function LaboratoryResultBrowser({children}:{children:ReactElement<ResultRowProps>[]}){
  const [filters,setFilters]=useState<Filters>(initialFilters),[page,setPage]=useState(0);
  function change(next:Filters){setPage(0);setFilters(next);}
  return <LaboratoryResultPage filters={filters} page={page} change={change} setPage={setPage}>{children}</LaboratoryResultPage>;
}

export function LaboratoryResultPage({children,filters,page,change,setPage}:{
  children:ReactElement<ResultRowProps>[];filters:Filters;page:number;
  change:(filters:Filters)=>void;setPage:(page:number)=>void;
}){
  const codes=new Set<string>(),contexts=new Map<string,Result>();
  for(const {props:{result}} of children){
    codes.add(result.loinc_code);
    contexts.set(laboratoryContextKey(result),result);
  }
  const matches=children.filter(({props:{result}})=>matchesLaboratoryFilters(result,filters));
  const start=page*PAGE_SIZE,end=Math.min(start+PAGE_SIZE,matches.length);
  return <>
    <div className="source-filters" role="group" aria-label="Filter current laboratory results">
      <div><label htmlFor="lab-filter-code">Test (exact LOINC code)</label>
        <select id="lab-filter-code" value={filters.code} onChange={e=>change({...filters,code:e.target.value})}>
          <option value="">All test codes</option>
          {Array.from(codes).sort().map(code=><option key={code} value={code}>{code}</option>)}
        </select></div>
      <div><label htmlFor="lab-filter-context">Original report and specimen</label>
        <select id="lab-filter-context" value={filters.context} onChange={e=>change({...filters,context:e.target.value})}>
          <option value="">All reports and specimens</option>
          {Array.from(contexts,([key,result])=><option key={key} value={key}>
            {result.document_id} v{result.document_version} · {result.specimen_reference}
          </option>)}
        </select></div>
      <div><label htmlFor="lab-filter-status">Reported result</label>
        <select id="lab-filter-status" value={filters.status} onChange={e=>change({...filters,status:e.target.value})}>
          <option value="">All result states</option><option value="reported_value">Quantity reported</option>
          <option value="reported_coded">Coded result</option><option value="reported_absent">Result absent</option>
        </select></div>
    </div>
    <div className="filter-summary">
      <p role="status" aria-live="polite">{matches.length===0?'No results match these filters.':
        `Showing ${start+1}–${end} of ${matches.length} matching ${matches.length===1?'result':'results'}.`} {children.length} current {children.length===1?'result':'results'} in this case.</p>
      {(filters.code||filters.context||filters.status)&&<button type="button" onClick={()=>change(initialFilters)}>Clear laboratory filters</button>}
    </div>
    {matches.length>0&&<ol className="world-observations" start={start+1}>{matches.slice(start,end)}</ol>}
    {matches.length>PAGE_SIZE&&<div className="actions" role="group" aria-label="Laboratory result pages">
      <button type="button" disabled={page===0} onClick={()=>setPage(page-1)}>Previous results</button>
      <button type="button" disabled={end===matches.length} onClick={()=>setPage(page+1)}>Next results</button>
    </div>}
  </>;
}

export function LaboratoryResultRow({result:item,children}:ResultRowProps){
  return <li data-testid="world-laboratory-observation">
    <p><strong>LOINC {item.loinc_code}</strong> · <time dateTime={item.effective_at}>{item.effective_at}</time></p>
    <p data-testid="world-laboratory-value">{item.status==='reported_value'?<><strong>{item.value_text}</strong> <code>{item.unit_code}</code> (UCUM)</>:item.status==='reported_coded'?<span className="lab-coded-label">{codedResultLabel(item.coded_result)}</span>:<>Result absent · source reason: <strong>{item.absent_reason}</strong></>}</p>
    <p>{item.document_id} v{item.document_version} · {item.specimen_reference} · {item.specimen_type_text}</p>
    <p>Source-reported, not clinically reviewed</p>
    <details><summary>Inspect result provenance</summary>
      <dl>
        <dt>Original report</dt><dd>{item.document_id} · version {item.document_version}</dd>
        <dt>Observation reference</dt><dd><code>{item.observation_reference}</code></dd>
        <dt>Report reference</dt><dd><code>{item.report_reference}</code></dd>
        <dt>Specimen reference</dt><dd><code>{item.specimen_reference}</code></dd>
        <dt>Specimen collected</dt><dd><time dateTime={item.specimen_collected_at}>{item.specimen_collected_at}</time></dd>
        <dt>Result effective</dt><dd><time dateTime={item.effective_at}>{item.effective_at}</time></dd>
        <dt>Result issued</dt><dd><time dateTime={item.issued_at}>{item.issued_at}</time></dd>
        <dt>Source identity</dt><dd><code>{item.source_id}</code></dd>
        <dt>Original SHA-256</dt><dd><code>{item.source_sha256}</code></dd>
      </dl>
      {item.status==='reported_coded'&&<CodingProvenance coding={item.coded_result}/>}
      <p>The reference above locates this result within its exact original.</p>
      {children}
    </details>
  </li>;
}
