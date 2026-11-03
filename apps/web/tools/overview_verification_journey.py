"""Patient Overview continuity against the actual H1 PostgreSQL/React owners.

Reuses the #294 verification continuation with an observed, completed return
whose delivery is interrupted once. No successful response is fabricated; the
explicit retry must recover the real receipt using the exact original body.
"""

import base64
import json
import re


def nav(cd, section):
    cd.evaluate("[...document.querySelectorAll('nav[aria-label=\"Patient workspace\"] button')]"
                ".find(b=>b.textContent.startsWith(" + json.dumps(section) + ")).click()")
    selector = {'Overview': '[data-testid=patient-continuity]',
                'Investigations': '[data-testid=source-question-panel]',
                'Review': '[data-testid=review-workspace]',
                'Records': '[data-testid=records-workspace]',
                'Journey': '[data-testid=world-workspace]'}[section]
    cd.wait('Boolean(document.querySelector(' + json.dumps(selector) + '))', section + ' workspace')
    cd.wait("document.querySelector('h1')===document.activeElement", 'navigation focuses workspace heading')


def no_prepared_sources(cd):
    assert cd.evaluate("!document.querySelector('[data-testid=source-quote-packet]')"
                       " && !document.querySelector('[data-testid=source-brief-preview]')"), \
        'Navigation must not restore a prepared quotation or brief'


def overview_counts(cd, *, current, reassessment):
    """Return through the existing question CTA without fetching another history."""
    nav(cd, 'Overview')
    assert cd.evaluate("document.querySelector('[data-testid=continuity-current]').textContent") == str(current)
    assert cd.evaluate("document.querySelector('[data-testid=continuity-reassessment]').textContent") == str(reassessment)
    summary = cd.evaluate("document.querySelector('[data-testid=patient-continuity]').textContent")
    assert 'last successful reads' in summary and 'without clinical review' in summary
    if not current and not reassessment:
        assert 'No saved questions were returned for this case and grant.' in summary
        assert 'This does not mean there are no care needs.' in summary
    cd.evaluate("document.querySelector('[data-testid=continuity-open-questions]').click()")
    cd.wait("Boolean(document.querySelector('[data-testid=source-question-panel]'))",
            'Overview opens the same authorized source questions')


def exercise_history_states(cd, credentials, write_grants):
    """Run before the first saved question; keep unchecked, empty and denied distinct."""
    previous_actions = list(credentials[0]['actions'])

    def unchecked():
        nav(cd, 'Overview')
        assert cd.evaluate("!document.querySelector('[data-testid=continuity-current]')"
                           " && !document.querySelector('[data-testid=continuity-reassessment]')")
        assert 'has not been checked for the current case, or is unavailable' in cd.evaluate(
            "document.querySelector('[data-testid=continuity-questions]').textContent")

    try:
        unchecked()
        credentials[0]['actions'] = sorted(set(previous_actions) | {'question_read'})
        write_grants()
        nav(cd, 'Investigations')
        cd.evaluate("document.querySelector('[data-testid=load-source-questions]').click()")
        cd.wait("document.querySelector('[data-testid=source-question-history]')?.textContent"
                ".includes('No saved source-linked questions are visible.')", 'actual checked empty question history')
        assert cd.evaluate("document.querySelectorAll('.question-items li').length===0")
        overview_counts(cd, current=0, reassessment=0)
        credentials[0]['actions'].remove('question_read')
        write_grants()
        cd.evaluate("document.querySelector('[data-testid=load-source-questions]').click()")
        cd.wait("document.querySelector('[data-testid=questions-status]').textContent.includes('unavailable')",
                'denied real question read clears the checked empty result')
        assert cd.evaluate("!document.querySelector('[data-testid=source-question-history]')")
        unchecked()
    finally:
        credentials[0]['actions'] = previous_actions
        write_grants()
    nav(cd, 'Journey')
    print('PASS OVERVIEW HISTORY STATES: unchecked and denied history remain unknown; '
          'a real authorized empty response alone shows zero counts, without clinical reassurance.')


