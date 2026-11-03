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
    const updateImport=()=>{
      $('source-upload-submit').disabled=importing || !pending || !$('source-upload-confirm').checked || !options.getCase();
      $('source-discard-button').disabled=importing || !$('source-file').files.length;
    };
    function resetScope() {
      sequence++;pending=null;$('source-file').value='';$('source-upload-confirm').checked=false;
      $('source-upload-preview').textContent='';$('source-preview-details').hidden=true;
      tell('source-upload-status','Choose an original fictional text report. Nothing uploads automatically.');updateImport();
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
      const file=$('source-file').files[0], caseId=options.getCase(), request=++sequence;
      pending=null;$('source-upload-confirm').checked=false;updateImport();
      $('source-upload-preview').textContent='';$('source-preview-details').hidden=true;
      if(!file)return;
      try {
        if(!caseId)throw Error('Create or select a workspace before choosing a source.');
        if(file.size>65536)throw Error('The source exceeds 65,536 bytes.');
        const decoded=decodeSource(new Uint8Array(await file.arrayBuffer()),file.name);
        if(request!==sequence || options.getCase()!==caseId)return;
        pending={...decoded,caseId};
        $('source-upload-preview').textContent=decoded.text;
        $('source-preview-details').hidden=false;
        tell('source-upload-status',file.name+' · '+decoded.byteLength+' bytes · declared subject '+decoded.declaredCase+
          (decoded.declaredCase!==caseId ? '. Different subject: the server will quarantine this, not attach its findings.' : '. Original text ready for inspection; not yet imported.'));
      } catch(error) {if(request===sequence)tell('source-upload-status',error.message,true);}
      updateImport();
    });
    $('source-discard-button').addEventListener('click',()=>{
      // Only clear an unsubmitted local original. Imported versions and history
      // remain in the existing ledger; an in-flight import cannot be discarded.
      if(importing)return;
      resetScope();
      tell('source-upload-status','Selected original discarded locally. No record was imported.');
    });
    $('source-upload-confirm').addEventListener('change',updateImport);
    fileForm.addEventListener('submit',async event=>{
      event.preventDefault();if(importing)return;
      const selected=pending, request=sequence;
      try {
        if(!selected || selected.caseId!==options.getCase() || !$('source-upload-confirm').checked)throw Error('Choose a source for the current workspace and confirm it is independently authored fictional data.');
        importing=true;updateImport();
        const result=await options.api('/api/cases/'+encodeURIComponent(selected.caseId)+'/imports',{text:selected.text});
        if(request!==sequence || options.getCase()!==selected.caseId)return;
        resetScope();
        tell('source-upload-status',result.result==='quarantined' ? 'Quarantined: the source belongs to a different case. No clinical findings were attached.' :
          result.result==='duplicate' ? 'Already received: no duplicate source or findings created.' :
          'Original source imported'+(result.version ? ' · version '+result.version : '')+'. Review the source-linked findings and timeline.');
        await options.imported(selected.caseId);
      } catch(error) {if(request===sequence)tell('source-upload-status',error.message,true);}
      finally {importing=false;updateImport();}
    });
    function render(state) {
      const id=state?.case?.case_id || null;
      const hasSources=Boolean(state?.sources?.length);
      if(id!==shownCase || hasSources!==hadSources) {
        resetScope();
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
  const exported={casePayload,decodeSource,journey,mount};
  if(typeof module!=='undefined' && module.exports)module.exports=exported;
  root.OIIntake=exported;
})(globalThis);
