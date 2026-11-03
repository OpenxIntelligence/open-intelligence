import {useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';
import {FICTIONAL_RETURN_REASON} from './review-queue-view';

/** Canonical source-question review return. Never professional approval. */
export function ReviewPanel({state,session}:{state:ViewState;session:RegistrySession}){
 const [caseId,setCaseId]=useState(()=>
   state.records?.find(r=>r.source_reference)?.source_reference?.case_id||'');
 const [reason,setReason]=useState(FICTIONAL_RETURN_REASON);
 const queue=state.reviewQueue;
 return <section className="panel review-panel" aria-labelledby="review-heading">
  <span className="step">SOURCE-LINKED QUESTIONS / REVIEW RETURN HISTORY</span>
  <h2 id="review-heading">Verification and review handoff</h2>
  <p>This is an operator-controlled, fictional <strong>nonterminal verification-return inbox</strong>
   derived from existing saved questions. It does not send notifications,
   assign a clinician, certify evidence or accept/approve care decisions.</p>
  {!state.patient?<p role="status">Open a separately authorized patient on Overview first.</p>:<>
   <form className="review-case-form" onSubmit={event=>{
     event.preventDefault();void session.loadReviewQueue(caseId);
   }}>
    <label htmlFor="review-case-id">Exact patient case</label>
    <div className="review-case-controls">
     <input id="review-case-id" data-testid="review-case-id" value={caseId}
      onChange={event=>setCaseId(event.target.value)} autoComplete="off"
      spellCheck={false} maxLength={40} pattern="CASE-[A-Z0-9-]{1,35}"
      placeholder="CASE-ALPHA" required/>
     <button type="submit" className="primary" data-testid="load-review-queue"
       disabled={state.reviewPhase==='loading'}>
      {state.reviewPhase==='loading'?'Checking source and queue grants…':'Refresh authorized review inbox'}
     </button>
    </div>
   </form>
   <p className={'status '+(state.reviewPhase==='error'?'error':'')}
    role="status" data-testid="review-status" aria-live="polite">{state.reviewMessage}</p>
   <p className={'status '+(state.reviewReturnPhase==='error'?'error':'')}
    role="status" data-testid="review-return-status" aria-live="polite">
    {state.reviewReturnMessage}</p>
   {state.reviewReturn&&<p data-testid="review-return-result" className="review-result">
     <strong>{state.reviewReturn.duplicate?'Original return receipt recovered':'Return receipt recorded'}:</strong>
     <code>{state.reviewReturn.receipt_id}</code> for <code>{state.reviewReturn.question_id}</code>.
     It is not clinical review, signoff or an external notification.
    </p>}
   {queue&&<div data-testid="review-queue-result">
     <div className="review-boundary" role="note">
      <strong>Clinical approval is unavailable.</strong> Reviewer identity is not verified.
      All entries are synthetic. The only permitted write is a version-bound,
      append-only return for independent verification.
     </div>
     <h3>Questions awaiting source verification</h3>
     {queue.items.length===0?<p>No source-linked questions are visible for this case.</p>:
      <ul className="review-items">{queue.items.map(item=><li
       key={item.question_id} data-testid="review-queue-item" className="review-item">
       <p className="step">SOURCE QUESTION · {item.source_context_state==='source_reassessment_required'?
         'HISTORICAL / REASSESSMENT REQUIRED':'CURRENT / UNREVIEWED'}</p>
       <h4>{item.question}</h4>
       <p><strong>Question ID:</strong> <code>{item.question_id}</code></p>
       <p><strong>Original:</strong> <code>{item.source_id}</code> · version {item.source_version},
        line {item.source_line}</p>
       <p><strong>Source context:</strong> {
        item.review_state==='source_reassessment_required'?
          'Source changed; previous return cannot become current.' :
        item.review_state==='returned_for_independent_verification'?
          'Returned for independent verification. No reviewer decision recorded.' :
          'Awaiting an explicit verification return. No external request sent.'
       }</p>
       <p><strong>Historical return receipts:</strong> {item.prior_return_count}
        {' '}· <strong>Current matching returns:</strong> {item.return_count}</p>
       {item.queue_fingerprint&&<p><strong>Version-bound review fingerprint:</strong>
        <code>{item.queue_fingerprint}</code></p>}
       {item.queue_fingerprint&&<div className="review-return-form">
        <label htmlFor={'reason-'+item.question_id}>Reason for independent verification</label>
        <textarea id={'reason-'+item.question_id} value={reason}
         onChange={event=>setReason(event.target.value)}
         maxLength={600} rows={2} spellCheck={false}/>
        <button type="button" data-testid="return-for-verification"
         disabled={state.reviewReturnPhase==='saving'||reason.trim().length<10}
         onClick={()=>void session.returnReviewQuestion(
           item.question_id,item.queue_fingerprint!,reason)}>
         {state.reviewReturnPhase==='saving'?'Recording return…':
           'Record verification return (no clinical approval)'}
        </button>
       </div>}
      </li>)}</ul>}
     <h3>Immutable return receipt history</h3>
     {queue.receipts.length===0?<p>No verification-return receipts have been recorded.</p>:
      <ul className="review-history" data-testid="review-return-history">
       {queue.receipts.map(receipt=><li key={receipt.receipt_id}>
        <strong>Returned for verification:</strong> <code>{receipt.receipt_id}</code>
        <p>Question <code>{receipt.question_id}</code> ·
          <time dateTime={receipt.created_at}>{receipt.created_at}</time></p>
        <p><strong>Reason:</strong> {receipt.reason}</p>
        <p className="muted">Synthetic actor label: {receipt.actor_label}.
         Not an authenticated clinician. No external notification or approval.</p>
       </li>)}
      </ul>}
    </div>}
  </>}
 </section>;
}