_OBSERVE_RECOVERY = r"""() => {
  if (window.__oiOverviewRecovery) throw Error('Overview recovery observer already installed');
  const actualFetch = window.fetch;
  const state = {requests:[], returns:[], sources:[], interruptNext:false};
  state.restore = () => {window.fetch=actualFetch;delete window.__oiOverviewRecovery;};
  window.__oiOverviewRecovery = state;
  window.fetch = async (input, init) => {
    const path = new URL(input instanceof Request ? input.url : input, location.href).pathname;
    const method = init?.method ?? (input instanceof Request ? input.method : 'GET');
    state.requests.push({path, method});
    const returning = path.endsWith('/return-for-verification') && method==='POST';
    const interrupt = returning && state.interruptNext;
    if (interrupt) state.interruptNext=false;
    const entry = returning ? {path, body:JSON.parse(init.body), status:null, receipt:null} : null;
    if (entry) state.returns.push(entry);
    const response = await actualFetch.call(window, input, init);
    if (returning) {
      const body = await response.clone().json();
      Object.assign(entry, {status:response.status, receipt:body.receipt_id, duplicate:body.duplicate});
      if (interrupt) throw new TypeError('Synthetic one-shot interruption after the real return committed');
    }
    if (path.endsWith('/sources') && method==='GET') {
      const body = await response.clone().json();
      state.sources.push({status:response.status, patient:body.patient_id, case:body.case_id,
        receipt:body.access_receipt_id});
    }
    return response;
  };
  return true;
}"""


