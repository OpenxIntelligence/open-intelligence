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
    const externalEvidence = data.external_evidence || [];
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
    const evidenceSection = document.createElement('section');
    evidenceSection.className = 'composer-external-evidence';
    evidenceSection.setAttribute('aria-label', 'External evidence for this question');
    evidenceSection.append(el('h4', 'External evidence for this question'));
    evidenceSection.append(el('p',
      'Source permissions are recorded declarations. Display permission and AI processing ' +
      'permission are checked separately. A citation or search result alone is not clinical evidence.',
      'tiny muted'));
    if (!externalEvidence.length) {
      evidenceSection.append(el('p', 'No external evidence is linked to this question.', 'muted'));
    }
    for (const evidence of externalEvidence) {
      const item = document.createElement('article');
      item.className = 'composer-evidence-item';
      item.dataset.brokerId = String(evidence.id);
      item.dataset.modelEligible = String(Boolean(evidence.model_eligible));
      item.append(el('strong', 'Evidence #' + evidence.id + ' · ' +
        evidence.source_key + ' · ' + evidence.version_label));
      item.append(el('p',
        'Relation: ' + evidence.relation + ' · Applicability: ' + evidence.applicability +
        ' · Rights: ' + evidence.rights_state, 'tiny muted'));
      if (evidence.citation_title) item.append(el('p', evidence.citation_title));
      if (evidence.excerpt) item.append(el('blockquote', evidence.excerpt));
      if (evidence.rationale) item.append(el('p', 'Assessment: ' + evidence.rationale, 'muted'));
      item.append(el('p', evidence.model_eligible
        ? 'Eligible for AI context under the recorded permissions; inclusion is subject to the task input limit.'
        : 'Excluded from AI context: ' + (evidence.withheld_reason || 'permission or usable source content is missing'),
      'tiny muted'));
      evidenceSection.append(item);
    }
    panel.append(evidenceSection);
    panel.append(missing, review, warning);

    // One actual read-only numeric tool. This is not the unavailable
    // specialist scientific pipeline advertised above. No new chat backend.
    const labIds = new Set(sources.filter(s => s.kind === 'laboratory').map(s => s.id));
    const labKeys = [...new Set(anchors.filter(a =>
      labIds.has(a.source_version_id) && /^OI-LAB-VALUE\/1;/.test(a.statement || '')
    ).map(a => a.finding_key))].sort();
    const labSection = document.createElement('section');
    labSection.className = 'composer-lab-tool';
    labSection.append(el('h4', 'Try a source-grounded numeric lab comparison'));
    labSection.append(el('p',
      'Read-only fictional source values. No unit conversion, clinical meaning, or verified laboratory QC.',
      'tiny muted'));
    if (labKeys.length) {
      const selector = document.createElement('select');
      selector.setAttribute('aria-label', 'Synthetic laboratory finding');
      for (const key of labKeys) {
        const option = el('option', key);
        option.value = key;
        selector.append(option);
      }
      const invoke = el('button', 'Calculate numerical change', 'button secondary');
      invoke.type = 'button';
      const output = document.createElement('div');
      output.setAttribute('aria-live', 'polite');
      output.className = 'composer-lab-result';
      invoke.addEventListener('click', async () => {
        const requestId = requestSequence;
        const requestCase = data.case_id;
        const requestQuestion = String(data.question_id);
        const requestFingerprint = data.fingerprint;
        if (shownKey !== requestCase + ':' + requestQuestion ||
            hidden.value !== requestFingerprint ||
            casePicker.value !== requestCase || question.value !== requestQuestion) return;
        invoke.disabled = true;
        output.replaceChildren(el('p', 'Running local synthetic numeric validation…', 'muted'));
        try {
          const params = new URLSearchParams({
            question_id: requestQuestion,
            context_fingerprint: requestFingerprint,
            finding_key: selector.value,
          });
          const response = await fetch('/api/cases/' + encodeURIComponent(requestCase) +
            '/composer/tools/lab-trend?' + params, {
            cache: 'no-store', credentials: 'same-origin',
          });
          const payload = await response.json();
          if (requestId !== requestSequence || casePicker.value !== requestCase ||
              question.value !== requestQuestion ||
              hidden.value !== requestFingerprint ||
              shownKey !== requestCase + ':' + requestQuestion) return;
          if (!response.ok) throw new Error(payload.error || 'Tool unavailable');
          if (payload.context_fingerprint !== requestFingerprint ||
              payload.result?.case_id !== requestCase) {
            throw new Error('Calculated result does not match the selected case context');
          }
          output.replaceChildren(el('p',
            'Tool status: ' + payload.status + '. ' + payload.execution_receipt +
            '. Clinical interpretation: ' + payload.clinical_interpretation + '.', 'tiny muted'));
          if (payload.status === 'computed') {
            output.append(el('p', 'Numerical difference: ' +
              payload.result.delta + ' ' + payload.result.unit + ' (' +
              payload.result.direction + '). This is not clinical significance.'));
          }
          for (const item of payload.result.points || []) {
            const source = item.source;
            const sourceButton = el('button',
              source.document_id + '@' + source.source_version +
              ' · line ' + source.source_line + ' · ' + item.value + ' ' + item.unit,
              'button secondary minor');
            sourceButton.type = 'button';
            sourceButton.addEventListener('click', () => {
              document.dispatchEvent(new CustomEvent('oi:composer-open-source', {
                detail: {caseId: requestCase,
                         sourceId: source.source_version_id, line: source.source_line},
              }));
            });
            output.append(sourceButton);
          }
          if (payload.result.holds?.length) {
            output.append(el('p',
              'No numerical conclusion: ' + payload.result.holds.map(x => x.reason).join('; '),
              'muted'));
          }
          output.append(el('p', payload.disclaimer, 'tiny muted'));
        } catch (error) {
          if (requestId === requestSequence && casePicker.value === requestCase &&
              question.value === requestQuestion) {
            output.replaceChildren(el('p',
              'Calculation unavailable: ' + String(error.message || error) +
              '. Refresh context if source versions changed.', 'muted'));
          }
        } finally {
          if (requestId === requestSequence && casePicker.value === requestCase &&
              question.value === requestQuestion) invoke.disabled = false;
        }
      });
      labSection.append(selector, invoke, output);

      const save = el('button', 'Queue and execute as saved work', 'button secondary');
      save.type = 'button';
      save.className = 'button secondary composer-save-run';
      const saveStatus = el('p', 'Saving a work item records an actual calculation and its source version.', 'tiny muted');
      const savedList = document.createElement('div');
      savedList.className = 'composer-saved-runs';
      savedList.setAttribute('aria-live', 'polite');
      labSection.append(save, saveStatus, savedList);
      const session = requestSequence;
      const caseScope = data.case_id;
      const questionScope = String(data.question_id);
      const token = data.fingerprint;
      const stillScoped = () => requestSequence === session &&
        casePicker.value === caseScope && question.value === questionScope &&
        hidden.value === token && shownKey === caseScope + ':' + questionScope;

      async function sendJson(path, payload) {
        const response = await fetch(path, {
          method: 'POST', cache: 'no-store', credentials: 'same-origin',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Work request failed');
        return result;
      }
      const runsEndpoint = '/api/cases/' + encodeURIComponent(caseScope) + '/composer/runs';
      async function loadSavedRuns() {
        const currentSeq = requestSequence;
        try {
          const response = await fetch(runsEndpoint, {cache: 'no-store', credentials: 'same-origin'});
          const data = await response.json();
          if (!stillScoped() || currentSeq !== requestSequence) return;
          if (!response.ok) throw new Error(data.error || 'Work history unavailable');
          savedList.replaceChildren(el('h4', 'Saved work sessions'));
          const forQuestion = (data.runs || []).filter(item =>
            item.case_id === caseScope && String(item.question_id) === questionScope
          ).slice(0, 8);
          if (!forQuestion.length) {
            savedList.append(el('p', 'No saved numerical work for this question.', 'tiny muted'));
            return;
          }
          for (const item of forQuestion) {
            const entry = document.createElement('div');
            entry.className = 'composer-saved-entry';
            entry.append(el('p', 'Run #' + item.run_id + ' · ' + item.state +
              ' · ' + item.finding_key + ' · ' + (item.updated_at || 'time unknown'), 'tiny'));
            const numeric = item.result?.result;
            if (numeric?.status === 'computed') {
              entry.append(el('p', 'Recorded numeric difference: ' + numeric.delta +
                ' ' + numeric.unit + ' (historical; inspect current source status).', 'tiny muted'));
            } else if (item.failure_code) {
              entry.append(el('p', 'Held/changed: ' + item.failure_code, 'tiny muted'));
            }
            if (item.state === 'queued') {
              const cancel = el('button', 'Cancel queued run', 'button secondary minor');
              cancel.type = 'button';
              cancel.addEventListener('click', async () => {
                if (!stillScoped()) return;
                cancel.disabled = true;
                try {
                  await sendJson(runsEndpoint + '/' + item.run_id + '/cancel', {});
                  if (stillScoped()) await loadSavedRuns();
                } catch (error) {
                  if (stillScoped()) saveStatus.textContent = 'Cancellation unavailable: ' +
                    String(error.message || error);
                }
              });
              entry.append(cancel);
            }
            savedList.append(entry);
          }
        } catch (error) {
          if (stillScoped()) savedList.replaceChildren(el('p',
            'Saved work unavailable: ' + String(error.message || error), 'muted'));
        }
      }
      save.addEventListener('click', async () => {
        if (!stillScoped()) return;
        save.disabled = true;
        saveStatus.textContent = 'Recording and executing a source-bound synthetic work item…';
        try {
          const queued = await sendJson(runsEndpoint, {
            question_id: Number(questionScope),
            context_fingerprint: token, finding_key: selector.value,
            idempotency_key: 'work-' + crypto.randomUUID(),
          });
          if (!stillScoped()) return;
          const finished = await sendJson(runsEndpoint + '/' + queued.run_id + '/execute', {});
          if (!stillScoped()) return;
          saveStatus.textContent = 'Saved run #' + finished.run_id + ': ' + finished.state +
            '. Clinical review: ' + finished.clinical_review_state + '.';
          await loadSavedRuns();
        } catch (error) {
          if (stillScoped()) saveStatus.textContent =
            'Saved work unavailable: ' + String(error.message || error);
        } finally {
          if (stillScoped()) save.disabled = false;
        }
      });
      // Rendering happens just before the context token is installed. Defer
      // history fetch to the next microtask, then verify its exact scope.
      queueMicrotask(() => { if (stillScoped()) void loadSavedRuns(); });
    } else {
      labSection.append(el('p',
        'No OI-LAB-VALUE/1 fictional laboratory measurements in the current source preview.',
        'tiny muted'));
    }
    panel.append(labSection);
    panel.setAttribute('aria-busy', 'false');
  }

  async function refresh() {
    const seq = ++requestSequence;
    const caseId = casePicker.value;
    const qid = question.value;
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
          question.value !== qid) return;
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
          question.value !== qid) return;
      panel.replaceChildren(el('p',
        'Context unavailable: ' + String(error.message || error) +
        '. Investigations are disabled until the source preview succeeds.',
        'muted'));
      panel.setAttribute('aria-busy', 'false');
    }
  }

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
