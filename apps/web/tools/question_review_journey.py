"""PR245 review-return scenarios through canonical React/FastAPI/PostgreSQL.

Only independently fictional fixtures and operator grants are used. The temporary
fetch wrapper holds delivery of a completed real response without replacing its
body or status. It is restored before the remainder of the browser journey.
"""

import base64
from contextlib import contextmanager
import json
import re


_HOLD_SOURCE_READS = r"""(paths) => {
  if (window.__oiNavigationSourceHold) throw Error('Source navigation hold already installed');
  const actualFetch=window.fetch;
  const state={held:{},releases:{},restored:false,failed:false};
  state.restore=()=>{
    state.restored=true;window.fetch=actualFetch;
    for(const release of Object.values(state.releases))release();
    delete window.__oiNavigationSourceHold;
  };
  window.__oiNavigationSourceHold=state;
  window.fetch=async (input,init)=>{
    const path=new URL(input instanceof Request?input.url:input,location.href).pathname;
    const kind=Object.keys(paths).find(key=>paths[key]===path);
    if(!kind)return actualFetch.call(window,input,init);
    const startedAt=performance.now();
    const signal=init?.signal??(input instanceof Request?input.signal:null);
    try{
      const response=await actualFetch.call(window,input,init);
      const body=await response.clone().json();
      const observed={status:response.status,contract:body.contract,
        patient:body.patient_id,case:body.case_id,
        question:body.question_id??body.question?.question_id,
        source:body.original_anchor?.source_id??body.selected_source?.source_id,
        receipt:body.source_access_receipt_id??body.access_receipt_id};
      if(!state.restored){
        if(state.held[kind])throw Error('Unexpected duplicate held source request');
        await new Promise(resolve=>{
          state.held[kind]={observed,startedAt,signal,delivered:false};
          state.releases[kind]=resolve;
        });
        state.held[kind].delivered=true;delete state.releases[kind];
      }
      return response;
    }catch(error){state.failed=true;throw error;}
  };
  return true;
}"""


