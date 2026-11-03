/* Native Composer context preview for the EXISTING bounded investigation form.
 * No parallel chat, browser-side model calls, local persistence or authority.
 * All patient/case/source values come from the same canonical local API.
 */
(() => {
  'use strict';
  const casePicker = document.getElementById('case-picker');
  const question = document.getElementById('model-investigation-question');
  const panel = document.getElementById('composer-context');
  const hidden = document.getElementById('composer-context-fingerprint');
  const run = document.getElementById('model-investigation-run');
  if (!casePicker || !question || !panel || !hidden || !run) return;

  let requestSequence = 0;
  let shownKey = '';
  let sharedWrites = 0;
  const writesByCase = new Map();
  const hasWrites = () => sharedWrites > 0 || (writesByCase.get(casePicker.value) || 0) > 0;
  function recordWrites(detail) {
    if (!detail || !Number.isInteger(detail.pendingWrites) || detail.pendingWrites < 0) return;
    if (detail.scope === 'all-cases') sharedWrites = detail.pendingWrites;
    else if (typeof detail.caseId === 'string') {
      if (detail.pendingWrites) writesByCase.set(detail.caseId, detail.pendingWrites);
      else writesByCase.delete(detail.caseId);
    }
  }
  const affectsSelection = detail => detail?.scope === 'all-cases' || detail?.caseId === casePicker.value;

  function el(name, value, className) {
    const item = document.createElement(name);
    if (value !== undefined && value !== null) item.textContent = String(value);
    if (className) item.className = className;
    return item;
  }
  function reset(message) {
    hidden.value = '';
    run.disabled = true;
    shownKey = '';
    panel.replaceChildren(el('p', message, 'muted'));
    panel.setAttribute('aria-busy', 'true');
  }
  function section(label, text) {
    const group = document.createElement('div');
    group.append(el('strong', label), el('p', text, 'muted'));
    return group;
  }
  function render(data) {
    const sources = data.current_sources || [];
    const anchors = data.source_anchors || [];
    const assessments = data.evidence_assessments || [];
    const status = data.tool_status || {};
    const metrics = data.mission?.where_am_i || {};

    const title = el('h4', 'Composer · source-bound work context');
    const scope = el('p', 'FICTIONAL SOURCE-REVIEW WORKSPACE · ' +
      data.case_id + ' · question Q' + data.question_id, 'tiny muted');
    const mode = section('Existing patient world / mission',
      'Source-ledger projection: ' + (data.mission?.workflow_status || 'unknown') +
      '. ' + (metrics.open_questions || 0) + ' open question(s), ' +
      (metrics.stale_investigations || 0) + ' stale draft(s).');
    const coverage = section('Evidence available to this task',
      data.source_count + ' current source version(s), ' +
      anchors.length + ' source-anchored statement(s) in the preview, ' +
      data.evidence_assessment_count + ' current human-authored fictional assessment(s). ' +
      'These sources are candidates, not findings of question-specific relevance.');
    const limit = el('p', 'Cutoff: ' +
      (data.data_cutoff || 'no current source receipt') +
      '. Source versions and evidence are checked again when the work is saved.',
      'tiny muted');
    const sourceList = document.createElement('ul');
    sourceList.setAttribute('aria-label', 'Source anchors for this question');
    for (const anchor of anchors.slice(0, 6)) {
      const entry = document.createElement('li');
      const button = el('button',
        anchor.document_id + '@' + anchor.version + ', line ' +
        anchor.source_line + ' · ' + anchor.reported_state);
      button.type = 'button';
      button.className = 'button secondary';
      button.dataset.sourceId = String(anchor.source_version_id);
      button.title = 'Open exact original source and highlight the cited line';
      button.addEventListener('click', () => {
        // The existing chart owns source opening and revalidates active case
        // membership. Composer never bypasses its case/source-read gate.
        document.dispatchEvent(new CustomEvent('oi:composer-open-source', {
          detail: {caseId: data.case_id, sourceId: anchor.source_version_id,
                   line: anchor.source_line},
        }));
      });
      entry.append(button);
      sourceList.append(entry);
    }
    const missing = section('Not available in this application yet',
      'Live guidelines: ' + status.external_guideline_search +
      '. Live trial matching: ' + status.live_clinical_trials +
      '. Scientific computation: ' + status.analysis_execution +
      '. Professional authorization: ' + status.clinical_authorization + '.');
    const review = el('p',
      'Task is bounded to an existing template. Replay is recorded data; live mode ' +
      'requires a separately configured operator API key. Neither is clinical review.',
      'tiny muted');
    const warning = el('p', data.disclaimer || 'No clinical validation or medical advice.', 'muted');
    panel.replaceChildren(scope, title, mode, coverage, limit);
    if (anchors.length) panel.append(sourceList);
    if (assessments.length) {
      const list = el('p',
        'Recorded evidence assessments: ' +
        assessments.slice(0, 5).map(a =>
          '#' + a.id + ': ' + a.relation + ' (' + a.applicability + ')').join('; ') +
        '. Original evidence is inspected through the existing evidence workspace.',
        'muted');
      panel.append(list);
    }
    panel.append(missing, review, warning);
    panel.setAttribute('aria-busy', 'false');
  }

  async function refresh() {
    const seq = ++requestSequence;
    const caseId = casePicker.value;
    const qid = question.value;
    if (hasWrites()) {
      reset('Saving source or evidence changes. Context preview is unavailable until they finish.');
      panel.setAttribute('aria-busy', 'false');
      return;
    }
    reset('Checking current source versions and existing evidence for the selected case…');
    if (!caseId || !/^\d+$/.test(qid)) {
      panel.replaceChildren(el('p',
        'Choose an existing case question to preview source-bound investigation context.',
        'muted'));
      panel.setAttribute('aria-busy', 'false');
      return;
    }
    const key = caseId + ':' + qid;
    try {
      const response = await fetch('/api/cases/' + encodeURIComponent(caseId) +
        '/composer/context?question_id=' + encodeURIComponent(qid), {
        cache: 'no-store', credentials: 'same-origin',
      });
      const data = await response.json();
      if (seq !== requestSequence || casePicker.value !== caseId ||
          question.value !== qid || hasWrites()) return;
      if (!response.ok) throw new Error(data.error || 'Context is unavailable');
      if (data.case_id !== caseId || String(data.question_id) !== qid ||
          !/^[a-f0-9]{64}$/.test(data.fingerprint)) {
        throw new Error('The returned context does not match this case and question');
      }
      render(data);
      hidden.value = data.fingerprint;
      shownKey = key;
      run.disabled = false;
    } catch (error) {
      if (seq !== requestSequence || casePicker.value !== caseId ||
          question.value !== qid || hasWrites()) return;
      panel.replaceChildren(el('p',
        'Context unavailable: ' + String(error.message || error) +
        '. Investigations are disabled until the source preview succeeds.',
        'muted'));
      panel.setAttribute('aria-busy', 'false');
    }
  }

  document.addEventListener('oi:case-state-invalidated', event => {
    recordWrites(event.detail);
    if (!affectsSelection(event.detail)) return;
    ++requestSequence;
    reset('Source or evidence context changed. A new preview is required.');
    panel.setAttribute('aria-busy', 'false');
  });
  document.addEventListener('oi:case-state-write-settled', event => {
    recordWrites(event.detail);
    // Do not restore an old preview on success or failure. The accepted host
    // update, a question change or explicit refresh obtains fresh context.
  });
  document.addEventListener('oi:case-state-updated', event => {
    if (affectsSelection(event.detail)) void refresh();
  });

  // The canonical chart renderer owns the question choices. Observe its
  // existing select rather than creating a second question/task store.
  const observer = new MutationObserver(() => { void refresh(); });
  observer.observe(question, {childList: true});
  question.addEventListener('change', () => { void refresh(); });
  document.addEventListener('oi:composer-refresh', () => { void refresh(); });
  casePicker.addEventListener('change', () => {
    requestSequence += 1;
    reset('Changing fictional patient context; prior source selection cleared.');
    // Existing chart code reloads question options; observer refreshes then.
  });
  void refresh();
})();
