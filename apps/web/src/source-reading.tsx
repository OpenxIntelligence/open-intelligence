import {SourceOncologyLabel} from './source-oncology-label';
import {useEffect,useRef,useState} from 'react';
import type {SourceIndex} from './source-contracts';
import type {SourceImagesState} from './source-images';

export type ReadingView = 'patient' | 'clinical';
export type SourceFilters = {query: string; versionState: string};
export const emptySourceFilters: SourceFilters = {query: '', versionState: 'all'};

function ImagePreview({preview,onClose}:{preview:NonNullable<SourceImagesState['sourceImagePreview']>;onClose?:()=>void}) {
  const [url,setUrl]=useState<string|null>(null);
  useEffect(()=>{
    let active=true;const reader=new FileReader();setUrl(null);
    reader.onload=()=>{if(active&&typeof reader.result==='string')setUrl(reader.result);};
    reader.readAsDataURL(new Blob([preview.png_bytes],{type:'image/png'}));
    return()=>{active=false;if(reader.readyState===FileReader.LOADING)reader.abort();};
  },[preview]);
  return <figure className="source-image-preview" data-testid="source-image-preview-panel">
    <div className="source-heading"><h6>Non-diagnostic preview</h6>
      <button type="button" data-testid="source-image-preview-close" onClick={onClose}>Close preview</button></div>
    <p className="warning-note"><strong>Not for diagnosis.</strong> This 8-bit grayscale view is a bounded engineering preview of the authorized synthetic CT original. It applies per-frame min/max scaling only and does not apply diagnostic windowing, calibration or interpretation.</p>
    {url&&<img data-testid="source-image-preview" src={url}
      alt="Non-diagnostic grayscale preview of the authorized synthetic CT original"/>}
    <figcaption className="small">Original SHA-256 <code>{preview.original_sha256}</code><br/>
      Preview read receipt <code data-testid="source-image-preview-receipt">{preview.access_receipt_id}</code></figcaption>
  </figure>;
}

