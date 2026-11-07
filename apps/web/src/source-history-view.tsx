import {useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';

/** Read-only history never enters the current question/Composer context. */
export function SourceHistoryView({session,state,busy}:{session:RegistrySession;state:ViewState;busy:boolean}){
  const model=state.worldModel!;
  const sources=[...model.current_sources,...model.history].sort((a,b)=>a.received_at.localeCompare(b.received_at));
  const cutoffs=[...new Set(sources.map(s=>s.received_at))];
  const [cutoff,setCutoff]=useState(cutoffs[0]??'');
  const history=state.sourceHistory;
  const past=history?.world_model;
  return <section aria-labelledby="history-heading" className="source-history" data-testid="source-history">
    <h3 id="history-heading">What was available then?</h3>
    <p>Reconstruct reports received by a selected time. Late-arriving reports appear when received, even if their clinical date is earlier. Access is checked now.</p>
    {cutoffs.length===0?<p>No source receipts are available yet.</p>:<>
      <label>Records received through <select data-testid="history-cutoff" value={cutoff} disabled={busy||state.historyPhase==='loading'}
        onChange={e=>{setCutoff(e.target.value);session.dismissSourceHistory();}}>
        {cutoffs.map(time=><option key={time} value={time}>{time} · {sources.filter(s=>s.received_at===time).map(s=>`${s.document_id} v${s.version}`).join(', ')}</option>)}
      </select></label>{' '}
      <button type="button" data-testid="history-load" disabled={busy||state.historyPhase==='loading'} onClick={()=>void session.loadSourceHistory(cutoff)}>Load historical context</button>
    </>}
    <p role="status" data-testid="history-status">{state.historyMessage}</p>
    {past&&<div data-testid="history-result">
      <h4>Historical context — through {history.received_through}</h4>
      <p>“Current” here means the latest version received by that time. This is not the current clinical record or a reviewed conclusion.</p>
      <p>{past.summary.current_sources} sources · {past.summary.current_observations} statements · {past.summary.unresolved_observations} unresolved · {past.summary.source_disagreements} source disagreements</p>
      {past.current_sources.length===0&&<p>No structured sources had been received by this cutoff.</p>}
      <ul>{past.current_sources.map(s=><li key={s.source_id} data-testid="history-source">
        <strong>{s.document_id} v{s.version}</strong> · event {s.event_date} · received {s.received_at}
        <p><code>{s.source_id}</code> · SHA-256 <code>{s.sha256}</code></p>
        {past.observations.filter(o=>o.source_id===s.source_id).map(o=><blockquote key={o.source_line}>
          {o.finding_key} · {o.reported_state} · line {o.source_line}: {o.source_statement}
        </blockquote>)}
        {past.laboratory_observations.filter(o=>o.source_id===s.source_id).map(o=><p key={o.observation_reference}>
          {o.loinc_code} · {o.status==='reported_value'?`${o.value_text} ${o.unit_code}`:`Result absent: ${o.absent_reason}`} · {o.effective_at} · {o.observation_reference}
        </p>)}
      </li>)}</ul>
      <details><summary>Historical receipt and fingerprint</summary><p><code>{past.access_receipt_id}</code></p><p><code data-testid="history-fingerprint">{past.snapshot_fingerprint}</code></p></details>
      <button type="button" onClick={()=>session.dismissSourceHistory()}>Close historical context</button>
    </div>}
  </section>;
}
