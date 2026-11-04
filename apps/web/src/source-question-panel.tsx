import type {RegistrySession,ViewState} from './registry-client';
import {canPrepareSourceBrief,downloadSourceBrief} from './source-brief';

/** Reuses the source-question intake panel from PR238 over the canonical World Model. */
export function SourceQuestionPanel({state,session,busy,onReview}:{state:ViewState;session:RegistrySession;busy:boolean;onReview?:()=>void}){
 const caseId=state.worldModel?.case_id??'';
 const brief=state.sourceBrief;
 const draft=state.questionDraft;
 const validDraft=!!draft&&draft.question.length>=8&&draft.question.length<=500&&
   draft.question.trim()===draft.question&&
   !Array.from(draft.question).some(ch=>ch.charCodeAt(0)<32||ch.charCodeAt(0)===127);
 const unresolvedWrite=state.questionSaveMessage.startsWith('Save outcome unknown.');
 return <section data-testid="source-question-panel" aria-label="Source-linked question intake">
   {draft&&<section className="question-draft" data-testid="question-draft-editor"
       aria-labelledby="question-draft-heading">
     <span className="step">FICTIONAL QUESTION · IN-MEMORY DRAFT</span>
     <h3 id="question-draft-heading">Write your own source-linked question</h3>
     <p><strong>Selected original:</strong> <code>{draft.source_id}</code> · line {draft.source_line}.
       The source and case are fixed for this draft. Changing the question requires a new, independently authorized preflight.</p>
     <label htmlFor="source-question-text">Question to investigate</label>
     <textarea id="source-question-text" data-testid="question-draft" rows={3}
       maxLength={500} spellCheck={false} autoComplete="off" value={draft.question}
       disabled={busy||unresolvedWrite}
       onChange={e=>session.changeQuestionDraft(e.target.value)}/>
     <p className="muted" data-testid="question-draft-count">{draft.question.length}/500 characters. One question, 8–500 characters, no surrounding spaces or control characters. No medical conclusion or AI execution.</p>
     <div className="actions">
       <button type="button" className="primary" data-testid="prepare-custom-question"
         disabled={busy||!validDraft||unresolvedWrite||state.composerPhase==='loading'}
         onClick={()=>void session.prepareDraftQuestion()}>
         {state.composerPhase==='loading'?'Checking source context…':'Prepare this question against current source'}
       </button>
       <button type="button" data-testid="discard-question-draft" disabled={busy||unresolvedWrite}
         onClick={()=>session.discardQuestionDraft()}>Discard unsaved draft</button>
     </div>
     {unresolvedWrite&&<p role="note">The save result is unknown. Retry the same prepared question before replacing or discarding this draft, so an uncertain write is not duplicated.</p>}
   </section>}
   <p className={'status '+(state.composerPhase==='error'?'error':'')}
      data-testid="composer-status" role="status" aria-live="polite">{state.composerMessage}</p>
   {state.composerPreview&&<section className="composer-preview" data-testid="composer-context"
       aria-labelledby="composer-context-heading">
     <span className="step">SOURCE CONTEXT · NO MODEL EXECUTION</span>
     <h3 id="composer-context-heading">Prepared source context</h3>
     <p><strong>Source-linked question:</strong>{' '}
       {state.composerPreview.question}</p>
     <blockquote>{state.composerPreview.selected_source.statement}</blockquote>
     <p><strong>Exact original:</strong>{' '}
       <code>{state.composerPreview.selected_source.source_id}</code>,
       line {state.composerPreview.selected_source.line},
       version {state.composerPreview.selected_source.version}.</p>
     <details><summary>Source context and access details</summary>
       <p><strong>Snapshot fingerprint:</strong> <code>{state.composerPreview.source_snapshot_sha256}</code></p>
       <p><strong>Source snapshot contract:</strong> <code>{state.composerPreview.source_snapshot_contract}</code></p>
       <p><strong>Preflight hash:</strong> <code>{state.composerPreview.preflight_sha256}</code></p>
       <p><strong>Source-context access receipt:</strong> <code>{state.composerPreview.access_receipt_id}</code></p>
       <p>These identify the prepared source context and its access check. They are not execution credentials or question or clinical approval.</p>
     </details>
     <p role="note"><strong>Not a clinical review.</strong> This preview alone does not
       save a question, execute a model, establish biomedical source rights or
       authorize a clinician. Saving below creates only a source-linked
       question-intake record with independent source revalidation.</p>
     <button type="button" className="primary" data-testid="save-source-question"
       disabled={busy||state.questionSavePhase==='saving'}
       onClick={()=>void session.savePreparedQuestion()}>
       {state.questionSavePhase==='saving'?'Saving authorized question…':
        'Save source-linked question (no clinical approval)'}
     </button>
     <p className={'status '+(state.questionSavePhase==='error'?'error':'')}
       data-testid="question-save-status" role="status" aria-live="polite">
       {state.questionSaveMessage}</p>
     {state.savedQuestion&&<p className="question-receipt" data-testid="saved-source-question">
       <strong>{state.savedQuestion.duplicate?'Existing question recovered':'Question saved'}:</strong>{' '}
       <code>{state.savedQuestion.question_id}</code>. This does not submit
       or approve a clinician review.</p>}
   </section>}
   <section className="question-history" aria-labelledby="question-history-heading">
    <div className="question-history-heading">
      <div><h3 id="question-history-heading">Saved source-linked questions</h3>
       <p>Durable question intake only. No clinical reviewer has received or approved these items.</p></div>
      <button type="button" data-testid="load-source-questions" disabled={!caseId||busy||state.questionListPhase==='loading'}
        onClick={()=>void session.loadSavedQuestions(caseId)}>
        {state.questionListPhase==='loading'?'Checking question history…':'Refresh question history'}
      </button>
    </div>
    <p data-testid="questions-status" role="status" aria-live="polite"
      className={'status '+(state.questionListPhase==='error'?'error':'')}>
      {state.questionListMessage}</p>
    {state.questions&&state.questionsCaseId===caseId&&<div data-testid="source-question-history">
      {state.questions.length>0&&onReview&&<div className="actions question-review-action">
       <button type="button" data-testid="open-question-review" disabled={busy}
        onClick={()=>{void session.loadReviewQueue(caseId);onReview();}}>Open verification inbox for these questions</button>
      </div>}
      <details><summary>Source-context access receipt</summary><code>{state.questionsAccessReceiptId}</code><p>Source access checked for this history read. No question or clinical approval is implied.</p></details>
      {state.questions.length===0?<p>No saved source-linked questions are visible.</p>:
       <ul className="question-items">
        {state.questions.map(item=><li key={item.question_id} data-question-id={item.question_id}>
          <div className="question-status-title">
           <strong>{item.question}</strong>
           <span className={'question-status '+(item.source_context_state==='source_reassessment_required'?'reassessment':'')}>
           {item.source_context_state==='source_reassessment_required'?
             (item.source_snapshot_contract==='oi.pg-source-world-model/1'?'Source changed — reassessment required':'Earlier source context — reassessment required'):'Current source context — unreviewed'}
           </span>
          </div>
          <p><strong>Original anchor:</strong> <code>{item.source_id}</code> · v{item.source_version}, line {item.source_line}.</p>
          <p><strong>Saved question:</strong> <code>{item.question_id}</code></p>
          <details><summary>Recorded source provenance</summary>
           <p><strong>Source snapshot contract:</strong> <code>{item.source_snapshot_contract}</code></p>
           <p><strong>Original SHA-256:</strong> <code>{item.source_sha256}</code></p>
           <p><strong>Snapshot fingerprint:</strong> <code>{item.source_snapshot_sha256}</code></p>
           <p><strong>Preflight hash:</strong> <code>{item.preflight_sha256}</code></p>
          </details>
          <p className="muted">Human review not submitted. Clinical approval: none.</p>
          <button type="button" data-testid="brief-prepare"
            disabled={busy||state.briefPhase==='loading'||state.worldPhase!=='ready'||
              !canPrepareSourceBrief(item,state.worldModel)}
            onClick={()=>void session.prepareSourceBrief(item.question_id)}>Prepare source brief</button>
          {!canPrepareSourceBrief(item,state.worldModel)&&<p className="muted">
            Prepare a new question from the current source context before exporting a brief.</p>}
          <button type="button" data-testid="source-quote-packet-open"
           disabled={busy||state.sourceQuotePhase==='loading'}
           onClick={()=>void session.loadQuestionSourcePacket(item.question_id)}>
           Inspect verified source quote and evidence gaps
          </button>
         </li>)}</ul>}
    </div>}
    <p data-testid="brief-status" role="status" aria-live="polite"
      className={'status '+(state.briefPhase==='error'?'error':'')}>{state.briefMessage}</p>
    {brief&&<section className="source-brief-preview" data-testid="source-brief-preview"
        aria-labelledby="source-brief-heading">
      <h3 id="source-brief-heading">Source-linked question brief</h3>
      <p><strong>Saved question:</strong> {brief.question.question}</p>
      <blockquote>{brief.selected_source.statement}</blockquote>
      <p><strong>Source-reported state:</strong> {brief.selected_source.reported_state} ·
        {brief.selected_source.event_date} · issued {brief.selected_source.issued_at}</p>
      <p>Fictional source context only. Biomedical evidence, AI analysis and clinical review are not included.</p>
      <details><summary>Read complete source context</summary>
        <pre data-testid="source-brief-body">{brief.body}</pre>
      </details>
      <details><summary>Brief source and verification details</summary>
        <p><strong>Question:</strong> <code>{brief.question.question_id}</code></p>
        <p><strong>Original:</strong> <code>{brief.selected_source.source_id}</code> ·
          v{brief.selected_source.version}, line {brief.selected_source.line}</p>
        <p><strong>Prepared:</strong> {brief.prepared_at}</p>
        <p><strong>Snapshot fingerprint:</strong> <code>{brief.source_snapshot_sha256}</code></p>
        <p><strong>Preflight hash:</strong> <code>{brief.question.preflight_sha256}</code></p>
        <p><strong>Brief SHA-256:</strong> <code data-testid="brief-body-sha256">{brief.body_sha256}</code></p>
        <p><strong>Access receipt:</strong> <code data-testid="brief-access-receipt">{brief.access_receipt_id}</code></p>
        <p>Hashes identify content. They do not establish clinical correctness or approval.</p>
      </details>
      <button type="button" data-testid="brief-download" disabled={busy||state.briefPhase==='loading'}
        onClick={()=>void downloadSourceBrief(session,brief.question.question_id)}>
        Recheck permission and download text
      </button>
      <p className="muted">Every download requests a new brief from the server. An earlier preview is never used when access is denied or the source changes.</p>
    </section>}
   </section>
   <p role="status" aria-live="polite" data-testid="source-quote-packet-status"
    className={'status '+(state.sourceQuotePhase==='error'?'error':'')}>
    {state.sourceQuoteMessage}</p>
   {state.sourceQuotePacket&&<section className="source-quote-inspection" data-testid="source-quote-packet"
    aria-labelledby="source-quote-heading">
    <span className="step">SOURCE QUOTATION / PROVENANCE INSPECTION</span>
    <h3 id="source-quote-heading">Review prerequisites — not a clinical assessment</h3>
    <p><strong>Saved question:</strong> {state.sourceQuotePacket.question}</p>
    <p><strong>Question record:</strong> <code>{state.sourceQuotePacket.question_id}</code></p>
    {state.sourceQuotePacket.selected_statement?<div>
     <p><strong>Source-reported statement, exactly quoted:</strong></p>
     <blockquote data-testid="source-quote-literal">{state.sourceQuotePacket.selected_statement.source_statement}</blockquote>
     <p>Reported state: <strong>{state.sourceQuotePacket.selected_statement.reported_state}</strong>
       {' '}· Document <code>{state.sourceQuotePacket.selected_statement.document_id}</code>
       {' '}v{state.sourceQuotePacket.selected_statement.document_version},
       line {state.sourceQuotePacket.selected_statement.source_line}</p>
     <p>Reported event: {state.sourceQuotePacket.selected_statement.event_date}
      {' '}· Specimen {state.sourceQuotePacket.selected_statement.specimen_id??'not specified'}</p>
     <h4>Related authored statements ({state.sourceQuotePacket.related_statement_count_total})</h4>
     {state.sourceQuotePacket.related_statements.length===0?
       <p>No other current same-specimen/date/finding statements were returned. This is not an exhaustive evidence search.</p>:
       <ul data-testid="source-quote-related">{state.sourceQuotePacket.related_statements.map(q=>
        <li key={q.source_id+':'+q.source_line}>
         <blockquote>{q.source_statement}</blockquote>
         <p>{q.reported_state} · <code>{q.source_id}</code> line {q.source_line}</p>
        </li>)}</ul>}
     {state.sourceQuotePacket.related_statements_truncated&&
       <p>Additional related statements exist. This bounded packet is not complete.</p>}
    </div>:<p role="note" data-testid="source-quote-stale">
     <strong>Historical source — reassessment required.</strong>
     The original question and source identifiers are retained, but the outdated
     quotation is not presented as current. Refresh sources and create a new
     source-linked question before review.</p>}
    <details><summary>Original source reference and packet integrity</summary>
     <p>Original <code>{state.sourceQuotePacket.original_anchor.source_id}</code>,
      version {state.sourceQuotePacket.original_anchor.source_version},
      line {state.sourceQuotePacket.original_anchor.source_line}</p>
     <p>Original SHA-256 <code>{state.sourceQuotePacket.original_anchor.source_sha256}</code></p>
     <p>Current source snapshot <code>{state.sourceQuotePacket.current_source_snapshot_sha256}</code></p>
     <p>Verified content packet SHA-256 <code>{state.sourceQuotePacket.packet_sha256}</code></p>
     <p>Source-access preparation receipt <code>{state.sourceQuotePacket.source_access_receipt_id}</code>.
      This is not proof of network delivery or a clinical authorization.</p>
    </details>
    <p role="note" className="source-quote-limit">
     <strong>Outstanding independent review:</strong> Biomedical literature appraisal,
     publisher rights, clinical relevance, professional identity, consent and
     signed decisions are not established by this packet. No model was run,
     treatment inferred or medical action authorized.
    </p>
   </section>}
 </section>;
}
