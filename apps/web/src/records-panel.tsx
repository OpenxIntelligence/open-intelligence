import {useEffect, useRef} from 'react';
import type {ViewState} from './registry-client';
import type {SourceFinding, SourceVersion} from './source-contracts';

export type ReadingView = 'patient' | 'clinical';
export type SourceFilters = {query: string; versionState: string};
type Props = {
  state: ViewState;
  view: ReadingView;
  filters: SourceFilters;
  onFiltersChange: (filters: SourceFilters) => void;
  onOverview: () => void;
  onLoadCases: () => void;
  onLoadSources: (caseId: string) => void;
};

function SourceRow({source, findings, view}: {source: SourceVersion; findings: readonly SourceFinding[]; view: ReadingView}) {
  return <li className={'source-row ' + source.state} data-testid="source-version">
    <div className="source-heading">
      <div><span className="source-kind">{source.kind}</span><h4>{source.document_id} <span className="version">v{source.version}</span></h4></div>
      <span className={'badge ' + (source.state === 'superseded' ? 'historical' : 'current')}>{source.state}</span>
    </div>
    <dl className="source-dates"><div><dt>Event date</dt><dd><time dateTime={source.event_date}>{source.event_date}</time></dd></div><div><dt>Issued</dt><dd><time dateTime={source.issued_at}>{source.issued_at}</time></dd></div>{view === 'clinical' && <div><dt>Specimen</dt><dd>{source.specimen_id ?? 'Not recorded'}</dd></div>}</dl>
    {findings.length > 0 && <div className="source-quotes">
      <p className="quote-label">{view === 'clinical' ? 'Source-reported statements' : 'What the report says'}</p>
      <ul className="finding-list">{findings.map((finding, index) => <li key={finding.source_id + ':' + finding.source_line + ':' + index} data-testid="source-finding">
        <p className="finding-context"><strong>{finding.finding_key}</strong><span>Reported state: <strong>{finding.reported_state}</strong></span><span>Line {finding.source_line}</span></p>
        <blockquote data-testid="source-statement">{finding.source_statement}</blockquote>
        <p className="review-status">Clinical review: not established</p>
      </li>)}</ul>
    </div>}
    {source.state === 'superseded' && <p className="history-note">Earlier version. Quoted statements for historical versions are not supplied by this response.</p>}
    {source.state === 'current' && findings.length === 0 && <p className="history-note">No quoted statements were returned for this version.</p>}
    <details className="source-provenance"><summary>Source details and provenance</summary>
      <dl className="source-metadata">
        <div><dt>Original source ID</dt><dd><code>{source.source_id}</code></dd></div>
        <div><dt>Original SHA-256</dt><dd><code>{source.sha256}</code></dd></div>
        <div><dt>Received</dt><dd><time dateTime={source.received_at}>{source.received_at}</time></dd></div>
        <div><dt>Specimen</dt><dd>{source.specimen_id ?? 'Not recorded'}</dd></div>
        {source.supersedes_id && <div className="metadata-wide"><dt>Supersedes</dt><dd><code>{source.supersedes_id}</code></dd></div>}
      </dl>
      <p className="small">A source identifier or matching hash does not establish clinical accuracy. Original document bytes are not available in this view.</p>
    </details>
  </li>;
}