def exercise_source_navigation_races(cd, patient_id, case_id, question_id, source_id, questions):
    """Discard actual late quotation and brief responses in mounted Questions."""
    row = '.question-items li[data-question-id="' + question_id + '"]'
    fingerprint = cd.evaluate("document.querySelector('[data-testid=world-fingerprint]').textContent")
    authored = cd.evaluate("document.querySelector('[data-testid=question-draft]').value")
    expected_ids = cd.evaluate("[...document.querySelectorAll('.question-items li')].map(e=>e.dataset.questionId)")
    assert cd.evaluate("Boolean(document.querySelector('[data-testid=source-quote-packet]'))"
                       " && Boolean(document.querySelector('[data-testid=source-brief-preview]'))"), \
        'Begin with both actual prepared readers, so navigation clearing is observable'

    def contextual_round_trip():
        cd.evaluate("document.querySelector('[data-testid=open-question-review]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=review-queue-result]'))", 'contextual handoff to actual Review')
        cd.evaluate("[...document.querySelectorAll('[data-testid=review-workspace] button')]"
                    ".find(e=>e.textContent==='View source questions').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=source-question-panel]'))", 'contextual return remounts Questions')

    def discarded():
        assert cd.evaluate("Boolean(document.querySelector('[data-testid=source-question-panel]'))")
        assert cd.evaluate("!document.querySelector('[data-testid=source-quote-packet]')"
                           " && !document.querySelector('[data-testid=source-brief-preview]')"), \
            'Contextual or same-section navigation must invalidate both prepared readers'
        assert cd.evaluate('!document.querySelector(' + json.dumps(row + ' [data-testid=source-quote-packet-open]') + ').disabled')
        assert cd.evaluate('!document.querySelector(' + json.dumps(row + ' [data-testid=brief-prepare]') + ').disabled')
        assert cd.evaluate("document.querySelector('[data-testid=question-draft]').value") == authored
        assert cd.evaluate("document.querySelector('[data-testid=world-fingerprint]').textContent") == fingerprint
        assert cd.evaluate("[...document.querySelectorAll('.question-items li')].map(e=>e.dataset.questionId)") == expected_ids

    contextual_round_trip()
    discarded()
    root = '/v1/patients/' + patient_id + '/cases/' + case_id + '/questions/' + question_id
    paths = {'packet': root + '/source-review-packet', 'brief': root + '/brief'}
    evidence = []
    for transition in ('contextual_round_trip', 'same_section'):
        cd.evaluate(f'({_HOLD_SOURCE_READS})({json.dumps(paths)})')
        try:
            cd.evaluate('document.querySelector(' + json.dumps(row + ' [data-testid=source-quote-packet-open]') + ').click()')
            cd.evaluate('document.querySelector(' + json.dumps(row + ' [data-testid=brief-prepare]') + ').click()')
            cd.wait('window.__oiNavigationSourceHold.failed || Object.keys(window.__oiNavigationSourceHold.held).length===2',
                    'actual completed quotation and brief responses held before delivery')
            assert not cd.evaluate('window.__oiNavigationSourceHold.failed')
            observed = cd.evaluate('Object.fromEntries(Object.entries(window.__oiNavigationSourceHold.held).map(([k,v])=>[k,v.observed]))')
            for kind, contract in (('packet', 'oi.synthetic-question-source-review-packet/1'),
                                   ('brief', 'oi.synthetic-source-brief/2')):
                actual = observed[kind]
                assert actual['status'] == 200 and actual['contract'] == contract
                assert actual['patient'] == patient_id and actual['case'] == case_id
                assert actual['question'] == question_id and actual['source'] == source_id
                assert re.fullmatch(r'ACCESS-[0-9A-F]{32}', actual['receipt'])
            if transition == 'contextual_round_trip':
                contextual_round_trip()
            else:
                questions.navigate('Investigations')
                cd.wait("document.querySelector('h1')===document.activeElement", 'same-section navigation retains heading focus')
            discarded()
            # Release before the client's own timeout. A deadline or aborted
            # request must not masquerade as successful navigation invalidation.
            cd.evaluate("""(()=>{const h=window.__oiNavigationSourceHold;
              for(const value of Object.values(h.held)){
                if(!value.signal||value.signal.aborted||performance.now()-value.startedAt>=10000)
                  throw Error('Source navigation race exceeded the client request deadline');
              }
              for(const release of Object.values(h.releases))release();
            })()""")
            cd.wait('Object.values(window.__oiNavigationSourceHold.held).every(value=>value.delivered)',
                    'both completed server responses delivered after navigation')
            cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
            discarded()
            evidence.append({'transition': transition, 'actual_responses': observed,
                             'questions_mounted_after_delivery': True, 'prepared_readers_restored': False})
        finally:
            cd.evaluate('window.__oiNavigationSourceHold?.restore()')
    (questions.artifacts/'source-navigation-races.json').write_text(json.dumps({
        'contract': 'oi.synthetic-source-navigation-race-acceptance/1',
        'patient_id': patient_id, 'case_id': case_id, 'question_id': question_id,
        'world_fingerprint': fingerprint, 'scenarios': evidence,
    }, indent=2) + '\n', encoding='utf-8')
    print('PASS SOURCE NAVIGATION RACES: prepared quotation and brief cleared; actual 200 responses '
          'held across contextual roundtrip and same-section navigation, delivered before timeout '
          'into mounted Questions and discarded; literal draft, saved questions and World Model retained.')


