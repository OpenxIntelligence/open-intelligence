import {useEffect,useRef,useState} from 'react';
import type {RegistrySession} from './registry-client';
import {receiptMicros} from './source-contracts';
import type {SourceIndex,SourceHistory as History} from './source-contracts';

export function SourceHistory({session,index,busy,onOpenOriginal}:{session:RegistrySession;index:SourceIndex;busy:boolean;
  onOpenOriginal:(sourceId:string,trigger:HTMLButtonElement)=>void}) {
  const [cutoff,setCutoff]=useState(''),[history,setHistory]=useState<History|null>(null);
  const [message,setMessage]=useState(''),[loading,setLoading]=useState(false);
  const pending=useRef<AbortController|null>(null),patient=session.snapshot().patient;
  useEffect(()=>()=>{pending.current?.abort();},[index]);
  const receipts=[...new Set(index.sources.map(s=>s.received_at))].sort((a,b)=>receiptMicros(a)<receiptMicros(b)?-1:1);
  function reset(value:string){pending.current?.abort();pending.current=null;setCutoff(value);setHistory(null);setMessage('');setLoading(false);}
  async function check(){
    if(!cutoff||loading||busy)return;
    pending.current?.abort();const control=new AbortController();pending.current=control;
    setLoading(true);setHistory(null);setMessage('');
    const current=()=>!control.signal.aborted&&pending.current===control&&session.snapshot().patient===patient&&session.snapshot().sourceIndex===index;
    try{const result=await session.sourceHistory(index,cutoff,control.signal);if(current())setHistory(result);}
    catch{if(current())setMessage('History could not be verified. Refresh records and check current access.');}
    finally{if(current())setLoading(false);}
  }
  return <section aria-labelledby="source-history-heading" className="source-history" data-testid="source-history">
    <h3 id="source-history-heading">Records at an earlier receipt</h3>
    <p>See the latest version of each structured report held by the platform at a selected receipt time. Clinical interpretations, manually reviewed documents and image files are outside this view.</p>
    <label htmlFor="source-history-cutoff">Include records received through (UTC)</label>
    <select id="source-history-cutoff" value={cutoff} disabled={busy} onChange={e=>reset(e.target.value)}>
      <option value="">Choose a receipt time</option>
      {receipts.map(value=><option key={value} value={value}>{value.replace('T',' ').replace('Z',' UTC')}</option>)}
    </select>
    <button type="button" disabled={!cutoff||loading||busy} onClick={()=>void check()} data-testid="source-history-check">{loading?'Checking history…':'Check historical records'}</button>
    <p role="status">{message|| (history?'Historical source membership checked using current access.':'')}</p>
    {history&&<div data-testid="source-history-result">
      <p>Received through <time dateTime={history.received_through}>{history.received_through}</time>. Receipt time describes when this platform stored a record, not when it was available elsewhere.</p>
      {history.sources.length===0?<p>No structured reports had been received at this cutoff.</p>:<ul>
        {history.sources.map(source=><li key={source.source_id} data-testid="source-history-version">
          <strong>{source.document_id} · version {source.version}</strong>
          <p>{source.kind} · Event {source.event_date} · Issued {source.issued_at}</p>
          <p className="muted">Received <time dateTime={source.received_at}>{source.received_at}</time></p>
          <button type="button" aria-label={`Open this exact original: ${source.document_id}, version ${source.version}`} disabled={busy} onClick={e=>onOpenOriginal(source.source_id,e.currentTarget)}>Open this exact original</button>
        </li>)}
      </ul>}
    </div>}
  </section>;
}
