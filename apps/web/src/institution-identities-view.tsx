import {useEffect,useRef,useState} from 'react';
import type {RegistrySession} from './registry-client';
import type {InstitutionCommand,InstitutionIdentity} from './institution-identities';

export function InstitutionIdentities({session,patientId,caseId,disabled,onSelect}:{session:RegistrySession;
  patientId:string;caseId:string;disabled:boolean;onSelect:(id:string|null)=>void}){
  const [rows,setRows]=useState<readonly InstitutionIdentity[]|null>(null),[busy,setBusy]=useState(false);
  const [message,setMessage]=useState('Refresh identities to inspect this case’s institution links.');
  const [org,setOrg]=useState(''),[system,setSystem]=useState(''),[subject,setSubject]=useState('');
  const [review,setReview]=useState(''),[pending,setPending]=useState<InstitutionCommand|null>(null);
  const [selected,setSelected]=useState('');const generation=useRef(0),controller=useRef<AbortController|null>(null);
  useEffect(()=>{generation.current++;controller.current?.abort();setRows(null);setPending(null);setBusy(false);
    setSelected('');setOrg('');setSystem('');setSubject('');setReview('');
    return()=>{generation.current++;controller.current?.abort();};},[patientId,caseId]);
  async function run(command?:InstitutionCommand){
    if(busy||disabled)return;
    const current=++generation.current,control=new AbortController();controller.current=control;
    setBusy(true);setRows(null);setSelected('');onSelect(null);
    if(command)setPending(command);
    setMessage(command?'Saving the explicit identity request…':'Checking current identity access…');
    try{
      const result=await session.institutionRequest(caseId,control.signal,command);
      if(current!==generation.current)return;
      if(Array.isArray(result)){setRows(result);setMessage('Current institution identities. Unresolved matches remain quarantined.');}
      else{setPending(null);setMessage('Identity decision saved. Refresh identities before selecting a link for import.');}
    }catch(error){if(current===generation.current)setMessage(error instanceof Error?error.message:'Outcome unknown. Retry the same request.');}
    finally{if(current===generation.current)setBusy(false);}
  }
  const locked=busy||disabled||pending!==null;
  return <details className="intake-panel" data-testid="institution-identities">
    <summary>Institution identities and unresolved matches</summary>
    <p>Each institution’s patient reference is qualified by its organization and system. New matches are quarantined until explicitly linked after review. These fictional decisions do not verify real identity.</p>
    <button type="button" disabled={busy||disabled} onClick={()=>void run()}>Refresh identities</button>
    <p role="status" data-testid="institution-status">{message}</p>
    {pending&&<div><button type="button" disabled={busy||disabled} onClick={()=>void run(pending)}>Retry exact identity request</button>
      <button type="button" disabled={busy||disabled} onClick={()=>{setPending(null);setMessage('Request recovery dismissed. Refresh identities before submitting another decision.');}}>Dismiss request recovery</button></div>}
    {rows&&<><label>Institution for the next laboratory import
      <select data-testid="institution-select" value={selected} disabled={locked} onChange={event=>{
        const id=event.target.value;setSelected(id);onSelect(id||null);}}>
        <option value="">Original case institution</option>
        {rows.filter(row=>row.status==='active'&&!row.primary_identity).map(row=><option key={row.identity_id} value={row.identity_id}>
          {row.source_organization} · {row.source_system} · {row.source_subject_ref}</option>)}
      </select></label>
      <label>Fictional linkage review reference<input data-testid="institution-review" maxLength={128} value={review} disabled={locked}
        onChange={event=>setReview(event.target.value)}/></label>
      <ul>{rows.map(row=><li key={row.identity_id} data-identity={row.identity_id}>
        <strong>{row.source_organization}</strong> · {row.source_system} · {row.source_subject_ref} — {row.status}
        {row.status==='quarantined'&&<div className="actions">{(['link','reject'] as const).map(decision=><button key={decision} type="button"
          disabled={locked||review.length<3} onClick={()=>void run({identityId:row.identity_id,
            body:JSON.stringify({synthetic:true,decision,review_ref:review})})}>
          {decision==='link'?'Link to this case':'Reject match'}</button>)}</div>}
      </li>)}</ul></>}
    <form onSubmit={event=>{event.preventDefault();void run({body:JSON.stringify({synthetic:true,
      request_key:crypto.randomUUID(),source_organization:org,source_system:system,source_subject_ref:subject})});}}>
      <label>Source organization<input data-testid="institution-org" value={org} minLength={3} maxLength={128} required disabled={locked} onChange={e=>setOrg(e.target.value)}/></label>
      <label>Source system<input data-testid="institution-system" value={system} minLength={3} maxLength={128} required disabled={locked} onChange={e=>setSystem(e.target.value)}/></label>
      <label>Institution patient reference<input data-testid="institution-subject" value={subject} minLength={3} maxLength={128} required disabled={locked} onChange={e=>setSubject(e.target.value)}/></label>
      <button disabled={locked} data-testid="institution-propose">Add identity for review</button>
    </form>
    <p className="small">Linking does not merge or rewrite originals. A disputed active linkage requires withdrawing the case mapping through the existing access workflow; institutional links cannot be silently reassigned.</p>
  </details>;
}
