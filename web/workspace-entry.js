'use strict';
// Thin entry adapter over the EXISTING browser owner and CaseStore HTTP contract.
// Does not create another case/source store, parser, investigation or review flow.
(() => {
  const $ = id => document.getElementById(id);
  const dirty = hasUnfinishedCaseWork;
  const current = () => {
    try { return readyCase(); } catch (_) { return null; }
  };
  let refreshQueued=false, lastScopedCase=null, lastPresentedCase=null, pendingCreation=null;
  let observedSelection=caseId, selectionRevision=0;
  const intake=globalThis.OIIntake.mount({
    api,
    getCase:current,
    canSwitch:() => !dirty(),
    getCreationContext:() => selectionRevision,
    created:async (id, selection=selectionRevision) => {
      // A user-selected chart after submission supersedes the old creation
      // navigation intent, even when the successful POST response was delayed.
      if(selection!==selectionRevision)return 'cancelled';
      const intent={id, selection, cancelled:false};
      pendingCreation=intent;
      if (!caseId) {
        // The POST has succeeded. Retain this activation intent across read
        // failures and supersede an older startup snapshot with a fresh roster.
        await initialize(id);
      } else {
        // This same path also covers startup completing while the POST waits.
        // A failed read leaves its intent recoverable via the existing worklist.
        await renderIncomingBoard();
      }
      schedule();
      if(intent.cancelled || intent.selection!==selectionRevision)return 'cancelled';
      return current()===id;
    },
    imported:async id => {
      if(current()!==id)return;
      await refresh();
      schedule();
    },
  });
  function renderIntakePresentation(state) {
    const id=state?.case?.case_id || null;
    const route=document.body.dataset.view;
    const disclosure=['source-intake','workspace-start'].includes(route) ? $(route) : null;
    const keepOpen=disclosure?.open;
    intake.render(state);
    // Intake's source-count defaults must not collapse the user's active page.
    // A new ready chart opens its selected destination; ordinary same-case
    // updates retain an intentionally opened or closed native disclosure.
    if(disclosure)disclosure.open=(Boolean(id) && id!==lastPresentedCase) || keepOpen;
    lastPresentedCase=id;
    // The original progress calculation is unchanged. Its formerly shared
    // investigation section now has separate question and report destinations.
    const destinations={'3. Questions':'#questions','5. Review & updates':'#reports'};
    for(const link of $('journey-steps').querySelectorAll('a'))
      if(Object.hasOwn(destinations,link.textContent)) link.href=destinations[link.textContent];
  }
  function sync() {
    refreshQueued=false;
    // The canonical owner notifies us after accepting a selection. Raw native
    // picker listeners can run before that decision, with microtasks between them.
    if(caseId!==lastScopedCase) {
      lastScopedCase=caseId;
      intake.resetScope();
    }
    const selected=current(), unavailable=!selected && (Boolean(caseId) || workspaceStartupPhase!=='empty');
    $('journey-steps').hidden=unavailable;
    $('source-intake-case').hidden=unavailable;
    if(selected) {
      document.body.dataset.workspaceState='ready';
      $('case-picker').disabled=false;
      renderIntakePresentation(active);
      if(pendingCreation?.id===selected) {
        pendingCreation=null;
        $('case-create-status').textContent='Workspace created. Import its first original source below.';
        $('case-create-status').dataset.error='false';
        workspacePresentation.navigate('source-intake');
        $('source-intake').open=true;
        $('source-intake').scrollIntoView({block:'start'});
      }
    } else if(!caseId && workspaceStartupPhase==='empty') {
      document.body.dataset.workspaceState='empty';
      $('case-picker').disabled=true;
      if($('case-heading').textContent!=='Create your first case workspace')
        $('case-heading').textContent='Create your first case workspace';
      renderIntakePresentation(null);
    } else if(unavailable) {
      document.body.dataset.workspaceState=workspaceStartupPhase==='failed' ? 'unavailable' : 'loading';
      $('case-picker').disabled=!caseId;
    }
  }
  function schedule() {
    if(refreshQueued)return;
    refreshQueued=true;queueMicrotask(sync);
  }
  const observer=new MutationObserver(schedule);
  for(const id of ['case-heading','source-list','question-list','snapshot-list'])
    observer.observe($(id),{childList:true,subtree:true});
  document.addEventListener('oi:case-selection-changed',()=>{
    // Initial automatic selection is not a later user choice. Subsequent
    // accepted switches synchronously cancel an obsolete creation intent.
    if(observedSelection && observedSelection!==caseId)selectionRevision++;
    observedSelection=caseId;
    if(pendingCreation) {
      if(caseId===pendingCreation.id)pendingCreation.selection=selectionRevision;
      else {
        pendingCreation.cancelled=true;
        pendingCreation=null;
        $('case-create-status').textContent='Workspace created and saved. Open it from Patients when you are ready.';
        $('case-create-status').dataset.error='false';
      }
    }
    schedule();
  });
  document.addEventListener('oi:workspace-startup-changed',schedule);
  document.addEventListener('oi:worklist-updated',()=>{
    if(!caseId || !pendingCreation || dirty())return;
    const picker=$('case-picker');
    if(![...picker.options].some(option=>option.value===pendingCreation.id))return;
    picker.value=pendingCreation.id;
    picker.dispatchEvent(new Event('change'));
    schedule();
  });
  $('new-workspace-button').addEventListener('click',()=>{
    workspacePresentation.navigate('workspace-start');
    $('workspace-start').open=true;$('new-case-panel').open=true;
    $('case-create-alias').focus();
  });
  schedule();
})();
