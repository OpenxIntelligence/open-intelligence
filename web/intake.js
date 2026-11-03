'use strict';
// Text and bounded PDF intake. All displayed passages are literal text, never markup.
(function (root) {
  function validatePdfPreview(preview) {
    const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
    const positive = value => Number.isSafeInteger(value) && value > 0;
    if (preview.media_type !== 'application/pdf' || !hash(preview.sha256) ||
        !hash(preview.extraction_sha256) || !positive(preview.page_count) ||
        preview.extractor?.name !== 'pypdf' || typeof preview.extractor.version !== 'string' ||
        !preview.extractor.version || !preview.extractor.configuration ||
        preview.extraction_method !== 'pypdf-text-v1' ||
        preview.annotation_method !== 'manual-exact-extraction-line-selection' ||
        preview.clinical_review !== 'not_performed' || !Array.isArray(preview.lines) ||
        !preview.lines.length || preview.lines.length > 512 ||
        !preview.lines.every((line, index) => line.line === index + 1 && typeof line.text === 'string' &&
          positive(line.page) && line.page <= preview.page_count && positive(line.page_line)))
      throw Error('The PDF preview is missing its extraction identity or page anchors. Preview the file again.');
  }
  function createSession({api, getCase, onChange = () => {}}) {
    let sequence = 0, payload = null;
    let current = {phase: 'idle', mode: 'upload', caseId: null, preview: null, result: null, error: ''};
    const state = () => ({...current});
    function publish(changes) { current = {...current, ...changes}; onChange(state()); }
    function sameCase(id) { try { return getCase() === id; } catch (_) { return false; } }
    function discard() {
      sequence++; payload = null;
      publish({phase: 'idle', mode: 'upload', caseId: null, preview: null, result: null, error: ''});
    }
    async function previewFile(file) {
      const ticket = ++sequence;
      payload = null;
      let requestedCase;
      try {
        requestedCase = getCase();
        publish({phase: 'loading', mode: 'upload', caseId: requestedCase, preview: null, result: null, error: ''});
        if (!file || !file.size || file.size > 65536)
          throw Error('Choose a nonempty text or PDF file up to 64 KiB.');
        if (!/\.(txt|pdf)$/i.test(file.name)) throw Error('Choose a .txt file or a text-based .pdf file. Scans and images are not supported.');
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
        if (/\.pdf$/i.test(file.name)) validatePdfPreview(preview);
        else if (preview.media_type === 'application/pdf') throw Error('Preview format does not match the selected file.');
        payload = candidate;
        publish({phase: 'ready', preview, error: ''});
      } catch (error) {
        if (ticket === sequence && (requestedCase === undefined || sameCase(requestedCase)))
          publish({phase: 'idle', preview: null, error: error.message});
      }
    }
    async function editSource(sourceId) {
      const ticket = ++sequence;
      payload = null;
      let requestedCase;
      try {
        requestedCase = getCase();
        publish({phase: 'loading', mode: 'annotations', caseId: requestedCase, preview: null, result: null, error: ''});
        if (!Number.isSafeInteger(sourceId) || sourceId <= 0) throw Error('Invalid source identifier.');
        const preview = await api('/api/cases/' + requestedCase + '/sources/' + sourceId + '/annotations');
        if (ticket !== sequence || !sameCase(requestedCase)) return;
        if (preview?.case_id !== requestedCase || preview.source_id !== sourceId ||
            !Number.isSafeInteger(preview.current_revision?.id) || preview.current_revision.id < 1 ||
            !Number.isSafeInteger(preview.current_revision?.revision) || preview.current_revision.revision < 1 ||
            !Array.isArray(preview.current_revision.findings) || !Array.isArray(preview.lines))
          throw Error('The selected source or its annotation revision is unavailable.');
        if (preview.media_type === 'application/pdf' || /\.pdf$/i.test(preview.filename)) validatePdfPreview(preview);
        publish({phase: 'ready', preview, error: ''});
      } catch (error) {
        if (ticket === sequence && (requestedCase === undefined || sameCase(requestedCase)))
          publish({phase: 'idle', preview: null, error: error.message});
      }
    }
    async function save({metadata, findings, confirmed, reason}) {
      if (current.phase === 'saving') return;
      const ticket = sequence, requestedCase = current.caseId;
      try {
        const editing = current.mode === 'annotations';
        if (!current.preview || (!editing && !payload)) throw Error('Preview a record before saving it.');
        if (!sameCase(requestedCase)) throw Error('The selected case changed. Preview the record again.');
        if (!confirmed) throw Error('Confirm the case, dates and selected passages before saving.');
        if (editing && current.preview.state !== 'current')
          throw Error('This original is superseded. Its selection history is read-only.');
        if (editing && (typeof reason !== 'string' || reason.trim().length < 3 || reason.trim().length > 500))
          throw Error('Give a reason for this change, from 3 to 500 characters.');
        const body = editing ? {
          findings, reason: reason.trim(), expected_revision: current.preview.current_revision.revision,
          expected_sha256: current.preview.sha256, confirmed_case_id: requestedCase,
          manual_transcription_confirmed: true,
        } : {
          ...payload, metadata: {...metadata, manual_transcription_confirmed: true}, findings,
          expected_sha256: current.preview.sha256, confirmed_case_id: requestedCase,
        };
        if (current.preview.media_type === 'application/pdf')
          body.expected_extraction_sha256 = current.preview.extraction_sha256;
        if (new TextEncoder().encode(JSON.stringify(body)).length > 131072)
          throw Error('The record and selected passages exceed the 128 KiB upload envelope. Keep the original intact and select fewer or shorter exact passages.');
        publish({phase: 'saving', error: ''});
        const route = editing ? '/api/cases/' + requestedCase + '/sources/' + current.preview.source_id + '/annotations'
          : '/api/cases/' + requestedCase + '/documents';
        const result = await api(route, body);
        if (ticket !== sequence || !sameCase(requestedCase)) return;
        payload = null;
        publish({phase: 'saved', result, error: ''});
      } catch (error) {
        if (ticket === sequence)
          publish({phase: current.preview && (payload || current.mode === 'annotations') ? 'ready' : 'idle', error: error.message});
      }
    }
    return {state, previewFile, editSource, save, discard,
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
      el('intake-passage-location').textContent = '';
      el('intake-annotation-history-list').replaceChildren();
    }
    function location(line, preview = shownPreview) {
      return preview?.media_type === 'application/pdf'
        ? 'page ' + line.page + ', extracted line ' + line.page_line : 'line ' + line.line;
    }
    function showLocation() {
      const line = shownPreview?.lines.find(item => item.line === Number(el('intake-line').value));
      el('intake-passage-location').textContent = line ? 'Selected from ' + location(line) + '.' : '';
    }
    const readOnly = () => session.state().mode === 'annotations' && shownPreview?.state !== 'current';
    function renderFindings() {
      const container = el('intake-passages'); container.replaceChildren();
      if (!findings.length) container.append(make('p', 'No passages selected. The original remains available. You can add exact passages later.', 'muted'));
      findings.forEach((finding, index) => {
        const card = make('article', undefined, 'intake-passage');
        const line = shownPreview.lines.find(item => item.line === finding.line);
        card.append(make('strong', finding.key + ' · User-selected: ' + finding.state + ' · ' + location(line)));
        card.append(make('p', finding.quote, 'quoted'));
        const remove = make('button', 'Remove passage', 'button secondary minor'); remove.type = 'button';
        remove.disabled = busy() || readOnly();
        remove.addEventListener('click', () => {
          if (busy() || readOnly()) return;
          findings.splice(index, 1); el('intake-confirm').checked = false; renderFindings();
        });
        card.append(remove); container.append(card);
      });
      el('intake-passage-count').textContent = findings.length + ' of 30 passages selected';
    }
    function showPreview(preview) {
      resetReview(); shownPreview = preview;
      const pdf = preview.media_type === 'application/pdf';
      if (preview.current_revision) findings = preview.current_revision.findings.map(item => ({...item}));
      el('intake-document-id').value = 'DOC-' + preview.sha256.slice(0, 12).toUpperCase();
      el('intake-review-heading').textContent = pdf ? 'Review the extracted text' : 'Review the original';
      el('intake-file-summary').textContent = preview.filename + ' · ' + preview.byte_count + ' bytes · ' +
        (pdf ? preview.page_count + ' pages · ' : '') + preview.lines.length + (pdf ? ' extracted lines' : ' lines');
      el('intake-preview-help').textContent = pdf
        ? 'This is extracted text, not the original PDF. Reading order, tables and visible content may be incomplete. Compare each passage with the original PDF before confirming. No OCR or clinical interpretation is performed.'
        : 'Select a line number to choose a passage. You can shorten it to an exact excerpt of that line.';
      el('intake-line-label').textContent = pdf ? 'Extraction line (across pages)' : 'Source line';
      el('intake-quote-label').textContent = pdf ? 'Exact extracted passage' : 'Exact source passage';
      el('intake-original-lines').setAttribute('aria-label', pdf
        ? 'Extracted PDF text with selectable page and line references' : 'Uploaded original with selectable source lines');
      el('intake-source-hash').textContent = 'Original SHA-256: ' + preview.sha256;
      el('intake-extraction-details').textContent = pdf
        ? 'Extracted-text SHA-256: ' + preview.extraction_sha256 + ' · ' + preview.extractor.name + ' ' + preview.extractor.version
        : '';
      el('intake-case-label').textContent = preview.case_id;
      if (preview.current_revision) {
        const current = preview.current_revision;
        el('intake-revision-summary').textContent = preview.document_id + '@' + preview.version +
          ' · Selection revision ' + current.revision + '. ' + (preview.state === 'current'
            ? 'Changing passages keeps the original file and earlier selections.'
            : 'This original has been superseded. Its selection history is read-only.');
        for (const revision of [...(preview.history || [])].reverse()) {
          const card = make('article', undefined, 'intake-passage');
          card.append(make('strong', 'Selection revision ' + revision.revision),
            make('p', revision.reason || 'Initial transcription confirmation', 'muted'),
            make('p', revision.confirmed_at || '', 'muted tiny'));
          if (!revision.findings.length) card.append(make('p', 'Original saved without selected passages.', 'muted'));
          for (const finding of revision.findings)
            card.append(make('p', finding.key + ' · User-selected: ' + finding.state + ' · ' +
              location(preview.lines.find(line => line.line === finding.line), preview), 'muted tiny'),
              make('p', finding.quote, 'quoted'));
          el('intake-annotation-history-list').append(card);
        }
      }
      for (const line of preview.lines) {
        const row = make('div', undefined, 'intake-source-line' + (pdf ? ' intake-source-line-pdf' : ''));
        const select = make('button', pdf ? 'Page ' + line.page + '\nLine ' + line.page_line : String(line.line), 'intake-line-select'); select.type = 'button';
        select.setAttribute('aria-label', 'Select passage from ' + location(line, preview));
        select.setAttribute('data-line', line.line);
        if (pdf) select.setAttribute('data-page', line.page);
        select.disabled = !line.text.trim() || readOnly();
        select.addEventListener('click', () => {
          if (busy() || readOnly()) return;
          el('intake-line').value = line.line;
          // Long lines require the user to choose a shorter exact excerpt.
          el('intake-quote').value = line.text;
          el('intake-key').value = 'finding-' + (findings.length + 1);
          el('intake-status').value = '';
          showLocation();
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
      const editing = state.mode === 'annotations';
      if (state.preview && state.preview !== shownPreview) showPreview(state.preview);
      el('intake-upload-fields').disabled = saving || loading || (editing && state.phase === 'ready');
      el('intake-metadata-fields').disabled = saving || readOnly();
      el('intake-passage-fields').disabled = saving || readOnly();
      el('intake-discard').disabled = saving;
      el('intake-discard').textContent = editing ? 'Close selection review without saving' : 'Discard this intake';
      el('intake-review').hidden = !state.preview || state.phase === 'saved';
      el('intake-record-details').hidden = editing;
      for (const input of el('intake-record-details').querySelectorAll('input, select')) input.disabled = editing;
      el('intake-revision-fields').hidden = !editing;
      el('intake-revision-reason').disabled = !editing;
      el('intake-revision-reason').required = editing;
      el('intake-revision-summary').hidden = !editing;
      el('intake-annotation-history').hidden = !editing;
      el('intake-preview-button').textContent = loading ? 'Reading record…' : 'Preview record';
      el('intake-save').textContent = editing ? (saving ? 'Saving revision…' : 'Save passage revision') :
        saving ? 'Adding record…' : 'Add record to this case';
      const message = el('intake-message');
      message.className = state.error ? 'notice error' : 'muted';
      message.textContent = state.error || (loading ? 'Reading the original file and its saved selections…' :
        saving ? 'Saving the original and the passages you confirmed…' :
          state.phase === 'ready' ? 'Check the record details and select any passages you want to track.' : '');
      if (saving && editing) message.textContent = 'Saving your selection revision and checking affected investigations…';
      if (state.phase === 'ready') renderFindings();
      if (state.phase === 'saved' && state.result !== savedReceipt) {
        savedReceipt = state.result;
        const duplicate = state.result.result === 'duplicate';
        message.textContent = editing ? (state.result.result === 'unchanged' ? 'The selections are unchanged. No revision was added.' :
          'Selection revision ' + state.result.annotation_revision + ' saved. Earlier selections and original bytes are preserved.') :
          duplicate ? 'This record is already saved. The original confirmation has been kept.' :
          'Record added. The original and your confirmed passages are now in this case.';
        if (editing && state.result.invalidated_snapshots?.length)
          message.textContent += ' ' + state.result.invalidated_snapshots.length + ' saved investigation(s) now need another review.';
        const actions = el('intake-success-actions'); actions.replaceChildren();
        const stillCurrent = () => {
          try { return savedReceipt === state.result && shownCase === state.caseId && getCase() === state.caseId; }
          catch (_) { return false; }
        };
        const view = make('button', state.preview.media_type === 'application/pdf' ? 'Read extracted text' : 'Open original', 'button secondary'); view.type = 'button';
        view.addEventListener('click', async () => {
          if (!stillCurrent()) return;
          try { await onSource(state.result.source_id); }
          catch (error) { if (stillCurrent()) message.textContent = error.message; }
        });
        const timeline = make('a', 'View timeline', 'button secondary'); timeline.href = '#timeline';
        const question = make('button', 'Ask a question about this record', 'button'); question.type = 'button';
        question.addEventListener('click', () => { if (stillCurrent()) onQuestion(state.result.source_id); });
        const revise = make('button', 'Review saved passages', 'button secondary'); revise.type = 'button';
        revise.addEventListener('click', () => { if (stillCurrent()) session.editSource(state.result.source_id); });
        actions.append(view, timeline, question, revise);
        el('intake-file').value = '';
        // Refresh the existing source, question and Composer projections.
        Promise.resolve(onImported(state.result)).catch(error => {
          if (stillCurrent())
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
      event.preventDefault(); if (busy() || readOnly() || !shownPreview) return;
      const finding = {key: el('intake-key').value.trim(), state: el('intake-status').value,
        quote: el('intake-quote').value, line: Number(el('intake-line').value)};
      const line = shownPreview.lines.find(item => item.line === finding.line);
      let error = '';
      if (findings.length >= 30) error = 'This record already has 30 selected passages.';
      else if (!line || !finding.quote.trim() || !line.text.includes(finding.quote)) error = 'Choose an exact passage from the indicated line in this preview.';
      else if (finding.quote.length > 1200) error = 'Choose an exact passage of at most 1,200 characters.';
      else if (findings.some(item => item.key === finding.key)) error = 'Use a different finding tag for this passage.';
      if (error) { el('intake-passage-message').textContent = error; return; }
      findings.push(finding); el('intake-confirm').checked = false; renderFindings();
      el('intake-passage-form').reset();
      showLocation();
      el('intake-passage-message').textContent = 'Passage added to this review. Confirm and save to keep the selection.';
    });
    el('intake-line').addEventListener('input', showLocation);
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
      session.save({metadata, findings: findings.map(item => ({...item})), confirmed: el('intake-confirm').checked,
        reason: el('intake-revision-reason').value});
    });
    render(session.state());
    return {
      hasDraft: () => session.hasDraft() || Boolean(el('intake-file').files.length),
      async editSource(sourceId) {
        if (session.hasDraft() || el('intake-file').files.length)
          throw Error('Save or discard the current record review before opening another one.');
        await session.editSource(sourceId);
        if (session.state().phase === 'ready') el('intake-review').scrollIntoView({block: 'start'});
      },
      syncCase(id) {
        if (shownCase !== id) { shownCase = id; session.discard(); resetReview(); el('intake-file').value = ''; }
      },
    };
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {createSession};
  if (root) root.OpenIntelligenceIntake = {createSession, mount};
})(typeof window !== 'undefined' ? window : null);
