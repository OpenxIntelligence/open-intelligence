import type {RegistrySession,ViewState} from './registry-client';

/** Reuses the source-question intake panel from PR238 over the canonical World Model. */
export function SourceQuestionPanel({state,session,busy}:{state:ViewState;session:RegistrySession;busy:boolean}){
 const caseId=state.worldModel?.case_id??'';
 const draft=state.questionDraft;
 const validDraft=!!draft&&draft.question.length>=8&&draft.question.length<=500&&
   draft.question.trim()===draft.question&&
   !Array.from(draft.question).some(ch=>ch.charCodeAt(0)<32||ch.charCodeAt(0)===127);
 const unresolvedWrite=state.questionSaveMessage.startsWith('Save outcome unknown.');
 const stage=unresolvedWrite?'uncertain':state.composerPreview?'prepared':draft?'draft':'select';
 return <section data-testid="source-question-panel" aria-label="Source-linked question intake">
   <div className="question-flow" data-testid="question-flow" aria-label="Question preparation steps">
    <h3>Investigate a source statement</h3>
    <ol>
     <li data-stage={stage==='select'?'current':'complete'}><strong>1. Select a source</strong><span>{stage==='select'?'Choose a source statement below':'Source selected'}</span></li>
     <li data-stage={stage==='draft'?'current':stage==='select'?'waiting':stage==='uncertain'?'attention':'complete'}><strong>2. Prepare context</strong><span>{stage==='uncertain'?'Save result uncertain':stage==='prepared'?'Source context prepared':stage==='draft'?'Check the current source':'Awaiting source'}</span></li>
     <li data-stage={stage==='prepared'?'current':stage==='uncertain'?'attention':'waiting'}><strong>3. Save question</strong><span>{stage==='uncertain'?'Retry same save':stage==='prepared'?'Explicit action required':'Not yet saved'}</span></li>
    </ol>
    <p>Question intake only. No AI execution or clinical review.</p>
   </div>
   {draft&&<section className="question-draft" data-testid="question-draft-editor"
       aria-labelledby="question-draft-heading">
     <span className="step">FICTIONAL QUESTION · IN-MEMORY DRAFT</span>
     <h3 id="question-draft-heading">Write your own source-linked question</h3>
     <p>The selected source and case remain fixed. Editing requires a new authorized source check.</p>
     <details className="question-technical"><summary>Selected source and line</summary><p><code>{draft.source_id}</code> · line {draft.source_line}</p></details>
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
      <details><summary>Source-context access receipt</summary><code>{state.questionsAccessReceiptId}</code><p>Source access checked for this history read. No question or clinical approval is implied.</p></details>
      {state.questions.length===0?<p>No saved source-linked questions are visible.</p>:
       <ul className="question-items">
        {state.questions.map(item=><li key={item.question_id}>
          <div className="question-status-title">
           <strong>{item.question}</strong>
           <span className={'question-status '+(item.source_context_state==='source_reassessment_required'?'reassessment':'')}>
           {item.source_context_state==='source_reassessment_required'?
             (item.source_snapshot_contract==='oi.pg-source-world-model/1'?'Source changed — reassessment required':'Earlier source context — reassessment required'):'Current source context — unreviewed'}
           </span>
          </div>
          <details className="question-technical" data-testid="saved-question-details"><summary>Original anchor and saved question ID</summary>
           <p><strong>Original anchor:</strong> <code>{item.source_id}</code> · v{item.source_version}, line {item.source_line}.</p>
           <p><strong>Saved question:</strong> <code>{item.question_id}</code></p>
          </details>
          <details><summary>Recorded source provenance</summary>
           <p><strong>Source snapshot contract:</strong> <code>{item.source_snapshot_contract}</code></p>
           <p><strong>Original SHA-256:</strong> <code>{item.source_sha256}</code></p>
           <p><strong>Snapshot fingerprint:</strong> <code>{item.source_snapshot_sha256}</code></p>
           <p><strong>Preflight hash:</strong> <code>{item.preflight_sha256}</code></p>
          </details>
          <p className="muted">Human review not submitted. Clinical approval: none.</p>
         </li>)}</ul>}
    </div>}
   </section>
 </section>;
}
