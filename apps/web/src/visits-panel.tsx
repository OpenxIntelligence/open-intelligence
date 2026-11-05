import {useEffect,useLayoutEffect,useMemo,useRef,useState} from 'react';
import type {RefObject} from 'react';
import type {Patient,RegistrySession} from './registry-client';
import {noteKinds,visitKinds,VisitHttpError} from './visits';
import type {Note,NoteKind,Page,Target,Version,Visit,VisitCommand,VisitKind,VisitStatus} from './visits';
import './visits.css';

type ListScreen={type:'list'; page:Page<Visit>; cursors:number[]};
type Detail={type:'detail'; visit:Visit; notes:Page<Note>|null; cursors:number[]};
type Reader={type:'reader'; visit:Visit; note:Note; version:Version};
type Screen=ListScreen|Detail|Reader;
type Form=
  |{type:'schedule'; kind:VisitKind; date:string; externalKey:string}
  |{type:'move'; target:Target}
  |{type:'note'; noteKey:string; kind:NoteKind|null; body:string; expected:number};
type Props={session:RegistrySession;patient:Patient;leaveGuard:RefObject<(()=>boolean)|null>};
const statuses:Record<VisitStatus,string>={scheduled:'Scheduled',in_progress:'In progress',completed:'Completed',cancelled:'Cancelled'};
const actions:Record<Target,string>={in_progress:'Start visit',completed:'Complete visit',cancelled:'Cancel visit'};
const targets:Record<VisitStatus,Target[]>={scheduled:['in_progress','cancelled'],in_progress:['completed','cancelled'],completed:[],cancelled:[]};
const readable=(value:string)=>value.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
const keyFor=(prefix:string)=>prefix+'-'+crypto.randomUUID().replaceAll('-','').toUpperCase();
const visitDate=(day:string)=>new Date(day+'T12:00:00Z').toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric',timeZone:'UTC'});
const canDraft=(v:Visit)=>v.status==='in_progress'||v.status==='completed';
const editable=(v:Version)=>v.status==='draft'||v.status==='draft_correction';
function Pager({cursors,next,onPage}:{cursors:number[];next:number|null;onPage:(p:number[])=>void}){
  if(cursors.length===1&&next===null)return null;
  return <div className="visit-pager" aria-label="List pages">
    <button disabled={cursors.length===1} onClick={()=>onPage(cursors.slice(0,-1))}>Previous page</button>
    <span>Page {cursors.length}</span><button disabled={next===null} onClick={()=>next!==null&&onPage([...cursors,next])}>Next page</button>
  </div>;
}