class QuestionReviewChecks:
    def __init__(self, cd, patient_id, case_id, question_id, source_id):
        self.cd = cd
        self.patient_id = patient_id
        self.case_id = case_id
        self.question_id = question_id
        self.source_id = source_id
        self.receipt_id = None
        self.reason = 'Independently verify the fictional marker wording and its unresolved status.'

    def navigate(self, section):
        self.cd.evaluate("[...document.querySelectorAll('nav button')].find(e=>e.textContent.startsWith("
                         + json.dumps(section) + ")).click()")
        selector = {'Review':'[data-testid=review-workspace]', 'Journey':'[data-view=journey]',
                    'Records':'[data-testid=records-workspace]'}[section]
        self.cd.wait('Boolean(document.querySelector(' + json.dumps(selector) + '))', section + ' workspace')

    def item(self, question_id=None):
        return '[data-testid=review-queue-item][data-question-id="' + (question_id or self.question_id) + '"]'

    def refresh(self, expected=None):
        self.cd.evaluate("document.querySelector('[data-testid=load-review-queue]').click()")
        self.cd.wait("Boolean(document.querySelector('[data-testid=review-queue-result]'))",
                     'authorized canonical review inbox')
        if expected:
            assert expected in self.cd.evaluate("document.querySelector('[data-testid=review-queue-result]').textContent")

    def reason_value(self, question_id, text):
        selector = self.item(question_id) + ' textarea'
        self.cd.evaluate("(() => {const e=document.querySelector(" + json.dumps(selector) + ");"
                         "Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,"
                         + json.dumps(text) + ");e.dispatchEvent(new Event('input',{bubbles:true}));})()")
        self.cd.wait('document.querySelector(' + json.dumps(selector) + ').value===' + json.dumps(text),
                     'independently editable return reason')

    def submit(self, question_id):
        self.cd.evaluate('document.querySelector(' + json.dumps(self.item(question_id))
                         + ").querySelector('[data-testid=return-for-verification]').click()")

    def start(self):
        fingerprint = self.cd.evaluate("document.querySelector('[data-testid=world-fingerprint]').textContent")
        self.cd.evaluate("document.querySelector('[data-testid=open-question-review]').click()")
        self.cd.wait("Boolean(document.querySelector('[data-testid=review-queue-result]'))",
                     'saved canonical question opens the existing Review workspace')
        # Exercise the contextual handoff in both directions, not only the
        # global navigation whose clearing behavior was already implemented.
        self.cd.evaluate("[...document.querySelectorAll('[data-testid=review-workspace] button')].find(e=>e.textContent==='View source questions').click()")
        self.cd.wait("Boolean(document.querySelector('[data-testid=source-question-panel]'))",
                     'contextual review link returns to the same source questions')
        assert self.cd.evaluate("!document.querySelector('[data-testid=source-quote-packet]')"), \
            'Contextual navigation must invalidate the prepared source packet'
        assert self.cd.evaluate("!document.querySelector('[data-testid=source-brief-preview]')"), \
            'Contextual navigation must invalidate the prepared brief'
        self.cd.evaluate("document.querySelector('[data-testid=open-question-review]').click()")
        self.cd.wait("Boolean(document.querySelector('[data-testid=review-queue-result]'))",
                     'same canonical question returns to independent verification')
        assert self.cd.evaluate("document.querySelectorAll('[data-testid=review-workspace]').length===1")
        assert self.cd.evaluate("document.querySelector('[data-testid=review-case-id]').textContent") == self.case_id
        assert self.cd.evaluate('document.querySelector(' + json.dumps(self.item()) + ').dataset.sourceId') == self.source_id
        assert self.cd.evaluate('document.querySelector(' + json.dumps(self.item()) + ').dataset.state') == 'awaiting_independent_verification'
        initial_access = self.cd.evaluate("document.querySelector('[data-testid=review-access-receipt]').textContent")
        assert initial_access.startswith('ACCESS-') and len(initial_access) == 39
        self.reason_value(self.question_id, self.reason)

        # Hold only delivery of an actual completed POST to prove navigation and
        # editable-field guards while its exact intent remains in flight.
        self.cd.evaluate("""(() => {
          const original=window.fetch;
          const hold={original,waiting:false,seen:false,release:null,body:null,status:null};
          window.__oiReviewHold=hold;
          window.fetch=async (input,init) => {
            const url=typeof input==='string'?input:input.url;
            if(!hold.seen && url.endsWith('/return-for-verification') && init?.method==='POST'){
              hold.seen=true;hold.body=JSON.parse(init.body);
              const response=await original(input,init);
              await response.clone().arrayBuffer();
              hold.status=response.status;hold.waiting=true;
              return new Promise(resolve=>{hold.release=()=>{hold.release=null;hold.waiting=false;resolve(response);};});
            }
            return original(input,init);
          };
          return true;
        })()""")
        try:
            self.submit(self.question_id)
            self.cd.wait('window.__oiReviewHold?.waiting===true', 'completed real return response held for delivery')
            assert self.cd.evaluate('window.__oiReviewHold.status') == 201
            assert self.cd.evaluate('window.__oiReviewHold.body.reason') == self.reason
            assert self.cd.evaluate('window.__oiReviewHold.body.expected_queue_fingerprint') != initial_access
            assert self.cd.evaluate('document.querySelector(' + json.dumps(self.item() + ' textarea') + ').disabled')
            self.navigate('Journey')
            assert self.cd.evaluate("document.querySelector('[data-testid=world-fingerprint]').textContent") == fingerprint
            self.navigate('Review')
            assert self.reason in self.cd.evaluate("document.querySelector('[data-testid=review-return-intent]').textContent")
            assert self.cd.evaluate('document.querySelector(' + json.dumps(self.item() + ' textarea') + ').value') == self.reason
            assert self.cd.evaluate('document.querySelector(' + json.dumps(self.item() + ' textarea') + ').disabled')
            self.cd.evaluate('window.__oiReviewHold.release()')
            self.cd.wait("document.querySelector('[data-testid=review-return-status]')?.dataset.phase==='saved'",
                         'actual nonterminal return receipt received')
            self.receipt_id = self.cd.evaluate("document.querySelector('[data-testid=review-return-id]').textContent")
            assert self.receipt_id.startswith('REVIEW-') and len(self.receipt_id) == 39
        finally:
            self.cd.evaluate("""(() => {const hold=window.__oiReviewHold;if(hold){
              window.fetch=hold.original;hold.release?.();delete window.__oiReviewHold;}return true;})()""")

        self.refresh(self.receipt_id)
        assert self.reason in self.cd.evaluate("document.querySelector('[data-testid=review-return-history]').textContent")
        assert self.cd.evaluate('document.querySelector(' + json.dumps(self.item()) + ').dataset.state') == 'returned_for_independent_verification'
        assert self.cd.evaluate("document.querySelector('[data-testid=review-access-receipt]').textContent") != initial_access

    def after_amendment(self):
        self.navigate('Review')
        self.refresh(self.receipt_id)
        row = self.cd.evaluate('document.querySelector(' + json.dumps(self.item()) + ').textContent')
        assert self.source_id in row and 'version 1, line 8' in row
        assert self.cd.evaluate('document.querySelector(' + json.dumps(self.item()) + ').dataset.state') == 'source_reassessment_required'
        assert self.cd.evaluate('!document.querySelector(' + json.dumps(self.item()) + ").querySelector('[data-testid=return-for-verification]')")
        history = self.cd.evaluate("document.querySelector('[data-testid=review-return-history]').textContent")
        assert self.receipt_id in history and self.reason in history
        self.navigate('Records')

    def finish(self, replacement_source_id, credentials, write_grants, screenshots,
               *, replacement_question_id, authored_question_id):
        expected_ids = [self.question_id, replacement_question_id, authored_question_id]
        assert len(set(expected_ids)) == 3
        previous_actions = list(credentials[0]['actions'])
        self.navigate('Review')
        try:
            # Saved question review does not inherit Composer execution/context permission.
            credentials[0]['actions'] = [a for a in previous_actions if a != 'composer_context_read']
            write_grants()
            self.refresh(self.receipt_id)
            actual_ids = self.cd.evaluate("[...document.querySelectorAll('[data-testid=review-queue-item]')].map(e=>e.dataset.questionId)")
            assert sorted(actual_ids) == sorted(expected_ids), 'Review contains the exact three persisted questions'
            assert self.cd.evaluate('document.querySelector(' + json.dumps(self.item()) + ').dataset.state') == 'source_reassessment_required'
            # Both current questions share one v2 source; select the exact default
            # question captured by the source journey, never the first source match.
            new_question = replacement_question_id
            assert new_question != self.question_id
            for question_id in (new_question, authored_question_id):
                row = 'document.querySelector(' + json.dumps(self.item(question_id)) + ')'
                assert self.cd.evaluate(row + '.dataset.sourceId') == replacement_source_id
                assert self.cd.evaluate(row + '.dataset.state') == 'awaiting_independent_verification'
                assert 'version 2, line 9' in self.cd.evaluate(row + '.textContent')
            current_reason = 'Independently verify the amended fictional marker against its new source version.'

            # A readable queue is not permission to append a return.
            credentials[0]['actions'].remove('review_return')
            write_grants()
            self.reason_value(new_question, current_reason)
            self.submit(new_question)
            self.cd.wait("document.querySelector('[data-testid=review-return-status]')?.dataset.phase==='error'",
                         'independent review-return grant denial')
            assert self.cd.evaluate("!document.querySelector('[data-testid=review-queue-result]') && !document.querySelector('[data-testid=review-return-history]')")
            assert self.patient_id in self.cd.evaluate("document.querySelector('[data-testid=review-workspace]').textContent")
            credentials[0]['actions'].append('review_return')
            write_grants()
            self.refresh(self.receipt_id)
            self.reason_value(new_question, current_reason)
            self.submit(new_question)
            self.cd.wait("document.querySelector('[data-testid=review-return-status]')?.dataset.phase==='saved'",
                         'restored independent grant records a current v2 return')
            new_receipt = self.cd.evaluate("document.querySelector('[data-testid=review-return-id]').textContent")
            assert new_receipt != self.receipt_id
            self.refresh(new_receipt)
            assert self.cd.evaluate('document.querySelector(' + json.dumps(self.item(new_question)) + ').dataset.state') == 'returned_for_independent_verification'
            assert self.cd.evaluate('document.querySelector(' + json.dumps(self.item(authored_question_id)) + ').dataset.state') == 'awaiting_independent_verification'
            history = self.cd.evaluate("document.querySelector('[data-testid=review-return-history]').textContent")
            assert self.reason in history and current_reason in history and self.receipt_id in history
            assert authored_question_id not in history, 'Returning the default v2 question cannot return the authored question'

            # Both independent read gates must clear the displayed projection on denial.
            for action in ('review_queue_read', 'question_read'):
                credentials[0]['actions'].remove(action)
                write_grants()
                self.cd.evaluate("document.querySelector('[data-testid=load-review-queue]').click()")
                self.cd.wait("document.querySelector('[data-testid=review-status]').textContent.includes('unavailable')",
                             action + ' denial clears review history')
                assert self.cd.evaluate("!document.querySelector('[data-testid=review-queue-result]') && !document.querySelector('[data-testid=review-return-intent]')")
                credentials[0]['actions'].append(action)
                write_grants()
                self.refresh(new_receipt)

            assert sorted(self.cd.evaluate("[...document.querySelectorAll('[data-testid=review-queue-item]')].map(e=>e.dataset.questionId)")) == sorted(expected_ids)
            assert self.cd.evaluate('document.querySelector(' + json.dumps(self.item(authored_question_id)) + ').dataset.state') == 'awaiting_independent_verification'

            screenshots.mkdir(parents=True, exist_ok=True)
            self.cd.command('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
            self.cd.wait('window.innerWidth===1440', 'review panel desktop viewport')
            self.cd.evaluate("document.querySelector('[data-testid=review-workspace]').scrollIntoView({block:'start'})")
            clip = self.cd.evaluate("""(() => {
              const r=document.querySelector('[data-testid=review-workspace]').getBoundingClientRect();
              return {x:r.left+scrollX,y:r.top+scrollY,width:r.width,height:r.height,scale:1};
            })()""")
            image = self.cd.command('Page.captureScreenshot', {'format':'png','captureBeyondViewport':True,'clip':clip})
            (screenshots/'h1-question-review-desktop.png').write_bytes(base64.b64decode(image['data']))
            self.cd.command('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
            self.cd.wait('window.innerWidth===390', 'review panel narrow viewport')
            assert self.cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
            self.cd.command('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
        finally:
            credentials[0]['actions'] = previous_actions
            write_grants()
        self.navigate('Journey')
        print('PASS QUESTION REVIEW: canonical saved question to one review inbox; editable captured reason; held real return response survives navigation; immutable v1 receipt remains historical after amendment; current v2 question/return; independent queue, question and return grants; Composer-independent operation; desktop screenshot and narrow containment; no clinical approval or external notification.')


@contextmanager
def exercise(cd, patient_id, case_id, question_id, source_id, credentials, write_grants):
    previous_actions = list(credentials[0]['actions'])
    try:
        credentials[0]['actions'] = sorted(set(previous_actions) | {'review_queue_read','review_return'})
        write_grants()
        checks = QuestionReviewChecks(cd, patient_id, case_id, question_id, source_id)
        checks.start()
        yield checks
    finally:
        credentials[0]['actions'] = previous_actions
        write_grants()
