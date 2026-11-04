import {useRef} from 'react';
import type {SourceIndex} from './source-contracts';

export type ReadingView = 'patient' | 'clinical';
export type SourceFilters = {query: string; versionState: string};
export const emptySourceFilters: SourceFilters = {query: '', versionState: 'all'};

/** Presentation of the existing response only; no retrieval or clinical state. */
export function SourceReading({index, view, filters, onFiltersChange, busy, questionBusy, onOpenOriginal, onAskQuestion}: {
  index: SourceIndex;
  view: ReadingView;
  filters: SourceFilters;
  onFiltersChange: (filters: SourceFilters) => void;
  busy: boolean;
  questionBusy: boolean;
  onAskQuestion: (sourceId: string, line: number) => void;
  onOpenOriginal: (sourceId: string, trigger: HTMLButtonElement) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
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
  if (index.sources.length === 0) return <p>No imported original sources for this case.</p>;
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
        </li>;
      })}</ol>}
  </div>;
}
