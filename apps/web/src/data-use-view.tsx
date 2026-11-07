import {useEffect,useState} from 'react';
import type {RegistrySession,ViewState,DataUseSnapshot} from './registry-client';

export function DataUseView({session,state,busy}:{session:RegistrySession;state:ViewState;busy:boolean}){
 const [purpose,setPurpose]=useState<'operations'|'research'>('operations');
 const [result,setResult]=useState<DataUseSnapshot|null>(null);
 const [message,setMessage]=useState('Not checked. A separate permission is required.');
 const [attempt,setAttempt]=useState(0);
 const [loading,setLoading]=useState(false);
 const [confirmed,setConfirmed]=useState(false);
 const [next,setNext]=useState<'restricted'|'unrestricted'>('restricted');
 const pending=state.dataUsePhase==='sending'||state.dataUsePhase==='unknown';
 useEffect(()=>setConfirmed(false),[result,purpose,next,state.dataUsePhase]);
 useEffect(()=>{
  if(!attempt)return;
  const control=new AbortController();setResult(null);setLoading(true);setMessage('Checking current restriction…');
  session.readDataUse(purpose,control.signal).then(value=>{
   if(!control.signal.aborted){setResult(value);setMessage('Snapshot from the latest successful check.');}
  }).catch(()=>{if(!control.signal.aborted)setMessage('Status unavailable. Access may be denied or the service unavailable.');})
   .finally(()=>{if(!control.signal.aborted)setLoading(false);});
  return ()=>control.abort();
 },[session,purpose,attempt]);
 if(!state.connected||(!state.patient&&!state.dataUseTarget))return null;
 return <details className="panel" data-testid="data-use-panel" open={state.dataUsePhase!=='idle'?true:undefined}><summary>Data-use restrictions</summary>
  <p>Administrative controls for this fictional patient. These restrictions can block existing access; they do not establish patient consent or grant permission.</p>
  <label>Purpose <select disabled={busy||pending||!state.patient} value={state.patient?purpose:state.dataUseTarget?.target_purpose??purpose} onChange={e=>{setResult(null);setMessage('Not checked.');setAttempt(0);setLoading(false);setPurpose(e.target.value as typeof purpose);}}><option value="operations">Operations</option><option value="research">Research</option></select></label>
  <button data-testid="data-use-check" disabled={loading||busy||pending||!state.patient} onClick={()=>setAttempt(n=>n+1)}>Check restriction</button>
  <p role="status">{message}</p>
  {result&&<p>{result.state==='restricted'?'Restricted':result.state==='unrestricted'?'Restriction lifted; independent access grants still required':'No restriction decision recorded; patient consent is not established'} · Decision revision {result.revision}</p>}
  {state.dataUseTarget&&<p>Decision patient <code>{state.dataUseTarget.patient_id}</code> · {state.dataUseTarget.target_purpose} · requested from decision revision {state.dataUseTarget.revision}</p>}
  {result&&state.patient?.status==='active'&&!pending&&<form onSubmit={event=>{event.preventDefault();void session.decideDataUse(result,next,confirmed);}}>
   <label>Decision <select data-testid="data-use-next" disabled={busy} value={next} onChange={e=>setNext(e.target.value as typeof next)}><option value="restricted">Restrict this purpose</option><option value="unrestricted">Lift this purpose restriction</option></select></label>
   <p>This clears patient content and unsaved drafts in this tab. Lifting a restriction does not grant access or establish consent.</p>
   <label className="check"><input data-testid="data-use-confirm" type="checkbox" checked={confirmed} disabled={busy} onChange={e=>setConfirmed(e.target.checked)}/>I intend to record this decision for this fictional patient and purpose.</label>
   <button data-testid="data-use-submit" disabled={busy||!confirmed}>Record decision</button>
  </form>}
  <p role="status" data-testid="data-use-write-status" data-phase={state.dataUsePhase}>{state.dataUseMessage}</p>
  {state.dataUseReceipt&&<p>Historical receipt: {state.dataUseReceipt.state} · decision revision {state.dataUseReceipt.revision}. Check again after reopening for current state.</p>}
  {state.dataUsePhase==='unknown'&&<div className="actions">
   <button data-testid="data-use-retry" onClick={()=>void session.retryDataUse()}>Retry unchanged decision</button>
   <button onClick={()=>session.leaveDataUseRecovery()}>Leave recovery</button>
   <p>Leaving discards this tab’s retry request. It does not cancel or reverse a decision.</p>
  </div>}
 </details>;
}
