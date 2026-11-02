'use strict';
// One synthetic case's record-acquisition tasks; source authority stays in CaseStore.
(() => {
  const $ = id => document.getElementById(id);
  const picker = $('case-picker'), panel = $('record-acquisition');
  const list = $('record-request-list'), status = $('record-request-status');
  const form = $('record-request-form');
  if (![picker, panel, list, status, form].every(Boolean)) return;

  let generation = 0, creating = false, idempotencyKey = null, scheduled = false;
  function node(tag, value, className = '') {
    const el = document.createElement(tag);
    if (value !== undefined) el.textContent = String(value);
    if (className) el.className = className;
    return el;
  }
  function clear(message = '') {
    list.replaceChildren();
    status.textContent = message;
  }
  function caseId() { return picker.value || null; }
  async function request(url, body) {
    const opts = {cache: 'no-store'};
    if (body) {
      opts.method = 'POST';
      opts.headers = {'Content-Type': 'application/json'};
      opts.body = JSON.stringify(body);
    }
    const response = await fetch(url, opts);
    const data = await response.json();
    if (!response.ok) throw Error(data?.error || 'Record request failed');
    return data;
  }
  const route = id => '/api/cases/' + encodeURIComponent(id) + '/record-requests';
  function attachRow(requestRecord, state, capturedGeneration, selected) {
    const row = node('article', undefined, 'source-card patient-record-item');
    const head = node('div', undefined, 'finding-head');
    head.append(node('strong', requestRecord.label),
      node('span', requestRecord.receipt_state.replaceAll('_', ' '), 'pill pill-neutral'));
    row.append(head, node('p', 'Category: ' + requestRecord.kind +
      ' · Requested from: ' + requestRecord.organization +
      ' · Request reference: #' + requestRecord.id, 'source-meta'));
    const matches = state.sources.filter(item => item.state === 'current' &&
      item.kind === requestRecord.kind &&
      (!requestRecord.received_source_id ||
       (requestRecord.receipt_state === 'source_superseded_reconciliation_needed'
        ? item.document_id === requestRecord.document_id
        : item.id === requestRecord.received_source_id)));
    if (requestRecord.status === 'received' && requestRecord.receipt_state === 'source_current') {
      row.append(node('p', 'Linked original: ' + requestRecord.document_id +
        ' v' + requestRecord.document_version + ' · SHA-256 ' +
        requestRecord.source_sha256 + '. Receipt does not establish clinical verification.', 'source-meta'));
    }
    if (requestRecord.status !== 'cancelled' &&
        requestRecord.receipt_state !== 'source_current') {
      if (requestRecord.receipt_state === 'source_superseded_reconciliation_needed')
        row.append(node('p', 'Earlier linked source was amended. Select the exact newer original to reconcile this request.', 'muted'));
      if (matches.length) {
        const select = node('select');
        select.setAttribute('aria-label', 'Choose source for request ' + requestRecord.id);
        for (const original of matches) {
          const option = node('option', original.document_id + ' v' + original.version +
            ' · source #' + original.id);
          option.value = String(original.id);
          select.append(option);
        }
        const action = node('button', requestRecord.status === 'received'
          ? 'Reconcile amended original' : 'Mark received with selected original', 'button secondary minor');
        action.type = 'button';
        action.addEventListener('click', async () => {
          if (generation !== capturedGeneration || caseId() !== selected || action.disabled) return;
          const source = Number(select.value);
          if (!Number.isSafeInteger(source) || source < 1) return;
          action.disabled = true;
          try {
            await request(route(selected) + '/' + requestRecord.id + '/receive', {source_version_id: source});
            if (generation === capturedGeneration && caseId() === selected) await refresh();
          } catch (_) {
            if (generation === capturedGeneration && caseId() === selected)
              status.textContent = 'Could not link this source; review the current record and try again.';
            action.disabled = false;
          }
        });
        row.append(select, action);
      } else {
        row.append(node('p', 'No matching current original is supplied here. Import and inspect it first.', 'muted'));
      }
    }
    if (requestRecord.status === 'requested') {
      const reason = node('input');
      reason.maxLength = 200;
      reason.placeholder = 'Why is this request no longer needed?';
      reason.setAttribute('aria-label', 'Cancellation reason for request ' + requestRecord.id);
      const cancel = node('button', 'Cancel request', 'button secondary minor');
      cancel.type = 'button';
      cancel.addEventListener('click', async () => {
        if (generation !== capturedGeneration || caseId() !== selected ||
            cancel.disabled || !reason.value.trim()) return;
        cancel.disabled = true;
        try {
          await request(route(selected) + '/' + requestRecord.id + '/cancel', {reason: reason.value});
          if (generation === capturedGeneration && caseId() === selected) await refresh();
        } catch (_) {
          if (generation === capturedGeneration && caseId() === selected)
            status.textContent = 'Could not cancel the request. Please retry.';
          cancel.disabled = false;
        }
      });
      row.append(reason, cancel);
    }
    list.append(row);
  }

  async function refresh() {
    const selected = caseId(), token = ++generation;
    clear(selected ? 'Loading record request history…' : 'Select or create a fictional case first.');
    if (!selected) return;
    try {
      const [acquisition, state] = await Promise.all([
        request(route(selected)), request('/api/cases/' + encodeURIComponent(selected) + '/state')
      ]);
      if (token !== generation || caseId() !== selected) return;
      if (acquisition.contract !== 'oi.synthetic-record-acquisition/1' ||
          acquisition.case_id !== selected || acquisition.synthetic !== true ||
          state.case.case_id !== selected ||
          !Array.isArray(acquisition.requests) || !Array.isArray(state.sources)) {
        throw Error('Record acquisition scope mismatch');
      }
      clear(acquisition.requests.length + ' local request(s) recorded. No external contact was made.');
      if (!acquisition.requests.length) list.append(node('p',
        'No records have been requested in this fictional workspace.', 'muted'));
      for (const item of acquisition.requests) attachRow(item, state, token, selected);
    } catch (_) {
      if (token === generation && caseId() === selected)
        clear('Record requests unavailable. No records or statuses were changed by this view.');
    }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const selected = caseId();
    if (!selected || creating) return;
    creating = true;
    $('record-request-submit').disabled = true;
    idempotencyKey ||= 'REQUEST-' + crypto.randomUUID().toUpperCase();
    try {
      await request(route(selected), {
        request_key: idempotencyKey,
        label: $('record-request-label').value,
        organization: $('record-request-from').value,
        kind: $('record-request-kind').value
      });
      if (caseId() === selected) {
        idempotencyKey = null;
        form.reset();
        await refresh();
      }
    } catch (_) {
      if (caseId() === selected)
        status.textContent = 'Could not save request. Details remain here for a safe retry.';
    } finally {
      creating = false;
      $('record-request-submit').disabled = false;
    }
  });
  picker.addEventListener('change', () => {
    idempotencyKey = null;
    refresh();
  });
  const sourceList = $('source-list');
  if (sourceList) {
    new MutationObserver(() => {
      if (scheduled || !panel.open) return;
      scheduled = true;
      queueMicrotask(() => {scheduled = false; refresh();});
    }).observe(sourceList, {childList: true});
  }
  panel.addEventListener('toggle', () => { if (panel.open) refresh(); });
  refresh();
})();
