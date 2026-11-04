/* Public metadata discovery is deliberately independent of the case workspace. */
(() => {
  'use strict';
  const form = document.getElementById('literature-search-form');
  if (!form) return;
  const terms = document.getElementById('literature-terms');
  const attestation = document.getElementById('literature-public-attestation');
  const submit = document.getElementById('literature-live-button');
  const clearButton = document.getElementById('literature-clear-button');
  const mode = document.getElementById('literature-mode');
  const feedback = document.getElementById('literature-feedback');
  const results = document.getElementById('literature-results');
  let enabled = false;
  let pending = false;
  let generation = 0;

  function make(tag, text, className = '') {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  }
  function validTerms() {
    return terms.value.length <= 240 && terms.value.trim().length >= 3;
  }
  function updateButton() {
    submit.disabled = !enabled || !attestation.checked || !validTerms() || pending;
    submit.textContent = pending ? 'Searching metadata…' : 'Search public metadata';
  }
  function invalidate(message) {
    generation++;
    results.replaceChildren();
    feedback.textContent = message;
    updateButton();
  }
  function count(value) {
    return Number.isSafeInteger(value) && value >= 0;
  }
  function recordLink(record) {
    const source = record.source_database;
    const id = record.source_record_id;
    const pattern = source === 'MED' ? /^[1-9][0-9]{0,9}$/ : source === 'PMC' ? /^PMC[1-9][0-9]{0,9}$/ : null;
    if (!pattern || typeof id !== 'string' || !pattern.test(id)) return null;
    const canonical = 'https://europepmc.org/article/' + source + '/' + id;
    return record.record_url === canonical ? canonical : null;
  }
  function render(data) {
    if (!data || data.provider !== 'europe_pmc' || data.metadata_only !== true ||
        data.clinical_evidence_appraised !== false || data.rights_status !== 'not_assessed' ||
        !count(data.provider_hit_count) || !count(data.returned_record_count) || data.returned_record_count > 10 ||
        !Array.isArray(data.citations) || data.citations.length > data.returned_record_count ||
        !data.excluded_counts || typeof data.excluded_counts !== 'object' || Array.isArray(data.excluded_counts))
      throw Error('Unsupported metadata response');
    const exclusions = Object.values(data.excluded_counts);
    if (!exclusions.every(count)) throw Error('Unsupported metadata response');
    const excluded = exclusions.reduce((total, value) => total + value, 0);
    if (excluded + data.citations.length !== data.returned_record_count ||
        data.returned_record_count > data.provider_hit_count) throw Error('Unsupported metadata response');
    const view = make('div');
    view.append(make('p', 'Provider matches: ' + data.provider_hit_count +
      ' · Returned page records: ' + data.returned_record_count +
      ' · Displayed citations: ' + data.citations.length + ' · Excluded: ' + excluded, 'muted'));
    view.append(make('p', 'Metadata only · Rights: unassessed · not evidence for a clinical conclusion. ' +
      'Provider ordering is not an appraisal of quality, applicability or completeness.', 'muted'));
    if (!data.citations.length) view.append(make('p',
      'No usable citation metadata was retained on this page. This does not establish an absence of relevant literature.', 'muted'));
    for (const record of data.citations) {
      if (!record || typeof record.title !== 'string' || !record.title || record.title.length > 1000 ||
          record.metadata_only !== true || record.clinical_evidence_appraised !== false || record.rights_status !== 'not_assessed')
        throw Error('Unsupported metadata record');
      const card = make('article', undefined, 'source-card');
      const link = recordLink(record);
      if (link) {
        const title = make('a', record.title);
        title.href = link;
        title.target = '_blank';
        title.rel = 'noopener noreferrer';
        card.append(title);
      } else {
        card.append(make('p', record.title), make('p', 'Canonical publication link unavailable.', 'muted'));
      }
      const bibliographic = [record.authors, record.journal,
        Number.isInteger(record.publication_year) ? String(record.publication_year) : 'Publication year unknown']
        .filter(value => typeof value === 'string' && value.length);
      card.append(make('p', bibliographic.join(' · '), 'muted'));
      const integrity = record.integrity;
      if (integrity?.status === 'provider_markers_present' && Array.isArray(integrity.markers)) {
        card.append(make('p', 'Integrity: provider markers present; inspect them before use. Marker presence is not an appraisal.', 'muted'));
        for (const marker of integrity.markers.slice(0, 20)) {
          if (typeof marker.value === 'string') card.append(make('p', marker.value, 'muted'));
        }
      } else {
        card.append(make('p', 'Integrity: unknown — a complete correction or retraction check was not performed.', 'muted'));
      }
      card.append(make('p', 'Rights: unassessed. Clinical evidence has not been appraised.', 'muted'));
      view.append(card);
    }
    results.replaceChildren(view);
  }
  const failures = {
    403: 'Live metadata search is disabled or the local request was not permitted.',
    422: 'Use 3–240 public biomedical characters and confirm the public-terms attestation.',
    429: 'A search is running or the request limit was reached. Try again shortly.',
    502: 'The metadata service is unavailable. Try again later.',
  };
  async function search(event) {
    event.preventDefault();
    if (!enabled || !attestation.checked || !validTerms() || pending) return;
    const requestGeneration = ++generation;
    const submittedTerms = terms.value;
    const current = () => requestGeneration === generation && terms.value === submittedTerms && attestation.checked;
    pending = true;
    results.replaceChildren();
    feedback.textContent = 'Searching public citation metadata…';
    updateButton();
    try {
      const response = await fetch('/api/literature/search', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({terms: submittedTerms, human_authored: true, public_terms_only: true, page_size: 5}),
      });
      if (!current()) return;
      if (!response.ok) {
        // Do not read or reflect provider/server error bodies.
        feedback.textContent = failures[response.status] || 'Metadata search could not complete. Try again later.';
        return;
      }
      const data = await response.json();
      if (!current()) return;
      render(data);
      feedback.textContent = 'Citation metadata retrieved. Nothing was saved or linked to a case.';
    } catch (_) {
      if (current()) {
        results.replaceChildren();
        feedback.textContent = 'Metadata search could not complete safely. Try again later.';
      }
    } finally {
      pending = false;
      updateButton();
    }
  }

  // A browser-restored value or checkbox is not fresh public-only attestation.
  terms.value = '';
  attestation.checked = false;
  terms.addEventListener('input', () => {
    attestation.checked = false;
    invalidate('Terms changed. Confirm the public-terms attestation before searching.');
  });
  attestation.addEventListener('change', () => invalidate(''));
  clearButton.addEventListener('click', () => {
    terms.value = '';
    attestation.checked = false;
    invalidate('Search cleared.');
    terms.focus();
  });
  form.addEventListener('submit', search);
  updateButton();
  (async () => {
    try {
      const response = await fetch('/api/literature/status');
      if (!response.ok) throw Error('Status unavailable');
      const status = await response.json();
      enabled = status.live_enabled === true;
      mode.textContent = enabled
        ? 'Public metadata search is enabled by the local operator. Each search needs your confirmation below.'
        : 'Public metadata search is disabled by the local operator.';
    } catch (_) {
      enabled = false;
      mode.textContent = 'Public metadata search status is unavailable; search remains disabled.';
    }
    updateButton();
  })();
})();