def _capture_recovery(cd, artifacts):
    artifacts.mkdir(parents=True, exist_ok=True)
    try:
        for width in (320, 390, 1440):
            cd.command('Emulation.setDeviceMetricsOverride', {
                'width': width, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
            cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
            cd.wait('document.documentElement.scrollWidth<=innerWidth+1', 'Overview reflows at ' + str(width))
            # Refocus after each resize so the browser scrolls the actual CTA into view.
            cd.evaluate("document.querySelector('h1').focus({preventScroll:true});"
                        "document.querySelector('[data-testid=continuity-recover-return]').focus()")
            cd.wait("(()=>{const h=document.querySelector('.topbar').getBoundingClientRect();"
                    "const f=document.activeElement.getBoundingClientRect();return "
                    "document.activeElement.dataset.testid==='continuity-recover-return'"
                    " && f.top>=h.bottom && f.bottom<=innerHeight})()",
                    'Overview recovery focus clears context header at ' + str(width))
            image = cd.command('Page.captureScreenshot', {'format': 'png'})
            (artifacts/f'h1-overview-recovery-{width}.png').write_bytes(base64.b64decode(image['data']))
    finally:
        cd.command('Emulation.setDeviceMetricsOverride', {
            'width': 1440, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': False})


def exercise(cd, patient_id, case_id, returned_receipt, *, pending_question_id, artifacts):
    """Run after the fourth question, while the existing source/review grants apply."""
    selected = '[data-testid=review-queue-item][data-question-id="' + pending_question_id + '"]'
    reason = 'Recover this exact fictional source verification return without starting another request.'

    def fresh_queue():
        old_access = cd.evaluate("document.querySelector('[data-testid=review-access-receipt]')?.textContent")
        cd.evaluate("document.querySelector('[data-testid=load-review-queue]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=review-access-receipt]'))"
                " && document.querySelector('[data-testid=review-access-receipt]').textContent!=="
                + json.dumps(old_access), 'fresh canonical review queue')
        assert cd.evaluate("document.querySelector('[data-testid=review-case-id]').textContent") == case_id
        assert cd.evaluate("document.querySelectorAll('[data-testid=review-queue-item]').length===4")
        assert returned_receipt in cd.evaluate("document.querySelector('[data-testid=review-return-history]').textContent")

    cd.evaluate(f'({_OBSERVE_RECOVERY})()')
    try:
        nav(cd, 'Overview')
        summary = cd.evaluate("document.querySelector('[data-testid=patient-continuity]').textContent")
        assert patient_id in summary and case_id in summary
        no_prepared_sources(cd)
        requests = cd.evaluate('window.__oiOverviewRecovery.requests.length')
        cd.evaluate("document.querySelector('[data-testid=continuity-open-verification]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=review-workspace]'))", 'Overview opens existing Review')
        assert cd.evaluate('window.__oiOverviewRecovery.requests.length') == requests, \
            'Overview verification navigation must not read or submit a return'
        fresh_queue()
        no_prepared_sources(cd)
        cd.evaluate("[...document.querySelectorAll('[data-testid=review-workspace] button')]"
                    ".find(b=>b.textContent==='View source questions').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=source-question-panel]'))", 'contextual return to Questions')
        no_prepared_sources(cd)
        nav(cd, 'Overview')
        cd.evaluate("document.querySelector('[data-testid=continuity-open-records]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=records-workspace]'))", 'Overview opens canonical Records')
        nav(cd, 'Journey')
        assert cd.evaluate("Boolean(document.querySelector('[data-testid=world-projection]'))")
        nav(cd, 'Review')
        fresh_queue()
        assert cd.evaluate('document.querySelector(' + json.dumps(selected) + ').dataset.state') == 'awaiting_independent_verification'
        prior_history_count = cd.evaluate("document.querySelectorAll('[data-testid=review-return-history] li').length")
        cd.evaluate("(()=>{const e=document.querySelector(" + json.dumps(selected + ' textarea') + ");"
                    "Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,"
                    + json.dumps(reason) + ");e.dispatchEvent(new Event('input',{bubbles:true}));})()")
        cd.wait('document.querySelector(' + json.dumps(selected + ' textarea') + ').value===' + json.dumps(reason),
                'literal reason for interrupted return')
        cd.evaluate('window.__oiOverviewRecovery.interruptNext=true')
        cd.evaluate('document.querySelector(' + json.dumps(selected)
                    + ").querySelector('[data-testid=return-for-verification]').click()")
        cd.wait("document.querySelector('[data-testid=review-return-status]')?.dataset.phase==='unknown'",
                'lost delivery retains exact return recovery intent')
        original, = cd.evaluate('window.__oiOverviewRecovery.returns')
        assert original['status'] == 201 and original['duplicate'] is False
        assert re.fullmatch(r'REVIEW-[0-9A-F]{32}', original['receipt'])
        assert original['path'].endswith('/questions/' + pending_question_id + '/return-for-verification')
        assert original['body']['reason'] == reason and original['body']['synthetic'] is True
        assert re.fullmatch(r'[0-9a-f-]{36}', original['body']['request_key'])
        assert re.fullmatch(r'[0-9a-f]{64}', original['body']['expected_queue_fingerprint'])
        intent = cd.evaluate("document.querySelector('[data-testid=review-return-intent]').textContent")
        assert all(value in intent for value in (reason, pending_question_id, case_id,
                                                original['body']['expected_queue_fingerprint']))

        # Metadata refresh really completes through PostgreSQL. It clears the
        # World Model while retaining the unknown return for this exact case.
        nav(cd, 'Records')
        cd.evaluate("document.querySelector('[data-testid=load-sources]').click()")
        cd.wait("window.__oiOverviewRecovery.sources.length===1"
                " && Boolean(document.querySelector('[data-testid=source-index]'))"
                " && document.querySelector('[data-testid=records-status]')?.textContent"
                ".includes('Exact original source metadata read.')",
                'fresh actual source metadata after interrupted return')
        source_read, = cd.evaluate('window.__oiOverviewRecovery.sources')
        assert source_read['status'] == 200 and source_read['patient'] == patient_id and source_read['case'] == case_id
        assert re.fullmatch(r'ACCESS-[0-9A-F]{32}', source_read['receipt'])
        nav(cd, 'Journey')
        assert cd.evaluate("!document.querySelector('[data-testid=world-projection]')"), \
            'The recovery scenario requires source refresh to have removed the World Model'
        nav(cd, 'Overview')
        cd.wait("Boolean(document.querySelector('[data-testid=continuity-return-recovery]'))",
                'Overview finds exact uncertain return without World Model')
        assert cd.evaluate("!document.querySelector('[data-testid=continuity-open-verification]')"
                           " && !document.querySelector('[data-testid=continuity-current]')"
                           " && !document.querySelector('[data-testid=continuity-reassessment]')")
        recovery = cd.evaluate("document.querySelector('[data-testid=continuity-return-recovery]').textContent")
        assert case_id in recovery and pending_question_id not in recovery and reason not in recovery
        _capture_recovery(cd, artifacts)
        requests = cd.evaluate('window.__oiOverviewRecovery.requests.length')
        cd.evaluate("document.querySelector('[data-testid=continuity-recover-return]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=retry-review-return]'))", 'existing explicit exact-return retry')
        cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        assert cd.evaluate('window.__oiOverviewRecovery.requests.length') == requests, \
            'Overview recovery must be neutral navigation without an API read or POST'
        assert cd.evaluate('window.__oiOverviewRecovery.returns.length') == 1
        assert cd.evaluate("document.querySelector('[data-testid=review-case-id]').textContent") == case_id
        assert cd.evaluate("document.querySelector('[data-testid=review-return-intent]').textContent") == intent
        assert cd.evaluate("document.querySelector('[data-testid=review-return-status]').dataset.phase") == 'unknown'
        assert cd.evaluate("!document.querySelector('[data-testid=review-queue-result]')")

        cd.evaluate("document.querySelector('[data-testid=retry-review-return]').click()")
        cd.wait("document.querySelector('[data-testid=review-return-status]')?.dataset.phase==='saved'",
                'explicit retry recovers the real immutable receipt')
        first, retry = cd.evaluate('window.__oiOverviewRecovery.returns')
        assert first == original
        assert retry['body'] == original['body'] and retry['path'] == original['path'], \
            'Retry must preserve the exact request key, question, reason and source fingerprint'
        assert retry['status'] == 200 and retry['duplicate'] is True and retry['receipt'] == original['receipt']
        assert cd.evaluate("document.querySelector('[data-testid=review-return-id]').textContent") == original['receipt']
        fresh_queue()
        assert cd.evaluate('document.querySelector(' + json.dumps(selected) + ').dataset.state') == 'returned_for_independent_verification'
        entries = cd.evaluate("[...document.querySelectorAll('[data-testid=review-return-history] li')].map(e=>e.textContent)")
        assert len(entries) == prior_history_count + 1
        assert sum(original['receipt'] in entry for entry in entries) == 1
        assert any(all(value in entry for value in (original['receipt'], pending_question_id, reason)) for entry in entries)
        assert cd.evaluate('window.__oiOverviewRecovery.returns.length') == 2
        (artifacts/'overview-verification-recovery.json').write_text(json.dumps({
            'contract': 'oi.synthetic-overview-return-recovery-acceptance/1',
            'patient_id': patient_id, 'case_id': case_id, 'question_id': pending_question_id,
            'original_return': original, 'explicit_retry': retry, 'source_refresh': source_read,
            'navigation_api_requests': 0, 'durable_matching_receipts': 1,
        }, indent=2) + '\n', encoding='utf-8')
        nav(cd, 'Journey')
        cd.evaluate("document.querySelector('[data-testid=world-load]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=world-projection]'))", 'restore fresh source-derived Journey')
    finally:
        cd.evaluate('window.__oiOverviewRecovery?.restore()')
    print('PASS OVERVIEW RETURN RECOVERY: real committed return delivery interrupted once; '
          'same-case source refresh clears World Model; neutral Overview CTA makes no API request; '
          'explicit retry preserves exact body and request key, recovering one real receipt; '
          '320/390/1440 Overview containment, visible recovery focus and screenshots.')
    print('PASS OVERVIEW VERIFICATION CONTINUATION: same patient/case and existing immutable '
          'history; contextual Questions/Records links; no stale quotation, brief or clinical approval.')
