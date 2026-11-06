import {useEffect,useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';

export function PatientSuspension({session,state,busy}:{session:RegistrySession;state:ViewState;busy:boolean}){
  const [confirmed,setConfirmed]=useState(false);
  const patient=state.patient,phase=state.suspensionPhase;
  useEffect(()=>setConfirmed(false),[patient?.patient_id,patient?.revision,phase]);
  if(!state.connected||(!patient&&!state.suspensionTarget&&phase==='idle'))return null;
  const target=patient??state.suspensionTarget;
  const pending=phase==='sending'||phase==='unknown';
  return <details className="panel" data-testid="patient-suspension-panel" open={phase!=='idle'?true:undefined}>
    <summary>Suspend access to this fictional patient</summary>
    <p>Operator action. The server requires a separate suspension grant. This blocks new source access and background work for this patient while preserving historical records and receipts.</p>
    {target&&<p>Patient <code>{target.patient_id}</code> · {patient?'Registry revision':'Requested from revision'} {target.revision}</p>}
    <p>This clears patient content and unsaved drafts from this tab. Reactivation is not available in this workspace. Suspension does not cancel historical work or delete records.</p>
    {patient?.status==='active'&&!pending&&<form onSubmit={event=>{event.preventDefault();void session.suspendPatient(confirmed);}}>
      <label className="check"><input type="checkbox" data-testid="suspension-confirm" checked={confirmed}
        onChange={event=>setConfirmed(event.target.checked)} disabled={busy}/>
        I intend to suspend access to this independently fictional patient and clear this tab’s patient content.</label>
      <button type="submit" data-testid="suspension-submit" disabled={busy||!confirmed}>Suspend patient access</button>
    </form>}
    {patient?.status==='suspended'&&<p>Registry status: suspended. A new suspension request is unavailable.</p>}
    <p role="status" aria-live="polite" data-testid="suspension-status" data-phase={phase}>{state.suspensionMessage}</p>
    {phase==='unknown'&&<div className="actions">
      <button type="button" data-testid="suspension-retry" onClick={()=>void session.retryPatientSuspension()}>Retry unchanged suspension request</button>
      <button type="button" data-testid="suspension-leave" onClick={()=>session.leaveSuspensionRecovery()}>Leave recovery</button>
      <p>Leaving recovery discards the local retry request. It does not cancel or reverse a suspension. Reopen the identity to check its status.</p>
    </div>}
  </details>;
}
