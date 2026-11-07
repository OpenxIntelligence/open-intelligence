import type {SourceFinding, SourceIndex, SourceVersion} from './source-contracts.js';

export type DiagnosticKind = 'pathology' | 'molecular';
export type DiagnosticFilters = Readonly<{
  query: string;
  versionState: string;
  specimen?: string | null;
  reportedState?: string;
}>;
export const DIAGNOSTIC_PAGE_SIZE = 12;
export type DiagnosticReportRow = Readonly<{
  source: SourceVersion;
  findings: readonly SourceFinding[];
  totalFindings: number;
}>;

/** A projection of one authorized response. Specimen labels never establish
 * biological identity, and absent historical quotations never become results. */
export function browseDiagnosticReports(index: SourceIndex, kind: DiagnosticKind,
  filters: DiagnosticFilters, requestedPage = 1) {
  const reports = index.sources.filter(source => source.kind === kind);
  const current = new Set(reports.filter(source => source.state === 'current').map(source => source.source_id));
  const bySource = new Map<string, SourceFinding[]>();
  for (const finding of index.source_reported_assertions) {
    if (!current.has(finding.source_id)) continue;
    const found = bySource.get(finding.source_id) ?? [];
    found.push(finding);
    bySource.set(finding.source_id, found);
  }
  const query = filters.query.trim().toLowerCase();
  const rows: DiagnosticReportRow[] = [];
  for (const source of reports) {
    if (filters.versionState !== 'all' && source.state !== filters.versionState) continue;
    if (filters.specimen !== undefined && source.specimen_id !== filters.specimen) continue;
    const findings = bySource.get(source.source_id) ?? [];
    const sourceMatches = !query || [source.document_id, source.source_id, source.kind,
      source.event_date, source.issued_at, source.specimen_id ?? ''].join(' ').toLowerCase().includes(query);
    const matched = findings.filter(finding =>
      (filters.reportedState === undefined || finding.reported_state === filters.reportedState) &&
      (sourceMatches || [finding.finding_key, finding.source_statement, finding.reported_state]
        .join(' ').toLowerCase().includes(query)));
    if ((filters.reportedState !== undefined || !sourceMatches) && matched.length === 0) continue;
    rows.push(Object.freeze({source, findings: Object.freeze(matched), totalFindings: findings.length}));
  }
  rows.sort((a, b) => Number(a.source.state === 'superseded') - Number(b.source.state === 'superseded'));
  const pageCount = Math.max(1, Math.ceil(rows.length / DIAGNOSTIC_PAGE_SIZE));
  const page = Math.min(pageCount, Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1);
  const allFindings = Array.from(bySource.values()).flat();
  return Object.freeze({
    rows: Object.freeze(rows.slice((page - 1) * DIAGNOSTIC_PAGE_SIZE, page * DIAGNOSTIC_PAGE_SIZE)),
    matchedReports: rows.length,
    totalReports: reports.length,
    totalStatements: allFindings.length,
    specimens: Object.freeze(Array.from(new Set(reports.flatMap(source => source.specimen_id === null ? [] : [source.specimen_id]))).sort()),
    withoutSpecimen: reports.filter(source => source.specimen_id === null).length,
    reportedStates: Object.freeze(Array.from(new Set(allFindings.map(finding => finding.reported_state))).sort()),
    page, pageCount,
    start: rows.length ? (page - 1) * DIAGNOSTIC_PAGE_SIZE + 1 : 0,
    end: Math.min(page * DIAGNOSTIC_PAGE_SIZE, rows.length),
  });
}
