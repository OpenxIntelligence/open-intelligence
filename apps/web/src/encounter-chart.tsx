import {useEffect, useLayoutEffect, useRef, useState} from 'react';
import {encounterKinds, noteKinds, EncounterHttpError, EncounterInputError} from './encounter-client';
import type {DraftNoteCommand, Encounter, EncounterKind, NoteHeader, NoteKind, NoteVersion,
  ScheduleCommand, TransitionCommand} from './encounter-client';
import type {RegistrySession} from './registry-client';
import {matchingVisits} from './visit-filter';
import type {StatusFilter} from './visit-filter';
import type {RefObject} from 'react';
import './encounter-chart.css';

type Intent =
  | {type:'schedule'; body:ScheduleCommand}
  | {type:'transition'; visit:number; body:TransitionCommand}
  | {type:'note'; visit:number; key:string; body:DraftNoteCommand; changed:readonly (keyof Fields)[]};

export function createEncounterScope(session:RegistrySession, patientId:string) {
  return {key:crypto.randomUUID(), client:session.encounterChart(patientId), pending:null as Intent|null};
}

type Scope = ReturnType<typeof createEncounterScope>;
type Page<T> = {items:readonly T[]; next:number|null};
type History = Page<NoteVersion> & {key:string};
type Fields = {kind:NoteKind|''; facility:string; department:string; body:string};
type Draft = Fields & {key:string; base:number; original:Readonly<Fields>; recoveredChanges?:readonly (keyof Fields)[]};
const blank:Readonly<Fields> = Object.freeze({kind:'',facility:'',department:'',body:''});
const emptyDraft = ():Draft => ({key:'',base:0,...blank,original:blank});
const fieldsOf = (v:NoteVersion):Readonly<Fields> => Object.freeze({kind:v.note_kind??'',
  facility:v.facility_id??'',department:v.department_id??'',body:v.body});
const fieldNames = ['kind','facility','department','body'] as const;
const changedFields = (d:Draft) => fieldNames.filter(k=>d[k]!==d.original[k]||d.recoveredChanges?.includes(k));
const label = (value:string) => value.replaceAll('_',' ').replace(/^./, c=>c.toUpperCase());
const keyPattern = String.raw`[A-Z][A-Z0-9\-]{1,39}`;
const attributionPattern = String.raw`[A-Za-z0-9_.:\-]{8,100}`;
const isDraft = (version:NoteVersion) => version.status==='draft'||version.status==='draft_correction';

