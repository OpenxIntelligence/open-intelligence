import {AttributionReview,ReassessmentPassages} from './attribution-review';
import {useEffect,useState} from 'react';
import type {RegistrySession,ViewState} from './registry-client';
import {attributionReviewStatus,FICTIONAL_RETURN_REASON,validReturnReason} from './review-queue-view';

function reviewCaseId(state:ViewState):string{
 return state.worldModel?.case_id??state.questionsCaseId??state.sourceIndex?.case_id??
  state.reviewQueue?.case_id??state.reviewReturnIntent?.case_id??'';
}

/** Unsaved presentation text follows the mounted app, not the visible screen.
 * Captured/uncertain writes remain owned by RegistrySession and take precedence.
 */
export function useReviewReasonDrafts(state:ViewState){
 const caseId=reviewCaseId(state),patientId=state.patient?.patient_id;
 // Review rechecks source authority independently. A fresh matching inbox may
 // recover editing even while an earlier World Model error remains visible.
 const freshQueue=state.reviewPhase==='ready'&&state.reviewQueue?.patient_id===patientId&&
  state.reviewQueue?.case_id===caseId;
 const usable=state.connected&&state.phase==='ready'&&patientId&&caseId&&
  state.cases?.some(item=>item.case_id===caseId&&item.status==='active')&&
  !state.recordsPhase.startsWith('loading')&&state.worldPhase!=='loading'&&
  (freshQueue||(state.recordsPhase!=='error'&&state.worldPhase!=='error'&&
   state.reviewPhase!=='error'&&state.reviewReturnPhase!=='error'));
 const scope=usable?JSON.stringify([patientId,caseId]):null;
 const [drafts,setDrafts]=useState<{scope:string|null;values:Record<string,string>}>({scope,values:{}});
 // Guard reads immediately as well as removing retained text after invalidation.
 const values=scope!==null&&drafts.scope===scope?drafts.values:{};
 useEffect(()=>{setDrafts(previous=>previous.scope===scope?previous:{scope,values:{}})},[scope]);
 function change(questionId:string,value:string){
  if(scope===null||!state.reviewQueue?.items.some(item=>item.question_id===questionId&&item.case_id===caseId))return;
  setDrafts(previous=>({scope,values:{...(previous.scope===scope?previous.values:{}),[questionId]:value}}));
 }
 return {values,change};
}