/** Presentation of the existing response only; no retrieval or clinical state. */
export function SourceReading({index, view, filters, onFiltersChange, busy, questionBusy, onOpenOriginal, onAskQuestion,
 sourceImages=null,sourceImagesSourceId=null,sourceImagesPhase='idle',sourceImagesMessage='',
 sourceImageDownload=null,sourceImageDownloadPhase='idle',sourceImageDownloadMessage='',
 sourceImagePreview=null,sourceImagePreviewPhase='idle',sourceImagePreviewMessage='',
 onInspectImages,onDownloadImage,onPreviewImage,onDismissImagePreview,onDismissImages}: {
  index: SourceIndex;
  view: ReadingView;
  filters: SourceFilters;
  onFiltersChange: (filters: SourceFilters) => void;
  busy: boolean;
  questionBusy: boolean;
  onAskQuestion: (sourceId: string, line: number) => void;
  onOpenOriginal: (sourceId: string, trigger: HTMLButtonElement) => void;
  onInspectImages?: (sourceId: string) => void;
  onDownloadImage?: (sourceId: string, imageId: string) => void;
  onPreviewImage?: (sourceId: string, imageId: string) => void;
  onDismissImagePreview?: () => void;
  onDismissImages?: () => void;
}&Partial<SourceImagesState>) {
  const input = useRef<HTMLInputElement>(null);
  const imageOpeners = useRef(new Map<string,HTMLButtonElement>());
  const search = filters.query.trim().toLowerCase();
  const sources = index.sources.filter(source =>
    (filters.versionState === 'all' || source.state === filters.versionState) &&
    (!search || [source.document_id, source.kind, source.event_date, source.issued_at,
      source.source_id, source.specimen_id ?? ''].join(' ').toLowerCase().includes(search)))
    .sort((a, b) => Number(a.state === 'superseded') - Number(b.state === 'superseded'));
  function clear() {
    onFiltersChange(emptySourceFilters);
    input.current?.focus();
  }
  if (index.sources.length === 0) return <p>No structured report sources for this case. Text and PDF originals are available in their section above.</p>;
  return <div className={'source-reading ' + view}>
    <div className="source-filters" role="search" aria-label="Filter loaded source versions">
      <div><label htmlFor="source-filter">Filter loaded sources</label><input id="source-filter" ref={input} type="search"
        value={filters.query} onChange={e => onFiltersChange({...filters, query: e.target.value})}
        placeholder="Document, type, date or source ID" aria-describedby="source-filter-help"/></div>
      <div><label htmlFor="source-state">Version status</label><select id="source-state" value={filters.versionState}
        onChange={e => onFiltersChange({...filters, versionState: e.target.value})}>
        <option value="all">All versions</option><option value="current">Current</option><option value="superseded">Superseded</option>
      </select></div>
    </div>
    <div className="filter-summary"><p id="source-filter-help">Only filters sources already loaded for this case.</p>
      <p role="status" aria-live="polite">{sources.length} of {index.sources.length} versions shown</p>
      {(filters.query || filters.versionState !== 'all') && <button type="button" data-testid="clear-source-filters" onClick={clear}>Clear filters</button>}
    </div>
    {sources.length === 0 ? <div className="source-empty" data-testid="source-no-match"><h4>No sources match these filters</h4><p>The loaded records have not changed. Clear the filters to see all versions.</p></div> :
      <ol className="source-list">{sources.map(item => {
        const findings = index.source_reported_assertions.filter(f => f.source_id === item.source_id);
        return <li key={item.source_id} data-testid="source-version" className={'source-row ' + item.state}>
          <div className="source-heading"><h4>{item.document_id} · v{item.version}</h4><span className="record-state">{item.state}</span></div>
          <dl className="source-metadata source-dates">
            <div><dt>Type</dt><dd>{item.kind}</dd></div><div><dt>Event date</dt><dd><time dateTime={item.event_date}>{item.event_date}</time></dd></div>
            <div><dt>Issued</dt><dd><time dateTime={item.issued_at}>{item.issued_at}</time></dd></div><div><dt>Specimen</dt><dd>{item.specimen_id ?? 'Not recorded'}</dd></div>
          </dl>
          {findings.length > 0 && <div className="source-quotes"><p className="quote-label">{view === 'patient' ? 'What the report says' : 'Source-reported statements'}</p>
            <ul className="finding-list">{findings.map((finding, i) => <li key={finding.source_id + ':' + finding.source_line + ':' + i} data-testid="source-finding">
              <p><strong>{finding.finding_key}</strong> · reported state: {finding.reported_state} · line {finding.source_line}</p>
              <SourceOncologyLabel context={finding.oncology} state={finding.reported_state}/>
              <blockquote data-testid="source-statement">{finding.source_statement}</blockquote>
              <small>Clinical review: not established · <code>{finding.source_id}</code></small>
              {item.state === 'current' && <div className="actions"><button type="button"
                aria-label={`Ask about this statement: ${item.document_id}, version ${item.version}, line ${finding.source_line}, ${finding.finding_key}`}
                data-testid="ask-source-question" disabled={busy || questionBusy}
                onClick={() => onAskQuestion(finding.source_id, finding.source_line)}>Ask about this statement</button></div>}
            </li>)}</ul>
          </div>}
          {item.state === 'superseded' && <p className="history-note">Earlier version. This response does not supply its historical quotations; inspect the original to read that version.</p>}
          {item.state === 'current' && findings.length === 0 && <p>No quoted statements were returned for this version.</p>}
          <details className="source-verify" data-testid="source-verify"><summary>Verify original details for {item.document_id} version {item.version}</summary>
            <dl className="source-metadata">
              <div><dt>Original source ID</dt><dd><code>{item.source_id}</code></dd></div>
              <div><dt>Original SHA-256</dt><dd><code>{item.sha256}</code></dd></div>
              <div><dt>Received</dt><dd><time dateTime={item.received_at}>{item.received_at}</time></dd></div>
              {item.supersedes_id && <div><dt>Supersedes</dt><dd><code>{item.supersedes_id}</code></dd></div>}
            </dl>
          </details>
          <button aria-label={`Inspect original v${item.version}: ${item.document_id}`} data-testid="open-original" disabled={busy} onClick={event => onOpenOriginal(item.source_id, event.currentTarget)}>Inspect original v{item.version}</button>
          {item.kind==='imaging'&&item.state==='current'&&<div className="source-image-section">
            <button type="button" data-testid="source-images-open" disabled={busy}
              ref={element=>{if(element)imageOpeners.current.set(item.source_id,element);else imageOpeners.current.delete(item.source_id);}}
              onClick={()=>onInspectImages?.(item.source_id)}>Inspect linked original images</button>
            {sourceImagesSourceId===item.source_id&&<section className="source-image-inspection"
              data-testid="source-images-inspection" aria-label={'Original images linked to '+item.document_id+' version '+item.version}>
              <div className="source-heading"><h5>Linked originals · v{item.version}</h5>
                <button type="button" data-testid="source-images-close" onClick={()=>{onDismissImages?.();imageOpeners.current.get(item.source_id)?.focus();}}>Close image inspection</button></div>
              <p role="status" aria-live="polite" data-testid="source-images-status">{sourceImagesMessage}</p>
              <p className="muted small">Original custody plus a bounded non-diagnostic preview only. No diagnostic viewer, clinical interpretation or verified patient identity is supplied by this screen.</p>
              {sourceImagesPhase==='ready'&&sourceImages&&<>
                <p className="small">Image metadata access receipt: <code data-testid="source-images-receipt">{sourceImages.access_receipt_id}</code></p>
                {sourceImages.images.length===0?<p data-testid="source-images-empty">No originals are linked to this current report.</p>:
                  <ul className="source-image-list">{sourceImages.images.map(image=><li key={image.image_id}
                    data-testid="source-image-row" data-image-id={image.image_id}>
                    <p><strong>{image.modality} original</strong> · <time dateTime={image.study_date}>{image.study_date}</time> · {image.byte_count.toLocaleString()} bytes</p>
                    <details><summary>Original integrity and identifiers</summary><dl className="source-metadata">
                      <div><dt>Image</dt><dd><code>{image.image_id}</code></dd></div>
                      <div><dt>Source</dt><dd><code>{image.source_id}</code></dd></div>
                      <div><dt>Original SHA-256</dt><dd><code>{image.sha256}</code></dd></div>
                      <div><dt>Study / Series / SOP</dt><dd><code>{image.study_uid} / {image.series_uid} / {image.sop_uid}</code></dd></div>
                    </dl></details>
                    <div className="actions">
                      <button type="button" data-testid="source-image-preview-open" disabled={busy||sourceImagePreviewPhase==='loading'}
                        onClick={()=>onPreviewImage?.(item.source_id,image.image_id)}>View non-diagnostic preview</button>
                      <button type="button" data-testid="source-image-download" disabled={busy||sourceImageDownloadPhase==='loading'}
                        onClick={()=>onDownloadImage?.(item.source_id,image.image_id)}>Recheck and download original DICOM</button>
                    </div>
                    {sourceImagePreview?.image_id===image.image_id&&sourceImagePreview.source_id===item.source_id&&
                      <ImagePreview preview={sourceImagePreview} onClose={onDismissImagePreview}/>}
                  </li>)}</ul>}
                {sourceImagePreviewPhase!=='idle'&&<p role="status" aria-live="polite" data-testid="source-image-preview-status">{sourceImagePreviewMessage}</p>}
              </>}
              {sourceImageDownloadPhase!=='idle'&&<p role="status" aria-live="polite" data-testid="source-image-download-status">{sourceImageDownloadMessage}</p>}
              {sourceImageDownload&&<p className="small" data-testid="source-image-download-receipt">Original read receipt: <code>{sourceImageDownload.access_receipt_id}</code></p>}
            </section>}
          </div>}
        </li>;
      })}</ol>}
  </div>;
}
