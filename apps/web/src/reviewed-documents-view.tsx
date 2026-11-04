import {useEffect,useMemo,useRef,useState,useSyncExternalStore} from 'react';
import {DocumentClient} from './reviewed-documents';
import type {Finding,Preview} from './reviewed-documents';
import type {RegistrySession} from './registry-client';

export function ReviewedDocumentWorkspace({session,patientId,caseId}:{session:RegistrySession;patientId:string;caseId:string}){
 const client=useMemo(()=>new DocumentClient((path,body)=>session.documentRequest(caseId,path,body)),[session,caseId,patientId]);
 const state=useSyncExternalStore(client.subscribe,client.snapshot);
 const [upload,setUpload]=useState<{synthetic:true;filename:string;original_base64:string}|null>(null);
 const [findings,setFindings]=useState<Finding[]>([]),[line,setLine]=useState(1),[quote,setQuote]=useState(''),[key,setKey]=useState('finding-one'),[classification,setClassification]=useState('not-assessed');
 const [documentId,setDocumentId]=useState(''),[kind,setKind]=useState('other'),[eventDate,setEventDate]=useState(''),[issuedDate,setIssuedDate]=useState(''),[amends,setAmends]=useState('');
 const [confirmed,setConfirmed]=useState(false),[reason,setReason]=useState(''),[localMessage,setLocalMessage]=useState(''),[downloading,setDownloading]=useState(false);
 const lifetime=useRef(0),fileGeneration=useRef(0),selected=useRef('');
 const fileInput=useRef<HTMLInputElement>(null);
 selected.current=state.document?state.document.source_id+state.document.sha256:'';
 useEffect(()=>{lifetime.current++;return()=>{lifetime.current++;fileGeneration.current++;client.dispose();}},[client]);
 useEffect(()=>{setFindings(state.document?.revisions.at(-1)?.findings??[]);setConfirmed(false);setReason('');setQuote('');setLine(1);},[state.preview,state.document]);
 const preview:Preview|null=state.preview??state.document?.preview??null;
 const locked=['loading','saving','uncertain'].includes(state.phase)||downloading;
 async function choose(file?:File){
  if(locked)return;const generation=++fileGeneration.current;client.discard();setUpload(null);setLocalMessage('');setFindings([]);
  if(!file)return;
  try{if(file.size<1||file.size>65536||!/\.(txt|pdf)$/i.test(file.name))throw Error('Choose a nonempty .txt or .pdf file up to 64 KiB.');
   const bytes=new Uint8Array(await file.arrayBuffer());if(generation!==fileGeneration.current)return;
   let binary='';for(const b of bytes)binary+=String.fromCharCode(b);
   setUpload({synthetic:true,filename:file.name,original_base64:btoa(binary)});setLocalMessage('File selected locally. Request a preview to send it for bounded extraction; nothing is saved yet.');
  }catch(e){if(generation===fileGeneration.current)setLocalMessage(e instanceof Error?e.message:'File unavailable');}
 }
 function add(){const row=preview?.lines[line-1];if(!row||!quote.trim()||!row.text.includes(quote)||quote.length>1200||!/^[a-z][a-z0-9_-]{0,59}$/.test(key)||findings.length>=30||findings.some(f=>f.key===key)){setLocalMessage('Use a unique finding key and an exact substring of the selected line (up to 1,200 characters).');return;}
  setFindings([...findings,{key,state:classification,quote,line}]);setQuote('');setKey('finding-'+(findings.length+2));setConfirmed(false);setLocalMessage('Passage selected locally; classification is user-selected and unreviewed.');
 }
 async function save(){if(!preview||!confirmed)return;
  if(state.document){const doc=state.document;await client.save('/'+doc.source_id+'/annotations',{
   synthetic:true,request_key:'ANNOTATE-'+crypto.randomUUID(),expected_revision_id:doc.revisions.at(-1)!.revision_id,
   confirmed_case_id:caseId,expected_sha256:preview.sha256,expected_extraction_sha256:preview.extraction_sha256??null,reason,findings});
  }else if(upload){await client.save('',{...upload,confirmed_case_id:caseId,expected_sha256:preview.sha256,
   expected_extraction_sha256:preview.extraction_sha256??null,metadata:{document_id:documentId,kind,event_date:eventDate,issued_at:issuedDate,
    manual_transcription_confirmed:true,...(amends?{amends_version:Number(amends)}:{})},findings});}
 }
 async function download(){const doc=state.document;if(!doc)return;const generation=lifetime.current;setDownloading(true);setLocalMessage('Authorizing original download…');
  try{const response=await session.documentRequest(caseId,'/'+doc.source_id+'/original');
   if(response.status!==200||!(response.body instanceof Uint8Array)||response.headers?.get('X-Content-SHA256')!==doc.sha256||!/^ACCESS-[A-F0-9]{32}$/.test(response.headers?.get('X-Access-Receipt-ID')??''))throw Error('Original download unavailable.');
   const bytes=response.body;const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new Uint8Array(bytes)))).map(v=>v.toString(16).padStart(2,'0')).join('');
   if(digest!==doc.sha256)throw Error('Original integrity check failed.');
   if(generation!==lifetime.current||selected.current!==doc.source_id+doc.sha256)return;
   const url=URL.createObjectURL(new Blob([new Uint8Array(bytes)],{type:doc.preview.media_type}));const a=document.createElement('a');a.href=url;a.download=doc.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);setLocalMessage('Exact original downloaded after a fresh authority check.');
  }catch(e){if(generation===lifetime.current){client.discard();setLocalMessage(e instanceof Error?e.message:'Download unavailable');}}
  finally{if(generation===lifetime.current)setDownloading(false);}
 }
 return <section className="intake-panel reviewed-documents" data-testid="reviewed-documents" aria-labelledby="reviewed-documents-heading">
  <h3 id="reviewed-documents-heading">Reviewed text and PDF records</h3>
  <p>Preview a fictional record, confirm its case and select exact passages. Originals and correction history stay preserved. PDF extraction supports small text-based files; no OCR or clinical interpretation.</p>
  <p className="small">Case <code>{caseId}</code> · Patient <code>{patientId}</code></p>
  <div className="actions"><button disabled={locked} onClick={()=>void client.load()}>Refresh reviewed documents</button>
   <button disabled={state.phase==='saving'} onClick={()=>{fileGeneration.current++;client.discard();setUpload(null);setFindings([]);setLocalMessage('');if(fileInput.current)fileInput.current.value='';}}>Discard local selection or uncertain intent</button></div>
  {state.documents.length>0&&<ul>{state.documents.map(doc=><li key={doc.source_id}><button disabled={locked} onClick={()=>void client.open(doc.source_id)}>{doc.document_id} · v{doc.version} · {doc.state}</button> <span>{doc.filename}</span></li>)}</ul>}
  <label>Fictional text or PDF file<input ref={fileInput} data-testid="reviewed-file" type="file" accept=".txt,.pdf,text/plain,application/pdf" disabled={locked} onChange={e=>void choose(e.target.files?.[0])}/></label>
  <button data-testid="preview-reviewed" disabled={!upload||locked} onClick={()=>void client.preview(upload)}>Preview selected file without saving</button>
  <p role="status" data-testid="reviewed-status">{state.message}</p>{localMessage&&<p role="status">{localMessage}</p>}
  {state.pending&&<button data-testid="retry-reviewed" disabled={state.phase==='saving'} onClick={()=>void client.retry()}>Retry exact save to recover receipt</button>}
  {state.receipt&&<div data-testid="reviewed-receipt"><p>Saved original <code>{state.receipt.source_id}</code> · v{state.receipt.version}. Selection receipt <code>{state.receipt.annotation_revision_id}</code>.</p><button onClick={()=>void client.open(state.receipt!.source_id)}>Inspect saved original and selection history</button></div>}
  {preview&&<div data-testid="reviewed-preview">
   <p><strong>{preview.filename}</strong> · {preview.byte_count} original bytes · <code>{preview.sha256}</code></p>
   {preview.extraction_sha256&&<p className="small">Frozen PDF extraction <code>{preview.extraction_sha256}</code>. Physical pages and extraction lines are not guaranteed visual reading order.</p>}
   {state.document&&<><p>{state.document.document_id} · v{state.document.version} · {state.document.state}</p><button data-testid="download-reviewed" disabled={locked} onClick={()=>void download()}>Download exact original</button>
    <details><summary>Preserved selection history ({state.document.revisions.length})</summary>{state.document.revisions.map(r=><section key={r.revision_id}><h4>Revision {r.revision}</h4><p>{r.reason} · user-selected · clinical review not performed</p><ul>{r.findings.map(f=><li key={f.key}>Line {f.line}: “{f.quote}” — {f.state}</li>)}</ul></section>)}</details></>}
   <ol className="document-lines">{preview.lines.map(row=><li key={row.line}><button type="button" disabled={locked} onClick={()=>{setLine(row.line);setQuote(row.text);setConfirmed(false);}}>Select line {row.line}{row.page?` · page ${row.page}`:''}</button><pre>{row.text||'(blank line)'}</pre></li>)}</ol>
   {state.document?.state!=='superseded'&&<form onSubmit={e=>{e.preventDefault();void save();}}>
    {!state.document&&<div className="document-metadata"><label>Document ID<input data-testid="document-id" value={documentId} onChange={e=>setDocumentId(e.target.value)} required pattern="[A-Z][A-Z0-9-]{1,39}"/></label>
     <label>Type<select value={kind} onChange={e=>setKind(e.target.value)}>{['clinical','pathology','laboratory','imaging','molecular','other'].map(x=><option key={x}>{x}</option>)}</select></label>
     <label>Event date<input data-testid="document-event" type="date" value={eventDate} onChange={e=>setEventDate(e.target.value)} required/></label><label>Issued date<input data-testid="document-issued" type="date" value={issuedDate} onChange={e=>setIssuedDate(e.target.value)} required/></label>
     <label>Amends version (optional)<input type="number" min="1" step="1" value={amends} onChange={e=>setAmends(e.target.value)}/></label></div>}
    <fieldset disabled={locked}><legend>Manual passage selections ({findings.length}/30)</legend>
     <label>Extraction line<input type="number" min="1" max={preview.lines.length} value={line} onChange={e=>{setLine(Number(e.target.value));setConfirmed(false);}}/></label>
     <label>Exact quotation<textarea data-testid="document-quote" value={quote} onChange={e=>setQuote(e.target.value)}/></label>
     <label>Finding key<input value={key} onChange={e=>setKey(e.target.value)}/></label>
     <label>User-selected status<select value={classification} onChange={e=>setClassification(e.target.value)}>{['not-assessed','not-reported','reported','negative','pending','indeterminate','conflicting'].map(x=><option key={x}>{x}</option>)}</select></label>
     <button type="button" onClick={add}>Add exact passage</button>
     <ul>{findings.map((f,i)=><li key={f.key}>Line {f.line}: “{f.quote}” · user-selected {f.state} <button type="button" onClick={()=>{setFindings(findings.filter((_,n)=>n!==i));setConfirmed(false);}}>Remove {f.key}</button></li>)}</ul>
    </fieldset>
    {state.document&&<label>Reason for this correction<textarea data-testid="document-reason" required minLength={3} maxLength={500} value={reason} onChange={e=>setReason(e.target.value)}/></label>}
    <label className="check"><input data-testid="document-confirm" type="checkbox" checked={confirmed} disabled={locked} onChange={e=>setConfirmed(e.target.checked)}/>I confirm this fictional case, document metadata and exact transcription. This is not clinical approval.</label>
    <button data-testid="save-reviewed" className="primary" disabled={!confirmed||locked}>{state.document?'Save new selection revision':'Save reviewed original'}</button>
   </form>}
  </div>}
  <p className="small muted">Manual selections are preserved for review. They are not yet included in source-authored World Model observations or investigation reports.</p>
 </section>;
}

/** Native disclosure retains local intent until the patient/case scope unmounts. */
export function ReviewedDocumentDisclosure({session,patientId,caseId}:{session:RegistrySession;patientId:string;caseId:string}){
 const [open,setOpen]=useState(false);
 return <details className="record-import-disclosure" data-testid="reviewed-document-disclosure"
  open={open} onToggle={event=>setOpen(event.currentTarget.open)}>
  <summary>Text and PDF originals</summary>
  <p className="muted small">Preview, save or inspect fictional text and PDF originals. Opening or closing this section keeps your local selection and sends no request.</p>
  <ReviewedDocumentWorkspace session={session} patientId={patientId} caseId={caseId}/>
 </details>;
}
