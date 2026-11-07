import {buildImagingChronology} from './imaging-report-chronology';
import type {SourceVersion} from './source-contracts';
import './imaging-report-chronology.css';

/** A navigation aid over already-authorized source versions, not an image comparison. */
export function ImagingReportChronology({sources,selectedSourceId,onSelect}:{
 sources:readonly SourceVersion[];
 selectedSourceId:string|null;
 onSelect:(sourceId:string)=>void;
}){
 const dates=buildImagingChronology(sources);
 const count=dates.reduce((sum,group)=>sum+group.reports.length,0);
 return <section className="imaging-chronology" aria-labelledby="imaging-chronology-heading" data-testid="imaging-chronology">
  <div className="imaging-chronology-heading">
   <div><span className="step">IMAGING · REPORT HISTORY</span><h3 id="imaging-chronology-heading">Imaging report chronology</h3></div>
   <span className="imaging-chronology-count">{count} loaded {count===1?'version':'versions'}</span>
  </div>
  <p className="small">Dates and version states come from the original reports. No clinical image or disease progression comparison is performed. Earlier DICOM pixels are not loaded automatically.</p>
  {dates.length===0?<p role="status">No imaging report versions are in the currently loaded case index. This does not establish that no imaging exists elsewhere.</p>:
   <ol className="imaging-chronology-dates">{dates.map(group=><li key={group.date} data-testid="imaging-chronology-date">
    <h4><time dateTime={group.date}>{group.date}</time></h4>
    <ul>{group.reports.map(report=><li key={report.source_id} data-testid="imaging-chronology-version" data-source-id={report.source_id}>
     <div><strong>{report.document_id}</strong> · version {report.version} <span className="imaging-chronology-state">{report.state}</span></div>
     <p className="small">Issued <time dateTime={report.issued_at}>{report.issued_at}</time></p>
     <button type="button" data-testid="imaging-select-version" aria-pressed={selectedSourceId===report.source_id}
      aria-label={`Show report ${report.document_id}, version ${report.version}, ${report.state}`}
      onClick={()=>onSelect(report.source_id)}>Show this report</button>
    </li>)}</ul>
   </li>)}</ol>}
 </section>;
}
