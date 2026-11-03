'use strict';
// Thin entry adapter over the EXISTING browser owner and CaseStore HTTP contract.
// Does not create another case/source store, parser, investigation or review flow.
(() => {
  const $ = id => document.getElementById(id);
  const dirty = () => ['question-text','report-text','draft-observations',
    'draft-summary','draft-assumptions','evidence-rationale',
    'evidence-withdraw-reason','option-description']
    .some(id => $(id)?.value.trim()) || Boolean($('source-file')?.files?.length);
  const current = () => {
    try { return readyCase(); } catch (_) { return null; }
  };
  let refreshQueued=false, lastScopedCase=null;
  const intake=globalThis.OIIntake.mount({
    api,
    getCase:current,
    canSwitch:() => !dirty(),
    created:async id => {
      const picker=$('case-picker');
      if (!caseId) {
        // The original empty startup exits before binding case change. Run it
        // once after first creation; repeated creation uses its existing listener.
        picker.replaceChildren();
        await initialize();
      } else {
        const list=await api('/api/cases'), selected=caseId;
        picker.replaceChildren();
        for(const entry of list) {
          const option=document.createElement('option');option.value=entry.case_id;
          option.textContent=entry.label.replace(/^Fictional case /,'')+', '+entry.case_id;
          picker.append(option);
        }
        picker.value=selected;
        await renderIncomingBoard(list);
      }
      if(!dirty() && id!==caseId) { picker.value=id;picker.dispatchEvent(new Event('change')); }
      $('source-intake').open=true;
      $('source-intake').scrollIntoView({block:'start'});
      schedule();
    },
    imported:async id => {
      if(current()!==id)return;
      await refresh();
      await renderIncomingBoard(await api('/api/cases'));
      schedule();
    },
  });
  function sync() {
    refreshQueued=false;
    const selected=current();
    if(selected) {
      lastScopedCase=selected;
      document.body.dataset.workspaceState='ready';
      $('case-picker').disabled=false;
      intake.render(active);
    } else if(!caseId && !$('case-picker').options.length &&
              ['No synthetic cases found','Create your first case workspace'].includes($('case-heading').textContent)) {
      document.body.dataset.workspaceState='empty';
      $('case-picker').disabled=true;
      if($('case-heading').textContent!=='Create your first case workspace')
        $('case-heading').textContent='Create your first case workspace';
      const message=$('notice');
      if(message.textContent.includes('seed before opening')) {message.hidden=true;message.textContent='';}
      intake.render(null);
    }
  }
  function schedule() {
    if(refreshQueued)return;
    refreshQueued=true;queueMicrotask(sync);
  }
  const observer=new MutationObserver(schedule);
  for(const id of ['case-heading','source-list','question-list','snapshot-list'])
    observer.observe($(id),{childList:true,subtree:true});
  $('case-picker').addEventListener('change',()=>{
    // Listener registration order may differ after initial empty-case setup.
    // Check the canonical app's accepted case AFTER all change listeners run.
    // A veto restores the old case and must not discard a staged original.
    queueMicrotask(()=>{
      if(caseId && lastScopedCase && caseId!==lastScopedCase) {
        lastScopedCase=caseId;
        intake.resetScope();
        document.body.dataset.workspaceState='loading';
      }
      schedule();
    });
  });
  $('new-workspace-button').addEventListener('click',()=>{
    $('workspace-start').open=true;$('new-case-panel').open=true;
    $('case-create-alias').focus();
  });
  schedule();
})();
