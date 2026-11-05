"""PR245 review-return scenarios through canonical React/FastAPI/PostgreSQL.

Only independently fictional fixtures and operator grants are used. One temporary
fetch wrapper holds delivery of a completed real return response without replacing
its body or status. A separate chronology check saves the original successful
queue response before changing one timestamp. Both wrappers are restored.
"""

import base64
from contextlib import contextmanager
import json


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

    def chronology(self, authored_question_id, expected_receipt, expected_ids, screenshots):
        screenshots.mkdir(parents=True, exist_ok=True)
        for field in ('question', 'history'):
            unsent_reason = 'Unsubmitted fictional reason before malformed ' + field + ' chronology.'
            self.reason_value(authored_question_id, unsent_reason)
            self.cd.evaluate("""((questionId,receiptId,field) => {
              const original=window.fetch;
              const fault={original,originalBody:null,mutatedBody:null,restoredBody:null,status:null,writes:0};
              window.__oiReviewChronology=fault;
              window.fetch=async (input,init) => {
                const url=typeof input==='string'?input:input.url;
                const method=(init?.method??input?.method??'GET').toUpperCase();
                if(method!=='GET'&&method!=='HEAD')fault.writes++;
                const response=await original(input,init);
                if(method==='GET'&&url.endsWith('/review-queue')&&response.status===200){
                  const body=await response.clone().text();
                  if(fault.originalBody===null){
                    fault.originalBody=body;fault.status=response.status;
                    const changed=JSON.parse(body);
                    const row=field==='question'?changed.items.find(r=>r.question_id===questionId):
                      changed.receipts.find(r=>r.receipt_id===receiptId);
                    if(!row)throw Error('Missing canonical chronology target');
                    row.created_at=field==='question'?'2026-02-30T10:00:00Z':'2026-11-03T24:00:00Z';
                    fault.mutatedBody=JSON.stringify(changed);
                    return new Response(fault.mutatedBody,{status:response.status,
                      statusText:response.statusText,headers:response.headers});
                  }
                  fault.restoredBody=body;
                }
                return response;
              };
              return true;
            })(""" + ','.join(map(json.dumps, (authored_question_id, expected_receipt, field))) + ')')
            try:
                self.cd.evaluate("document.querySelector('[data-testid=load-review-queue]').click()")
                self.cd.wait("typeof window.__oiReviewChronology?.mutatedBody==='string'",
                             'actual successful Review response captured before timestamp fault')
                original_text = self.cd.evaluate('window.__oiReviewChronology.originalBody')
                mutated_text = self.cd.evaluate('window.__oiReviewChronology.mutatedBody')
                (screenshots/('review-chronology-' + field + '-original.json')).write_text(original_text, encoding='utf-8')
                (screenshots/('review-chronology-' + field + '-fault.json')).write_text(mutated_text, encoding='utf-8')
                assert self.cd.evaluate('window.__oiReviewChronology.status') == 200
                original = json.loads(original_text)
                expected_fault = json.loads(original_text)
                rows, key, target = ('items', 'question_id', authored_question_id) if field == 'question' else \
                    ('receipts', 'receipt_id', expected_receipt)
                target_row = next(row for row in expected_fault[rows] if row[key] == target)
                target_row['created_at'] = '2026-02-30T10:00:00Z' if field == 'question' else '2026-11-03T24:00:00Z'
                assert json.loads(mutated_text) == expected_fault, 'Only one actual response timestamp is altered'
                self.cd.wait("document.querySelector('[data-testid=review-status]').textContent.includes('could not be verified')",
                             'malformed ' + field + ' chronology withholds the prior Review projection')
                assert self.cd.evaluate("!document.querySelector('[data-testid=review-queue-result]') && "
                                        "!document.querySelector('[data-testid=review-return-history]') && "
                                        "!document.querySelector('[data-testid=review-reason]') && "
                                        "!document.querySelector('[data-testid=return-for-verification]')")
                assert self.cd.evaluate('window.__oiReviewChronology.writes') == 0

                self.refresh(expected_receipt)
                restored_text = self.cd.evaluate('window.__oiReviewChronology.restoredBody')
                restored = json.loads(restored_text)
                (screenshots/('review-chronology-' + field + '-restored.json')).write_text(restored_text, encoding='utf-8')
                assert restored['items'] == original['items'] and restored['receipts'] == original['receipts'], \
                    'A fresh real read restores the exact unchanged questions and immutable history'
                assert sorted(self.cd.evaluate("[...document.querySelectorAll('[data-testid=review-queue-item]')].map(e=>e.dataset.questionId)")) == sorted(expected_ids)
                assert self.cd.evaluate("[...document.querySelectorAll('[data-testid=review-queue-item]')].map(e=>[e.dataset.questionId,e.dataset.sourceId])") == \
                    [[item['question_id'], item['source_id']] for item in restored['items']], \
                    'Rendered question/source anchors must match the restored authoritative queue'
                assert self.cd.evaluate("[...document.querySelectorAll('[data-testid=review-return-history] time')].map(e=>[e.getAttribute('datetime'),e.textContent])") == \
                    [[receipt['created_at'], receipt['created_at']] for receipt in restored['receipts']], \
                    'Visible and machine-readable history timestamps must preserve each restored value exactly'
                history = self.cd.evaluate("document.querySelector('[data-testid=review-return-history]').textContent")
                assert all(receipt['receipt_id'] in history for receipt in restored['receipts'])
                row = 'document.querySelector(' + json.dumps(self.item(authored_question_id)) + ')'
                assert self.cd.evaluate(row + ".querySelector('[data-testid=review-reason]').value") != unsent_reason, \
                    'A valid reread cannot resurrect an unsent reason cleared by invalid projection data'
                assert self.cd.evaluate(row + ".querySelector('[data-testid=return-for-verification]').disabled") is False
                assert self.cd.evaluate('window.__oiReviewChronology.writes') == 0, \
                    'Fault and restoration reads must not append any verification return'
            finally:
                self.cd.evaluate("""(() => {const fault=window.__oiReviewChronology;if(fault){
                  window.fetch=fault.original;delete window.__oiReviewChronology;}return true;})()""")
        print('PASS REVIEW CHRONOLOGY: actual successful queue originals saved separately; one impossible question/history timestamp at a time clears prior content and return controls; fresh authorized reads restore unchanged questions/history; unsent reasons stay cleared; no return writes.')

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

            self.chronology(authored_question_id, new_receipt, expected_ids, screenshots)

            # Both independent read gates must clear the displayed projection on denial.
            for action in ('review_queue_read', 'question_read'):
                unsent_reason = 'Unsubmitted fictional reason before loss of ' + action
                self.reason_value(authored_question_id, unsent_reason)
                credentials[0]['actions'].remove(action)
                write_grants()
                self.cd.evaluate("document.querySelector('[data-testid=load-review-queue]').click()")
                self.cd.wait("document.querySelector('[data-testid=review-status]').textContent.includes('unavailable')",
                             action + ' denial clears review history')
                assert self.cd.evaluate("!document.querySelector('[data-testid=review-queue-result]') && !document.querySelector('[data-testid=review-return-intent]')")
                credentials[0]['actions'].append(action)
                write_grants()
                self.refresh(new_receipt)
                assert self.cd.evaluate('document.querySelector(' + json.dumps(self.item(authored_question_id))
                                        + ").querySelector('[data-testid=review-reason]').value") != unsent_reason, \
                    'Restoring authority must not resurrect an unsent reason cleared on denial'

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
