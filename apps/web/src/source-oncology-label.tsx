import type {ReportedOncologyContext} from './source-contracts';

export function SourceOncologyLabel({context, state}: {
  context?: ReportedOncologyContext;
  state?: string;
}) {
  if (!context) return null;
  return <p>Source-reported {context.role} · {context.episode_id ?? 'Episode unassigned'}{state && ' · ' + state}</p>;
}
