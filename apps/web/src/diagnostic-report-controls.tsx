import type {DiagnosticFilters, DiagnosticKind, browseDiagnosticReports} from './diagnostic-report-browser';
import './diagnostic-report-browser.css';

export function DiagnosticReportControls({kind, result, filters, onChange}: {
  kind: DiagnosticKind;
  result: ReturnType<typeof browseDiagnosticReports>;
  filters: DiagnosticFilters;
  onChange: (filters: DiagnosticFilters) => void;
}) {
  return <section className="diagnostic-report-controls" aria-labelledby="diagnostic-browser-heading" data-testid="diagnostic-report-controls">
    <h3 id="diagnostic-browser-heading">{kind === 'pathology' ? 'Pathology' : 'Molecular'} report browser</h3>
    <p>{result.totalReports} loaded report versions · {result.totalStatements} quoted current statements · {result.specimens.length} recorded specimen IDs</p>
    <div className="diagnostic-report-fields">
      <div><label htmlFor="diagnostic-specimen">Reported specimen</label>
        <select id="diagnostic-specimen" value={filters.specimen === undefined ? 'all' : filters.specimen === null ? 'none' : 'id:' + filters.specimen}
          onChange={event => onChange({...filters, specimen: event.target.value === 'all' ? undefined : event.target.value === 'none' ? null : event.target.value.slice(3)})}>
          <option value="all">All specimen labels</option>
          {result.withoutSpecimen > 0 && <option value="none">Not recorded ({result.withoutSpecimen} versions)</option>}
          {result.specimens.map(specimen => <option key={specimen} value={'id:' + specimen}>{specimen}</option>)}
        </select>
      </div>
      <div><label htmlFor="diagnostic-reported-state">Reported statement state</label>
        <select id="diagnostic-reported-state" value={filters.reportedState === undefined ? 'all' : 'state:' + filters.reportedState}
          aria-describedby="diagnostic-state-help"
          onChange={event => onChange({...filters, reportedState: event.target.value === 'all' ? undefined : event.target.value.slice(6)})}>
          <option value="all">All reported states</option>
          {result.reportedStates.map(state => <option key={state} value={'state:' + state}>{state}</option>)}
        </select>
      </div>
    </div>
    <p className="small" id="diagnostic-state-help">States retain the report’s wording. Earlier versions have no quotations in this list. Choose All reported states to find their originals. Specimen labels do not establish that samples are the same.</p>
  </section>;
}

export function DiagnosticReportPagination({result, onPage}: {
  result: ReturnType<typeof browseDiagnosticReports>;
  onPage: (page: number) => void;
}) {
  if (result.pageCount < 2) return null;
  return <nav className="diagnostic-report-pagination" aria-label="Report pages" data-testid="diagnostic-report-pagination">
    <button type="button" disabled={result.page === 1} onClick={() => onPage(result.page - 1)}>Previous reports</button>
    <span role="status" aria-live="polite">Page {result.page} of {result.pageCount}</span>
    <button type="button" disabled={result.page === result.pageCount} onClick={() => onPage(result.page + 1)}>Next reports</button>
  </nav>;
}
