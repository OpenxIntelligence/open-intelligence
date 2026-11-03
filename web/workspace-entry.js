'use strict';
// Thin entry adapter over the EXISTING browser owner and CaseStore HTTP contract.
// Does not create another case/source store, parser, investigation or review flow.
(() => {
  const $ = id => document.getElementById(id);
  const dirty = hasUnfinishedCaseWork;
  const current = () => {
    try { return readyCase(); } catch (_) { return null; }
  };
  let refreshQueued=false, lastScopedCase=null, lastPresentedCase=null;
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
      workspacePresentation.navigate('source-intake');
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
    const selected=current(), unavailable=Boolean(caseId) && !selected;
    $('journey-steps').hidden=unavailable;
    $('source-intake-case').hidden=unavailable;
    if(selected) {
      document.body.dataset.workspaceState='ready';
      $('case-picker').disabled=false;
      renderIntakePresentation(active);
    } else if(!caseId && !$('case-picker').options.length &&
              ['No synthetic cases found','Create your first case workspace'].includes($('case-heading').textContent)) {
      document.body.dataset.workspaceState='empty';
      $('case-picker').disabled=true;
      if($('case-heading').textContent!=='Create your first case workspace')
        $('case-heading').textContent='Create your first case workspace';
      const message=$('notice');
      if(message.textContent.includes('seed before opening')) {message.hidden=true;message.textContent='';}
      renderIntakePresentation(null);
    } else if(unavailable) {
      document.body.dataset.workspaceState='loading';
    }
  }
  function schedule() {
    if(refreshQueued)return;
    refreshQueued=true;queueMicrotask(sync);
  }
  const observer=new MutationObserver(schedule);
  for(const id of ['case-heading','source-list','question-list','snapshot-list'])
    observer.observe($(id),{childList:true,subtree:true});
  document.addEventListener('oi:case-selection-changed',schedule);
  $('new-workspace-button').addEventListener('click',()=>{
    workspacePresentation.navigate('workspace-start');
    $('workspace-start').open=true;$('new-case-panel').open=true;
    $('case-create-alias').focus();
  });
  schedule();
})();