/** Reuses the source-question review owner from PR245 in the current patient workspace. */
export function ReviewPanel({state,session,busy,onOverview,onInvestigations,onOriginal,drafts}:{
 state:ViewState;session:RegistrySession;busy:boolean;onOverview:()=>void;onInvestigations:()=>void;
 onOriginal:(caseId:string,sourceId:string,version:number,digest:string)=>void;
 drafts:ReturnType<typeof useReviewReasonDrafts>;
}){
 const changing=state.worldPhase==='loading'||state.recordsPhase.startsWith('loading');
 const caseId=reviewCaseId(state);
 const queue=state.reviewQueue?.case_id===caseId&&!changing?state.reviewQueue:null;
 const intent=state.reviewReturnIntent;
 const returning=state.reviewReturnPhase==='saving',uncertain=state.reviewReturnPhase==='unknown';
 return <section className="panel review-panel" aria-labelledby="review-heading" data-testid="review-workspace">
  <span className="step">SAVED QUESTIONS / VERIFICATION RETURN HISTORY</span>
  <h2 id="review-heading">Questions for independent verification</h2>
  <p>Read saved questions in this patient’s source context, record why a source needs independent
   verification, and inspect the unchanged return history. Recording a return does not assign a
   clinician, send a notification or approve a clinical decision.</p>
  {!state.patient?<div><p role="status">Open an authorized fictional patient first.</p>
   <button onClick={onOverview}>Go to patient overview</button></div>:<>
   <p className="record-scope"><strong>Patient:</strong> <code>{state.patient.patient_id}</code>
    {caseId&&<> · <strong>Case:</strong> <code data-testid="review-case-id">{caseId}</code></>}</p>
   <div className="actions">
    <button type="button" className="primary" data-testid="load-review-queue"
     disabled={!caseId||changing||busy||state.reviewPhase==='loading'}
     onClick={()=>void session.loadReviewQueue(caseId)}>
     {state.reviewPhase==='loading'?'Checking source and inbox grants…':'Refresh authorized review inbox'}
    </button>
    <button type="button" onClick={onInvestigations}>View source questions</button>
   </div>
   {!caseId&&<p>Select a source case in Investigations to continue in the same patient context.</p>}
   <p className={'status '+(state.reviewPhase==='error'?'error':'')} data-testid="review-status"
    role="status" aria-live="polite">{state.reviewMessage}</p>
   <p className={'status '+(state.reviewReturnPhase==='error'?'error':'')} data-testid="review-return-status"
    data-phase={state.reviewReturnPhase} role="status" aria-live="polite">{state.reviewReturnMessage}</p>
   {intent&&(returning||uncertain)&&<section className="review-recovery" data-testid="review-return-intent"
     aria-label="Exact verification return awaiting a receipt">
    <h3>{returning?'Recording the captured return':'Recover the earlier return receipt'}</h3>
    <p><strong>Captured reason:</strong> {intent.reason}</p>
    {intent.comparison_source&&<p>Second source <code>{intent.comparison_source.source_id}</code> · line {intent.comparison_source.source_line}</p>}
    <p>This exact intent keeps its original request key. A later source amendment does not turn it
     into a return against the new source version.</p>
    <details><summary>Captured question and source context</summary>
     <p>Question <code>{intent.question_id}</code> · case <code>{intent.case_id}</code></p>
     <p>Original return fingerprint <code>{intent.queue_fingerprint}</code></p>
    </details>
    {uncertain&&<button type="button" data-testid="retry-review-return" disabled={busy||changing}
     onClick={()=>void session.retryReviewReturn()}>Retry this exact return</button>}
   </section>}
   {state.reviewReturn&&<section data-testid="review-return-result" className="review-result">
    <strong>{state.reviewReturn.duplicate?'Original return receipt recovered':'Verification return recorded'}.</strong>
    <p>The question remains unreviewed. No clinician or external provider was notified.</p>
    <details><summary>Recorded receipt</summary>
     <p><code data-testid="review-return-id">{state.reviewReturn.receipt_id}</code></p>
     <p>Question <code>{state.reviewReturn.question_id}</code></p>
     {state.reviewReturn.artifacts&&<p>Verified brief <code>{state.reviewReturn.artifacts.run_id}</code>
       {' '}and comparison report <code>{state.reviewReturn.artifacts.report_id}</code></p>}
    </details>
   </section>}
   {queue&&<div data-testid="review-queue-result">
    <details className="review-access"><summary>Source-context access details</summary>
     <p>Read receipt <code data-testid="review-access-receipt">{queue.access_receipt_id}</code></p>
     <p>Projection <code>{queue.contract}</code>. This receipt records source access for the inbox read;
      it is not a return authorization or clinical approval.</p>
    </details>
    <h3>Saved questions and current source status</h3>
    {queue.items.length===0?<p>No source-linked questions are visible for this case.</p>:
     <ul className="review-items">{queue.items.map(item=>{
      const captured=intent?.question_id===item.question_id&&intent.case_id===item.case_id?intent:null;
      const draft=captured&&(returning||uncertain)?captured.reason:
       drafts.values[item.question_id]??captured?.reason??FICTIONAL_RETURN_REASON;
      const historical=item.source_context_state==='source_reassessment_required';
      return <li key={item.question_id} data-testid="review-queue-item" data-question-id={item.question_id}
       data-source-id={item.source_id} data-state={item.review_state} className="review-item">
       <div className="question-status-title">
        <h4>{item.question}</h4>
        <span className={'question-status '+(historical?'reassessment':'')}>
         {historical?'Reassessment required':item.review_state==='returned_for_independent_verification'?
          'Returned for verification · unreviewed':'Current source · unreviewed'}</span>
       </div>
       <p><strong>Original anchor:</strong> version {item.source_version}, line {item.source_line}.</p>
       <p>{historical?(item.source_snapshot_contract==='oi.pg-source-world-model/1'?
         'Source context changed. The original question and earlier returns remain historical.':
         'This question uses an earlier source contract and needs a new canonical source context.'):
         item.review_state==='returned_for_independent_verification'?
         'A verification return was recorded for this exact context. No reviewer decision is recorded.':
         'A separate permission is required to record a verification return.'}</p>
       <p><strong>Earlier return receipts:</strong> {item.prior_return_count}{' '}·{' '}
        <strong>Returns matching this context:</strong> {item.return_count}</p>
       <details><summary>Question and original provenance</summary>
        <p>Question <code>{item.question_id}</code></p>
        <p>Original <code>{item.source_id}</code> · SHA-256 <code>{item.source_sha256}</code></p>
        <p>Source context <code>{item.source_snapshot_contract}</code> · <code>{item.source_snapshot_sha256}</code></p>
        <p>Preflight <code>{item.preflight_sha256}</code></p>
        <p>Return context <code>{item.queue_fingerprint_contract}</code> · <code>{item.queue_fingerprint??'Not current'}</code></p>
       </details>
       <AttributionReview key={item.question_id+':'+queue.access_receipt_id} session={session} state={state}
        question={item} disabled={busy||returning||uncertain}/>
       {item.queue_fingerprint&&<div className="review-return-form">
        <label htmlFor={'reason-'+item.question_id}>Reason for independent verification</label>
        <textarea id={'reason-'+item.question_id} data-testid="review-reason" value={draft}
         disabled={returning||uncertain} maxLength={600} rows={3} spellCheck={false}
         onChange={event=>drafts.change(item.question_id,event.target.value)}/>
        <button type="button" data-testid="return-for-verification"
         disabled={busy||returning||uncertain||!validReturnReason(draft)}
         onClick={()=>void session.returnReviewQuestion(item.question_id,item.queue_fingerprint!,draft)}>
         {returning&&captured?'Recording return…':'Record verification return'}
        </button>

       </div>}
      </li>;
     })}</ul>}
    <h3>Immutable return history</h3>
    {queue.receipts.length===0?<p>No verification-return receipts have been recorded.</p>:
     <ul className="review-history" data-testid="review-return-history">{queue.receipts.map(receipt=><li key={receipt.receipt_id}>
      <strong>{receipt.comparison_source?'Episode attribution left unresolved':'Returned for independent verification'}</strong>
      {receipt.comparison_source&&(()=>{
       const first=queue.items.find(item=>item.question_id===receipt.question_id)!;
       const second=receipt.comparison_source;
       return <div><p>{attributionReviewStatus(first,second,state.worldModel?.case_id===caseId?state.worldModel.history:[])}</p>
        <button type="button" disabled={busy||returning||uncertain} onClick={()=>onOriginal(caseId,first.source_id,first.source_version,first.source_sha256)}>First original · v{first.source_version}, line {first.source_line}</button>{' '}
        <button type="button" disabled={busy||returning||uncertain} onClick={()=>onOriginal(caseId,second.source_id,second.source_version,second.source_sha256)}>Second original · {second.document_id} v{second.source_version}, line {second.source_line}</button>
        <p><button type="button" disabled={busy||returning||uncertain}
          data-testid="inspect-attribution" onClick={()=>void session.inspectAttribution(receipt.receipt_id)}>
          Compare recorded and current passages
        </button></p>
        {state.attributionTarget===receipt.receipt_id&&<>
         <p role="status">{state.attributionMessage}</p>
         {state.attributionInspection&&<button type="button" disabled={busy||returning||uncertain}
          data-testid="recheck-attribution" onClick={()=>void session.inspectAttribution(receipt.receipt_id,state.attributionInspection!.comparison_sha256)}>
          Recheck this exact comparison
         </button>}
         {state.attributionInspection&&<ReassessmentPassages packet={state.attributionInspection} disabled={busy||returning||uncertain}
          onOriginal={version=>onOriginal(caseId,version.source_id,version.source_version,version.source_sha256)}/>}
        </>}
       </div>;
      })()}
      <p><strong>Reason:</strong> {receipt.reason}</p>
      <p><time dateTime={receipt.created_at}>{receipt.created_at}</time> · {receipt.source_snapshot_contract==='oi.pg-source-world-model/1'?
       'Canonical source context at recording':'Earlier source context; retained as history'}</p>
      <details><summary>Immutable receipt and provenance</summary>
       <p><code>{receipt.receipt_id}</code> · question <code>{receipt.question_id}</code></p>
       <p>Source context <code>{receipt.source_snapshot_contract}</code> · <code>{receipt.source_snapshot_sha256}</code></p>
       <p>Return context <code>{receipt.queue_fingerprint_contract}</code> · <code>{receipt.queue_fingerprint}</code></p>
       <p>Synthetic actor label: <code>{receipt.actor_label}</code>. Professional identity is not verified.</p>
      </details>
      <p className="muted">No clinical approval, external notification or completed review.</p>
     </li>)}</ul>}
   </div>}
  </>}
 </section>;
}