export function RecordsPanel({state, view, filters, onFiltersChange, onOverview, onLoadCases, onLoadSources}: Props) {
  const {query, versionState} = filters;
  const sourceHeading = useRef<HTMLHeadingElement>(null);
  const sourceFilter = useRef<HTMLInputElement>(null);
  const focusSources = useRef(false);
  // Navigation retains the parent's response-scoped filters. Only explicit
  // source inspection moves focus; a reading preference never requests records.
  useEffect(() => {
    if (state.sourceIndex && focusSources.current) {
      sourceHeading.current?.focus();
      focusSources.current = false;
    }
  }, [state.sourceIndex]);
  const clinical = view === 'clinical';
  const loading = state.recordsPhase.startsWith('loading');
  const index = state.sourceIndex;
  const search = query.trim().toLowerCase();
  const filtered = index?.sources.filter(source =>
    (versionState === 'all' || source.state === versionState) &&
    (!search || [source.document_id, source.kind, source.event_date, source.issued_at, source.source_id, source.specimen_id ?? ''].join(' ').toLowerCase().includes(search)))
    .sort((left, right) => Number(left.state === 'superseded') - Number(right.state === 'superseded')) ?? [];
  const hasFilter = Boolean(query) || versionState !== 'all';
  function clearFilters() { onFiltersChange({query: '', versionState: 'all'}); sourceFilter.current?.focus(); }
  function inspectSources(caseId: string) { focusSources.current = true; onLoadSources(caseId); }

  return <section className="records-workspace" data-testid="records-workspace" aria-labelledby="records-heading" aria-busy={loading}>
    <div className="records-introduction"><h2 id="records-heading">{clinical ? 'Original source records' : 'Records available to you'}</h2><span className="badge">Read only</span></div>
    <p className="source-scope-note">Source-reported information · clinical review not established. Only the last successful response is shown.</p>
    {!state.patient ? <div className="panel empty-state" data-testid="records-no-patient"><h3>Open a patient record first</h3><p>No patient is selected. Return to {clinical ? 'the workspace' : 'home'} to open an authorized fictional identity.</p><button type="button" className="primary" onClick={onOverview}>Go to patient overview</button></div> : <>
      <div className="records-toolbar"><p className="record-scope" data-testid="records-patient"><span className="muted">Records for</span> <code>{state.patient.patient_id}</code></p><button type="button" className="primary" data-testid="load-cases" disabled={loading || state.phase === 'reading' || state.phase === 'creating'} onClick={onLoadCases}>{state.recordsPhase === 'loading-cases' ? 'Checking cases…' : 'Check authorized cases'}</button></div>
      <p role="status" aria-live="polite" data-testid="records-status" className={'status ' + (state.recordsPhase === 'error' ? 'error' : '')}>{state.recordMessage}</p>
      <div className={'records-layout ' + (index ? 'has-sources' : '')}>
        {state.cases !== null && <details className="case-panel" open={clinical || !index} data-testid="records-cases">
          <summary id="case-list-heading">{clinical ? 'Case mappings' : index ? 'Linked case: ' + index.case_id : 'Choose a linked case'}</summary>
          {state.cases.length === 0 ? <div className="empty-state"><p>No current authorized case mappings were returned.</p></div> :
            <ul className="case-list">{state.cases.map(item => <li key={item.case_id} className="case-row" data-testid="case-row" data-selected={index?.case_id === item.case_id || undefined}>
              <div className="case-heading"><strong>{item.case_id}</strong><span className="badge">{item.status}</span></div>
              <p>{item.source_organization}</p>
              {clinical ? <p className="small">System: {item.source_system} · Version {item.revision}</p> : <details className="case-provenance"><summary>Case details</summary><p>System: {item.source_system} · Version {item.revision}</p></details>}
              <button type="button" data-testid="load-sources" aria-label={'Inspect source versions for ' + item.case_id} disabled={item.status !== 'active' || loading} onClick={() => inspectSources(item.case_id)}>Inspect source versions</button>
              {item.status === 'revoked' && <p className="small">This case mapping is revoked. Source inspection is unavailable.</p>}
            </li>)}</ul>}
          <p className="small muted">Fictional identity verification is not established. Clinical sources are not automatically linked.</p>
        </details>}
        {index && <section className="records-detail" data-testid="source-index" aria-labelledby="sources-heading">
          <div className="section-heading"><div><p className="eyebrow">{index.case_id}</p><h3 id="sources-heading" tabIndex={-1} ref={sourceHeading}>Source history</h3><span className="count-label">{index.sources.length} {index.sources.length === 1 ? 'version' : 'versions'}</span></div><button type="button" className="quiet source-refresh" data-testid="refresh-sources" disabled={loading} onClick={() => inspectSources(index.case_id)}>Refresh sources</button></div>
          {index.sources.length === 0 ? <div className="panel empty-state"><p>No imported original sources were returned for this case.</p></div> : <>
            <div className="source-filters" role="search" aria-label="Filter loaded source versions">
              <div className="source-query"><label htmlFor="source-filter">Filter loaded sources</label><input id="source-filter" ref={sourceFilter} type="search" value={query} onChange={event => onFiltersChange({...filters, query: event.target.value})} placeholder="Document, type, date or source ID" aria-describedby="source-filter-help"/></div>
              <div><label htmlFor="source-state">Version status</label><select id="source-state" value={versionState} onChange={event => onFiltersChange({...filters, versionState: event.target.value})}><option value="all">All versions</option><option value="current">Current</option><option value="superseded">Superseded</option></select></div>
            </div>
            <div className="filter-summary"><p id="source-filter-help" className="small">Filters only the sources loaded for this case.</p><p role="status" aria-live="polite">{filtered.length} of {index.sources.length} versions shown</p>{hasFilter && <button type="button" className="quiet" data-testid="clear-source-filters" onClick={clearFilters}>Clear filters</button>}</div>
            {filtered.length === 0 ? <div className="panel empty-state" data-testid="source-no-match"><h4>No sources match these filters</h4><p>The loaded records have not changed. Clear the filters to see all versions.</p></div> :
              <ol className="source-list">{filtered.map(source => <SourceRow key={source.source_id} source={source} view={view} findings={index.source_reported_assertions.filter(finding => finding.source_id === source.source_id)}/>)}</ol>}
          </>}
          <p className="small muted source-footnote">Amendments remain separate versions. This screen does not update research conclusions or establish clinical review.</p>
        </section>}
        {!index && state.cases !== null && state.cases.some(item => item.status === 'active') && state.recordsPhase !== 'error' && <div className="source-prompt"><span className="eyebrow">SOURCE HISTORY</span><h3>{loading ? 'Checking source access…' : 'Choose a case to inspect its records'}</h3><p>See document versions, dates and the statements reported by each current source.</p></div>}
      </div>
    </>}
  </section>;
}
