import {useEffect,useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';
import {permissionKey} from './patient-permissions';

export function PatientConsent({session,state,patientId}:{session:RegistrySession;state:ViewState;patientId:string}){
  const console=session.currentConsent(),page=console?.page,busy=Boolean(console?.busy||console?.pending);
  const [actor,setActor]=useState(''),[purpose,setPurpose]=useState('operations'),[maker,setMaker]=useState('');
  const [basis,setBasis]=useState('self'),[reference,setReference]=useState(''),[from,setFrom]=useState(''),[until,setUntil]=useState('');
  const [allowed,setAllowed]=useState<string[]>([]),[confirmed,setConfirmed]=useState(false);
  useEffect(()=>{setActor('');setMaker('');setReference('');setFrom('');setUntil('');setAllowed([]);setConfirmed(false);},[console]);
  const current=page?.decisions.find(r=>r.actor===actor&&r.target_purpose===purpose&&r.status!=='superseded');
  const revision=current?.revision??0;
  const valid=confirmed&&permissionKey(actor)&&permissionKey(maker)&&permissionKey(reference);
  const send=(withdraw:boolean)=>{
    if(!console||!valid)return;
    void console.command({synthetic:true,request_key:crypto.randomUUID(),actor,target_purpose:purpose,
      expected_revision:revision,state:withdraw?'withdrawn':'granted',actions:withdraw?[]:allowed,
      decision_maker:maker,basis,authority_ref:reference,
      valid_from:withdraw?null:new Date(from).toISOString(),expires_at:withdraw?null:new Date(until).toISOString()});
  };
  return <details className="panel" data-testid="patient-consent"><summary>Consent decisions</summary>
    <p>Record or withdraw a fictional declaration for one recipient, purpose and set of uses. This does not verify identity or legal authority. Opening this console clears current patient records.</p>
    {!console?<button disabled={!state.connected||!permissionKey(patientId)||session.permissionChangePending()||state.suspensionPhase==='sending'||state.suspensionPhase==='unknown'} onClick={()=>session.managePatientConsent(patientId)}>Manage consent for this patient ID</button>:<>
      <p><strong>Patient:</strong> <code>{console.scope.patientId}</code></p><p role="status">{console.message}</p>
      {console.pending?<button disabled={console.busy} onClick={()=>void console.retry()}>Retry exact consent decision</button>:<button disabled={busy} onClick={()=>void console.read()}>Check consent history</button>}
      {page&&<>
        <p>{page.enforcement==='required'?'A current consent decision is required in addition to credentials and permission grants.':'This server enforces recorded decisions; patients without a decision retain fixture behavior.'} Purpose restrictions still apply.</p>
        <p>Scope: this patient’s record, limited to the listed uses and purpose. A recorded decision is not permission to deliver treatment.</p>
        <ul>{page.decisions.map(row=><li key={row.event_id}><h3>{row.actor} · {row.status}</h3>
          <p>{row.target_purpose} · revision {row.revision} · recorded by {row.recorded_by}</p>
          <p>Decision maker: {row.decision_maker} · {row.basis.replaceAll('_',' ')} · reference <code>{row.authority_ref}</code></p>
          {row.valid_from&&row.expires_at&&<p>Valid from {new Date(row.valid_from).toLocaleString()} until {new Date(row.expires_at).toLocaleString()}</p>}
          {row.actions.length>0&&<p>Uses: {row.actions.join(', ')}</p>}
          {row.status!=='superseded'&&<button disabled={busy} onClick={()=>{setActor(row.actor);setPurpose(row.target_purpose);setMaker(row.decision_maker);setBasis(row.basis);setAllowed(row.actions);setReference('');setConfirmed(false);}}>Use revision {row.revision} for {row.actor}</button>}
        </li>)}</ul>
        {!page.decisions.length&&<p>No consent decisions on this page.</p>}
        {page.next_before&&<button disabled={busy} onClick={()=>void console.read(page.next_before!)}>Older consent decisions</button>}
        <form onSubmit={e=>{e.preventDefault();if(Number.isFinite(Date.parse(from))&&Number.isFinite(Date.parse(until)))send(false);}}>
          <h3>Record or withdraw a declaration</h3>
          <label htmlFor="consent-actor">Recipient actor ID</label><input id="consent-actor" value={actor} onChange={e=>setActor(e.target.value)} disabled={busy} required maxLength={128}/>
          <label htmlFor="consent-purpose">Purpose</label><select id="consent-purpose" value={purpose} onChange={e=>setPurpose(e.target.value)} disabled={busy}><option value="operations">Care operations</option><option value="research">Research</option></select>
          <p>Expected current revision: {revision}. A concurrent change requires a fresh history check. A new decision replaces the current one immediately; a future start date holds access until that time.</p>
          <label htmlFor="consent-maker">Declared decision-maker ID</label><input id="consent-maker" value={maker} onChange={e=>setMaker(e.target.value)} disabled={busy} required maxLength={128}/>
          <label htmlFor="consent-basis">Declared authority basis</label><select id="consent-basis" value={basis} onChange={e=>setBasis(e.target.value)} disabled={busy}><option value="self">Patient’s own declaration</option><option value="guardian">Guardian</option><option value="animal_owner">Animal owner</option><option value="authorized_representative">Authorized representative</option></select>
          <label htmlFor="consent-reference">Declaration or withdrawal reference</label><input id="consent-reference" value={reference} onChange={e=>setReference(e.target.value)} disabled={busy} required maxLength={128}/>
          <label htmlFor="consent-from">Valid from (your local time)</label><input id="consent-from" type="datetime-local" value={from} onChange={e=>setFrom(e.target.value)} disabled={busy}/>
          <label htmlFor="consent-until">Expires at (your local time)</label><input id="consent-until" type="datetime-local" value={until} onChange={e=>setUntil(e.target.value)} disabled={busy}/>
          <fieldset disabled={busy}><legend>Consented uses</legend>{page.available_actions.map(action=><label className="check" key={action}><input type="checkbox" checked={allowed.includes(action)} onChange={e=>setAllowed(e.target.checked?[...allowed,action]:allowed.filter(a=>a!==action))}/>{action.replaceAll('_',' ').replaceAll('.',' ')}</label>)}</fieldset>
          <label className="check"><input data-testid="consent-confirm" type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} disabled={busy}/>This is an independently fictional declaration; legal authority has not been verified.</label>
          <div className="actions"><button data-testid="consent-submit" type="submit" disabled={busy||!valid||!allowed.length||!Number.isFinite(Date.parse(from))||Date.parse(until)<=Date.parse(from)||!Number.isFinite(Date.parse(until))}>Record consent decision</button>
            <button data-testid="consent-withdraw" type="button" disabled={busy||!valid} onClick={()=>send(true)}>Record withdrawal</button></div>
        </form>
      </>}
    </>}
  </details>;
}
