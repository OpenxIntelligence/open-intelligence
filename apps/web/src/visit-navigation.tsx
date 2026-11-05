import {useLayoutEffect,useRef} from 'react';

/** Native modal supplies focus containment and Escape handling on mobile and desktop. */
export function LeaveVisitForm({destination,onStay,onLeave}:{destination:string;onStay:()=>void;onLeave:()=>void}){
  const ref=useRef<HTMLDialogElement>(null);
  useLayoutEffect(()=>{
    const dialog=ref.current;
    if(!dialog)return;
    const trigger=document.activeElement;
    dialog.showModal();
    return ()=>{
      dialog.close();
      if(trigger instanceof HTMLElement&&trigger.isConnected)trigger.focus();
    };
  },[]);
  return <dialog ref={ref} className="visit-leave-dialog" aria-labelledby="visit-leave-title"
    aria-describedby="visit-leave-description" onCancel={event=>{event.preventDefault();onStay();}}>
    <h2 id="visit-leave-title">Leave the unsaved visit form?</h2>
    <p id="visit-leave-description">Leaving for {destination} discards the changes you haven’t saved.</p>
    <div className="actions"><button type="button" autoFocus onClick={onStay}>Keep editing</button>
      <button type="button" onClick={onLeave}>Discard and leave</button></div>
  </dialog>;
}
