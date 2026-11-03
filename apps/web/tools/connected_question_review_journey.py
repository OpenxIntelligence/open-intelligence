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
        questions.navigate('Overview')
        cd.wait("document.querySelector('[data-testid=continuity-draft]')?.dataset.state==='unsaved'",
                'Overview offers the same unfinished authored question')
        cd.evaluate("document.querySelector('[data-testid=continuity-resume]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=question-draft]'))",
                'Overview resumes the existing question editor')
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
        questions.overview_counts(current=3, reassessment=1)

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
        # Inspecting the source before submitting must not silently replace the
        # operator's unfinished reason with the fictional example text.
        prior_history = cd.evaluate("document.querySelector('[data-testid=review-return-history]')?.textContent")
        cd.evaluate("[...document.querySelectorAll('[data-testid=review-workspace] button')]"
                    ".find(e=>e.textContent==='View source questions').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=source-question-panel]'))",
                'contextual source inspection before return submission')
        questions.navigate('Records')
        questions.navigate('Overview')
        review.navigate('Review')
        assert cd.evaluate('document.querySelector(' + json.dumps(review.item())
                           + ").querySelector('[data-testid=review-reason]').value") == reason, \
            'Same-context navigation must preserve the exact unfinished verification reason'
        assert cd.evaluate("document.querySelector('[data-testid=review-return-history]')?.textContent") == prior_history, \
            'Navigation must not submit an unfinished verification return'
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
        questions.overview_counts(current=3, reassessment=1)
        inspect_exact_quote()
        after = fresh_brief()
        assert after['selected_source'] == before['selected_source']
        assert after['source_snapshot_sha256'] == before['source_snapshot_sha256']
        assert after['access_receipt_id'] != before['access_receipt_id']
        download_path, downloaded = questions.download_brief(question_id)
        assert custom.encode('utf-8') in downloaded and b'Clinical approval: false' in downloaded
        review.navigate('Review')
        verify_return()
        review.navigate('Journey')
        assert cd.evaluate('localStorage.length===0 && sessionStorage.length===0')
        continuity_receipt = {
            'contract': 'oi.synthetic-patient-continuity-acceptance/1',
            'patient_id': patient_id, 'case_id': case_id,
            'question_id': question_id, 'question': custom,
            'question_ids': expected_ids, 'return_receipt_id': receipt_id,
            'return_reason': reason, 'selected_source': after['selected_source'],
            'source_snapshot_sha256': after['source_snapshot_sha256'],
            'brief_access_before_return': before['access_receipt_id'],
            'brief_access_after_return': after['access_receipt_id'],
            'download_receipt': 'source-brief-' + question_id + '.json',
            'download_relative_path': str(download_path.relative_to(questions.artifacts)),
            'download_sha256': hashlib.sha256(downloaded).hexdigest(),
            'download_bytes': len(downloaded),
            'overview_current_unreviewed': 3, 'overview_reassessment_required': 1,
            'draft_resumed_through_overview': True,
            'clinical_approval': after['clinical_approval'],
            'model_executed': after['model_executed'],
            'biomedical_evidence_included': after['biomedical_evidence_included'],
        }
        (questions.artifacts/'patient-continuity-workflow.json').write_text(
            json.dumps(continuity_receipt, indent=2)+'\n', encoding='utf-8')
        print('PASS PATIENT CONTINUITY: Overview resumes the literal authored question, '
              'preserves scoped current/reassessment counts before and after its verification '
              'return, and connects the exact original to the actual fresh brief download.')
        print('PASS CONNECTED QUESTION REVIEW: literal authored question, exact original quotation, '
              'fresh source brief and actual download, explicit durable verification-return reason, '
              'same question and provenance after revisit; no clinical approval or model execution.')
        return {'question_id': question_id, 'source_id': source_id, 'return_receipt_id': receipt_id}
    finally:
        credentials[0]['actions'] = previous_actions
        write_grants()