export function EncounterChart({scope,dirtyRef,onRecords}:{scope:Scope;dirtyRef:RefObject<boolean>;onRecords:(visitId:number)=>void}) {
  const [query,setQuery]=useState(''),[status,setStatus]=useState<StatusFilter>('all');
  const selectedHeading=useRef<HTMLHeadingElement>(null),editorHeading=useRef<HTMLHeadingElement>(null);
  const scheduleHeading=useRef<HTMLHeadingElement>(null);
  const [scheduling,setScheduling]=useState(false);
  const [cancelConfirm,setCancelConfirm]=useState(false);
  const [visits,setVisits] = useState<Page<Encounter>|null>(null);
  const [visit,setVisit] = useState<Encounter|null>(null);
  const [notes,setNotes] = useState<Page<NoteHeader>|null>(null);
  const [history,setHistory] = useState<History|null>(null);
  const [draft,setDraft] = useState<Draft|null>(null);
  const [recoverDraft,setRecoverDraft] = useState<Extract<Intent,{type:'note'}>|null>(null);
  const [conflict,setConflict] = useState<Intent['type']|null>(null);
  const [visitKey,setVisitKey] = useState(''), [kind,setKind] = useState<EncounterKind>('outpatient');
  const [date,setDate] = useState('');
  const [message,setMessage] = useState(scope.pending?'An earlier command has no confirmed receipt here. Check visit access to recover it.':'');
  const [busy,setBusy] = useState(false);
  const locked = useRef(false), generation = useRef(0);
  const client = scope.client;
  const filtered=visits?matchingVisits(visits.items,query,status):[];
  const dirty=!!recoverDraft || !!draft&&(draft.key!==''&&draft.base===0||changedFields(draft).length>0)
    || scheduling&&(visitKey!==''||date!==''||kind!=='outpatient');
  useLayoutEffect(()=>{dirtyRef.current=dirty&&!scope.pending;return()=>{dirtyRef.current=false;}});
  useEffect(()=>{
    if(!dirty)return;
    const warn=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue='';};
    window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);
  },[dirty]);
  useLayoutEffect(()=>{if(visit)selectedHeading.current?.focus();},[visit?.id]);
  useLayoutEffect(()=>{if(draft)editorHeading.current?.focus();},[!!draft]);
  useLayoutEffect(()=>{if(scheduling)scheduleHeading.current?.focus();},[scheduling]);
  // Selection internals live only in this Records view. The outer, patient-scoped
  // handle retains exactly one unconfirmed command when the view unmounts.
  useLayoutEffect(()=>()=>{generation.current++;},[scope]);
  const blocked = busy||scope.pending!==null;
  const latest = history?.next===null ? history.items.at(-1) : undefined;

  function clearSelection() {
    setVisit(null); setNotes(null); setHistory(null); setDraft(null); setConflict(null); setRecoverDraft(null); setCancelConfirm(false);
  }
  function clearChart() {
    scope.pending=null; clearSelection(); setVisits(null); setVisitKey(''); setDate(''); setKind('outpatient'); setScheduling(false);setQuery('');setStatus('all');
  }

  // Serialize actions (including rapid duplicate clicks). A late response from
  // an old Records view cannot reopen it, unlock a new request or edit a draft.
  async function request<T>(send:()=>Promise<T>, accept:(value:T)=>void,
    reject:(status:number)=>void = ()=>setMessage('Could not verify this read. Try checking it again.')) {
    if(locked.current)return;
    const turn=++generation.current;
    locked.current=true; setBusy(true);
    try {
      const response=await send();
      if(turn!==generation.current)return;
      locked.current=false; setBusy(false); accept(response);
    } catch(error) {
      if(turn!==generation.current)return;
      locked.current=false; setBusy(false);
      const status=error instanceof EncounterHttpError?error.status:error instanceof EncounterInputError?422:0;
      if(status===401||status===403||status===404){
        clearChart(); setMessage('Access is unavailable. Visit and note details have been cleared.');
      }else reject(status);
    }
  }

  function readVisits(after=0, receipt='') {
    if(draft||locked.current)return;
    setMessage(receipt||'Checking visit access…');
    void request(()=>client.visits(after),page=>{
      setVisits(previous=>({items:[...(after?previous?.items??[]:[]),...page.encounters],next:page.next_after_id}));
      if(!after) {clearSelection(); setConflict(null);}
      setMessage(receipt||(scope.pending?'Visit access checked. Retry the earlier request to recover its receipt.':'Visits checked.'));
    },()=>{setVisits(null); clearSelection(); setMessage((receipt?receipt+' ':'')+'Could not verify the visit list. Check visits again.');});
  }
  function openVisit(row:Encounter) {
    if(blocked||draft)return;
    clearSelection(); setVisit(row); setMessage('');
  }
  function readNotes(id:number, after=0, receipt='') {
    if(locked.current)return;
    setMessage(receipt||'Checking note access…');
    void request(()=>client.notes(id,after),page=>{
      setNotes(previous=>({items:[...(after?previous?.items??[]:[]),...page.notes],next:page.next_after_id}));
      if(!after)setHistory(null);
      setMessage(receipt||'Notes checked.');
    },()=>{setNotes(null); setHistory(null); setMessage((receipt?receipt+' ':'')+'Could not verify the note list. Check notes again.');});
  }
  function readHistory(key:string, after=0) {
    if(!visit||blocked)return;
    setMessage('Checking note history…');
    void request(()=>client.versions(visit.id,key,after),page=>{
      setHistory(previous=>({key,items:[...(after&&previous?.key===key?previous.items:[]),...page.versions],next:page.next_after_version}));
      setMessage('Note history checked.');
    },()=>{setHistory(null); setMessage('Could not verify this history. Check the note history again.');});
  }

  function write(intent:Intent) {
    if(locked.current||(scope.pending!==null&&scope.pending!==intent))return;
    // Record the exact command before sending. Opening Records again, or a
    // lost/invalid response, can only replay this same path, key and body.
    scope.pending=intent;
    setMessage('Checking permission and saving…');
    const fail=(status:number)=>{
      if(status===409||status===422) {
        scope.pending=null;
        setConflict(status===409?intent.type:null);
        if(intent.type==='note'){
          if(!draft)setRecoverDraft(intent);
          else if(!draft.key)setDraft({...draft,key:intent.key});
        }
        if(intent.type==='schedule'){setScheduling(true);setVisitKey(intent.body.external_key);setKind(intent.body.kind);setDate(intent.body.service_date);}
        setMessage(status===409?'The command conflicts with the saved record.':
          'The server rejected these values. Check the form and try again.');
      }else{
        setMessage('The outcome is unknown. Retry the exact request to check whether it was saved.');
      }
    };
    if(intent.type==='note'){
      void request(()=>client.saveNote(intent.visit,intent.key,intent.body),result=>{
        scope.pending=null; setConflict(null); setDraft(null); setHistory(null);
        const receipt='Saved '+result.note_key+' · version '+result.version+'.';
        if(visit?.id===intent.visit&&notes)readNotes(intent.visit,0,receipt);
        else setMessage(receipt);
      },fail);
    }else{
      void request(()=>intent.type==='schedule'?client.schedule(intent.body):client.transition(intent.visit,intent.body),result=>{
        scope.pending=null; setConflict(null);
        const receipt='Visit '+label(result.status).toLowerCase()+' · revision '+result.revision+'.';
        if(intent.type==='transition'&&visit?.id===result.encounter_id){
          // A replay can return an earlier receipt. Re-read the row instead of
          // presenting the receipt's revision as the current encounter state.
          refreshVisit(result.encounter_id,receipt);
        }else{
          setScheduling(false);setVisitKey(''); setDate('');setKind('outpatient');setQuery('');setStatus('all'); readVisits(0,receipt);
        }
      },fail);
    }
  }
  function refreshVisit(id:number, receipt='') {
    setMessage(receipt||'Checking the current visit…');
    void request(()=>client.visits(id-1),page=>{
      const row=page.encounters.find(item=>item.id===id);
      if(!row){clearChart(); setMessage('This visit is no longer available. Check visit access again.');return;}
      setVisits(previous=>previous&&({...previous,items:previous.items.map(old=>old.id===id?row:old)}));
      setVisit(row); setConflict(null); setMessage(receipt||'Current visit checked.');
    },()=>{clearSelection();setVisits(null);setMessage((receipt?receipt+' ':'')+'Could not verify the current visit. Check visits again.');});
  }
  function reopenDraft(intent:Extract<Intent,{type:'note'}>) {
    // This retry returned a definite rejection after navigation. Recover the
    // editor only after checking current visit and note access for its path.
    setMessage('Checking this visit and note before reopening the draft…');
    void request(async()=>{
      const page=await client.visits(intent.visit-1);
      const row=page.encounters.find(item=>item.id===intent.visit);
      if(!row)throw new EncounterHttpError(404);
      return {row,page:await client.versions(row.id,intent.key)};
    },result=>{
      setVisit(result.row);setNotes(null);setRecoverDraft(null);
      setHistory({key:intent.key,items:result.page.versions,next:result.page.next_after_version});
      const c=intent.body;
      const fields:Readonly<Fields>=Object.freeze({kind:c.note_kind??'',facility:c.facility_id??'',department:c.department_id??'',body:c.body});
      setDraft({key:intent.key,base:c.expected_version,...fields,original:fields,recoveredChanges:intent.changed});
      setMessage('Your earlier unsaved text is available to review.');
    });
  }
  function transition(target:TransitionCommand['target']) {
    if(!visit||blocked||draft||conflict)return;
    write({type:'transition',visit:visit.id,body:Object.freeze({synthetic:true,request_key:crypto.randomUUID(),target,expected_revision:visit.revision})});
  }
  function editLatest() {
    if(blocked||draft||!history||!latest||!isDraft(latest))return;
    const original=fieldsOf(latest);
    setDraft({key:history.key,base:latest.version,...original,original});
    setConflict(null); setMessage('');
  }
  function changeDraft(patch:Partial<Fields & {key:string}>) {
    if(!blocked)setDraft(previous=>previous&&({...previous,...patch}));
  }
  function rebaseDraft() {
    if(!draft||blocked||history?.key!==draft.key||!latest||!isDraft(latest)||latest.version<=draft.base)return;
    const original=fieldsOf(latest),changed=changedFields(draft);
    // Carry forward concurrent edits to untouched fields, including source
    // attribution. Only an explicit choice advances the editor's base version.
    setDraft({key:draft.key,base:latest.version,original,
      kind:changed.includes('kind')?draft.kind:original.kind,
      facility:changed.includes('facility')?draft.facility:original.facility,
      department:changed.includes('department')?draft.department:original.department,
      body:changed.includes('body')?draft.body:original.body});
    setConflict(null);setMessage('Your edits were retained. Other fields now match version '+latest.version+'. Review before saving.');
  }
  function saveDraft() {
    if(!visit||!draft||!writableVisit||blocked||conflict||!draft.body.length)return;
    write({type:'note',visit:visit.id,key:draft.key||'NOTE-'+crypto.randomUUID().replaceAll('-','').toUpperCase(),changed:changedFields(draft),body:Object.freeze({synthetic:true,request_key:crypto.randomUUID(),
      expected_version:draft.base,body:draft.body,note_kind:draft.kind||null,
      facility_id:draft.facility||null,department_id:draft.department||null})});
  }
  const writableVisit=visit?.status==='in_progress'||visit?.status==='completed';
  return <section className="panel encounter-chart" data-testid="encounter-chart" aria-labelledby="encounter-heading">
    <h2 id="encounter-heading">Visit history</h2>
    <p>Check this fictional patient’s visits, then open a visit to see its notes. Each read and change requires its own permission.</p>
    <button type="button" data-testid="encounter-load" disabled={busy||!!draft||(!!scope.pending&&!!visits)} onClick={()=>readVisits()}>
      {visits?'Refresh visits':'Check visits'}</button>
    <p className="status" data-testid="encounter-status" role="status" aria-live="polite">{message}</p>
    {visits&&scope.pending&&<button type="button" data-testid="encounter-retry" disabled={busy} onClick={()=>{if(scope.pending)write(scope.pending);}}>Retry exact request</button>}
    {visits&&recoverDraft&&<button type="button" disabled={blocked} onClick={()=>reopenDraft(recoverDraft)}>Reopen unsaved draft</button>}
    {visits&&<>
      {!scheduling&&<button data-testid="encounter-schedule-open" className="primary" disabled={blocked||!!draft} onClick={()=>{setScheduling(true);clearSelection();}}>Schedule a visit</button>}
      {visits.items.length>0&&<div className="visit-filters">
        <label>Find a visit<input type="search" data-testid="visit-search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Date, visit type or reference"/></label>
        <label>Status<select data-testid="visit-status-filter" value={status} onChange={e=>setStatus(e.target.value as StatusFilter)}>
          <option value="all">All statuses</option>{(['scheduled','in_progress','completed','cancelled'] as const).map(s=><option key={s} value={s}>{label(s)}</option>)}</select></label>
        <span role="status">{filtered.length} of {visits.items.length} loaded visits</span>
      </div>}
      {query||status!=='all'?<button onClick={()=>{setQuery('');setStatus('all');}}>Clear filters</button>:null}
      {visits.items.length>0&&!filtered.length&&<p>No loaded visits match these filters.</p>}
      {visits.items.length===0?<p>No visits returned for this patient.</p>:<ul className="case-list" aria-label="Visits">
        {filtered.map(row=><li key={row.id} className="encounter-row" data-testid="encounter-row">
          <div><strong>{label(row.kind)} · {row.service_date}</strong><span className="record-state">{label(row.status)}</span><br/><code>{row.external_key}</code></div>
          <button type="button" data-testid="encounter-open" aria-label={'Open visit '+row.external_key} disabled={blocked||!!draft||scheduling} onClick={()=>openVisit(row)}>Open visit</button>
        </li>)}</ul>}
      {visits.next!==null&&<button type="button" data-testid="encounter-visits-more" disabled={blocked||!!draft} onClick={()=>readVisits(visits.next!)}>Show more visits</button>}
      {visit&&<section className="encounter-detail" aria-labelledby="selected-visit-heading" data-testid="encounter-selected">
        <h3 tabIndex={-1} ref={selectedHeading} id="selected-visit-heading">{label(visit.kind)} visit · {visit.service_date}</h3>
        <button type="button" data-testid="visit-inspect-records" disabled={blocked||!!draft} onClick={()=>onRecords(visit.id)}>Inspect linked records</button>
        <p><code>{visit.external_key}</code> · {label(visit.status)} · Revision {visit.revision}</p>
        <div className="actions">
          {visit.status==='scheduled'&&<button type="button" data-testid="encounter-start" disabled={blocked||!!draft||!!conflict} onClick={()=>transition('in_progress')}>Start visit</button>}
          {visit.status==='in_progress'&&<button type="button" data-testid="encounter-complete" disabled={blocked||!!draft||!!conflict} onClick={()=>transition('completed')}>Complete visit</button>}
          {(visit.status==='scheduled'||visit.status==='in_progress')&&<button type="button" data-testid="encounter-cancel" disabled={blocked||!!draft||!!conflict} onClick={()=>setCancelConfirm(true)}>Cancel visit</button>}
        </div>
        {cancelConfirm&&<div className="encounter-conflict" role="group" aria-label="Confirm visit cancellation"><p>Cancel this visit? A cancelled visit cannot be reopened.</p>
          <div className="actions"><button type="button" onClick={()=>setCancelConfirm(false)}>Keep visit</button>
          <button type="button" disabled={blocked||!!draft||!!conflict} onClick={()=>{setCancelConfirm(false);transition('cancelled');}}>Confirm cancellation</button></div></div>}
        {conflict==='transition'&&<div className="encounter-conflict" role="alert" data-testid="encounter-conflict"><p>The visit may have changed. Check its current status before making another change.</p>
          <button type="button" disabled={blocked} onClick={()=>refreshVisit(visit.id)}>Check current visit</button></div>}
        <h5>Notes for this visit</h5>
        <div className="actions">
          <button type="button" data-testid="encounter-notes-load" disabled={blocked||!!draft} onClick={()=>readNotes(visit.id)}>{notes?'Refresh notes':'Check notes'}</button>
          {writableVisit&&!draft&&<button type="button" data-testid="encounter-note-new" disabled={blocked||!!conflict} onClick={()=>{setDraft(emptyDraft());setHistory(null);setMessage('');}}>New draft note</button>}
        </div>
        {notes&&(notes.items.length===0?<p>No saved notes returned for this visit.</p>:<ul className="case-list" aria-label="Notes">
          {notes.items.map(row=><li key={row.id} className="encounter-row" data-testid="encounter-note-row">
            <div><strong>{row.note_key}</strong> · Version {row.latest_version}</div>
            <button type="button" data-testid="encounter-history-open" disabled={blocked||!!draft} onClick={()=>readHistory(row.note_key)}>Read note history</button>
          </li>)}</ul>)}
        {notes&&notes.next!==null&&<button type="button" data-testid="encounter-notes-more" disabled={blocked||!!draft} onClick={()=>readNotes(visit.id,notes.next!)}>Show more notes</button>}
        {history&&<section aria-label="Saved note history">
          <h5>Saved versions · {history.key}</h5>
          {!history.items.length&&<p>No saved versions were returned.</p>}
          <ol className="case-list">{history.items.map(version=><li key={version.id} className="encounter-version" data-testid="encounter-version-row">
            <strong>Version {version.version}{version.version===1?' · Original':''}</strong> <span className="record-state">{label(version.status)}</span>
            <div>{version.note_kind?label(version.note_kind):'Note type not recorded'} · {version.created_at}</div>
            <div>Author: <code>{version.authored_by}</code> · Facility: {version.facility_id??'Not recorded'} · Department: {version.department_id??'Not recorded'}</div>
            <pre>{version.body}</pre>
          </li>)}</ol>
          {history.next!==null&&<button type="button" data-testid="encounter-history-more" disabled={blocked} onClick={()=>readHistory(history.key,history.next!)}>Show more versions</button>}
          {writableVisit&&!draft&&latest&&isDraft(latest)&&<button type="button" data-testid="encounter-note-edit" disabled={blocked} onClick={editLatest}>Edit version {latest.version}</button>}
        </section>}
        {draft&&<form className="encounter-form" onSubmit={event=>{event.preventDefault();saveDraft();}}>
          <h5 tabIndex={-1} ref={editorHeading}>{draft.base?'Edit draft · version '+draft.base:'New draft note'}</h5>
          <p>Use independently fictional text only. Saving adds a draft version and preserves earlier versions.</p>
          <fieldset disabled={blocked}>
            <legend className="encounter-legend">Note details</legend>
            <div className="encounter-fields">
              <label>Note reference<input placeholder="Generated when saved" data-testid="encounter-note-key" value={draft.key} readOnly={draft.base!==0||conflict==='note'} pattern={keyPattern} title="2–40 uppercase letters, digits or hyphens; start with a letter" maxLength={40} onChange={e=>changeDraft({key:e.target.value})}/></label>
              <label>Note type<select data-testid="encounter-note-kind" value={draft.kind} onChange={e=>changeDraft({kind:e.target.value as NoteKind|''})}><option value="">Unspecified</option>{noteKinds.map(k=><option key={k} value={k}>{label(k)}</option>)}</select></label>
              <label>Facility ID (optional)<input data-testid="encounter-note-facility" value={draft.facility} pattern={attributionPattern} title="8–100 letters, digits, periods, colons, hyphens or underscores" maxLength={100} onChange={e=>changeDraft({facility:e.target.value})}/></label>
              <label>Department ID (optional)<input data-testid="encounter-note-department" value={draft.department} pattern={attributionPattern} title="8–100 letters, digits, periods, colons, hyphens or underscores" maxLength={100} onChange={e=>changeDraft({department:e.target.value})}/></label>
            </div>
            <label>Fictional note text<textarea data-testid="encounter-note-body" value={draft.body} required maxLength={20000} rows={5} onChange={e=>changeDraft({body:e.target.value})}/></label>
            {draft.base>0&&<p className="small">Omitted attribution carries forward from the preceding version.</p>}
            <div className="actions"><button className="primary" data-testid="encounter-note-save" disabled={!!conflict||!writableVisit||!draft.body.length}>Save draft version</button>
              <button type="button" onClick={()=>{setDraft(null);setConflict(null);setMessage('Unsaved changes discarded.');}}>Discard changes</button></div>
          </fieldset>
          {conflict==='note'&&<div className="encounter-conflict" role="alert" data-testid="encounter-conflict">
            <p>The saved note or visit changed. Your text is still here. Compare it with the saved history before starting another version.</p>
            <button type="button" data-testid="encounter-conflict-refresh" disabled={blocked} onClick={()=>readHistory(draft.key)}>Check latest saved versions</button>
            {history?.key===draft.key&&latest&&isDraft(latest)&&latest.version>draft.base&&<button type="button" data-testid="encounter-conflict-rebase" disabled={blocked} onClick={rebaseDraft}>Keep my edits and use version {latest.version} for unchanged fields</button>}
          </div>}
        </form>}
      </section>}
      {scheduling&&<form className="encounter-form" onSubmit={event=>{
        event.preventDefault();if(blocked||draft)return;
        write({type:'schedule',body:Object.freeze({synthetic:true,request_key:crypto.randomUUID(),external_key:visitKey||'VISIT-'+crypto.randomUUID().replaceAll('-','').toUpperCase(),kind,service_date:date})});
      }}>
        <h3 tabIndex={-1} ref={scheduleHeading}>Schedule a fictional visit</h3>
        <fieldset disabled={blocked||!!draft}>
          <legend className="encounter-legend">Visit details</legend>
          <div className="encounter-fields">
            <label>Visit reference (optional)<input placeholder="Generated when saved" data-testid="encounter-schedule-key" value={visitKey} pattern={keyPattern} title="2–40 uppercase letters, digits or hyphens; start with a letter" maxLength={40} onChange={e=>{setVisitKey(e.target.value);if(conflict==='schedule')setConflict(null);}}/></label>
            <label>Visit type<select data-testid="encounter-schedule-kind" value={kind} onChange={e=>setKind(e.target.value as EncounterKind)}>{encounterKinds.map(k=><option key={k} value={k}>{label(k)}</option>)}</select></label>
            <label>Visit date<input data-testid="encounter-schedule-date" type="date" required value={date} onChange={e=>setDate(e.target.value)}/></label>
          </div>
          <button type="submit" data-testid="encounter-schedule" disabled={conflict==='schedule'}>Schedule visit</button>
          <button type="button" onClick={()=>{setScheduling(false);setVisitKey('');setDate('');setKind('outpatient');setConflict(null);}}>Discard form</button>
        </fieldset>
        {conflict==='schedule'&&<p data-testid="encounter-conflict" role="alert">This visit key may already exist. Refresh visits or use another key.</p>}
      </form>}
    </>}
  </section>;
}
