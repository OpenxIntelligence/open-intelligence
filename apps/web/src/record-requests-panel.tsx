import {useLayoutEffect,useState} from 'react';
import type {FormEvent} from 'react';
import {requestKinds,validRequestFields} from './record-requests';
import type {RecordRequestSession,RequestKind,RequestRow,RequestsView} from './record-requests';
import type {SourceIndex} from './source-contracts';

type Props={session:RecordRequestSession;index:SourceIndex;view:RequestsView;busy:boolean;
  onOriginal:(sourceId:string,trigger:HTMLButtonElement)=>void};
const receiptLabels:Record<RequestRow['receipt_status'],string>={
  not_received:'Awaiting a record',
  source_current_unreviewed:'Current source · unreviewed',
  source_superseded_reconciliation_required:'Linked version superseded · reconciliation required',
  binding_revoked_not_usable:'Case access revoked · receipt cannot be used',
};
function Item({row,index,busy,session,onOriginal}:Omit<Props,'view'>&{row:RequestRow}){
  const [selection,select]=useState('');
  const options=index.sources.filter(s=>s.state==='current' && s.kind===row.kind);
  return <li className="case-row" data-testid="request-row" data-request-id={row.request_id} data-status={row.status} data-receipt-status={row.receipt_status}>
    <strong>{row.record_label}</strong>
    <p>{row.source_organization} · {row.kind} · {row.status}</p>
    {row.status==='requested'?<div>
      <label>Source version to link
        <select data-testid="request-source" value={selection} disabled={busy || !options.length} onChange={e=>select(e.target.value)}>
          <option value="">Choose a current {row.kind} source</option>
          {options.map(s=><option key={s.source_id} value={s.source_id}>{s.document_id} · v{s.version} · {s.source_id}</option>)}
        </select>
      </label>
      <button type="button" data-testid="request-receive" disabled={busy || !options.some(s=>s.source_id===selection)}
        onClick={()=>void session.receive(index,row.request_id,selection)}>Link selected version</button>
      {!options.length&&<p>No current {row.kind} source is listed in this case.</p>}
    </div>:row.status==='received'?<>
      <p><strong>{receiptLabels[row.receipt_status]}</strong></p>
      {row.source?<><p>{row.source.document_id} · v{row.source.version} · <code>{row.source.source_id}</code></p>
        <button type="button" data-testid="request-inspect-original" disabled={busy}
          onClick={e=>onOriginal(row.source!.source_id,e.currentTarget)}>Inspect linked original</button></>:
        <p>Source details withheld in this case.</p>}
    </>:<p>No record linked.</p>}
  </li>;
}
export function RecordRequestsDisclosure({session,index,view,busy,onOriginal}:Props){
  const [open,setOpen]=useState(false);
  const [fields,setFields]=useState({kind:'clinical' as RequestKind,record_label:'',source_organization:''});
  useLayoutEffect(()=>()=>session.close(index),[index,session]);
  const blocked=busy || view.busy;
  function create(event:FormEvent){
    event.preventDefault();
    if(blocked || !view.rows || view.retryCreate || !validRequestFields(fields))return;
    void session.create(index,fields);
    setFields({...fields,record_label:'',source_organization:''});
  }
  return <details className="record-import-disclosure request-panel" data-testid="record-requests-disclosure"
    onToggle={event=>{const next=event.currentTarget.open;setOpen(next);if(next)session.open(index);else session.close(index);}}>
    <summary>Record requests</summary>
    {open&&<>
      <p>Track missing records for this fictional patient across cases. Requests stay in this workspace. Linking a source does not verify which organization sent it.</p>
      <button type="button" data-testid="requests-refresh" disabled={blocked} onClick={()=>void session.refresh(index)}>Refresh requests</button>
      <p role="status" aria-live="polite">{view.message}</p>
      {view.retryCreate && !view.busy && <div>
        {view.retryFields && <p>Earlier request: {view.retryFields.record_label} · {view.retryFields.source_organization} · {view.retryFields.kind}</p>}
        <div className="actions"><button type="button" disabled={blocked} onClick={()=>void session.retryCreate(index)}>Retry exact request</button>
          {view.rows && <button type="button" disabled={blocked} onClick={()=>session.abandonCreate(index)}>Discard retry</button>}</div>
      </div>}
      {view.rows && <>
        {view.rows.length>0&&<ul className="case-list" aria-label="Patient record requests">{view.rows.map(row=>
          <Item key={row.request_id} row={row} index={index} session={session} busy={blocked || view.retryCreate} onOriginal={onOriginal}/>)}</ul>}
        {!view.retryCreate&&<form onSubmit={create} aria-label="New missing-record request">
          <h4>Request a missing record</h4>
          <label>Record label<input data-testid="request-label" value={fields.record_label} required maxLength={140}
            onChange={e=>setFields({...fields,record_label:e.target.value})}/></label>
          <label>Source organization<input data-testid="request-organization" value={fields.source_organization} required maxLength={100}
            onChange={e=>setFields({...fields,source_organization:e.target.value})}/></label>
          <label>Record kind<select data-testid="request-kind" value={fields.kind}
            onChange={e=>setFields({...fields,kind:e.target.value as RequestKind})}>
            {requestKinds.map(k=><option key={k} value={k}>{k}</option>)}
          </select></label>
          <button data-testid="request-create" type="submit" disabled={blocked || !validRequestFields(fields)}>Save local request</button>
        </form>}
      </>}
    </>}
  </details>;
}
