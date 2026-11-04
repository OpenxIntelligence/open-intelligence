"""Actual PostgreSQL/React patient Overview → verification continuation contract.

Synthetic only. Exercises the existing source-question, original-source and
nonterminal verification-return owners; no extra APIs, clinical approvals or
local browser persistence.
"""
import json


def nav(cd, section):
    cd.evaluate("Array.from(document.querySelectorAll('nav[aria-label=\"Patient workspace\"] button'))"
                ".find(b=>b.textContent.includes("+json.dumps(section)+")).click()")


def exercise(cd, patient_id, case_id, returned_receipt):
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
    print("PASS OVERVIEW VERIFICATION CONTINUATION: same patient/case, source-linked"
          " nonterminal return history, no stale quotation/brief, contextual"
          " navigation to Investigations/Records and original World Model.")
