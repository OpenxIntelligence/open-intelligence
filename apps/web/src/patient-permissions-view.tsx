import {useEffect,useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';
import {permissionKey} from './patient-permissions';

export function PatientPermissions({session,state,patientId}:{session:RegistrySession;state:ViewState;patientId:string}){
  const console=session.currentPermissions();
  const [actor,setActor]=useState(''),[reference,setReference]=useState(''),[expires,setExpires]=useState('');
  const [relationship,setRelationship]=useState('patient'),[purpose,setPurpose]=useState('operations');
  const [actions,setActions]=useState<string[]>([]),[confirmed,setConfirmed]=useState(false);
  useEffect(()=>{setActor('');setReference('');setExpires('');setActions([]);setConfirmed(false);},[console]);
  const busy=Boolean(console?.busy||console?.pending),page=console?.page;
  return <details className="panel" data-testid="patient-permissions">
    <summary>Patient permissions</summary>
    <p>Record who may access this patient, for which purpose and until when. Opening this console clears the current patient records.</p>
    {!console?<button type="button" disabled={!state.connected||!permissionKey(patientId)||state.suspensionPhase==='sending'||state.suspensionPhase==='unknown'} onClick={()=>session.managePatientPermissions(patientId)}>Manage permissions for this patient ID</button>:<>
      <p><strong>Patient:</strong> <code>{console.scope.patientId}</code></p>
      <p role="status">{console.message}</p>
      {console.pending?<button disabled={console.busy} onClick={()=>void console.retry()}>Retry exact permission change</button>:
        <button disabled={busy} onClick={()=>void console.read()}>Check permission history</button>}
      {page&&<>
        <p>{page.enforcement==='persisted_grants'?'Stored grants are required in addition to operator credential scope.':'This server is using fixture permissions. Stored declarations are recorded but do not currently govern access.'}</p>
        <ul>{page.grants.map(grant=><li key={grant.grant_id}>
          <h3>{grant.actor} · {grant.status}</h3>
          <p>{grant.relationship.replaceAll('_',' ')} · {grant.purpose} · expires {new Date(grant.expires_at).toLocaleString()}</p>
          <p>Actions: {grant.actions.join(', ')}</p>
          <p>Authority reference: <code>{grant.authority_ref}</code></p>
          {grant.status!=='revoked'&&<button data-testid="permission-revoke" disabled={busy||!confirmed||!permissionKey(reference)} onClick={()=>void console.command({synthetic:true,
            request_key:crypto.randomUUID(),authority_ref:reference,expected_revision:1},grant.grant_id)}>Revoke this permission for {grant.actor}</button>}
          {grant.revocation_ref&&<p>Revocation reference: <code>{grant.revocation_ref}</code></p>}
        </li>)}</ul>
        {page.grants.length===0&&<p>No permissions on this page.</p>}
        {page.next_after&&<button disabled={busy} onClick={()=>void console.read(page.next_after!)}>Next permissions</button>}
        <form onSubmit={event=>{event.preventDefault();if(!Number.isFinite(Date.parse(expires)))return;void console.command({synthetic:true,request_key:crypto.randomUUID(),authority_ref:reference,
          actor,purpose,relationship,actions,expires_at:new Date(expires).toISOString()});}}>
          <h3>Record a permission</h3>
          <label htmlFor="permission-actor">Recipient actor ID</label><input id="permission-actor" value={actor} onChange={e=>setActor(e.target.value)} required minLength={3} maxLength={128} disabled={busy}/>
          <label htmlFor="permission-relationship">Recipient relationship</label><select id="permission-relationship" value={relationship} onChange={e=>setRelationship(e.target.value)} disabled={busy}>
            <option value="patient">Patient</option><option value="guardian">Guardian</option><option value="animal_owner">Animal owner</option><option value="care_team">Care team</option><option value="research_delegate">Research delegate</option></select>
          <label htmlFor="permission-purpose">Purpose</label><select id="permission-purpose" value={purpose} onChange={e=>setPurpose(e.target.value)} disabled={busy}><option value="operations">Care operations</option><option value="research">Research</option></select>
          <label htmlFor="permission-expiry">Expires at (your local time)</label><input id="permission-expiry" type="datetime-local" value={expires} onChange={e=>setExpires(e.target.value)} required disabled={busy}/>
          <fieldset disabled={busy}><legend>Allowed actions</legend>{page.available_actions.map(action=><label className="check" key={action}><input type="checkbox" checked={actions.includes(action)} onChange={e=>setActions(e.target.checked?[...actions,action]:actions.filter(a=>a!==action))}/>{action.replaceAll('_',' ').replaceAll('.',' ')}</label>)}</fieldset>
          <label htmlFor="permission-reference">Authority reference for this grant or revocation</label><input id="permission-reference" value={reference} onChange={e=>setReference(e.target.value)} required disabled={busy}/>
          <label className="check"><input data-testid="permission-confirm" type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} disabled={busy}/>This records an independently fictional authorization declaration.</label>
          <button data-testid="permission-submit" type="submit" disabled={busy||!confirmed||!actions.length||!permissionKey(actor)||!permissionKey(reference)}>Record permission</button>
        </form>
      </>}
    </>}
  </details>;
}
