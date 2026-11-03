"""Actual PostgreSQL/React patient Overview → verification continuation contract.

Synthetic only. Exercises the existing source-question, original-source and
nonterminal verification-return owners; no extra APIs, clinical approvals or
local browser persistence.
"""
import json


def nav(cd, section):
    cd.evaluate("Array.from(document.querySelectorAll('nav[aria-label=\"Patient workspace\"] button'))"
                ".find(b=>b.textContent.includes("+json.dumps(section)+")).click()")


def exercise(cd, patient_id, case_id, returned_receipt, pending_question_id=None):
    nav(cd, "Overview")
    cd.wait("Boolean(document.querySelector('[data-testid=patient-continuity]'))",
            "existing scoped patient Overview projection")
    summary=cd.evaluate("document.querySelector('[data-testid=patient-continuity]').textContent")
    assert patient_id in summary and case_id in summary
    assert cd.evaluate("Boolean(document.querySelector('[data-testid=continuity-open-verification]'))")
    assert cd.evaluate("!document.querySelector('[data-testid=source-quote-packet]')"
                       " && !document.querySelector('[data-testid=source-brief-preview]')")

    # Overview does not create another review queue, authorize a clinician or
    # silently return an item. It links to the preexisting permission-scoped UI.
    cd.evaluate("document.querySelector('[data-testid=continuity-open-verification]').click()")
    cd.wait("Boolean(document.querySelector('[data-testid=review-workspace]'))",
            "Overview opens canonical verification-return workflow")
    cd.evaluate("document.querySelector('[data-testid=load-review-queue]').click()")
    cd.wait("document.querySelector('[data-testid=review-return-history]')?.textContent.includes("
            +json.dumps(returned_receipt)+")",
            "exact immutable verification return still visible after Overview handoff")
    assert cd.evaluate("document.querySelector('[data-testid=review-case-id]').textContent==="
                       +json.dumps(case_id))
    assert cd.evaluate("document.querySelectorAll('[data-testid=review-queue-item]').length===4")
    assert cd.evaluate("!document.querySelector('[data-testid=source-quote-packet]')"
                       " && !document.querySelector('[data-testid=source-brief-preview]')")

    # Contextual navigation follows the same freshness boundary as the rail.
    cd.evaluate("[...document.querySelectorAll('[data-testid=review-workspace] button')]"
                ".find(b=>b.textContent==='View source questions').click()")
    cd.wait("Boolean(document.querySelector('[data-view=investigations]'))",
            "Review contextual link opens the original Investigations workspace")
    nav(cd,"Overview")
    cd.wait("Boolean(document.querySelector('[data-testid=continuity-open-records]'))",
            "patient Overview remains available after Review")
    cd.evaluate("document.querySelector('[data-testid=continuity-open-records]').click()")
    cd.wait("Boolean(document.querySelector('[data-testid=records-workspace]'))",
            "Overview opens the same canonical source Records")
    nav(cd,"Journey")
    cd.wait("Boolean(document.querySelector('[data-testid=world-projection]'))",
            "source-derived journey remains present after navigation")
    if pending_question_id:
        # Inject a one-shot *network-delivery* failure, never a fabricated
        # positive API response. All reads and the later retry still hit the
        # disposable PostgreSQL/FastAPI source and return owners.
        nav(cd, "Review")
        cd.evaluate("document.querySelector('[data-testid=load-review-queue]').click()")
        selected='[data-testid=review-queue-item][data-question-id="'+pending_question_id+'"]'
        cd.wait("Boolean(document.querySelector("+json.dumps(selected)+"))",
                "known current fictional question for uncertain return")
        assert cd.evaluate("document.querySelector("+json.dumps(selected)+").dataset.state") == "awaiting_independent_verification"
        cd.evaluate("""(() => {
          const original=window.fetch, hook={original,seen:false};
          window.__oiReturnDeliveryFault=hook;
          window.fetch=(input,init)=>{
            const url=typeof input==='string'?input:input.url;
            if(!hook.seen && url.endsWith('/return-for-verification') && init?.method==='POST'){
              hook.seen=true;
              return Promise.reject(new TypeError('Synthetic one-shot interrupted network delivery'));
            }
            return original(input,init);
          };
          return true;
        })()""")
        try:
            cd.evaluate("document.querySelector("+json.dumps(selected)+")"
                        ".querySelector('[data-testid=return-for-verification]').click()")
            cd.wait("document.querySelector('[data-testid=review-return-status]')?.dataset.phase==='unknown'",
                    "interrupted return retains exact same-session recovery intent")
            assert cd.evaluate("window.__oiReturnDeliveryFault.seen===true")
            assert cd.evaluate("document.querySelector('[data-testid=review-return-intent]')?.textContent.includes("
                               +json.dumps(pending_question_id)+")")
        finally:
            cd.evaluate("""(() => {const h=window.__oiReturnDeliveryFault;if(h){
              window.fetch=h.original;delete window.__oiReturnDeliveryFault;}return true;})()""")

        # Reading source metadata clears the current World Model but must not
        # destroy an uncertain return for the SAME still-active patient/case.
        nav(cd, "Records")
        cd.evaluate("document.querySelector('[data-testid=load-sources]').click()")
        cd.wait("document.querySelector('[data-testid=source-index]')!==null",
                "real source metadata refresh after interrupted verification return")
        nav(cd, "Overview")
        cd.wait("Boolean(document.querySelector('[data-testid=continuity-return-recovery]'))",
                "Overview shows neutral exact-return recovery without World Model")
        assert cd.evaluate("!document.querySelector('[data-testid=continuity-open-verification]')")
        assert cd.evaluate("document.querySelector('[data-testid=continuity-return-recovery]').textContent.includes("
                           +json.dumps(case_id)+")")
        assert cd.evaluate("!document.querySelector('[data-testid=continuity-return-recovery]').textContent.includes("
                           +json.dumps(pending_question_id)+")")
        cd.evaluate("document.querySelector('[data-testid=continuity-recover-return]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=retry-review-return]'))",
                "Overview recovers only the exact original return intent")
        assert cd.evaluate("document.querySelector('[data-testid=review-case-id]').textContent==="
                           +json.dumps(case_id))
        cd.evaluate("document.querySelector('[data-testid=retry-review-return]').click()")
        cd.wait("document.querySelector('[data-testid=review-return-status]')?.dataset.phase==='saved'",
                "legitimate retry commits through canonical review-return owner")
        receipt=cd.evaluate("document.querySelector('[data-testid=review-return-id]').textContent")
        assert receipt.startswith('REVIEW-') and len(receipt)==39
        cd.evaluate("document.querySelector('[data-testid=load-review-queue]').click()")
        cd.wait("document.querySelector('[data-testid=review-return-history]')?.textContent.includes("
                +json.dumps(receipt)+")", "retried return has one durable immutable receipt")
        nav(cd, "Journey")
        cd.evaluate("document.querySelector('[data-testid=world-load]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=world-projection]'))",
                "fresh source-derived context restored after retry")
        print("PASS OVERVIEW RETURN RECOVERY: one-shot synthetic network failure,"
              " source refresh cleared World Model, same-patient/case Overview"
              " recovery retained exact return intent, real authorized retry"
              " and immutable receipt, no new patient or review owner.")
    print("PASS OVERVIEW VERIFICATION CONTINUATION: same patient/case, source-linked"
          " nonterminal return history, no stale quotation/brief, contextual"
          " navigation to Investigations/Records and original World Model.")
