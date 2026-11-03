'use strict';
// Patient / care-team views for the connected workspace host only.
// Regroups the EXISTING sections into tab panels (moved, never copied or
// removed), docks the EXISTING source dialogs as an inspector and renders
// read-only summaries from the EXISTING case state. No new store, write
// action, network origin, clinical inference or second patient record.
(() => {
  const $ = id => document.getElementById(id);
  const make = (tag, text, className) => {
    const item = document.createElement(tag);
    if (text !== undefined && text !== null) item.textContent = String(text);
    if (className) item.className = className;
    return item;
  };
  const params = new URLSearchParams(location.search);
  const ROLE_KEY = 'oi-view-role';
  const ROLES = {careteam: 'Care team', patient: 'Patient'};
  const remembered = () => { try { return localStorage.getItem(ROLE_KEY); } catch (_) { return null; } };
  const remember = value => { try { localStorage.setItem(ROLE_KEY, value); } catch (_) { /* optional */ } };
  let role = params.get('role') in ROLES ? params.get('role') : (remembered() === 'patient' ? 'patient' : 'careteam');

  // [tab key, nav label, block ids]. The first id is the tab's link target.
  const LAYOUT = {
    careteam: [
      ['board', 'Incoming board', ['incoming-board']],
      ['overview', 'Overview', ['overview', 'workspace-start', 'source-intake', 'metrics', 'view-glance', 'view-next']],
      ['records', 'Records & timeline', ['timeline', 'sources', 'biological-assets', 'import']],
      ['investigations', 'Investigations', ['investigations']],
      ['research', 'Evidence & research', ['evidence', 'bibliography']],
      ['review', 'Review & changes', ['changes-since-review', 'patient-mission', 'activity']],
      ['options', 'Options & tasks', ['options']],
    ],
    patient: [
      ['home', 'Overview', ['pt-home']],
      ['reports', 'My reports', ['timeline', 'sources', 'patient-view']],
      ['research', 'Research', ['pt-research', 'bibliography']],
      ['questions', 'My questions', ['pt-questions']],
    ],
  };
  const DEFAULT_TAB = {careteam: 'overview', patient: 'home'};

  const main = $('main-content');
  const blocks = {};
  for (const id of ['incoming-board', 'overview', 'workspace-start', 'source-intake', 'metrics', 'patient-view',
    'patient-mission', 'timeline', 'sources', 'biological-assets', 'import', 'investigations', 'evidence',
    'bibliography', 'changes-since-review', 'activity', 'options']) blocks[id] = $(id);
  blocks['view-glance'] = main && main.querySelector(':scope > .glance-layout');
  const missing = Object.keys(blocks).filter(id => !blocks[id]);
  if (!main || missing.length) {
    // Leave the original page fully intact rather than guess at a changed template.
    console.error('Open Intelligence views: owner template changed; missing ' + missing.join(', '));
    return;
  }

  function card(id, eyebrow, title) {
    const section = make('section', null, 'panel view-card');
    section.id = id;
    const heading = make('h2', title);
    heading.id = id + '-title';
    section.setAttribute('aria-labelledby', heading.id);
    if (eyebrow) section.append(make('p', eyebrow, 'view-eyebrow'));
    section.append(heading);
    const body = make('div');
    section.append(body);
    return {section, body};
  }
  const next = card('view-next', 'Next investigation', 'Which question to work on');
  const home = card('pt-home', 'Summary', 'Loading…');
  const research = card('pt-research', 'Research', 'Research about my case');
  const questions = card('pt-questions', 'My questions', 'Questions for my care team');
  blocks['view-next'] = next.section;
  blocks['pt-home'] = home.section;
  blocks['pt-research'] = research.section;
  blocks['pt-questions'] = questions.section;

  // Containers: panels for the active role, parking for everything else.
  const panels = make('div', null, 'view-panels');
  panels.id = 'view-panels';
  const parking = make('div', null, 'view-parking');
  parking.id = 'view-parking';
  parking.hidden = true;
  main.insertBefore(panels, main.firstChild);
  main.insertBefore($('notice'), panels);
  main.insertBefore(parking, main.querySelector(':scope > footer'));
  for (const leftover of main.querySelectorAll(':scope > .workspace, :scope > .glance-layout')) {
    if (!leftover.children.length) leftover.hidden = true;
  }

  // Navigation and role switch.
  const nav = make('nav', null, 'view-nav');
  nav.id = 'view-nav';
  nav.setAttribute('aria-label', 'Workspace views');
  const oldMenu = document.querySelector('.rail .section-menu');
  oldMenu.before(nav);
  oldMenu.hidden = true;
  const roleBox = make('div', null, 'view-role');
  const roleGroup = make('div', null, 'view-role-group');
  roleGroup.setAttribute('role', 'group');
  roleGroup.setAttribute('aria-label', 'View as (development only)');
  roleBox.append(make('span', 'Dev view', 'view-role-label'), roleGroup);
  const roleButtons = {};
  for (const [key, label] of Object.entries(ROLES)) {
    const button = make('button', label);
    button.type = 'button';
    button.dataset.role = key;
    button.addEventListener('click', () => setRole(key));
    roleButtons[key] = button;
  }
  roleGroup.append(roleButtons.patient, roleButtons.careteam);
  document.querySelector('.top-right').prepend(roleBox);

  let currentTab = null;
  let arrangedRole = null;
  const effectiveRole = () => document.body.dataset.workspaceState === 'empty' ? 'careteam' : role;

  function arrange() {
    const layoutRole = effectiveRole();
    arrangedRole = layoutRole;
    document.documentElement.dataset.viewRole = layoutRole;
    for (const [key, button] of Object.entries(roleButtons)) button.setAttribute('aria-pressed', String(key === role));
    const placed = new Set();
    const built = [];
    for (const [key, label, ids] of LAYOUT[layoutRole]) {
      const panel = make('div', null, 'view-panel');
      panel.id = 'view-' + key;
      panel.dataset.tab = key;
      panel.setAttribute('role', 'region');
      panel.setAttribute('aria-label', label);
      for (const id of ids) { panel.append(blocks[id]); placed.add(id); }
      built.push(panel);
    }
    for (const [id, block] of Object.entries(blocks)) if (!placed.has(id)) parking.append(block);
    panels.replaceChildren(...built);
    nav.replaceChildren();
    for (const [key, label, ids] of LAYOUT[layoutRole]) {
      const link = make('a', null, key === 'board' ? 'view-nav-board' : '');
      link.href = '#' + ids[0];
      link.dataset.tab = key;
      link.append(make('span', label));
      const badge = make('span', '', 'view-badge');
      badge.hidden = true;
      link.append(badge);
      link.addEventListener('click', () => show(key));
      nav.append(link);
    }
    currentTab = null;
    route();
    paint();
    filterNotice();
  }

  function show(key) {
    if (!LAYOUT[arrangedRole].some(tab => tab[0] === key)) key = DEFAULT_TAB[arrangedRole];
    currentTab = key;
    for (const panel of panels.children) panel.hidden = panel.dataset.tab !== key;
    for (const link of nav.querySelectorAll('a')) {
      if (link.dataset.tab === key) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
  }

  function route() {
    const id = decodeURIComponent(location.hash.slice(1));
    const target = id ? document.getElementById(id) : null;
    const panel = target && target.closest('.view-panel');
    if (panel && panels.contains(panel)) {
      show(panel.dataset.tab);
      requestAnimationFrame(() => target.scrollIntoView({block: 'start'}));
    } else if (!currentTab) {
      show(DEFAULT_TAB[arrangedRole]);
    }
  }
  addEventListener('hashchange', route);

  function setRole(next) {
    if (!(next in ROLES) || next === role) return;
    role = next;
    remember(role);
    const url = new URL(location.href);
    url.searchParams.set('role', role);
    url.hash = '';
    history.replaceState(null, '', url);
    arrange();
    scrollTo(0, 0);
  }

  // Source inspector: dock the existing dialogs instead of opening them modally.
  const top = document.querySelector('.top');
  const syncTop = () => document.documentElement.style.setProperty('--view-top', (top ? top.getBoundingClientRect().bottom : 0) + 'px');
  const dialogs = ['source-dialog', 'compare-dialog'].map($);
  for (const dialog of dialogs) {
    dialog.classList.add('view-inspector');
    dialog.showModal = function showDocked() { if (!this.open) { syncTop(); this.show(); } };
    dialog.addEventListener('keydown', event => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      dialog.querySelector('.dialog-head button').click();
    });
  }
  const syncInspector = () => document.body.classList.toggle('view-inspector-open', dialogs.some(d => d.open));
  new MutationObserver(syncInspector).observe(dialogs[0], {attributes: true, attributeFilter: ['open']});
  new MutationObserver(syncInspector).observe(dialogs[1], {attributes: true, attributeFilter: ['open']});
  addEventListener('scroll', syncTop, {passive: true});
  addEventListener('resize', syncTop);

  // Read-only summaries from the existing case state.
  const plainName = key => String(key).split('-').map((word, index) =>
    word.length === 1 ? word.toUpperCase() : index === 0 ? word[0].toUpperCase() + word.slice(1) : word).join(' ');
  const plainState = value => {
    const text = (typeof CERTAINTY_PLAIN !== 'undefined' && CERTAINTY_PLAIN[value]) || String(value || '').replace(/-/g, ' ');
    return text ? text[0].toUpperCase() + text.slice(1) : '';
  };
  const ready = () => {
    try { return typeof active !== 'undefined' && active && active.case && active.case.case_id === caseId ? active : null; }
    catch (_) { return null; }
  };
  const reopened = state => new Set(state.snapshots
    .filter(s => s.state === 'stale' && state.questions.some(q => Number(q.id) === Number(s.question_id) && q.state === 'open'))
    .map(s => Number(s.question_id)));
  const amendedPair = state => {
    const current = state.sources.find(s => s.state === 'current' && s.supersedes_id);
    const previous = current && state.sources.find(s => s.id === current.supersedes_id);
    return current && previous ? {previous, current} : null;
  };
  function viewSource(label, sourceId, line) {
    const button = make('button', label, 'view-link-button');
    button.type = 'button';
    button.addEventListener('click', () => openSource({id: Number(sourceId)}, line === undefined ? null : Number(line)));
    return button;
  }

  let changes = null;
  let changesCase = null;
  let changesSequence = 0;
  async function loadChanges(state) {
    const sequence = ++changesSequence;
    const requested = state.case.case_id;
    try {
      const data = await api('/api/cases/' + encodeURIComponent(requested) + '/changes-since-review');
      if (sequence !== changesSequence || requested !== caseId) return;
      changes = data;
      changesCase = requested;
      paintHome(ready());
    } catch (_) { /* The existing Review & changes panel reports errors. */ }
  }

  function paintHome(state) {
    const {section, body} = home;
    body.replaceChildren();
    if (!state) return;
    section.querySelector('h2').textContent = state.case.label.replace(/^Fictional case /, '');
    const pending = reopened(state).size;
    const pair = amendedPair(state);
    const status = make('p', pending ? 'A corrected report is waiting for your care team’s review'
      : pair ? 'Your records were updated' : 'No changes waiting for review', 'view-status');
    if (pending) status.dataset.tone = 'attention';
    body.append(status);
    const amendments = changesCase === state.case.case_id && changes ? changes.amendments || [] : [];
    for (const item of amendments) {
      const box = make('div', null, 'view-change');
      box.append(make('strong', item.document_id + ' was corrected (version ' + item.superseded_version + ' → ' + item.version + ')'));
      for (const change of (item.finding_key_diff || {}).reported_state_changes || []) {
        const row = make('div', null, 'view-change-row');
        row.append(make('span', plainName(change.finding_key) + ':'), make('span', plainState(change.previous_reported_state), 'view-was'),
          make('span', '→'), make('span', plainState(change.reported_state), 'view-now'));
        box.append(row);
      }
      box.append(make('span', 'The earlier version is kept. Your care team reviews what this change means.', 'view-label'));
      body.append(box);
    }
    body.append(make('h3', 'My results'));
    if (!state.assertions.length) { body.append(make('p', 'No results in your records yet.', 'muted')); return; }
    const table = make('table', null, 'view-table');
    const tbody = make('tbody');
    for (const assertion of state.assertions) {
      const row = make('tr');
      const name = make('th', plainName(assertion.finding_key));
      name.scope = 'row';
      name.append(make('span', assertion.quote, 'view-quote'));
      const source = state.sources.find(s => s.id === assertion.source_version_id);
      const ref = make('td');
      ref.append(viewSource((source ? source.document_id + ' v' + source.version : 'Source') + ' · line ' + assertion.source_line,
        assertion.source_version_id, assertion.source_line));
      row.append(name, make('td', plainState(assertion.certainty)), ref);
      tbody.append(row);
    }
    table.append(tbody);
    body.append(table);
  }

  function paintResearch(state) {
    const {body} = research;
    body.replaceChildren();
    if (!state) return;
    const linked = new Set((state.evidence_assessments || []).map(a => Number(a.evidence_version_id)));
    const items = (state.evidence || []).filter(item => item.state === 'current');
    body.append(make('p', 'Research your care team connected to this workspace. You can also look up publications yourself with the search below.', 'muted'));
    if (!items.length) { body.append(make('p', 'Your care team hasn’t connected any research yet.', 'muted')); return; }
    const list = make('ul', null, 'view-list');
    for (const item of items) {
      const row = make('li');
      const text = make('div');
      text.append(make('strong', item.title), make('div', item.evidence_key + ' · version ' + item.version +
        (linked.has(Number(item.id)) ? ' · assessed for your case' : ''), 'view-label'));
      const read = make('button', 'Read', 'view-link-button');
      read.type = 'button';
      read.addEventListener('click', () => openEvidence({id: Number(item.id)}));
      row.append(text, read);
      list.append(row);
    }
    body.append(list);
  }

  function paintQuestions(state) {
    const {body} = questions;
    body.replaceChildren();
    if (!state) return;
    const reopenedIds = reopened(state);
    if (!state.questions.length) { body.append(make('p', 'No questions recorded yet.', 'muted')); return; }
    const list = make('ul', null, 'view-list');
    for (const question of state.questions) {
      const row = make('li');
      const again = reopenedIds.has(Number(question.id));
      const label = make('span', again ? 'Reopened because a report changed' : question.state === 'open' ? 'Open' : 'Closed', 'view-label');
      if (again) label.dataset.tone = 'attention';
      row.append(make('span', question.question), label);
      list.append(row);
    }
    body.append(list);
  }

  function paintNext(state) {
    const {body} = next;
    body.replaceChildren();
    if (!state) return;
    const open = state.questions.filter(q => q.state === 'open');
    const reopenedIds = reopened(state);
    const link = make('a', open.length ? 'Open Investigations' : 'Ask a question');
    link.href = '#investigations';
    if (!open.length) { body.append(make('p', 'No open questions.', 'muted'), link); return; }
    const first = open.find(q => reopenedIds.has(Number(q.id))) || open[0];
    const label = make('p', reopenedIds.has(Number(first.id))
      ? 'Reopened by an amended source · prepare a new draft' : 'Open', 'view-label');
    if (reopenedIds.has(Number(first.id))) label.dataset.tone = 'attention';
    body.append(make('p', 'Q' + first.id + ' · ' + first.question), label, link);
  }

  function paintAttention(state) {
    const box = $('review-attention');
    let button = $('view-compare-changed');
    const pair = state && box.dataset.state === 'needs-review' ? amendedPair(state) : null;
    if (!pair) { if (button) button.hidden = true; return; }
    if (!button) {
      button = make('button', '', 'button');
      button.id = 'view-compare-changed';
      button.type = 'button';
      box.append(button);
    }
    button.hidden = false;
    button.textContent = 'Compare ' + pair.current.document_id + ' v' + pair.previous.version + ' → v' + pair.current.version;
    button.onclick = () => {
      location.hash = '#changes-since-review';
      openComparison({id: pair.previous.id}, {id: pair.current.id});
    };
  }

  function paintBadges(state) {
    const counts = {
      review: state ? reopened(state).size : 0,
      questions: state ? reopened(state).size : 0,
      home: state && arrangedRole === 'patient' && reopened(state).size ? 1 : 0,
    };
    for (const link of nav.querySelectorAll('a')) {
      const badge = link.querySelector('.view-badge');
      const count = counts[link.dataset.tab] || 0;
      badge.textContent = count ? String(count) : '';
      badge.hidden = !count;
    }
  }

  let paintQueued = false;
  let paintedCase = null;
  function paint() {
    paintQueued = false;
    const state = ready();
    if (state && paintedCase !== state.case.case_id + ':' + state.sources.length + ':' + state.snapshots.length) {
      paintedCase = state.case.case_id + ':' + state.sources.length + ':' + state.snapshots.length;
      loadChanges(state);
    }
    paintHome(state);
    paintResearch(state);
    paintQuestions(state);
    paintNext(state);
    paintAttention(state);
    paintBadges(state);
  }
  function schedule() {
    if (paintQueued) return;
    paintQueued = true;
    queueMicrotask(paint);
  }
  const watch = new MutationObserver(schedule);
  for (const id of ['case-heading', 'assertion-list', 'snapshot-list', 'source-list', 'question-list', 'evidence-list'])
    watch.observe($(id), {childList: true, subtree: true});
  watch.observe($('review-attention'), {attributes: true, attributeFilter: ['data-state']});
  // Draft-editing warnings belong to the care team's authoring tools, which the
  // patient view parks. Errors from the patient's own actions still show.
  const notice = $('notice');
  const AUTHORING_NOTICES = ['An investigation source changed while you were editing'];
  const filterNotice = () => {
    if (arrangedRole === 'patient' && !notice.hidden &&
        AUTHORING_NOTICES.some(text => notice.textContent.startsWith(text))) notice.hidden = true;
  };
  new MutationObserver(filterNotice).observe(notice, {childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ['hidden']});
  new MutationObserver(() => { if (effectiveRole() !== arrangedRole) arrange(); })
    .observe(document.body, {attributes: true, attributeFilter: ['data-workspace-state']});

  // Demo helper: ?live=1 re-reads the selected case so two windows stay in step.
  if (params.get('live') === '1') {
    const unsaved = () => ['draft-observations', 'draft-summary', 'draft-assumptions', 'evidence-rationale',
      'evidence-withdraw-reason', 'option-description', 'question-text', 'report-text']
      .some(id => $(id) && $(id).value.trim());
    setInterval(() => {
      if (document.hidden || unsaved() || dialogs.some(d => d.open) || !ready()) return;
      refresh();
    }, 4000);
  }

  arrange();
})();
