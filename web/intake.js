'use strict';
// First-party entry into the existing local case/source workflow. No separate store.
(function (root) {
  const ID = /^[A-Z][A-Z0-9-]{1,39}$/;
  function casePayload(id, alias, confirmed) {
    if (confirmed !== true) throw Error('Confirm this workspace contains only independently authored fictional data.');
    if (typeof id !== 'string' || !ID.test(id) || /\s/.test(id)) throw Error('Use a 2–40 character uppercase case reference: A–Z, numbers and hyphens.');
    if (typeof alias !== 'string' || !alias.trim() || alias.trim().length > 65 || /[\u0000-\u001f\u007f]/.test(alias)) throw Error('Enter a fictional alias of 1–65 characters, not a real name.');
    return {case_id: id, label: 'Fictional case ' + alias.trim()};
  }
  function decodeSource(input, name) {
    if (typeof name !== 'string' || !/\.txt$/i.test(name)) throw Error('Use an authored .txt source. PDF, imaging and document extraction are not connected here yet.');
    const data = input instanceof Uint8Array ? input : new Uint8Array(input);
    if (!data.byteLength || data.byteLength > 65536) throw Error('The source must contain 1–65,536 bytes.');
    let text;
    try { text = new TextDecoder('utf-8', {fatal:true, ignoreBOM:true}).decode(data); }
    catch (_) { throw Error('The file must be valid UTF-8 text; its bytes were not imported.'); }
    if (text.includes('\r')) throw Error('This source contract requires LF line endings. The original file was not normalized or imported.');
    const lines = text.split('\n');
    if (lines[0] !== 'OI-SYNTHETIC-REPORT/1' || text.includes('\0')) throw Error('Expected the original OI-SYNTHETIC-REPORT/1 format; no clinical extraction or format guessing was performed.');
    const patients = lines.filter(line => line.startsWith('Patient:'));
    if (patients.length !== 1 || !/^Patient: [A-Z][A-Z0-9-]{1,39}$/.test(patients[0])) throw Error('The source needs one unambiguous Patient header.');
    return {text, declaredCase:patients[0].slice(9), byteLength:data.byteLength};
  }
  const MAX_FILES=20, MAX_BATCH_BYTES=1048576;
  // Single first-party intake owner: inspect exact bytes BEFORE all write attempts.
  // Original identity is left untouched so mismatched subjects reach quarantine.
  async function prepareBatch(files, caseId) {
    if (!Array.isArray(files) || files.length < 1 || files.length > MAX_FILES ||
        typeof caseId !== 'string' || !ID.test(caseId)) {
      throw Error('Choose 1–20 fictional source files for an existing case.');
    }
    let size=0;
    for (const file of files) {
      if (!file || typeof file.name !== 'string' || !/\\.txt$/i.test(file.name) ||
          typeof file.arrayBuffer !== 'function' || !Number.isSafeInteger(file.size) ||
          file.size < 1 || file.size > 65536) {
        throw Error('Each source must have 1–65,536 original bytes.');
      }
      size+=file.size;
      if(size>MAX_BATCH_BYTES) throw Error('The selected batch exceeds 1 MiB.');
    }
    const prepared=[];
    for (const file of files) {
      const original=new Uint8Array(await file.arrayBuffer());
      if (original.byteLength!==file.size) throw Error('Original file size changed while inspecting.');
      const record=decodeSource(original,file.name);
      const roundtrip=new TextEncoder().encode(record.text);
      if (roundtrip.length!==original.length ||
          roundtrip.some((byte,index)=>byte!==original[index])) {
        throw Error('Exact original UTF-8 bytes could not be preserved.');
      }
      prepared.push({name:file.name,caseId,...record});
    }
    return prepared;
  }
  // Reuse the canonical /imports endpoint. 4xx means rejected; 5xx, missing
  // receipt, malformed response or network failure means UNKNOWN, not "failed".
  // Never silently retry after an ambiguous outcome; earlier writes may persist.
  async function importPreparedBatch(prepared,{caseId,send,isCurrent=()=>true,onReceipt=()=>{}}={}) {
    if(!Array.isArray(prepared)||prepared.length<1||prepared.length>MAX_FILES ||
       typeof caseId!=='string'||!ID.test(caseId)||typeof send!=='function'||
       prepared.some(x=>x.caseId!==caseId||typeof x.text!=='string')) {
      throw Error('A prepared, case-scoped batch and sender are required.');
    }
    const results=[];
    let stop=false;
    for (const item of prepared) {
      let receipt;
      if(stop||!isCurrent()) {
        stop=true;
        receipt={name:item.name,caseId,status:'not_attempted',
          message:'Not sent. Reconcile the selected case and earlier receipts first.'};
      } else {
        let response=null;
        try {response=await send(caseId,item.text);}catch (_) {/* status is unknown */}
        const body=response?.body, status=response?.status;
        if(status===200 && body && ['imported','duplicate'].includes(body.result) &&
           Number.isSafeInteger(body.source_id)&&body.source_id>0 &&
           Number.isSafeInteger(body.version)&&body.version>0) {
          receipt={name:item.name,caseId,status:body.result,sourceId:body.source_id,
            version:body.version,message:body.result==='duplicate'
              ?'Existing exact original preserved; no duplicate created.'
              :'Original source version preserved; clinical meaning is not established.'};
        } else if(status===200 && body?.result==='quarantined' &&
                  Number.isSafeInteger(body.quarantine_id)&&body.quarantine_id>0) {
          receipt={name:item.name,caseId,status:'quarantined',
            quarantineId:body.quarantine_id,
            message:'Different declared patient: quarantined, with no findings attached.'};
        } else if(Number.isInteger(status)&&status>=400&&status<500) {
          receipt={name:item.name,caseId,status:'rejected',
            message:'Local source validation rejected this file; no accepted receipt.'};
        } else {
          stop=true;
          receipt={name:item.name,caseId,status:'unknown',
            message:'This request may have been saved; inspect current originals before retrying. No rollback is claimed.'};
        }
      }
      results.push(receipt);
      onReceipt(receipt);
    }
    return results;
  }
  function journey(state) {
    const current = (state?.sources || []).filter(s => s.state === 'current');
    const questions = state?.questions || [], snapshots = state?.snapshots || [];
    const changed = snapshots.some(s => s.state === 'stale' && questions.some(q => q.id === s.question_id && q.state === 'open'));
    const reviewed = snapshots.filter(s => s.state === 'reviewed_in_demo').length;
    const pending = snapshots.some(s => s.state === 'draft');
    return [
      {title:'1. Workspace', href:'#workspace-start', status:state ? 'Created' : 'Start here', detail:state?.case?.case_id || 'Create a fictional case'},
      {title:'2. Records', href:'#source-intake', status:current.length ? 'Sources received' : 'Add a source', detail:current.length + ' current document(s); originals retained'},
      {title:'3. Questions', href:'#investigations', status:questions.length ? 'Questions saved' : 'Ask a question', detail:questions.length + ' recorded question(s)'},
      {title:'4. Research & report', href:'#model-investigation-heading', status:snapshots.length ? 'Reports saved' : 'Prepare a report', detail:snapshots.length + ' report version(s); evidence and uncertainty stay visible'},
      {title:'5. Review & updates', href:'#investigations', status:changed ? 'Update needs review' : pending ? 'Review pending' : reviewed ? 'Demo review recorded' : 'Not reviewed', detail:'Demo acknowledgment is not professional sign-off'},
    ];
  }
  function mount(options) {
    const $ = id => document.getElementById(id);
    const createForm=$('case-create-form'), fileForm=$('source-upload-form');
    if (!createForm || !fileForm) return null;
    let creating=false, importing=false, sequence=0, pending=null, shownCase=null, hadSources=false;
    const tell=(id,text,error=false)=>{const target=$(id);target.textContent=text;target.dataset.error=String(error);};
    const updateImport=()=>{$('source-upload-submit').disabled=importing || !Array.isArray(pending) ||
      !pending.length || !$('source-upload-confirm').checked || !options.getCase();};
    function resetScope(retainReceipts=false) {
      sequence++;pending=null;$('source-file').value='';$('source-upload-confirm').checked=false;
      $('source-upload-preview').textContent='';$('source-preview-details').hidden=true;
      if(!retainReceipts)$('source-import-receipts').replaceChildren();
      tell('source-upload-status','Choose original fictional reports. Nothing uploads automatically.');updateImport();
    }
    createForm.addEventListener('submit',async event=>{
      event.preventDefault();if(creating)return;
      try {
        if(!options.canSwitch())throw Error('Save or clear the current draft before creating another workspace.');
        const payload=casePayload($('case-create-code').value,$('case-create-alias').value,$('case-create-confirm').checked);
        creating=true;$('case-create-submit').disabled=true;
        tell('case-create-status','Creating the workspace in the existing local case ledger…');
        await options.api('/api/cases',payload);
        await options.created(payload.case_id);
        createForm.reset();
        tell('case-create-status','Workspace created. Import its first original source below.');
      } catch(error) {tell('case-create-status',error.message,true);}
      finally {creating=false;$('case-create-submit').disabled=false;}
    });
    $('source-file').addEventListener('change',async()=>{
      const files=[...$('source-file').files], selected=options.getCase(), token=++sequence;
      pending=null;$('source-upload-confirm').checked=false;updateImport();
      $('source-import-receipts').replaceChildren();
      $('source-upload-preview').textContent='';$('source-preview-details').hidden=true;
      if(!files.length)return;
      try {
        if(!selected)throw Error('Create or select a fictional case before choosing originals.');
        const batch=await prepareBatch(files,selected);
        if(token!==sequence||options.getCase()!==selected)return;
        pending=batch;
        // One inspection surface, not another intake application. For a
        // single file keep the exact plain-text preview unchanged.
        $('source-upload-preview').textContent=batch.length===1 ? batch[0].text :
          batch.map(file=>'FILE '+file.name+' ('+file.byteLength+' bytes)\n'+file.text)
            .join('\n------ NEXT ORIGINAL ------\n');
        $('source-preview-details').hidden=false;
        const mismatched=batch.filter(item=>item.declaredCase!==selected).length;
        tell('source-upload-status',batch.length+' original file(s) inspected · '+
          batch.reduce((sum,item)=>sum+item.byteLength,0)+' bytes. '+mismatched+
          ' declared subject(s) differ and will be quarantined by the original store. Review every file before confirming.');
      } catch(error) {
        if(token===sequence)tell('source-upload-status',error.message,true);
      }
      updateImport();
    });
    $('source-upload-confirm').addEventListener('change',updateImport);
    fileForm.addEventListener('submit',async event=>{
      event.preventDefault();if(importing)return;
      const batch=pending, token=sequence, selected=options.getCase();
      try {
        if(!Array.isArray(batch)||!batch.length||
           batch.some(item=>item.caseId!==selected)||
           !$('source-upload-confirm').checked) {
          throw Error('Inspect and confirm each fictional original for the current case first.');
        }
        importing=true;updateImport();$('source-file').disabled=true;$('case-picker').disabled=true;
        $('source-import-receipts').replaceChildren();
        const results=await importPreparedBatch(batch,{
          caseId:selected,
          isCurrent:()=>token===sequence&&options.getCase()===selected,
          onReceipt:receipt=>{
            if(token!==sequence||options.getCase()!==selected)return;
            const li=document.createElement('li');
            li.textContent=receipt.name+' — '+receipt.status+' · '+receipt.message;
            li.dataset.status=receipt.status;
            $('source-import-receipts').append(li);
          },
          send:async(id,text)=>{
            const response=await fetch('/api/cases/'+encodeURIComponent(id)+'/imports',{
              method:'POST',headers:{'Content-Type':'application/json'},
              body:JSON.stringify({text}),cache:'no-store'});
            let body=null;
            try{body=await response.json();}catch(_){/* unknown outcome */}
            return {status:response.status,body};
          }
        });
        if(token!==sequence||options.getCase()!==selected)return;
        const unknown=results.some(r=>r.status==='unknown'||r.status==='not_attempted');
        const imported=results.filter(r=>r.status==='imported').length;
        // A network error may follow a committed write; never blind-retry it.
        resetScope(true);
        tell('source-upload-status',results.length+' individual receipt(s) · '+imported+
          ' newly imported. '+(unknown
            ?'At least one outcome is unknown or unattempted; inspect the source ledger before retrying.'
            :'Every attempted file has an explicit outcome. Inspect originals and their review status.'),
          unknown);
        await options.imported(selected);
      } catch(error) {
        if(token===sequence)tell('source-upload-status',error.message,true);
      } finally {
        importing=false;$('source-file').disabled=false;$('case-picker').disabled=false;updateImport();
      }
    });
    function render(state) {
      const id=state?.case?.case_id || null;
      const hasSources=Boolean(state?.sources?.length);
      if(id!==shownCase || hasSources!==hadSources) {
        resetScope(id===shownCase);
        $('workspace-start').open=!hasSources;
        $('source-intake').open=Boolean(state) && !hasSources;
        $('new-case-panel').open=!state;
      }
      shownCase=id;hadSources=hasSources;
      const list=$('journey-steps');list.replaceChildren();
      for(const step of journey(state)) {
        const li=document.createElement('li'),link=document.createElement('a'),status=document.createElement('strong'),detail=document.createElement('span');
        link.href=step.href;link.textContent=step.title;status.textContent=step.status;detail.textContent=step.detail;
        li.append(link,status,detail);list.append(li);
      }
      if(!state) { $('workspace-start').open=true; $('new-case-panel').open=true; }
      $('source-intake-case').textContent=id || 'No workspace selected';
      updateImport();
    }
    render(null);
    return {render,resetScope};
  }
  const exported={casePayload,decodeSource,prepareBatch,importPreparedBatch,journey,mount};
  if(typeof module!=='undefined' && module.exports)module.exports=exported;
  root.OIIntake=exported;
})(globalThis);
