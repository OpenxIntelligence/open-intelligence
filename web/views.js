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
  // Anything not listed is parked: still in the page, out of view.
  const LAYOUT = {
    careteam: [
      ['board', 'Worklist', ['view-worklist', 'workspace-start', 'view-board-details']],
      ['overview', 'Overview', ['view-glance', 'journey']],
      ['records', 'Records & timeline', ['source-intake', 'timeline', 'sources', 'biological-assets', 'import']],
      ['investigations', 'Investigations', ['investigations', 'synthesis']],
      ['research', 'Evidence & research', ['evidence', 'bibliography', 'synthetic-metrics']],
      ['review', 'Review & changes', ['changes-since-review', 're-review-tasks', 'scoped-review', 'activity', 'view-mission']],
      ['options', 'Options & tasks', ['options']],
    ],
    patient: [
      ['home', 'Home', ['pt-home']],
      ['reports', 'My records', ['pt-results', 'timeline', 'sources', 'patient-view']],
      ['questions', 'My questions', ['pt-next']],
      ['research', 'Research', ['pt-research', 'bibliography']],
    ],
    // No case yet: only the owner's setup, as the original entry flow expects.
    empty: [
      ['overview', 'Get started', ['overview', 'workspace-start']],
    ],
  };
  // Clinicians start from the cross-case worklist; patients from their home.
  const DEFAULT_TAB = {careteam: 'board', patient: 'home', empty: 'overview'};

  const main = $('main-content');
  const blocks = {};
  for (const id of ['incoming-board', 'overview', 'workspace-start', 'source-intake', 'metrics', 'patient-view',
    'patient-mission', 'timeline', 'sources', 'biological-assets', 'import', 'investigations', 'evidence',
    'bibliography', 'changes-since-review', 'activity', 'options']) blocks[id] = $(id);
  blocks['view-glance'] = main && main.querySelector(':scope > .glance-layout');
  if (blocks['view-glance'] && !blocks['view-glance'].id) blocks['view-glance'].id = 'view-glance';
  const missing = Object.keys(blocks).filter(id => !blocks[id]);
  if (!main || missing.length) {
    // Leave the original page fully intact rather than guess at a changed template.
    console.error('Open Intelligence views: owner template changed; missing ' + missing.join(', '));
    return;
  }
  // Sections added on newer owner branches (guided journey, synthesis, scoped
  // review, re-review tasks, metrics): placed in their tab when present,
  // skipped when absent, so the same layer works on either base.
  for (const id of ['journey', 'synthesis', 'scoped-review', 're-review-tasks', 'synthetic-metrics'])
    if ($(id) && $(id).closest('#main-content') === main) blocks[id] = $(id);

  // Patient Mission repeats every finding as a workflow projection; keep it,
  // collapsed, at the end of Review & changes.
  const mission = make('details', null, 'panel view-disclosure view-mission');
  mission.id = 'view-mission';
  mission.append(make('summary', 'Patient Mission · workflow projection'), blocks['patient-mission']);
  blocks['view-mission'] = mission;
  delete blocks['patient-mission'];

  // Investigations: put the main path first (question -> run -> saved drafts)
  // and tuck the hand-written draft form into a disclosure. Same elements and
  // IDs, only their order changes; skipped if the owner's structure differs.
  (() => {
    const section = blocks.investigations;
    const grid = section.querySelector(':scope > .investigation-grid');
    const draft = grid && grid.querySelector(':scope > .draft-pane');
    const history = section.querySelector(':scope > .investigation-history');
    const model = section.querySelector(':scope > .model-investigation');
    if (!grid || !draft || !history || !model) return;
    const manual = make('details', null, 'view-disclosure');
    manual.id = 'view-manual-draft';
    manual.append(make('summary', 'Write a draft by hand'), draft);
    grid.classList.add('view-single');
    grid.after(model);
    model.after(history);
    history.after(manual);
    // A half-written draft blocks case switching; keep it visible when it exists.
    for (const id of ['draft-observations', 'draft-summary', 'draft-assumptions'])
      $(id).addEventListener('input', () => { if ($(id).value.trim()) manual.open = true; });
  })();

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
  const worklist = card('view-worklist', 'All fictional cases', 'Worklist');
  const home = card('pt-home', null, 'Your care, in one place');
  const prepare = card('pt-next', null, 'For your next conversation');
  const recent = card('pt-recent', null, 'Recently');
  const results = card('pt-results', null, 'My results');
  const research = card('pt-research', 'Research', 'Research about my case');
  const questions = card('pt-questions', 'My questions', 'Questions for my care team');
  home.section.classList.add('view-hello');
  for (const [id, item] of Object.entries({'view-next': next, 'view-worklist': worklist, 'pt-home': home, 'pt-next': prepare,
    'pt-recent': recent, 'pt-results': results, 'pt-research': research, 'pt-questions': questions})) blocks[id] = item.section;
  // The original board stays available, collapsed, under the worklist.
  const boardDetails = make('details', null, 'panel view-disclosure view-mission');
  boardDetails.id = 'view-board-details';
  boardDetails.append(make('summary', 'Incoming board · original view'), blocks['incoming-board']);
  blocks['view-board-details'] = boardDetails;
  delete blocks['incoming-board'];

  // Containers: panels for the active role, parking for everything else.
  const panels = make('div', null, 'view-panels');
  panels.id = 'view-panels';
  const parking = make('div', null, 'view-parking');
  parking.id = 'view-parking';
  parking.hidden = true;
  main.insertBefore(panels, main.firstChild);
  main.insertBefore($('notice'), panels);
  // Persistent case header for the clinician workspace (not on the worklist).
  const casebar = make('div', null, 'view-casebar');
  casebar.id = 'view-casebar';
  casebar.setAttribute('aria-live', 'polite');
  main.insertBefore(casebar, panels);
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
  // Park (not just hide) the original section list: the owner's Tab handler
  // looks for '.rail nav a[href="#overview"]' and must not find a hidden copy.
  parking.append(oldMenu);
  // Hide only header pills that repeat the global "FICTIONAL DEMO" banner;
  // other boundary labels (e.g. "DISCUSSION ONLY") stay visible. Runs after
  // every arrange(), when every block (panels or parking) is in the document.
  const markDuplicateBanners = () => {
    for (const pill of document.querySelectorAll('.panel-head .pill-warn'))
      if (/FICTIONAL DEMO/i.test(pill.textContent)) pill.classList.add('view-dup-banner');
  };
  // The header logo links to #overview, which may be parked; treat it as "home".
  document.querySelector('.top .brand')?.addEventListener('click', event => {
    event.preventDefault();
    show(defaultTab());
    scrollTo(0, 0);
  });
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
  const effectiveRole = () => document.body.dataset.workspaceState === 'empty' ? 'empty' : role;

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
      for (const id of ids) if (blocks[id]) { panel.append(blocks[id]); placed.add(id); }
      built.push(panel);
    }
    for (const [id, block] of Object.entries(blocks)) if (!placed.has(id)) parking.append(block);
    panels.replaceChildren(...built);
    markDuplicateBanners();
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

  const defaultTab = () => DEFAULT_TAB[arrangedRole];
  const caseTab = () => arrangedRole === 'patient' ? 'home' : 'overview';

  function show(key) {
    if (!LAYOUT[arrangedRole].some(tab => tab[0] === key)) key = defaultTab();
    currentTab = key;
    for (const panel of panels.children) panel.hidden = panel.dataset.tab !== key;
    casebar.hidden = arrangedRole !== 'careteam' || key === 'board';
    if (key === 'board') paintWorklist();
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
      show(defaultTab());
    }
  }
  addEventListener('hashchange', route);
  // The board's "Open this case" scrolls to #overview, which sits in another
  // tab here. After the owner's handler switches the case, show that tab.
  // (Found through its wrapper: the board is not in the document until arrange().)
  boardDetails.querySelector('#incoming-list').addEventListener('click', event => {
    if (!event.target.closest('button')) return;
    show(caseTab());
    requestAnimationFrame(() => scrollTo(0, 0));
  });
  // Worklist rows switch the case through the owner's picker (which may refuse
  // while a draft is unsaved and says so), then open its workspace.
  function openCase(id) {
    const picker = $('case-picker');
    if (picker.value !== id) { picker.value = id; picker.dispatchEvent(new Event('change')); }
    show(caseTab());
    requestAnimationFrame(() => scrollTo(0, 0));
  }

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
  // The header scrolls away; never place the inspector above the viewport.
  const syncTop = () => document.documentElement.style.setProperty('--view-top',
    Math.max(0, top ? top.getBoundingClientRect().bottom : 0) + 'px');
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
  // Amendments since the last review, from the owner's changes-since-review
  // endpoint (loaded below); empty until it answers for this case.
  const amendmentsFor = state => changesCase === state.case.case_id && changes ? changes.amendments || [] : [];
  // The version pair to compare: the amendment that made a currently reopened
  // investigation stale, else the most recent amendment since review.
  const amendedPair = state => {
    const staleIds = new Set(state.snapshots.filter(s => s.state === 'stale' && reopened(state).has(Number(s.question_id)))
      .map(s => Number(s.id)));
    const items = amendmentsFor(state).slice().sort((a, b) => Number(b.event_id) - Number(a.event_id));
    const item = items.find(a => (a.invalidated_snapshot_ids || []).some(id => staleIds.has(Number(id)))) || items[0];
    if (!item) return null;
    const current = state.sources.find(s => Number(s.id) === Number(item.source_id));
    const previous = state.sources.find(s => Number(s.id) === Number(item.supersedes_source_id));
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
      paintAttention(ready());
    } catch (_) { /* The existing Review & changes panel reports errors. */ }
  }

  const UNRESOLVED = ['pending', 'indeterminate', 'conflicting', 'not-reported', 'not-assessed'];
  const shortDate = value => String(value || '').slice(0, 10);
  const stamp = value => String(value || '').replace('T', ' ').slice(0, 16);
  const link = (text, hash) => { const a = make('a', text); a.href = hash; return a; };

  // One amended report, explained without implying the person's condition changed.
  function changeBox(state, item) {
    const box = make('div', null, 'view-change');
    box.append(make('strong', 'A report was updated'),
      make('p', 'The earlier summary needs another look. You can still view both versions.', 'view-change-lead'),
      make('span', item.document_id + ' · version ' + item.superseded_version + ' → ' + item.version, 'view-label'));
    const diff = item.finding_key_diff || {};
    const row = (...parts) => { const line = make('div', null, 'view-change-row'); line.append(...parts); box.append(line); };
    for (const change of diff.reported_state_changes || [])
      row(make('span', plainName(change.finding_key) + ':'), make('span', plainState(change.previous_reported_state), 'view-was'),
        make('span', '→'), make('span', plainState(change.reported_state), 'view-now'));
    for (const key of diff.added_finding_keys || []) {
      const added = state.assertions.find(a => Number(a.source_version_id) === Number(item.source_id) && a.finding_key === key);
      row(make('span', plainName(key) + ':'), make('span', 'New in the corrected report'),
        make('span', added ? plainState(added.certainty) : '', 'view-now'));
    }
    for (const key of diff.removed_finding_keys || [])
      row(make('span', plainName(key) + ':'), make('span', 'No longer in the corrected report', 'view-was'));
    return box;
  }

  // Patient home: introduction, the most relevant update, then (separate
  // cards) what to bring to the next conversation and a short timeline.
  function paintHome(state) {
    const {section, body} = home;
    body.replaceChildren();
    section.querySelector(':scope > .view-eyebrow')?.remove();
    if (!state) return;
    const current = state.sources.filter(s => s.state === 'current');
    const amendments = amendmentsFor(state);
    const open = state.questions.filter(q => q.state === 'open');
    const unresolved = state.assertions.filter(a => UNRESOLVED.includes(a.certainty));
    const latest = current.map(s => s.issued_at).sort().pop();
    section.prepend(make('p', state.case.label.replace(/^Fictional case /, '') + ' · fictional case', 'view-eyebrow'));
    body.append(make('p', current.length
      ? current.length + ' current report' + (current.length === 1 ? '' : 's') + ' in your record' +
        (latest ? ', the latest issued ' + shortDate(latest) : '') + '.'
      : 'No reports are in your record yet. Your care team adds them here.', 'view-intro'));
    if (!current.length) return;
    // One primary action, chosen from the situation.
    const pair = amendedPair(state);
    const action = make('a', null, 'button view-primary');
    if (amendments.length && pair) {
      action.textContent = 'See what changed';
      action.href = '#pt-home';
      action.addEventListener('click', event => { event.preventDefault(); openComparison({id: pair.previous.id}, {id: pair.current.id}); });
    } else if (open.length || unresolved.length) { action.textContent = 'Review my questions'; action.href = '#pt-next'; }
    else { action.textContent = 'Open my records'; action.href = '#pt-results'; }
    body.append(action);
    for (const item of amendments) body.append(changeBox(state, item));
    if (!amendments.length) body.append(make('p', 'Nothing has changed since your care team’s last review.', 'view-status'));
  }

  function paintPrepare(state) {
    const {body} = prepare;
    body.replaceChildren();
    if (!state) return;
    const reopenedIds = reopened(state);
    const list = make('ul', null, 'view-list');
    for (const question of state.questions.filter(q => q.state === 'open')) {
      const row = make('li');
      const label = make('span', reopenedIds.has(Number(question.id)) ? 'Reopened because a report changed' : 'Saved question', 'view-label');
      if (reopenedIds.has(Number(question.id))) label.dataset.tone = 'attention';
      row.append(make('span', question.question), label);
      list.append(row);
    }
    for (const assertion of state.assertions.filter(a => UNRESOLVED.includes(a.certainty))) {
      const row = make('li');
      const text = make('div');
      text.append(make('span', plainName(assertion.finding_key) + ': ' + plainState(assertion.certainty).toLowerCase()),
        make('span', assertion.quote, 'view-quote'));
      const source = state.sources.find(s => s.id === assertion.source_version_id);
      row.append(text, viewSource('Report says…' + (source ? ' (' + source.document_id + ')' : ''), assertion.source_version_id, assertion.source_line));
      list.append(row);
    }
    if (!list.children.length) body.append(make('p', 'No open questions or unclear results right now.', 'muted'));
    else body.append(make('p', 'Saved questions and results that are not settled yet, with the report behind each.', 'muted'), list);
  }

  function paintRecent(state) {
    const {body} = recent;
    body.replaceChildren();
    if (!state) return;
    // Most recent by the report's own issue date, as a patient would read them.
    const events = state.sources.slice().sort((a, b) => String(b.issued_at).localeCompare(String(a.issued_at))).slice(0, 3);
    const list = make('ul', null, 'view-list');
    for (const source of events) {
      const row = make('li');
      row.append(make('span', plainName(source.kind) + ' report ' + source.document_id +
        (source.version > 1 ? ' corrected (version ' + source.version + ')' : '')), make('span', 'Issued ' + shortDate(source.issued_at), 'view-label'));
      list.append(row);
    }
    if (events.length) body.append(list);
    body.append(link('See your full record', '#pt-results'));
  }

  function paintResults(state) {
    const {body} = results;
    body.replaceChildren();
    if (!state) return;
    body.append(make('p', 'Each result as the report states it, with the exact report line.', 'muted'));
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
    body.append(make('p', 'Research your care team connected to this workspace. The public literature search below takes general topics only, never details from your records.', 'muted'));
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
      ? 'Source amended · dependent draft requires reassessment' : 'Open', 'view-label');
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
  // Clinician worklist across cases, from recorded workflow facts only (no
  // clinical urgency is inferred). Reads the same endpoints as the owner's board.
  let worklistSequence = 0;
  async function paintWorklist() {
    const sequence = ++worklistSequence;
    let cases;
    try { cases = await api('/api/cases'); } catch (_) { return; }
    const rows = await Promise.all(cases.map(async entry => {
      const id = encodeURIComponent(entry.case_id);
      try {
        const [state, delta] = await Promise.all([api('/api/cases/' + id + '/state'), api('/api/cases/' + id + '/changes-since-review')]);
        return {entry, state, delta};
      } catch (error) { return {entry, error}; }
    }));
    if (sequence !== worklistSequence) return;
    const {body} = worklist;
    body.replaceChildren();
    if (!rows.length) { body.append(make('p', 'No fictional cases yet. Create one from Overview.', 'muted')); return; }
    const facts = rows.map(row => {
      if (row.error) return {...row, review: 0, last: ''};
      const last = (row.state.events || []).map(e => e.occurred_at).sort().pop() || '';
      return {...row, review: reopened(row.state).size, last};
    }).sort((a, b) => (b.review - a.review) || String(b.last).localeCompare(String(a.last)));
    const table = make('table', null, 'view-table view-worklist-table');
    const head = make('thead');
    const headRow = make('tr');
    for (const label of ['Case', 'New since review', 'Review status', 'Open questions', 'Last update', ''])
      headRow.append(Object.assign(make('th', label), {scope: 'col'}));
    head.append(headRow);
    const tbody = make('tbody');
    for (const row of facts) {
      const tr = make('tr');
      const name = make('th', row.entry.label.replace(/^Fictional case /, ''));
      name.scope = 'row';
      name.append(make('span', row.entry.case_id + (row.entry.case_id === caseId ? ' · open now' : ''), 'view-quote'));
      if (row.error) { tr.append(name, make('td', 'Summary unavailable', 'muted')); tbody.append(tr); continue; }
      const counts = row.delta.counts || {};
      const fresh = [counts.amendments ? counts.amendments + ' amended' : '', counts.new_sources ? counts.new_sources + ' new' : '']
        .filter(Boolean).join(' · ') || '—';
      const status = make('span', row.review ? 'Source amended · draft needs reassessment'
        : row.state.snapshots.length ? 'No open review' : 'No drafts yet', 'view-label');
      if (row.review) status.dataset.tone = 'attention';
      const statusCell = make('td'); statusCell.append(status);
      const open = make('button', 'Open', 'view-link-button');
      open.type = 'button';
      open.addEventListener('click', () => openCase(row.entry.case_id));
      const action = make('td'); action.append(open);
      tr.append(name, make('td', fresh), statusCell,
        make('td', String(row.state.questions.filter(q => q.state === 'open').length)), make('td', stamp(row.last)), action);
      tbody.append(tr);
    }
    table.append(head, tbody);
    body.append(make('p', 'Sorted by review status, then most recent recorded activity. No clinical urgency is inferred.', 'muted'), table);
  }

  function paintCasebar(state) {
    casebar.replaceChildren();
    if (!state) return;
    const current = state.sources.filter(s => s.state === 'current');
    const received = state.sources.map(s => s.received_at).sort().pop();
    casebar.append(make('strong', state.case.label.replace(/^Fictional case /, '')), make('span', state.case.case_id, 'view-casebar-id'),
      make('span', current.length + ' current record' + (current.length === 1 ? '' : 's')),
      make('span', received ? 'Information received up to ' + stamp(received) : 'No records yet'),
      make('span', 'Fictional case', 'view-casebar-tag'));
  }

  // Make the origin of each draft explicit: recorded replay, live model output,
  // hand-written, or a demo acknowledgment (never presented as clinical review).
  function setOrigin(item, text, origin) {
    let tag = item.querySelector(':scope > .view-origin');
    if (!tag) { tag = make('span', '', 'view-origin'); item.prepend(tag); }
    if (tag.textContent !== text) tag.textContent = text;
    if (tag.dataset.origin !== origin) tag.dataset.origin = origin;
  }
  // Origin comes from recorded data, never from a draft's (user-written) text:
  // a saved draft's investigation_origin is null when written by hand and holds
  // the run's mode/model otherwise; model runs carry their own mode/model.
  let runs = {key: null, byId: new Map()};
  let runsSequence = 0;
  async function loadRuns(state) {
    const count = document.querySelectorAll('#model-investigation-list .snapshot').length;
    const key = state.case.case_id + ':' + count;
    if (runs.key === key || !count) return;
    const sequence = ++runsSequence;
    try {
      const data = await api('/api/cases/' + encodeURIComponent(state.case.case_id) + '/investigations');
      if (sequence !== runsSequence || state.case.case_id !== caseId) return;
      runs = {key, byId: new Map((data.investigations || []).map(run => [Number(run.id), run]))};
      paintOrigins(ready());
    } catch (_) { /* Labels stay absent rather than guessed. */ }
  }
  function paintOrigins(state) {
    if (!state) return;
    loadRuns(state);
    for (const item of document.querySelectorAll('#model-investigation-list .snapshot')) {
      // The heading is rendered by the owner's code from the run id, not from model text.
      const match = /^Model investigation #(\d+)$/.exec(item.querySelector('.topline strong')?.textContent || '');
      const run = match && runs.byId.get(Number(match[1]));
      if (!run) continue;
      setOrigin(item, run.mode === 'replay' ? 'Recorded replay · not a live AI run' : 'AI draft · ' + run.model + ' · unreviewed',
        run.mode === 'replay' ? 'replay' : 'ai');
    }
    for (const item of document.querySelectorAll('#snapshot-list .snapshot')) {
      const match = /^snapshot-(\d+)$/.exec(item.id);
      const snapshot = match && state.snapshots.find(s => Number(s.id) === Number(match[1]));
      if (!snapshot) continue;
      const origin = snapshot.investigation_origin;
      const replay = !!origin && origin.mode === 'replay';
      const basis = !origin ? 'Hand-written draft' : replay ? 'Draft from a recorded replay' : 'AI-assisted draft (' + (origin.model || 'model') + ')';
      const [text, kind] = snapshot.state === 'stale' ? ['Out of date · a source changed · kept in history', 'stale']
        : snapshot.state === 'draft' ? [basis + ' · unreviewed', origin && !replay ? 'ai' : 'replay']
        : snapshot.state === 'reviewed_in_demo' ? ['Demo acknowledgment · not a clinical review', 'demo']
        : [String(snapshot.state).replace(/_/g, ' '), 'replay'];
      setOrigin(item, text, kind);
    }
  }

  function paint() {
    paintQueued = false;
    const state = ready();
    const key = state && [state.case.case_id, state.sources.map(s => s.id + s.state).join(','),
      state.snapshots.map(s => s.id + s.state).join(',')].join('|');
    if (state && paintedCase !== key) {
      paintedCase = key;
      loadChanges(state);
    }
    paintHome(state);
    paintPrepare(state);
    paintRecent(state);
    paintResults(state);
    paintResearch(state);
    paintQuestions(state);
    paintNext(state);
    paintAttention(state);
    paintBadges(state);
    paintCasebar(state);
    paintOrigins(state);
    if (currentTab === 'board') paintWorklist();
  }
  function schedule() {
    if (paintQueued) return;
    paintQueued = true;
    queueMicrotask(paint);
  }
  const watch = new MutationObserver(schedule);
  for (const id of ['case-heading', 'assertion-list', 'snapshot-list', 'source-list', 'question-list', 'evidence-list', 'model-investigation-list'])
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
  // "Create workspace" in the rail opens the setup form, which lives on the
  // Worklist here; show it before the owner's handler focuses the form.
  document.addEventListener('click', event => {
    if (event.target.closest('#new-workspace-button') && arrangedRole === 'careteam') show('board');
  }, true);
  new MutationObserver(() => {
    const before = arrangedRole;
    if (effectiveRole() === before) return;
    arrange();
    // First case just created: continue where the owner's flow continues, adding records.
    if (before === 'empty' && arrangedRole === 'careteam') { show('records'); $('source-intake').open = true; }
  })
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
