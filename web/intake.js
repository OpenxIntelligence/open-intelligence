'use strict';
// Ordinary text-file intake. All source text is rendered as text, never markup.
(function (root) {
  function createSession({api, getCase, onChange = () => {}}) {
    let sequence = 0, payload = null;
    let current = {phase: 'idle', caseId: null, preview: null, result: null, error: ''};
    const state = () => ({...current});
    function publish(changes) { current = {...current, ...changes}; onChange(state()); }
    function sameCase(id) { try { return getCase() === id; } catch (_) { return false; } }
    function discard() {
      sequence++; payload = null;
      publish({phase: 'idle', caseId: null, preview: null, result: null, error: ''});
    }
    async function previewFile(file) {
      const ticket = ++sequence;
      payload = null;
      let requestedCase;
      try {
        requestedCase = getCase();
        publish({phase: 'loading', caseId: requestedCase, preview: null, result: null, error: ''});
        if (!file || !file.size || file.size > 65536)
          throw Error('Choose a nonempty UTF-8 text file up to 64 KiB.');
        if (!/\.txt$/i.test(file.name)) throw Error('Choose a .txt file. PDF and image files are not supported yet.');
        const bytes = new Uint8Array(await file.arrayBuffer());
        if (ticket !== sequence || !sameCase(requestedCase)) return;
        if (!bytes.length || bytes.length > 65536) throw Error('The file must be nonempty and at most 64 KiB.');
        // Base64 preserves bytes that text decoding would normalize or strip.
        let binary = '';
        for (const byte of bytes) binary += String.fromCharCode(byte);
        const candidate = {filename: file.name, content_base64: btoa(binary)};
        const preview = await api('/api/cases/' + requestedCase + '/documents/preview', candidate);
        if (ticket !== sequence || !sameCase(requestedCase)) return;
        if (preview.case_id !== requestedCase) throw Error('Preview case does not match the selected case.');
        payload = candidate;
        publish({phase: 'ready', preview, error: ''});
      } catch (error) {
        if (ticket === sequence && (requestedCase === undefined || sameCase(requestedCase)))
          publish({phase: 'idle', preview: null, error: error.message});
      }
    }
    async function save({metadata, findings, confirmed}) {
      if (current.phase === 'saving') return;
      const ticket = sequence, requestedCase = current.caseId;
      try {
        if (!payload || !current.preview) throw Error('Preview a record before saving it.');
        if (!sameCase(requestedCase)) throw Error('The selected case changed. Preview the record again.');
        if (!confirmed) throw Error('Confirm the case, dates and selected passages before saving.');
        const body = {
          ...payload, metadata: {...metadata, manual_transcription_confirmed: true}, findings,
          expected_sha256: current.preview.sha256, confirmed_case_id: requestedCase,
        };
        if (new TextEncoder().encode(JSON.stringify(body)).length > 131072)
          throw Error('The record and selected passages exceed the 128 KiB upload envelope. Keep the original intact and select fewer or shorter exact passages.');
        publish({phase: 'saving', error: ''});
        const result = await api('/api/cases/' + requestedCase + '/documents', body);
        if (ticket !== sequence || !sameCase(requestedCase)) return;
        payload = null;
        publish({phase: 'saved', result, error: ''});
      } catch (error) {
        if (ticket === sequence) publish({phase: payload ? 'ready' : 'idle', error: error.message});
      }
    }
    return {state, previewFile, save, discard,
      hasDraft: () => ['loading', 'ready', 'saving'].includes(current.phase)};
  }

  function mount({api, getCase, onImported, onSource, onQuestion}) {
    const el = id => document.getElementById(id);
    const make = (tag, text, className) => {
      const item = document.createElement(tag);
      if (text !== undefined) item.textContent = text;
      if (className) item.className = className;
      return item;
    };
    let findings = [], shownPreview = null, shownCase = null, savedReceipt = null;
    const session = createSession({api, getCase, onChange: render});
    function busy() { return ['loading', 'saving'].includes(session.state().phase); }
    function resetReview() {
      findings = []; shownPreview = null; savedReceipt = null;
      el('intake-metadata-form').reset(); el('intake-passage-form').reset();
      el('intake-passages').replaceChildren(); el('intake-original-lines').replaceChildren();
      el('intake-success-actions').replaceChildren();
    }
    function renderFindings() {
      const container = el('intake-passages'); container.replaceChildren();
      if (!findings.length) container.append(make('p', 'No passages selected. You can save the original without findings. Passage editing after saving is not available yet.', 'muted'));
      findings.forEach((finding, index) => {
        const card = make('article', undefined, 'intake-passage');
        card.append(make('strong', finding.key + ' · ' + finding.state + ' · line ' + finding.line));
        card.append(make('p', finding.quote, 'quoted'));
        const remove = make('button', 'Remove passage', 'button secondary minor'); remove.type = 'button';
        remove.addEventListener('click', () => {
          if (busy()) return;
          findings.splice(index, 1); el('intake-confirm').checked = false; renderFindings();
        });
        card.append(remove); container.append(card);
      });
      el('intake-passage-count').textContent = findings.length + ' of 30 passages selected';
    }
    function showPreview(preview) {
      resetReview(); shownPreview = preview;
      el('intake-document-id').value = 'DOC-' + preview.sha256.slice(0, 12).toUpperCase();
      el('intake-file-summary').textContent = preview.filename + ' · ' + preview.byte_count + ' bytes · ' + preview.lines.length + ' lines';
      el('intake-source-hash').textContent = 'SHA-256: ' + preview.sha256;
      el('intake-case-label').textContent = preview.case_id;
      for (const line of preview.lines) {
        const row = make('div', undefined, 'intake-source-line');
        const select = make('button', String(line.line), 'intake-line-select'); select.type = 'button';
        select.setAttribute('aria-label', 'Select passage from line ' + line.line);
        select.disabled = !line.text.trim();
        select.addEventListener('click', () => {
          if (busy()) return;
          el('intake-line').value = line.line;
          // Long lines require the user to choose a shorter exact excerpt.
          el('intake-quote').value = line.text;
          el('intake-key').value = 'finding-' + (findings.length + 1);
          el('intake-status').value = '';
          el('intake-passage-message').textContent = line.text.length > 1200
            ? 'Shorten the passage to an exact excerpt of at most 1,200 characters.' : 'Choose a status for what this passage reports.';
          el('intake-quote').focus();
        });
        row.append(select, make('span', line.text)); el('intake-original-lines').append(row);
      }
      renderFindings();
    }
    function render(state) {
      const saving = state.phase === 'saving', loading = state.phase === 'loading';
      el('intake-upload-fields').disabled = saving || loading;
      el('intake-metadata-fields').disabled = saving;
      el('intake-passage-fields').disabled = saving;
      el('intake-discard').disabled = saving;
      el('intake-review').hidden = !state.preview || state.phase === 'saved';
      el('intake-preview-button').textContent = loading ? 'Reading record…' : 'Preview record';
      el('intake-save').textContent = saving ? 'Adding record…' : 'Add record to this case';
      const message = el('intake-message');
      message.className = state.error ? 'notice error' : 'muted';
      message.textContent = state.error || (loading ? 'Reading the original file. Nothing has been added to the case.' :
        saving ? 'Saving the original and the passages you confirmed…' :
          state.phase === 'ready' ? 'Check the record details and select any passages you want to track.' : '');
      if (state.preview && state.preview !== shownPreview) showPreview(state.preview);
      if (state.phase === 'saved' && state.result !== savedReceipt) {
        savedReceipt = state.result;
        const duplicate = state.result.result === 'duplicate';
        message.textContent = duplicate ? 'This record is already saved. The original confirmation has been kept.' :
          'Record added. The original and your confirmed passages are now in this case.';
        const actions = el('intake-success-actions'); actions.replaceChildren();
        const stillCurrent = () => {
          try { return savedReceipt === state.result && shownCase === state.caseId && getCase() === state.caseId; }
          catch (_) { return false; }
        };
        const view = make('button', 'Open original', 'button secondary'); view.type = 'button';
        view.addEventListener('click', async () => {
          if (!stillCurrent()) return;
          try { await onSource(state.result.source_id); }
          catch (error) { if (stillCurrent()) message.textContent = error.message; }
        });
        const timeline = make('a', 'View timeline', 'button secondary'); timeline.href = '#timeline';
        const question = make('button', 'Ask a question about this record', 'button'); question.type = 'button';
        question.addEventListener('click', () => { if (stillCurrent()) onQuestion(state.result.source_id); });
        actions.append(view, timeline, question);
        el('intake-file').value = '';
        // Refresh the existing source, question and Composer projections.
        Promise.resolve(onImported(state.result)).catch(error => {
          if (savedReceipt === state.result && shownCase === state.caseId)
            message.textContent += ' Refresh the case to load its updated timeline: ' + error.message;
        });
      }
    }
    el('intake-upload-form').addEventListener('submit', event => {
      event.preventDefault(); if (busy()) return;
      resetReview(); session.previewFile(el('intake-file').files[0]);
    });
    el('intake-file').addEventListener('change', () => { session.discard(); resetReview(); });
    el('intake-discard').addEventListener('click', () => {
      if (busy() && session.state().phase === 'saving') return;
      session.discard(); resetReview(); el('intake-file').value = '';
    });
    el('intake-passage-form').addEventListener('submit', event => {
      event.preventDefault(); if (busy() || !shownPreview) return;
      const finding = {key: el('intake-key').value.trim(), state: el('intake-status').value,
        quote: el('intake-quote').value, line: Number(el('intake-line').value)};
      const line = shownPreview.lines.find(item => item.line === finding.line);
      let error = '';
      if (findings.length >= 30) error = 'This record already has 30 selected passages.';
      else if (!line || !finding.quote.trim() || !line.text.includes(finding.quote)) error = 'Choose an exact passage from the indicated original line.';
      else if (finding.quote.length > 1200) error = 'Choose an exact passage of at most 1,200 characters.';
      else if (findings.some(item => item.key === finding.key)) error = 'Use a different finding tag for this passage.';
      if (error) { el('intake-passage-message').textContent = error; return; }
      findings.push(finding); el('intake-confirm').checked = false; renderFindings();
      el('intake-passage-form').reset();
      el('intake-passage-message').textContent = 'Passage added to this review. It will be saved with the record.';
    });
    el('intake-metadata-form').addEventListener('input', event => {
      if (event.target !== el('intake-confirm')) el('intake-confirm').checked = false;
    });
    el('intake-metadata-form').addEventListener('submit', event => {
      event.preventDefault(); if (busy()) return;
      const metadata = {document_id: el('intake-document-id').value.trim(), kind: el('intake-kind').value,
        event_date: el('intake-event-date').value, issued_at: el('intake-issued-date').value};
      const specimen = el('intake-specimen').value.trim(), amendment = el('intake-amends').value;
      if (specimen) metadata.specimen_id = specimen;
      if (amendment) metadata.amends_version = Number(amendment);
      session.save({metadata, findings: findings.map(item => ({...item})), confirmed: el('intake-confirm').checked});
    });
    render(session.state());
    return {
      hasDraft: () => session.hasDraft() || Boolean(el('intake-file').files.length),
      syncCase(id) {
        if (shownCase !== id) { shownCase = id; session.discard(); resetReview(); el('intake-file').value = ''; }
      },
    };
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {createSession};
  if (root) root.OpenIntelligenceIntake = {createSession, mount};
})(typeof window !== 'undefined' ? window : null);
