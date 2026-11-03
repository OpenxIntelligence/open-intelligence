"""One authored question through the actual source, brief and review owners.

Adds a fourth question after both existing three-question finish checks, inside
the source-question context that observes actual brief responses. Uses the fictional case,
operator grants, Chromium, FastAPI and PostgreSQL; no backend response is mocked.
"""

import hashlib
import json

from question_review_journey import QuestionReviewChecks


def exercise(cd, patient_id, case_id, source_id, source_text,
             credentials, write_grants, questions):
    findings = [(number, line.split('|', 2)[2])
                for number, line in enumerate(source_text.splitlines(), 1)
                if line.startswith('Finding: ')]
    assert len(findings) == 1, 'Use the existing single-finding fictional source'
    source_line, statement = findings[0]
    source_sha = hashlib.sha256(source_text.encode('utf-8')).hexdigest()
    custom = ('Which exact original line supports the current fictional marker entry, '
              'and what wording still needs verification?')
    reason = ('Please independently verify this fictional source wording against the '
              'original report; this is not clinical approval.')
    previous_actions = list(credentials[0]['actions'])
    try:
        credentials[0]['actions'] = sorted(set(previous_actions) | {
            'patient_read', 'source_read', 'composer_context_read', 'question_create',
            'question_read', 'review_packet_read', 'source_brief_export',
            'review_queue_read', 'review_return'})
        write_grants()
        assert cd.evaluate('Boolean(window.__oiBriefChecks)'), 'Active source-question context required'
        questions.navigate('Investigations')
        cd.evaluate("document.querySelector('[data-testid=world-load]').click()")
        observation = ("[...document.querySelectorAll('[data-testid=world-observation]')]"
                       '.find(e=>e.textContent.includes(' + json.dumps(source_id) + '))')
        cd.wait('Boolean(' + observation + ')', 'current fictional source observation')
        questions.history('Clinical approval: none')
        prior_ids = cd.evaluate("[...document.querySelectorAll('.question-items li')].map(e=>e.dataset.questionId)")
        assert len(prior_ids) == len(set(prior_ids)) == 3
        cd.evaluate(observation + ".querySelector('[data-testid=choose-question-draft]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=question-draft]'))", 'authoring field')
        cd.evaluate("""(() => {
          const input=document.querySelector('[data-testid=question-draft]');
          Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(input,
        """ + json.dumps(custom) + ");input.dispatchEvent(new Event('input',{bubbles:true}));})()")
        cd.wait("document.querySelector('[data-testid=question-draft]').value===" + json.dumps(custom),
                'literal patient-authored question')
        questions.navigate('Records')
        questions.navigate('Investigations')
        assert cd.evaluate("document.querySelector('[data-testid=question-draft]').value") == custom
        cd.evaluate("document.querySelector('[data-testid=prepare-custom-question]').click()")
        cd.wait("document.querySelector('[data-testid=composer-context]')?.textContent.includes("
                + json.dumps(custom) + ')', 'current source preflight for authored text')
        assert source_id in cd.evaluate("document.querySelector('[data-testid=composer-context]').textContent")
        question_id = questions.save()
        assert question_id not in prior_ids
        assert question_id in questions.history(custom)
        expected_ids = sorted(prior_ids + [question_id])
        assert sorted(cd.evaluate("[...document.querySelectorAll('.question-items li')].map(e=>e.dataset.questionId)")) == expected_ids
        row = '.question-items li[data-question-id="' + question_id + '"]'
        assert 'Clinical approval: none' in cd.evaluate('document.querySelector(' + json.dumps(row) + ').textContent')

        def inspect_exact_quote():
            questions.inspect_quote(question_id, current=True, expected_text=statement)
            assert cd.evaluate("document.querySelector('[data-testid=source-quote-literal]').textContent") == statement
            packet = cd.evaluate("document.querySelector('[data-testid=source-quote-packet]').textContent")
            assert all(value in packet for value in (question_id, custom, source_id, source_sha))
            assert 'line ' + str(source_line) in packet

        def fresh_brief():
            count = cd.evaluate('window.__oiBriefChecks.reads.length')
            questions.prepare_brief(question_id)
            cd.wait('window.__oiBriefChecks.reads.length===' + str(count + 1)
                    + " && document.querySelector('[data-testid=brief-access-receipt]')?.textContent==="
                    + 'window.__oiBriefChecks.reads.at(-1).access_receipt_id', 'fresh actual brief response')
            brief = cd.evaluate('window.__oiBriefChecks.reads.at(-1)')
            assert brief['status'] == 200 and brief['question']['question_id'] == question_id
            assert cd.evaluate("document.querySelector('[data-testid=source-brief-body]').textContent") == brief['body']
            assert brief['question']['question'] == custom
            assert brief['question']['source_context_state'] == 'current_unreviewed_question'
            assert brief['selected_source']['source_id'] == source_id
            assert brief['selected_source']['sha256'] == source_sha
            assert brief['selected_source']['line'] == source_line
            assert brief['selected_source']['statement'] == statement
            assert hashlib.sha256(brief['body'].encode('utf-8')).hexdigest() == brief['body_sha256']
            assert 'Human review: not_submitted' in brief['body'] and 'Clinical approval: false' in brief['body']
            assert not any(brief[key] for key in ('clinical_approval', 'model_executed', 'biomedical_evidence_included'))
            return brief

        inspect_exact_quote()
        before = fresh_brief()
        # Contextual question -> Review -> question navigation must invalidate prepared
        # source disclosures, as the sidebar already does. The saved question stays.
        cd.evaluate("document.querySelector('[data-testid=open-question-review]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=review-workspace]'))",
                'contextual entry to the verification inbox')
        cd.evaluate("""[...document.querySelectorAll('[data-testid=review-workspace] button')]
            .find(button => button.textContent.trim() === 'View source questions').click()""")
        cd.wait("Boolean(document.querySelector('[data-testid=source-question-panel]'))",
                'contextual return to source questions')
        assert not cd.evaluate("Boolean(document.querySelector('[data-testid=source-quote-packet]'))"), \
            'Contextual return must not resurrect a previously prepared source packet'
        assert not cd.evaluate("Boolean(document.querySelector('[data-testid=source-brief-preview]'))"), \
            'Contextual return must not resurrect a previously prepared source brief'
        assert question_id in questions.history(custom), 'Saved question must survive context navigation'
        review = QuestionReviewChecks(cd, patient_id, case_id, question_id, source_id)
        review.navigate('Review')

        def fresh_queue():
            old_access = cd.evaluate("document.querySelector('[data-testid=review-access-receipt]')?.textContent")
            review.refresh()
            cd.wait("Boolean(document.querySelector('[data-testid=review-access-receipt]'))"
                    + " && document.querySelector('[data-testid=review-access-receipt]').textContent!=="
                    + json.dumps(old_access) + ' && Boolean(document.querySelector('
                    + json.dumps(review.item()) + '))', 'fresh canonical review queue for this question')
            assert cd.evaluate("document.querySelector('[data-testid=review-case-id]').textContent") == case_id
            assert cd.evaluate('document.querySelector(' + json.dumps(review.item()) + ').dataset.sourceId') == source_id
            assert sorted(cd.evaluate("[...document.querySelectorAll('[data-testid=review-queue-item]')].map(e=>e.dataset.questionId)")) == expected_ids

        fresh_queue()
        assert cd.evaluate('document.querySelector(' + json.dumps(review.item()) + ').dataset.state') == 'awaiting_independent_verification'
        review.reason_value(question_id, reason)
        prior_return = cd.evaluate("document.querySelector('[data-testid=review-return-id]')?.textContent")
        review.submit(question_id)
        cd.wait("document.querySelector('[data-testid=review-return-status]')?.dataset.phase==='saved'"
                + " && Boolean(document.querySelector('[data-testid=review-return-id]'))"
                + " && document.querySelector('[data-testid=review-return-id]').textContent!=="
                + json.dumps(prior_return), 'new nonterminal return recorded for authored question')
        receipt_id = cd.evaluate("document.querySelector('[data-testid=review-return-id]').textContent")
        assert receipt_id.startswith('REVIEW-') and len(receipt_id) == 39
        result = cd.evaluate("document.querySelector('[data-testid=review-return-result]').textContent")
        assert question_id in result and 'question remains unreviewed' in result

        def verify_return():
            fresh_queue()
            assert cd.evaluate('document.querySelector(' + json.dumps(review.item()) + ').dataset.state') == 'returned_for_independent_verification'
            entry = cd.evaluate("[...document.querySelectorAll('[data-testid=review-return-history] li')]"
                                '.find(e=>e.textContent.includes(' + json.dumps(receipt_id) + '))?.textContent')
            assert entry and all(value in entry for value in (receipt_id, question_id, reason))
            assert 'No clinical approval, external notification or completed review.' in entry

        verify_return()
        questions.navigate('Investigations')
        assert question_id in questions.history(custom)
        inspect_exact_quote()
        after = fresh_brief()
        assert after['selected_source'] == before['selected_source']
        assert after['source_snapshot_sha256'] == before['source_snapshot_sha256']
        assert after['access_receipt_id'] != before['access_receipt_id']
        _, downloaded = questions.download_brief(question_id)
        assert custom.encode('utf-8') in downloaded and b'Clinical approval: false' in downloaded
        review.navigate('Review')
        verify_return()
        review.navigate('Journey')
        assert cd.evaluate('localStorage.length===0 && sessionStorage.length===0')
        print('PASS CONNECTED QUESTION REVIEW: literal authored question, exact original quotation, '
              'fresh source brief and actual download, explicit durable verification-return reason, '
              'same question and provenance after revisit; no clinical approval or model execution.')
        return {'question_id': question_id, 'source_id': source_id, 'return_receipt_id': receipt_id}
    finally:
        credentials[0]['actions'] = previous_actions
        write_grants()
