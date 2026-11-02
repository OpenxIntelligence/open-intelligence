/* Read-only view over CaseStore and its synthetic world-model projection. */
(() => {
  'use strict';
  const labels = Object.freeze({reported: 'Reported', negative: 'Negative', pending: 'Pending',
    indeterminate: 'Indeterminate', 'not-reported': 'Not reported', 'not-assessed': 'Not assessed', conflicting: 'Conflicting'});
  const unresolvedStates = new Set(['pending', 'indeterminate', 'not-reported', 'not-assessed', 'conflicting']);
  // These are source *format categories*, not required diagnostics or clinical gaps.
  const recordKinds = Object.freeze([
    ['clinical', 'Clinical notes'],
    ['pathology', 'Pathology'],
    ['laboratory', 'Laboratory'],
    ['imaging', 'Imaging'],
    ['molecular', 'Molecular'],
    ['other', 'Other documents'],
  ]);
  const positive = value => Number.isSafeInteger(value) && value > 0;
  function requireMatch(condition) { if (!condition) throw Error('Record response does not match the loaded case'); }
  function sameIds(actual, expected) {
    requireMatch(Array.isArray(actual) && actual.every(positive) && new Set(actual).size === actual.length);
    requireMatch(actual.length === expected.length && actual.every(id => expected.includes(id)));
  }

  function validate(model, state) {
    requireMatch(model && model.contract === 'oi.synthetic-world-model/1' && model.synthetic === true &&
      model.scope === 'fictional_case_only_not_a_verified_patient' && model.case_id === state.case.case_id &&
      model.authority === 'source_report_only_unreviewed' && model.clinical_interpretation === 'not_generated');
    for (const key of ['sources', 'assertions', 'questions', 'snapshots', 'events']) requireMatch(Array.isArray(state[key]));
    for (const key of ['current_sources', 'history', 'observations', 'unresolved', 'conflicts']) requireMatch(Array.isArray(model[key]));
    requireMatch(state.events.every(event => positive(event.id)));
    const latest = state.events.reduce((a, b) => !a || b.id > a.id ? b : a, null);
    requireMatch(model.as_of_ledger?.event_id === (latest?.id ?? null) &&
      model.as_of_ledger?.recorded_at === (latest?.occurred_at ?? null));
    const sources = new Map(state.sources.map(source => [source.id, source]));
    requireMatch(sources.size === state.sources.length);
    const seen = new Set();
    for (const [items, expectedState] of [[model.current_sources, 'current'], [model.history, 'superseded']]) {
      for (const item of items) {
        const source = sources.get(item.source_version_id);
        requireMatch(positive(item.source_version_id) && source && !seen.has(source.id));
        seen.add(source.id);
        requireMatch(typeof source.sha256 === 'string' && /^[a-f0-9]{64}$/.test(source.sha256) &&
          item.source_sha256 === source.sha256 && item.state === expectedState && source.state === expectedState &&
          item.supersedes_source_id === source.supersedes_id);
        for (const key of ['document_id', 'version', 'kind', 'specimen_id', 'event_date', 'issued_at', 'received_at'])
          requireMatch(item[key] === source[key]);
      }
    }
    requireMatch(seen.size === sources.size);
    const assertions = new Map(state.assertions.map(assertion => [assertion.id, assertion]));
    requireMatch(assertions.size === state.assertions.length);
    const observations = new Map();
    for (const item of model.observations) {
      const assertion = assertions.get(item.assertion_id), source = sources.get(item.source_version_id);
      requireMatch(positive(item.assertion_id) && assertion && source && source.state === 'current' &&
        !observations.has(item.assertion_id) && positive(item.source_line) &&
        Object.hasOwn(labels, item.reported_state) && item.source_sha256 === source.sha256 &&
        item.source_version_id === assertion.source_version_id && item.source_line === assertion.source_line &&
        item.finding_key === assertion.finding_key && item.source_statement === assertion.quote &&
        item.reported_state === assertion.certainty && item.document_id === source.document_id &&
        item.document_version === source.version && item.source_kind === source.kind &&
        item.review_state === 'not_established' && item.clinical_meaning === null);
      for (const key of ['specimen_id', 'event_date', 'issued_at', 'received_at']) requireMatch(item[key] === source[key]);
      observations.set(item.assertion_id, item);
    }
    requireMatch(observations.size === assertions.size);
    sameIds(model.unresolved.map(item => item.assertion_id), model.observations
      .filter(item => unresolvedStates.has(item.reported_state)).map(item => item.assertion_id));
    for (const conflict of model.conflicts) {
      requireMatch(conflict.specimen_id != null && conflict.status === 'unresolved_source_disagreement' &&
        conflict.clinical_interpretation === 'not_performed' && Array.isArray(conflict.observation_refs));
      const states = new Set();
      for (const ref of conflict.observation_refs) {
        const observation = observations.get(ref.assertion_id);
        requireMatch(observation && observation.source_version_id === ref.source_version_id && observation.source_line === ref.source_line &&
          observation.specimen_id === conflict.specimen_id && observation.event_date === conflict.event_date &&
          observation.finding_key === conflict.finding_key);
        states.add(observation.reported_state);
      }
      requireMatch(states.has('reported') && states.has('negative'));
    }
    requireMatch(model.review_needed);
    requireMatch(state.snapshots.every(snapshot => positive(snapshot.question_id) &&
      state.questions.some(question => question.id === snapshot.question_id)));
    for (const [field, list, status] of [['open_question_ids', state.questions, 'open'],
      ['draft_snapshot_ids', state.snapshots, 'draft'], ['stale_snapshot_ids', state.snapshots, 'stale']]) {
      requireMatch(list.every(item => positive(item.id) && (!item.case_id || item.case_id === state.case.case_id)));
      sameIds(model.review_needed[field], list.filter(item => item.state === status).map(item => item.id));
    }
    return {sources, observations};
  }

  function create({elements, fetchModel, onOpenSource, onOpenQuestion, onRefresh}) {
    const {root, status, timeline, findings, questions, uncertainty, inventory} = elements;
    const document = root.ownerDocument;
    let generation = 0;
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    function node(tag, text, className = '') {
      const item = document.createElement(tag);
      if (text !== undefined) item.textContent = String(text);
      if (className) item.className = className;
      return item;
    }
    function setState(value) {
      root.dataset.state = value;
      root.setAttribute('aria-busy', value === 'loading' ? 'true' : 'false');
    }
    function wipe(message = '') {
      for (const area of [timeline, findings, questions, uncertainty, inventory]) area.replaceChildren();
      status.textContent = message;
    }
    function clear(message = '', loading = false) {
      generation += 1;
      wipe(message);
      setState(loading ? 'loading' : 'unavailable');
    }
    function button(text, token, action) {
      const item = node('button', text, 'button secondary minor');
      item.type = 'button';
      item.addEventListener('click', () => { if (token === generation) action(); });
      return item;
    }
    function sourceButton(source, line, token) {
      const item = button(`Read ${source.document_id} · v${source.version}${line === null ? '' : ' · line ' + line}`,
        token, () => onOpenSource(source.id, line));
      item.setAttribute('data-source-id', source.id);
      if (line !== null) item.setAttribute('data-source-line', line);
      return item;
    }
    function finding(item, sources, token) {
      const card = node('article', undefined, 'finding patient-record-item');
      const head = node('div', undefined, 'finding-head');
      head.append(node('strong', item.finding_key), node('span', labels[item.reported_state],
        'pill ' + (unresolvedStates.has(item.reported_state) ? 'pill-warn' : 'pill-neutral')));
      card.append(head, node('p', item.source_statement, 'quoted'),
        node('p', `${item.event_date} · ${item.specimen_id ? 'Specimen ' + item.specimen_id : 'Specimen not recorded'}`, 'source-meta'),
        sourceButton(sources.get(item.source_version_id), item.source_line, token));
      return card;
    }
    function sourceRow(source, token) {
      const row = node('article', undefined, 'source-card patient-record-item');
      row.append(node('strong', `${source.event_date} · ${source.kind}`),
        node('p', `${source.document_id} · version ${source.version} · ${source.state === 'current' ? 'Current' : 'Earlier version'}`, 'source-meta'),
        node('p', `Issued ${source.issued_at} · Received ${source.received_at}`, 'source-meta'),
        sourceButton(source, null, token));
      return row;
    }
    function renderInventory(model, sources, token) {
      // Read the same validated source ledger and PWM projection; never infer clinical absence.
      for (const [kind, label] of recordKinds) {
        const current = model.current_sources.filter(item => item.kind === kind);
        const historical = model.history.filter(item => item.kind === kind);
        const row = node('article', undefined, 'source-card patient-record-item');
        const head = node('div', undefined, 'finding-head');
        head.append(node('strong', label));
        const availability = current.length
          ? 'Supplied here'
          : historical.length ? 'Earlier versions only' : 'Not supplied';
        head.append(node('span', availability, 'pill ' +
          (current.length ? 'pill-neutral' : 'pill-warn')));
        row.append(head, node('p',
          current.length + ' current document(s), ' + historical.length +
          ' earlier version(s). ' +
          (current.length ? 'View the original records below.' :
            'No current ' + label.toLowerCase() + ' document is in this workspace. ' +
            'This does not establish whether a test or encounter happened elsewhere.'),
          'source-meta'));
        // Existing source reader owns exact bytes, version, and review context.
        for (const item of current) row.append(sourceButton(sources.get(item.source_version_id), null, token));
        inventory.append(row);
      }
    }
    function render(model, state, checked, token) {
      const {sources, observations} = checked;
      renderInventory(model, sources, token);
      status.textContent = `${model.current_sources.length} current records · ${model.observations.length} source findings. ` +
        'Fictional case for development. These findings have not been clinically reviewed.';
      if (!model.current_sources.length) timeline.append(node('p', 'No current records have been added.', 'empty'));
      for (const item of model.current_sources) timeline.append(sourceRow(sources.get(item.source_version_id), token));
      if (model.history.length) {
        const history = node('details');
        history.append(node('summary', `Earlier record versions (${model.history.length})`));
        for (const item of model.history) history.append(sourceRow(sources.get(item.source_version_id), token));
        timeline.append(history);
      }
      if (!model.observations.length) findings.append(node('p', 'No source findings have been recorded.', 'empty'));
      for (const item of model.observations) findings.append(finding(item, sources, token));
      for (const item of model.unresolved) uncertainty.append(finding(observations.get(item.assertion_id), sources, token));
      for (const conflict of model.conflicts) {
        const card = node('article', undefined, 'source-card patient-record-item');
        card.append(node('strong', `Sources disagree: ${conflict.finding_key}`),
          node('p', `Specimen ${conflict.specimen_id} · ${conflict.event_date}`, 'source-meta'),
          node('p', 'Not resolved. The differing source statements are preserved for review.'));
        for (const ref of conflict.observation_refs) card.append(sourceButton(sources.get(ref.source_version_id), ref.source_line, token));
        uncertainty.append(card);
      }
      if (!model.unresolved.length && !model.conflicts.length)
        uncertainty.append(node('p', 'No unresolved source findings are recorded. Missing records may still leave questions unanswered.', 'empty'));
      const open = state.questions.filter(question => question.state === 'open');
      if (!open.length) questions.append(node('p', 'No open questions are recorded.', 'empty'));
      for (const question of open) {
        const row = node('article', undefined, 'source-card patient-record-item');
        const action = button('Investigate question', token, () => onOpenQuestion(question.id));
        action.setAttribute('data-question-id', question.id);
        row.append(node('p', question.question), action);
        questions.append(row);
      }
      const review = model.review_needed;
      if (state.snapshots.length) {
        const openIds = new Set(open.map(question => question.id));
        const needsReview = state.snapshots.filter(snapshot =>
          snapshot.state === 'stale' && openIds.has(snapshot.question_id)).length;
        const historical = review.stale_snapshot_ids.length - needsReview;
        questions.append(node('p', `${review.draft_snapshot_ids.length} draft reports await review; ` +
          `${needsReview} earlier reports need reassessment. ` +
          `${historical} historical stale version(s) are preserved. Earlier reports remain available.`, 'source-meta'));
        const link = node('a', 'View investigation history');
        link.href = '#investigations';
        link.addEventListener('click', event => { if (token !== generation) event.preventDefault(); });
        questions.append(link);
      }
    }
    async function load(state) {
      const token = ++generation;
      wipe('Loading the selected case…');
      setState('loading');
      try {
        requireMatch(typeof state?.case?.case_id === 'string' && state.case.case_id.length > 0);
        const model = await fetchModel(state.case.case_id);
        if (token !== generation) return false;
        const checked = validate(model, state);
        render(model, state, checked, token);
        setState('ready');
        return true;
      } catch (_) {
        if (token !== generation) return false;
        // A partial render must invalidate its callbacks as well as remove its nodes.
        const retryToken = ++generation;
        wipe('The record view could not be loaded for the selected case. Refresh to try again. ');
        setState('unavailable');
        status.append(button('Retry', retryToken, onRefresh));
        return false;
      }
    }
    return {load, clear};
  }
  globalThis.OpenIntelligencePatientRecord = Object.freeze({create});
})();
