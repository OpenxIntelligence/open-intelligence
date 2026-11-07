import './laboratory-result-browser.css';
import {useState} from 'react';
import type {ReactElement,ReactNode} from 'react';
import type {WorldLaboratoryObservation} from './source-world-model';
import {
  emptyLaboratoryFilters,laboratoryContextKey,selectLaboratoryResults,LABORATORY_PAGE_SIZE,
} from './laboratory-result-view.js';
import type {LaboratoryFilters,LaboratoryLayout} from './laboratory-result-view.js';

type Result=WorldLaboratoryObservation;
type ResultRowProps={result:Result;children?:ReactNode};

/** Receives result rows in the order of the already validated server timeline. */
export function LaboratoryResultBrowser({children}:{children:ReactElement<ResultRowProps>[]}){
  const [filters,setFilters]=useState<LaboratoryFilters>(emptyLaboratoryFilters),[page,setPage]=useState(0);
  const [layout,setLayout]=useState<LaboratoryLayout>('cards');
  function change(next:LaboratoryFilters){setPage(0);setFilters(next);}
  return <LaboratoryResultPage filters={filters} page={page} change={change} setPage={setPage}
    layout={layout} setLayout={setLayout}>{children}</LaboratoryResultPage>;
}

export function LaboratoryResultPage({children,filters,page,change,setPage,layout='cards',setLayout}:{
  children:ReactElement<ResultRowProps>[];filters:LaboratoryFilters;page:number;
  change:(filters:LaboratoryFilters)=>void;setPage:(page:number)=>void;
  layout?:LaboratoryLayout;setLayout?:(layout:LaboratoryLayout)=>void;
}){
  const codes=new Set<string>(),contexts=new Map<string,Result>();
  const results=children.map(({props:{result}})=>result);
  for(const result of results){
    codes.add(result.loinc_code);
    contexts.set(laboratoryContextKey(result),result);
  }
  const view=selectLaboratoryResults(results,filters,page);
  const visible=view.indices.map(index=>children[index]);
  const {start,end,summary}=view;
  return <>
    <dl className="laboratory-record-summary" aria-label="Current loaded laboratory record">
      <div><dt>Current results</dt><dd>{summary.results}</dd></div>
      <div><dt>Original reports</dt><dd>{summary.reports}</dd></div>
      <div><dt>Test codes</dt><dd>{summary.testCodes}</dd></div>
      <div><dt>Values reported</dt><dd>{summary.reported}</dd></div>
      <div><dt>Results absent</dt><dd>{summary.absent}</dd></div>
    </dl>
    {setLayout&&<div className="laboratory-layout" role="group" aria-label="Laboratory result layout">
      <span>View results as</span>
      <button type="button" aria-pressed={layout==='cards'} onClick={()=>setLayout('cards')}>Cards</button>
      <button type="button" aria-pressed={layout==='table'} onClick={()=>setLayout('table')}>Table</button>
    </div>}
    <div className="source-filters laboratory-filters" role="group" aria-label="Filter current laboratory results">
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
          <option value="">All result states</option><option value="reported_value">Value reported</option>
          <option value="reported_absent">Result absent</option>
        </select></div>
    </div>
    <div className="filter-summary">
      <p role="status" aria-live="polite">{view.matching===0?'No results match these filters.':
        `Showing ${start+1}–${end} of ${view.matching} matching ${view.matching===1?'result':'results'}.`} {children.length} current {children.length===1?'result':'results'} in this case.</p>
      {(filters.code||filters.context||filters.status)&&<button type="button" onClick={()=>change(emptyLaboratoryFilters)}>Clear laboratory filters</button>}
    </div>
    {view.matching>0&&(layout==='table'?<>
      <p id="laboratory-table-help" className="laboratory-table-help">Scroll sideways to inspect every column. Open a row’s provenance for its exact source and record actions.</p>
      <div className="laboratory-table-scroll" role="region" aria-label="Laboratory results table" aria-describedby="laboratory-table-help" tabIndex={0}>
        <table className="laboratory-results-table">
          <caption>Current source-reported laboratory results · not clinically reviewed</caption>
          <thead><tr><th scope="col">Test code</th><th scope="col">Reported result</th><th scope="col">Result effective</th><th scope="col">Original and specimen</th><th scope="col">Provenance</th></tr></thead>
          <tbody>{visible.map(({props:{result,children:actions}})=><tr key={result.source_id+':'+result.observation_reference} data-testid="world-laboratory-observation">
            <th scope="row">LOINC {result.loinc_code}</th>
            <td data-testid="world-laboratory-value"><LaboratoryResultValue result={result}/></td>
            <td><time dateTime={result.effective_at}>{result.effective_at}</time></td>
            <td><strong>{result.document_id} v{result.document_version}</strong><span className="laboratory-table-specimen">{result.specimen_reference}</span><span className="laboratory-table-specimen">{result.specimen_type_text}</span></td>
            <td><LaboratoryResultProvenance result={result}>{actions}</LaboratoryResultProvenance></td>
          </tr>)}</tbody>
        </table>
      </div>
    </>:<ol className="world-observations" start={start+1}>{visible}</ol>)}
    {view.matching>LABORATORY_PAGE_SIZE&&<div className="actions laboratory-pagination" role="group" aria-label="Laboratory result pages">
      <button type="button" disabled={view.page===0} onClick={()=>setPage(view.page-1)}>Previous results</button>
      <button type="button" disabled={end===view.matching} onClick={()=>setPage(view.page+1)}>Next results</button>
    </div>}
  </>;
}

function LaboratoryResultValue({result:item}:{result:Result}){
  return item.status==='reported_value'?<><strong>{item.value_text}</strong> <code>{item.unit_code}</code> (UCUM)</>:
    <>Result absent · source reason: <strong>{item.absent_reason}</strong></>;
}

function LaboratoryResultProvenance({result:item,children}:ResultRowProps){
  return <details><summary>Inspect result provenance</summary>
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
    <p>The reference above locates this result within its exact original.</p>
    {children}
  </details>;
}

export function LaboratoryResultRow({result:item,children}:ResultRowProps){
  return <li data-testid="world-laboratory-observation">
    <p><strong>LOINC {item.loinc_code}</strong> · <time dateTime={item.effective_at}>{item.effective_at}</time></p>
    <p data-testid="world-laboratory-value"><LaboratoryResultValue result={item}/></p>
    <p>{item.document_id} v{item.document_version} · {item.specimen_reference} · {item.specimen_type_text}</p>
    <p>Source-reported, not clinically reviewed</p>
    <LaboratoryResultProvenance result={item}>{children}</LaboratoryResultProvenance>
  </li>;
}