export function VisitsPanel({session,patient,leaveGuard}:Props){
  const client=useMemo(()=>session.visitClient(patient),[session,patient]);
  const [screen,setScreen]=useState<Screen|null>(null),[form,setForm]=useState<Form|null>(null);
  const [notice,setNotice]=useState(''),[fault,setFault]=useState(''),[busy,setBusy]=useState(false);
  const [pending,setPending]=useState<VisitCommand|null>(null),[conflict,setConflict]=useState(false);
  const serial=useRef(0),working=useRef(false),moveFocus=useRef(false),sectionTitle=useRef<HTMLHeadingElement>(null);
  const inputRef=useRef<HTMLHeadingElement>(null);
  const current=(id:number)=>serial.current===id && session.snapshot().patient===patient;
  function clearForm(){setForm(null);setPending(null);setConflict(false);}
  function clearRead(message:string){clearForm();setScreen(null);setFault(message);setNotice('');}
  function start(){
    working.current=true;setBusy(true);setFault('');return ++serial.current;
  }
  function finish(id:number){if(current(id)){working.current=false;setBusy(false);}}
  function guard(){
    if(working.current&&form)return false;
    return !form||window.confirm(pending?'Leave and check the saved record before trying again?':'Discard the changes in this form?');
  }
  useLayoutEffect(()=>{leaveGuard.current=guard;return()=>{leaveGuard.current=null};});
  useEffect(()=>{
    if(!form)return;
    const warn=(e:BeforeUnloadEvent)=>{e.preventDefault();e.returnValue='';};
    window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);
  },[form]);
  useLayoutEffect(()=>{
    if(!busy&&moveFocus.current){(form?inputRef.current:sectionTitle.current)?.focus();moveFocus.current=false;}
  },[busy,form,screen]);
  async function read(load:()=>Promise<Screen>,message='',focus=true){
    const id=start();setScreen(null);clearForm();setNotice('');
    try{const result=await load();if(current(id)){setScreen(result);setNotice(message);moveFocus.current=focus;}}
    catch(e){if(current(id))clearRead(e instanceof VisitHttpError&&[401,403,404].includes(e.status)
      ?'Access to this visit record is unavailable. Check your access or return to the visit list.'
      :(message?message+' ':'')+'Could not verify this visit record. Try loading the visit list again.');}
    finally{finish(id);}
  }
  function list(cursors=[0],message='',focus=true){
    return read(async()=>({type:'list',page:await client.list(cursors[cursors.length-1]),cursors}),message,focus);
  }
  async function visitAt(id:number){
    const [visit]=(await client.list(id-1)).items;
    if(visit?.id!==id)throw Error('Visit changed');
    return visit;
  }
  function detail(id:number,cursors=[0],message=''){
    return read(async()=>{
      const visit=await visitAt(id);
      let notes:Page<Note>|null=null;
      try{notes=await client.notes(id,cursors[cursors.length-1]);}
      catch(e){if(!(e instanceof VisitHttpError&&[403,404].includes(e.status)))throw e;}
      return {type:'detail',visit,notes,cursors};
    },message);
  }
  async function readVersion(visitId:number,noteId:number,noteKey:string,number?:number):Promise<Reader>{
    const visit=await visitAt(visitId);
    const [note]=(await client.notes(visitId,noteId-1)).items;
    if(note?.id!==noteId||note.note_key!==noteKey)throw Error('Note changed');
    const version=await client.version(visitId,noteKey,number??note.latest_version);
    return {type:'reader',visit,note,version};
  }
  function reader(visitId:number,note:Note,number?:number){
    return read(()=>readVersion(visitId,note.id,note.note_key,number));
  }
  useEffect(()=>{
    void list([0],'',false);
    return ()=>{serial.current++;working.current=false;};
    // The active patient object identifies this authorization context.
  },[client]);
  function openForm(next:Form){
    setFault('');setNotice('');moveFocus.current=true;setForm(next);
  }
  async function save(c:VisitCommand){
    if(working.current)return;
    const id=start();setPending(c);
    try{
      const resultId=await client.submit(c);
      if(!current(id))return;
      if(c.type==='save'){
        await read(()=>readVersion(c.visitId,resultId,c.noteKey,c.expected+1),'Draft version '+(c.expected+1)+' saved.');
      }else{
        await detail(resultId,[0],c.type==='schedule'?'Visit scheduled.':'Visit status updated.');
      }
    }catch(e){
      if(!current(id))return;
      if(e instanceof VisitHttpError && [401,403,404].includes(e.status)){clearRead('Access is unavailable. Recheck the visit list.');}
      else if(e instanceof VisitHttpError&&e.status===409){
        setPending(null);setConflict(true);
        setFault('The saved record conflicts with this change. Review the current record before saving.');
      }else if(e instanceof VisitHttpError&&[400,413,422].includes(e.status)){
        setPending(null);setFault('The API rejected these values. Check the form and try again.');
      }else{
        setFault('The save outcome is unknown. Retry the exact request to recover its receipt.');
      }
    }finally{finish(id);}
  }
  async function reviewConflict(){
    if(!screen||!form||working.current)return;
    if(form.type!=='note'||screen.type!=='reader'){void list();return;}
    const id=start();
    try{
      const latest=await readVersion(screen.visit.id,screen.note.id,screen.note.note_key);
      if(!current(id))return;
      if(!canDraft(latest.visit)||!editable(latest.version)||latest.version.hasNewer){
        clearForm();setScreen(latest);setNotice('The current version is available for reading.');return;
      }
      setScreen(latest);setForm({...form,expected:latest.version.version});setConflict(false);
      setNotice('Your unsaved text is below. Compare it with the saved version above before saving another version.');
    }catch{if(current(id))clearRead('The current note could not be verified. Recheck your access to the visit list.');}
    finally{finish(id);}
  }
  function submit(){
    if(!form||!screen||working.current||conflict)return;
    if(pending){void save(pending);return;}
    const requestKey=crypto.randomUUID();
    if(form.type==='schedule')void save({type:'schedule',externalKey:form.externalKey,date:form.date,kind:form.kind,requestKey});
    else if(form.type==='move'&&screen.type==='detail')void save({type:'move',visitId:screen.visit.id,target:form.target,expected:screen.visit.revision,requestKey});
    else if(form.type==='note'&&screen.type!=='list')void save({type:'save',visitId:screen.visit.id,noteKey:form.noteKey,
      expected:form.expected,kind:form.kind,body:form.body,requestKey});
  }
  const visit=screen&&screen.type!=='list'?screen.visit:null;
  const title=!visit?'Visit list':screen?.type==='reader'?'Note history':readable(visit.kind)+' visit';
  return <section className="panel visits" data-visit-id={visit?.id} aria-labelledby="visits-title">
    <div className="visit-bar">
      <div><h2 ref={sectionTitle} tabIndex={-1} id="visits-title">{title}</h2>
      {visit&&<div className="visit-subtitle"><time dateTime={visit.service_date}>{visitDate(visit.service_date)}</time><span className={'visit-status '+visit.status}>{statuses[visit.status]}</span></div>}</div>
      {!form&&screen?.type==='list'&&<button className="primary" onClick={()=>openForm({type:'schedule',kind:'outpatient',date:'',externalKey:keyFor('VISIT')})}>Schedule a visit</button>}
      {!form&&visit&&<button onClick={()=>screen?.type==='reader'?void detail(visit.id):void list()}>{screen?.type==='reader'?'Back to visit':'Back to visit list'}</button>}
    </div>
    <p role="status" className="visit-feedback" aria-live="polite">{busy?(pending?'Saving…':'Loading…'):notice}</p>
    {fault&&<p role="alert" className="status error">{fault}</p>}
    {!busy&&!screen&&<button onClick={()=>void list()}>Reload visit list</button>}
    {screen?.type==='list'&&!form&&<>
      {!screen.page.items.length?<div className="visit-empty"><h3>No visits on this page</h3><p>{screen.cursors.length===1?'Schedule a fictional visit to start this patient’s visit history.':'Return to the previous page to see earlier entries.'}</p></div>:
      <ul className="visit-list">{screen.page.items.map(v=><li key={v.id}>
        <button className="visit-row" onClick={()=>void detail(v.id)}><span><strong>{readable(v.kind)} visit</strong><small>{visitDate(v.service_date)} · Visit {v.id}</small></span>
        <span className={'visit-status '+v.status}>{statuses[v.status]}</span></button></li>)}</ul>}
      <Pager cursors={screen.cursors} next={screen.page.next} onPage={p=>void list(p)}/>
      <button onClick={()=>void list(screen.cursors)}>Refresh visits</button>
    </>}
    {screen?.type==='detail'&&!form&&<>
      <dl className="visit-metadata"><div><dt>Visit reference</dt><dd>{screen.visit.external_key}</dd></div><div><dt>Record revision</dt><dd>{screen.visit.revision}</dd></div></dl>
      <div className="actions">{targets[screen.visit.status].map(target=><button key={target} onClick={()=>openForm({type:'move',target})}>{actions[target]}</button>)}</div>
      <div className="visit-notes"><div className="visit-bar"><h3>Visit notes</h3>
        {screen.notes&&canDraft(screen.visit)&&<button onClick={()=>openForm({type:'note',noteKey:keyFor('NOTE'),kind:'progress',body:'',expected:0})}>Write a draft note</button>}</div>
        {!screen.notes?<p>Note access is unavailable for this visit.</p>:<>
          {!screen.notes.items.length&&<p>No notes were returned on this page.</p>}
          {screen.visit.status==='scheduled'&&<p>Start the visit to write a draft note.</p>}
          <ul className="visit-list">{screen.notes.items.map(n=><li key={n.id}><button className="visit-row" onClick={()=>void reader(screen.visit.id,n)}>
            <span><strong>Visit note {n.id}</strong><small>{n.note_key}</small></span><span>Version {n.latest_version}</span></button></li>)}</ul>
          <Pager cursors={screen.cursors} next={screen.notes.next} onPage={p=>void detail(screen.visit.id,p)}/></>}
      </div>
    </>}
    {screen?.type==='reader'&&<article className="visit-original" aria-label="Saved note version">
      <div className="visit-bar"><h3>{screen.version.note_kind?readable(screen.version.note_kind)+' note':'Visit note'}</h3>
        <span className="visit-status">{readable(screen.version.status)} · Version {screen.version.version}</span></div>
      <p>Recorded by {screen.version.authored_by} · <time dateTime={screen.version.created_at}>{new Date(screen.version.created_at).toLocaleString()}</time></p>
      <div className="visit-body" dir="auto">{screen.version.body}</div>
      <details><summary>Version details</summary><dl className="visit-metadata"><div><dt>Note reference</dt><dd>{screen.note.note_key}</dd></div>
        <div><dt>Content SHA-256</dt><dd>{screen.version.sha256}</dd></div>
        {screen.version.facility_id&&<div><dt>Facility</dt><dd>{screen.version.facility_id}</dd></div>}
        {screen.version.department_id&&<div><dt>Department</dt><dd>{screen.version.department_id}</dd></div>}
        {screen.version.amendment_reason&&<div><dt>Amendment reason</dt><dd>{screen.version.amendment_reason}</dd></div>}</dl></details>
      {!form&&<div className="actions">
        {screen.version.version>1&&<button onClick={()=>void reader(screen.visit.id,screen.note,screen.version.version-1)}>Previous version</button>}
        {screen.version.hasNewer?<button onClick={()=>void reader(screen.visit.id,screen.note,screen.version.version+1)}>Next version</button>:
          canDraft(screen.visit)&&editable(screen.version)&&<button onClick={()=>openForm({type:'note',noteKey:screen.note.note_key,expected:screen.version.version,body:screen.version.body,kind:screen.version.note_kind})}>Revise draft</button>}
      </div>}
    </article>}
    {form&&<form className="visit-form" onSubmit={e=>{e.preventDefault();submit();}}>
      <h3 tabIndex={-1} ref={inputRef}>{form.type==='schedule'?'Schedule a visit':form.type==='move'?actions[form.target]:form.expected?'Revise draft note':'New draft note'}</h3>
      <fieldset disabled={busy||!!pending||conflict}>
        {form.type==='schedule'&&<><label htmlFor="visit-kind">Visit type</label><select id="visit-kind" value={form.kind} onChange={e=>setForm({...form,kind:e.target.value as VisitKind})}>{visitKinds.map(k=><option key={k} value={k}>{readable(k)}</option>)}</select>
          <label htmlFor="visit-date">Visit date</label><input id="visit-date" type="date" required value={form.date} onChange={e=>setForm({...form,date:e.target.value})}/></>}
        {form.type==='move'&&<p>Change this visit from <strong>{visit&&statuses[visit.status]}</strong> to <strong>{statuses[form.target]}</strong>?</p>}
        {form.type==='note'&&<><label htmlFor="visit-note-kind">Note type</label><select id="visit-note-kind" value={form.kind??''} onChange={e=>setForm({...form,kind:e.target.value as NoteKind})}>
          {form.kind===null&&<option value="">Unspecified</option>}{noteKinds.map(k=><option key={k} value={k}>{readable(k)}</option>)}</select>
          <label htmlFor="visit-note-body">Draft text</label><textarea id="visit-note-body" rows={7} required value={form.body} aria-describedby="draft-help" onChange={e=>setForm({...form,body:e.target.value})}/>
          <p id="draft-help">Use fictional information only. Saving creates a new version. {Array.from(form.body).length.toLocaleString()} / 20,000 characters.</p></>}
      </fieldset>
      <div className="actions">{conflict?<button type="button" disabled={busy} onClick={()=>void reviewConflict()}>{form.type==='note'&&screen?.type==='reader'?'Compare with current version':'Reload visit list'}</button>:
        <button className="primary" disabled={busy||form.type==='note'&&(!form.body.trim()||[...form.body].length>20000)}>{pending?'Retry exact request':form.type==='note'?'Save draft version':form.type==='move'?'Confirm status change':'Save scheduled visit'}</button>}
        <button type="button" disabled={busy} onClick={()=>{if(!guard())return;if(pending||conflict){void list();return;}clearForm();setFault('');moveFocus.current=true;}}>{pending?'Leave and check visit list':'Discard form'}</button></div>
    </form>}
  </section>;
}
