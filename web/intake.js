/* Case/file intake over the existing local reference APIs. No new patient store.
 * Only explicitly authored fictional OI-SYNTHETIC-REPORT/1 text is supported.
 */
(function () {
  'use strict';
  const MAX_FILE = 65536, MAX_FILES = 20, MAX_BATCH = 1048576;
  const CASE = /^[A-Z][A-Z0-9-]{1,39}$/;
  const positive = value => Number.isSafeInteger(value) && value > 0;
  function validCase(id) {
    if (typeof id !== 'string' || !CASE.test(id) || id.includes('\n'))
      throw Error('Use a 2–40 character uppercase case ID with letters, numbers and hyphens.');
    return id;
  }
  function validateCaseInput(id, label) {
    validCase(id);
    if (typeof label !== 'string' || !label.trim() || label.trim().length > 66)
      throw Error('Give this fictional case a short label (1–66 characters), not a real name.');
    return {case_id: id, label: 'Fictional case ' + label.trim()};
  }
  function fileBoundary(file) {
    if (!file || typeof file.name !== 'string' || !file.name.toLowerCase().endsWith('.txt') ||
        !Number.isSafeInteger(file.size) || file.size <= 0 || file.size > MAX_FILE ||
        typeof file.arrayBuffer !== 'function')
      throw Error('Only nonempty .txt reports up to 64 KiB are supported. PDF, images and OCR are not implemented here.');
  }
  async function readReportFile(file) {
    fileBoundary(file);
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (bytes.length !== file.size || bytes.length > MAX_FILE)
      throw Error('File size changed while reading; no import was sent.');
    // ignoreBOM=true preserves BOM as a character rather than silently removing it.
    const text = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true}).decode(bytes);
    const encoded = new TextEncoder().encode(text);
    if (encoded.length !== bytes.length || encoded.some((b, i) => b !== bytes[i]))
      throw Error('The original UTF-8 bytes could not be preserved.');
    if (!text.startsWith('OI-SYNTHETIC-REPORT/1\n'))
      throw Error('This is not a supported original-fictional structured report. Nothing was uploaded.');
    return text;
  }
  async function importReportFiles(files, options) {
    const {caseId, send, isCurrent = () => true, onReceipt = () => {}} = options || {};
    validCase(caseId);
    if (typeof send !== 'function' || !Array.isArray(files) || !files.length || files.length > MAX_FILES)
      throw Error('Choose 1–20 supported report files.');
    if (files.some(f => !f || !Number.isSafeInteger(f.size) || f.size < 0) ||
        files.reduce((n, f) => n + f.size, 0) > MAX_BATCH)
      throw Error('The selected batch exceeds the 1 MiB limit.');
    const results = [];
    let stopped = false;
    const emit = (file, values) => {
      const receipt = {name: file.name, caseId, ...values};
      results.push(receipt); onReceipt(receipt);
    };
    for (const file of files) {
      if (stopped || !isCurrent()) {
        stopped = true; emit(file, {status:'not_attempted',message:'Not sent; reconcile the earlier result or selected case before a new batch.'});
        continue;
      }
      let text;
      try { text = await readReportFile(file); }
      catch (error) { emit(file, {status:'rejected',message:String(error.message || error)}); continue; }
      if (!isCurrent()) {
        stopped = true; emit(file, {status:'not_attempted',message:'Case selection changed before upload; file was not sent.'});
        continue;
      }
      let response;
      try { response = await send(caseId, text); }
      catch (_) { response = null; }
      const body = response?.body;
      if (response?.status >= 400 && response.status < 500) {
        emit(file, {status:'rejected',message:typeof body?.error === 'string' ? body.error : 'The local import service refused this file.'});
      } else if (response?.status === 200 && body &&
          ['imported','duplicate'].includes(body.result) && positive(body.source_id) && positive(body.version)) {
        emit(file, {status:body.result,sourceId:body.source_id,version:body.version,
          invalidatedCount:Array.isArray(body.invalidated_snapshots) ? body.invalidated_snapshots.length : 0,
          message:body.result === 'duplicate' ? 'Already preserved; no new source version.' : 'Original source preserved; statements remain unreviewed.'});
      } else if (response?.status === 200 && body?.result === 'quarantined' && positive(body.quarantine_id)) {
        emit(file, {status:'quarantined',quarantineId:body.quarantine_id,
          message:'Declared patient does not match this case. Quarantined; no findings imported.'});
      } else {
        stopped = true;
        emit(file, {status:'unknown',message:'The request may have been saved, but its receipt was not confirmed. Refresh and inspect sources before retrying; identical reports are deduplicated by the server.'});
      }
    }
    return results;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {readReportFile, importReportFiles, validateCaseInput};
  }
  if (typeof document === 'undefined') return;
  const get = id => document.getElementById(id);
  let busy = false;
  const setBusy = value => {
    busy = value;
    get('case-picker').disabled = value;
    for (const id of ['intake-create-button','intake-import-button','intake-files']) get(id).disabled = value;
    get('case-intake').setAttribute('aria-busy', String(value));
  };
  document.addEventListener('oi:before-case-switch', event => {
    if (busy) { event.preventDefault(); notice('Finish the current intake before switching cases.', true); }
  });
  document.addEventListener('oi:case-selected', () => {
    get('intake-files').value = '';
    get('intake-file-fictional').checked = false;
    get('intake-selection').textContent = 'No files selected for this case. Nothing uploaded.';
    get('intake-complete').textContent = '';
    get('intake-receipts').replaceChildren();
  });
  function showReceipt(receipt) {
    const row = node('li', null, 'source-card');
    row.dataset.status = receipt.status; row.dataset.caseId = receipt.caseId;
    row.append(node('strong', receipt.name + ' — ' + receipt.status),
      node('p', receipt.caseId + (receipt.sourceId ? ', source #' + receipt.sourceId + '@' + receipt.version : '') +
        (receipt.quarantineId ? ', quarantine #' + receipt.quarantineId : ''), 'snapshot-meta'),
      node('p',receipt.message,'muted'));
    if (receipt.invalidatedCount) row.append(node('p',receipt.invalidatedCount + ' saved investigation(s) now require review.','muted'));
    get('intake-receipts').append(row);
  }
  get('new-case-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    if (!get('intake-case-fictional').checked) return notice('Confirm this is an independently authored fictional case.', true);
    try {
      if (hasUnsavedCaseWork()) throw Error('Save or explicitly clear unfinished work before creating another case.');
      const payload = validateCaseInput(get('intake-case-id').value, get('intake-case-label').value);
      setBusy(true);
      const response = await fetch('/api/cases', {method:'POST', headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const body = await response.json();
      if (!response.ok) throw Error(body.error || 'Case was not created.');
      if (response.status !== 201 || body.result !== 'created') throw Error('Creation outcome is unknown; refresh the case list before retrying.');
      setBusy(false); // The following explicit, guarded case switch is now permitted.
      await activateCreatedCase(payload.case_id);
      get('intake-case-label').value = ''; get('intake-case-fictional').checked = false;
      notice('Created ' + payload.case_id + '. Select its supported fictional source files below.');
      get('intake-files').focus();
    } catch (error) { notice('Case intake: ' + String(error.message || error) + ' Check the case list before retrying if the connection failed.', true); }
    finally { setBusy(false); }
  });
  get('intake-files').addEventListener('change', () => {
    const files = [...get('intake-files').files];
    get('intake-selection').textContent = files.length + ' file(s) selected, ' + files.reduce((n,f)=>n+f.size,0) + ' bytes. Nothing uploaded yet.';
    get('intake-file-fictional').checked = false;
  });
  get('file-intake-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    if (!get('intake-file-fictional').checked) return notice('Confirm the files are independently authored fictional reports, not patient records.', true);
    let selected;
    try {
      selected = readyCase();
      const files = [...get('intake-files').files];
      if (!files.length) throw Error('Choose supported .txt reports first.');
      setBusy(true); get('intake-receipts').replaceChildren();
      const results = await importReportFiles(files, {caseId:selected,
        isCurrent:()=>get('case-picker').value === selected,
        onReceipt:showReceipt,
        send:async (id,text)=>{
          const response=await fetch('/api/cases/'+encodeURIComponent(id)+'/imports',{
            method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
          return {status:response.status,body:await response.json()};
        }});
      const unknown = results.some(r=>r.status==='unknown');
      get('intake-complete').textContent = unknown ?
        'Some outcomes are unknown. Inspect the receipts and original sources before retrying.' :
        'Batch complete. Inspect each result below, then review the available sources and ask an investigation question.';
      if (selected === get('case-picker').value) {
        await refresh();
        await renderIncomingBoard(await api('/api/cases'));
      }
      get('intake-files').value = ''; get('intake-file-fictional').checked = false;
      get('intake-selection').textContent = 'No files selected. Previous batch receipts remain below.';
    } catch (error) { notice('Source intake: ' + String(error.message || error),true); }
    finally { setBusy(false); }
  });
})();
