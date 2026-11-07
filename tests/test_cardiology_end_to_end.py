"""Second vertical end-to-end (program plan slice V2): full cardiology
end-to-end with zero core changes.

V2 is the capstone: a synthetic cardiology case (CASE-CARDIO,
independently authored fictional data, explicit provenance) flows
through the same coordination core + ledger + dimensions as the
oncology path — route, K-checks, Skeptic, T6, D1 extraction and T3
specimen chain, D2 terminology and FHIR exchange, D3 longitudinal /
lab series / imaging comparison / therapy lines, D4 patient
analytics, D5 HYPOTHESIS composition and T5 assembly, and the D6–D9
care loop — with the core untouched. The core-change accounting is in
the V2 section of ``docs/IMPLEMENTATION_STATUS.md``; this file proves
the pipeline side.

The K-check context is built from the ledger (``investigation_facts``
+ ``source_version_facts`` + ``build_kcheck_context``), exactly as the
live route does — not from a hand-built fixture — and the cardiology
vertical's own substance names are supplied, so the K7 substance arm
runs on cardiology data for the first time (the live path still
passes none; see the V1 section of IMPLEMENTATION_STATUS.md).

No live model call is made here: the Skeptic and repair model calls
are injectable, and the end-to-end drives them with stubs. The live
model proof is still blocked by the Meta billing fix (HTTP 402), and
no substitute model was used — the stub verdicts prove wiring, not
the model.
"""

import tempfile
import unittest
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from open_intelligence import CaseStore
from open_intelligence.extraction import validate_extraction_proposal
from open_intelligence.fhir_exchange import build_fhir_bundle
from open_intelligence.hypothesis import (
    assemble_hypothesis_report,
    claim_id,
    compose_hypothesis,
)
from open_intelligence.imaging import compare_imaging
from open_intelligence.investigation import validate_output
from open_intelligence.kchecks import build_kcheck_context
from open_intelligence.lab_series import lab_series
from open_intelligence.literature import list_records
from open_intelligence.longitudinal import longitudinal_picture
from open_intelligence.notifications import notifications_view
from open_intelligence.orchestrator import decide_route
from open_intelligence.patient_analytics import patient_analytics
from open_intelligence.skeptic import run_verification
from open_intelligence.specimen_chain import validate_specimen_chain
from open_intelligence.terminology import (
    codings_for,
    validate_coding,
)
from open_intelligence.therapy import (
    compute_therapy_lines,
    record_therapy_lines,
    therapy_lines,
)
from open_intelligence.trials import list_listings, render_listing
from open_intelligence.vertical import get_vertical


def report(patient, document, kind, event_date, findings, *, specimen=None,
           issued=None, amends=None):
    """Build one synthetic report in the OI-SYNTHETIC-REPORT/1 format."""
    lines = ["OI-SYNTHETIC-REPORT/1", f"Patient: {patient}",
             f"Document: {document}", f"Type: {kind}",
             f"Event-Date: {event_date}", f"Issued-At: {issued or event_date}"]
    if specimen:
        lines.append(f"Specimen: {specimen}")
    if amends:
        lines.append(f"Amends: {amends}")
    for key, state, quote in findings:
        lines.append(f"Finding: {key}|{state}|{quote}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _claim(text, source_id):
    return {"text": text, "support": "context",
            "citations": [{"type": "source", "id": source_id}],
            "uncertainty": "moderate", "limits": "Synthetic only."}


def _stub_skeptic(verdicts):
    """A stub Skeptic returning one canned verdict per kept claim."""
    def call(prompt):
        return {"reviews": [
            {"claim_index": index, "verdict": verdict,
             "reason": f"stub review {index}: {verdict}"}
            for index, verdict in enumerate(verdicts)]}
    return call


def _stub_repair_cannot_repair():
    """A schema-valid stub repair: the one repairable drop cannot be
    repaired, because no cited evidence carries the invented
    substance. The honest outcome for an invented token."""
    def call(prompt):
        return {"repairs": [{"claim_index": 0, "repaired_text": None,
                             "cannot_repair": True,
                             "reason": "stub: no cited evidence carries "
                                       "furosemide"}]}
    return call


class CardiologyEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.dir.name) / "t.db")
        self.store.add_case("CASE-CARDIO", "Fictional cardiology case")
        self.question_id = self.store.add_question(
            "CASE-CARDIO", "What does the cardiac record report?")
        self.vertical = get_vertical("cardiology")
        self._seed_sources()
        self._seed_dicom()
        self._seed_chain()
        self._seed_notes()

    def tearDown(self):
        self.store.close()
        self.dir.cleanup()

    def _import(self, raw):
        return self.store.import_report("CASE-CARDIO", raw)["source_id"]

    def _seed_sources(self):
        # ECG: rhythm reported. Echo pair: the same ejection-fraction
        # value persists; rhythm flips not-reported -> reported and
        # heart-failure drops out — the T1 diff and the T6 rhythm
        # group. Imaging reports carry no specimen: an echo study is
        # not a biopsy sample. Labs: one creatinine series. Clinical
        # reports: therapy regimens in class-agent keys.
        self.ecg = self._import(report(
            "CASE-CARDIO", "ECG-A", "clinical", "2026-05-03",
            [("rhythm", "reported",
              "Atrial fibrillation was identified.")],
            specimen="SPEC-ECG"))
        self.echo_a = self._import(report(
            "CASE-CARDIO", "ECHO-A", "imaging", "2026-05-17",
            [("ejection-fraction", "reported",
              "The ejection fraction was measured as 31%."),
             ("heart-failure", "reported", "Heart failure was noted."),
             ("rhythm", "not-reported",
              "Atrial fibrillation was not performed.")]))
        self.echo_b = self._import(report(
            "CASE-CARDIO", "ECHO-B", "imaging", "2026-06-17",
            [("ejection-fraction", "reported",
              "The ejection fraction was measured as 31%."),
             ("rhythm", "reported",
              "Atrial fibrillation was identified.")]))
        self.lab_a = self._import(report(
            "CASE-CARDIO", "LAB-A", "laboratory", "2026-05-03",
            [("creatinine", "reported",
              "Creatinine was measured as 1.1 mg/dL.")],
            specimen="SPEC-LAB-A"))
        self.lab_b = self._import(report(
            "CASE-CARDIO", "LAB-B", "laboratory", "2026-05-10",
            [("creatinine", "reported",
              "Creatinine was measured as 1.2 mg/dL.")],
            specimen="SPEC-LAB-B"))
        self.clin_a = self._import(report(
            "CASE-CARDIO", "CLIN-A", "clinical", "2026-05-03",
            [("beta-blocker-metoprolol", "reported",
              "Beta-blocker metoprolol was given.")]))
        self.clin_b = self._import(report(
            "CASE-CARDIO", "CLIN-B", "clinical", "2026-05-10",
            [("beta-blocker-atenolol", "reported",
              "Beta-blocker atenolol was given.")]))
        self.clin_c = self._import(report(
            "CASE-CARDIO", "CLIN-C", "clinical", "2026-05-17",
            [("ace-inhibitor-lisinopril", "reported",
              "ACE-inhibitor lisinopril was given.")]))
        self.clin_d = self._import(report(
            "CASE-CARDIO", "CLIN-D", "clinical", "2026-05-24",
            [("beta-blocker-metoprolol", "reported",
              "Beta-blocker metoprolol was given again.")]))

    def _seed_dicom(self):
        for study, source_id in (
                ("OI-SYNTHETIC-STUDY-US1", self.echo_a),
                ("OI-SYNTHETIC-STUDY-US2", self.echo_b)):
            self.store.record_dicom_report("CASE-CARDIO", {
                "study_uid": study, "modality": "US",
                "accession": "ACC-" + study[-3:],
                "report_text": "Fictional echo narrative.",
                "source_version_id": source_id})

    def _seed_chain(self):
        # A cardiac tissue chain: biopsy block -> slide -> WSI, all
        # anchored to the ECG source. A myocardial biopsy follows
        # exactly this block/slide/WSI shape.
        self.block = self.store.add_biological_asset(
            "CASE-CARDIO", "CARDIAC-BLOCK-A", "ffpe_block",
            "EPISODE-CARDIO", "2026-05-03", self.ecg,
            specimen_state="recorded", specimen_id="CARDIAC-BIOPSY-1")
        self.slide = self.store.add_biological_asset(
            "CASE-CARDIO", "CARDIAC-SLIDE-A", "slide",
            "EPISODE-CARDIO", "2026-05-04", self.ecg,
            parent_asset_id=self.block,
            specimen_state="recorded", specimen_id="CARDIAC-BIOPSY-1")
        self.wsi = self.store.add_biological_asset(
            "CASE-CARDIO", "CARDIAC-WSI-A", "digital_wsi",
            "EPISODE-CARDIO", "2026-05-05", self.ecg,
            parent_asset_id=self.slide,
            specimen_state="recorded", specimen_id="CARDIAC-BIOPSY-1")

    def _seed_notes(self):
        self.store.add_patient_note(
            "CASE-CARDIO", "symptom",
            "Fictional shortness of breath noted.", "2026-05-04")
        self.store.add_patient_note(
            "CASE-CARDIO", "symptom",
            "Fictional shortness of breath noted.", "2026-05-18")

    def test_full_cardiology_end_to_end(self):
        store = self.store
        vertical = self.vertical

        # D1 extraction: a new field on the ECG source validates clean.
        validation = validate_extraction_proposal(
            store, "CASE-CARDIO", self.ecg, [
                {"finding_key": "rhythm-note", "certainty": "reported",
                 "quote": "A new fictional rhythm note.", "source_line": 3}])
        self.assertEqual(
            [k["finding_key"] for k in validation.kept], ["rhythm-note"])
        self.assertEqual(validation.dropped, [])

        # T3 specimen chain: the cardiac biopsy chain is intact.
        chain = validate_specimen_chain(store, "CASE-CARDIO", self.wsi)
        self.assertTrue(chain.intact)
        self.assertEqual(chain.breaks, [])
        self.assertEqual([link.asset_pk for link in chain.links],
                         [self.block, self.slide, self.wsi])

        # Route: decided before any agent event, through the same
        # orchestrator as the oncology path; A1 only.
        route = decide_route(store, "CASE-CARDIO", "evidence-summary",
                             self.question_id, "clinician")
        self.assertEqual(route["agents"], ["A1"])
        self.assertEqual(route["templateId"], "evidence-summary")

        # K-checks, from a ledger-built context under the cardiology
        # vertical — with the vertical's own substance names, so the
        # K7 substance arm runs on cardiology data.
        facts = store.investigation_facts("CASE-CARDIO", self.question_id)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        context = build_kcheck_context(
            facts, store.source_version_facts("CASE-CARDIO"),
            case_id="CASE-CARDIO", snapshot_as_of=now,
            synonyms=vertical.synonyms,
            scope_patterns=vertical.scope_patterns,
            condition_terms=vertical.condition_terms,
            lot_ruleset=vertical.lot_ruleset,
            current_lot_ruleset=vertical.lot_ruleset,
            substance_names=list(vertical.substance_names),
            evidence_tiers={})
        validated = validate_output(
            {"claims": [
                _claim("The ejection fraction was measured as 31%.",
                       self.echo_a),
                _claim("The ejection fraction was measured as 31 cm.",
                       self.echo_a),
                _claim("Atrial fibrillation was identified.", self.ecg),
                _claim("You have heart failure and should know.", self.ecg),
                _claim("Metoprolol was given.", self.clin_a),
                _claim("Furosemide was given.", self.ecg),
            ], "abstentions": []},
            facts["valid_sources"], facts["valid_assessments"], context)
        # Four kept: the supported claims and the planted misstatement
        # (it passes K1–K7 by construction, as in C4 — the Skeptic's
        # catch, not the checks'). Two dropped: the K6 scope claim
        # (cardiology condition term "heart failure") and the K7
        # substance claim (furosemide is named, but no cited evidence
        # carries it; metoprolol passes because CLIN-A does).
        self.assertEqual(
            [c["text"] for c in validated.claims],
            ["The ejection fraction was measured as 31%.",
             "The ejection fraction was measured as 31 cm.",
             "Atrial fibrillation was identified.",
             "Metoprolol was given."])
        self.assertEqual(
            [d["reason"] for d in validated.dropped],
            ["k6_scope", "k7_unsupported_token"])
        k6 = validated.dropped[0]
        self.assertEqual(k6["detail"]["matched"], "You have heart failure")
        k7 = validated.dropped[1]
        self.assertEqual(k7["detail"],
                         {"token": "furosemide", "kind": "substance"})

        # Verification: the stub Skeptic supports the true claims and
        # challenges the planted misstatement; the repair round cannot
        # repair the invented substance (nothing to restate from).
        record = run_verification(
            validated, context, facts, mode="live",
            store=store, case_id="CASE-CARDIO",
            skeptic_call=_stub_skeptic(
                ["supported", "challenged", "supported", "supported"]),
            repair_call=_stub_repair_cannot_repair())
        self.assertEqual(
            [c["text"] for c in validated.claims],
            ["The ejection fraction was measured as 31%.",
             "Atrial fibrillation was identified.",
             "Metoprolol was given."])
        self.assertEqual(
            sorted(d["reason"] for d in validated.dropped),
            ["k6_scope", "k7_unsupported_token", "skeptic_challenged"])
        held = next(d for d in validated.dropped
                    if d["reason"] == "skeptic_challenged")
        self.assertEqual(held["claim"]["text"],
                         "The ejection fraction was measured as 31 cm.")
        self.assertEqual(record["repair"]["status"], "completed")
        self.assertEqual(record["repair"]["repaired"], [])
        self.assertEqual(len(record["repair"]["unrepaired"]), 1)
        self.assertEqual(record["skeptic"]["status"], "completed")
        codes = record.get("abstention_codes", [])
        origins = sorted(code.get("origin") for code in codes
                         if code.get("code") == "AB-CONFLICT")
        self.assertEqual(origins, ["skeptic_challenge", "source_disagreement"])
        # No AB-MODEL: both stub calls were schema-valid.
        self.assertEqual(
            [code for code in codes if code.get("code") == "AB-MODEL"], [])
        # T6 groups the rhythm disagreement across the three sources
        # that state rhythm; nothing is merged, voted on, or resolved.
        groups = record.get("t6", {}).get("contradictions", [])
        self.assertEqual(len(groups), 1)
        rhythm = groups[0]
        self.assertEqual(rhythm.get("field"), "rhythm")
        self.assertEqual(rhythm.get("origin"), "source_disagreement")
        self.assertEqual(set(rhythm.get("source_version_ids", [])),
                         {self.ecg, self.echo_a, self.echo_b})

        # D2 terminology: the cardiology bindings resolve, pinned
        # from the publishers' own listings.
        self.assertEqual(
            codings_for("ejection-fraction", vertical),
            ({"system": "http://loinc.org", "code": "10230-1",
              "display": "Left ventricular Ejection fraction"},))
        self.assertEqual(
            codings_for("heart-failure", vertical),
            ({"system": "http://hl7.org/fhir/sid/icd-10", "code": "I50.9",
              "display": "Heart failure, unspecified"},))
        self.assertEqual(
            validate_coding("http://loinc.org", "10230-1",
                            vertical=vertical)["code"], "10230-1")
        self.assertEqual(
            validate_coding("http://hl7.org/fhir/sid/icd-10", "I50.9",
                            vertical=vertical)["code"], "I50.9")
        result = build_fhir_bundle(store.state("CASE-CARDIO"), vertical,
                                   codings_for=codings_for)
        bundle = result["bundle"]
        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual(
            Counter(e["resource"]["resourceType"]
                    for e in bundle["entry"]),
            {"Patient": 1, "Observation": 12, "DiagnosticReport": 9,
             "Condition": 1})
        ef = next(e["resource"] for e in bundle["entry"]
                  if e["resource"]["resourceType"] == "Observation"
                  and e["resource"]["code"]["text"] == "ejection-fraction")
        self.assertEqual(ef["code"]["coding"], [{
            "system": "http://loinc.org", "code": "10230-1",
            "display": "Left ventricular Ejection fraction"}])
        condition = next(e["resource"] for e in bundle["entry"]
                         if e["resource"]["resourceType"] == "Condition")
        self.assertEqual(condition["code"]["coding"], [{
            "system": "http://hl7.org/fhir/sid/icd-10", "code": "I50.9",
            "display": "Heart failure, unspecified"}])
        self.assertEqual(
            condition["verificationStatus"]["coding"][0]["code"],
            "unconfirmed")
        self.assertEqual(result["mcode"]["status"], "not_claimed")
        # Bound keys are coded; the rest are listed, never fabricated.
        self.assertEqual(result["unbound_findings"], sorted([
            "ace-inhibitor-lisinopril", "beta-blocker-atenolol",
            "beta-blocker-metoprolol", "rhythm"]))

        # D3 analysis: longitudinal tracks, lab series, imaging
        # comparison, and therapy lines under therapy-rules-1.
        picture = longitudinal_picture(store, "CASE-CARDIO")
        self.assertEqual(sorted(picture.tracks.keys()), [
            "ace-inhibitor-lisinopril", "beta-blocker-atenolol",
            "beta-blocker-metoprolol", "creatinine", "ejection-fraction",
            "heart-failure", "rhythm"])
        series = lab_series(store, "CASE-CARDIO",
                            codings_for=codings_for, vertical=vertical)
        creatinine = series.series["creatinine"]
        self.assertEqual(
            [(p["occurred"], p["value"], p["unit"])
             for p in creatinine["points"]],
            [("2026-05-03", 1.1, "mg/dL"), ("2026-05-10", 1.2, "mg/dL")])
        self.assertEqual(len(creatinine["deltas"]), 1)
        self.assertEqual(creatinine["deltas"][0]["delta_status"], "computed")
        self.assertAlmostEqual(creatinine["deltas"][0]["absolute"], 0.1)
        self.assertAlmostEqual(creatinine["deltas"][0]["percent"],
                               0.1 / 1.1 * 100.0)
        self.assertEqual(creatinine["codings"], [{
            "system": "http://loinc.org", "code": "2160-0",
            "display": "Creatinine [Mass/volume] in Serum or Plasma"}])
        self.assertEqual(series.unbound, [])
        imaging = compare_imaging(store, "CASE-CARDIO")
        self.assertEqual(len(imaging.comparisons), 1)
        comparison = imaging.comparisons[0]
        self.assertEqual(comparison["modality"], "US")
        self.assertEqual(comparison["persisting"], ["ejection-fraction"])
        self.assertEqual(comparison["changed_state"], [{
            "finding_key": "rhythm",
            "from_certainty": "not-reported", "to_certainty": "reported"}])
        self.assertEqual(comparison["added"], [])
        self.assertEqual(comparison["removed"], ["heart-failure"])
        self.assertEqual(comparison["chain"]["checked"], False)
        self.assertEqual(imaging.unpaired, [])
        self.assertEqual(imaging.unanchored, [])
        regimens = ("beta-blocker-metoprolol", "beta-blocker-atenolol",
                    "ace-inhibitor-lisinopril")
        computed = compute_therapy_lines(store, "CASE-CARDIO", regimens,
                                         vertical=vertical)
        self.assertEqual(computed.ruleset_version, "therapy-rules-1")
        # One line per therapy class: the two beta-blockers share a
        # line (metoprolol re-appearing resumes it); the ACE
        # inhibitor starts a new line.
        self.assertEqual(
            [(line["line_number"], line["regimen_key"],
              line["first_occurred"], line["last_occurred"])
             for line in computed.lines],
            [(1, "beta-blocker", "2026-05-03", "2026-05-24"),
             (2, "ace-inhibitor", "2026-05-17", "2026-05-17")])
        recorded = record_therapy_lines(store, "CASE-CARDIO", regimens,
                                        vertical=vertical)
        self.assertEqual(len(recorded.recorded_ids), 2)
        self.assertEqual(len(therapy_lines(store, "CASE-CARDIO")), 2)

        # D4 patient analytics over the T2 series.
        analytics = patient_analytics(store, "CASE-CARDIO",
                                      lab_series=asdict(series))
        trend = analytics["lab_trends"]["trends"]["creatinine"]
        self.assertEqual(trend["trend"], "rising")
        self.assertEqual(trend["first_value"], 1.1)
        self.assertEqual(trend["last_value"], 1.2)
        self.assertAlmostEqual(trend["percent_change"], 0.1 / 1.1 * 100.0)
        self.assertEqual(trend["points_used"], 2)
        symptoms = analytics["symptom_progression"]
        self.assertEqual(symptoms["status"], "has_symptom_notes")
        self.assertEqual(symptoms["note_count"], 2)
        self.assertEqual([e["recurrence"] for e in symptoms["notes"]],
                         ["first_report", "repeat"])
        completeness = {c["key"]: c["count"]
                        for c in analytics["record_completeness"]["checks"]}
        self.assertEqual(completeness["sources"], 9)
        self.assertEqual(completeness["laboratory_sources"], 2)
        self.assertEqual(completeness["imaging_sources"], 2)
        self.assertEqual(completeness["therapy_lines"], 2)
        self.assertEqual(completeness["symptom_notes"], 2)
        self.assertEqual(completeness["specimen_assets"], 3)
        self.assertEqual(completeness["questions"], 1)
        outcomes = analytics["outcomes_tracking"]["therapy_lines"]
        self.assertEqual(outcomes["current_count"], 2)

        # D5 hypothesis generation: compose from the kept claims only,
        # with the cardiology substance names — the substance check
        # runs instead of skipping.
        kept = [{"id": claim_id(1, index + 1), "text": c["text"],
                 "uncertainty": c.get("uncertainty", "moderate"),
                 "citations": c.get("citations", [])}
                for index, c in enumerate(validated.claims)]
        hypothesis = compose_hypothesis(
            [{"text": "The ejection fraction was measured as 31% and "
                      "atrial fibrillation was identified.",
              "claim_ids": [kept[0]["id"], kept[1]["id"]]}],
            kept, substance_names=list(vertical.substance_names))
        self.assertEqual(hypothesis["status"], "composed")
        self.assertEqual(hypothesis["substance_check"], "checked")
        self.assertEqual(hypothesis["violations"], [])
        self.assertEqual(
            hypothesis["text"],
            "The ejection fraction was measured as 31% and atrial "
            "fibrillation was identified.")
        literature = list_records()
        trials = [render_listing(item) for item in list_listings()]
        self.assertEqual(len(literature), 6)
        self.assertEqual(len(trials), 4)
        self.assertTrue(all(
            item.get("label")
            == "Registry listing — not an eligibility determination."
            for item in trials))
        assembled = assemble_hypothesis_report(
            "CASE-CARDIO", kept, literature, trials,
            hypothesis=hypothesis, abstentions=[])
        self.assertEqual(assembled["hypothesis"]["status"], "composed")
        self.assertEqual(
            [c["id"] for c in assembled["kept_claims"]],
            [kept[0]["id"], kept[1]["id"], kept[2]["id"]])
        self.assertEqual(len(assembled["literature"]["records"]), 6)
        self.assertEqual(len(assembled["trials"]["listings"]), 4)
        self.assertEqual(assembled["counts"]["literature_records"], 6)
        self.assertEqual(assembled["counts"]["trial_listings"], 4)

        # Care loop D6–D9 against the cardiology case: an appointment,
        # the notification it derives, a referral, a shared update,
        # and a handoff — all records, none of them sending anything.
        appointment_id = store.create_appointment(
            "CASE-CARDIO", "Follow-up visit", scheduled_date="2026-05-20",
            scheduled_time="09:30", purpose="Review the fictional report",
            location="Room 4", actor_label="Fictional recorder",
            reason="Planned at intake, one day after the fictional report")
        self.assertEqual(type(appointment_id), int)
        view = notifications_view(store, "CASE-CARDIO", "operator",
                                  today="2026-06-02")
        kinds = {(n["kind"], n["key"])
                 for n in view.get("notifications", [])}
        self.assertIn(
            ("appointment-due",
             f"appointment-due:{appointment_id}:2026-05-20"), kinds)
        referral_id = store.create_referral(
            "CASE-CARDIO", self.question_id, "Cardiology",
            "The fictional record needs another team's input",
            [self.echo_a], actor_label="Fictional recorder")
        self.assertEqual(type(referral_id), int)
        update_id = store.create_team_update(
            "CASE-CARDIO",
            "The fictional team noted the shared record for the patient",
            author_label="Fictional recorder", author_role="clinician")
        self.assertEqual(type(update_id), int)
        handoff_id = store.create_handoff(
            "CASE-CARDIO", self.question_id,
            "Fictional sender", "Fictional receiver",
            "The fictional record needs another team's input",
            [self.echo_a], actor_label="Fictional recorder")
        self.assertEqual(type(handoff_id), int)

    def test_therapy_rules_1_hyphenless_key_is_its_own_class(self):
        # The class rule's edge: a regimen key with no hyphen is its
        # own class, so a re-appearing hyphen-less regimen resumes its
        # single line.
        self._import(report(
            "CASE-CARDIO", "CLIN-X", "clinical", "2026-05-03",
            [("statin", "reported", "Fictional statin was given.")]))
        self._import(report(
            "CASE-CARDIO", "CLIN-Y", "clinical", "2026-05-10",
            [("statin", "reported", "Fictional statin was given again.")]))
        result = compute_therapy_lines(
            self.store, "CASE-CARDIO", ("statin",),
            vertical=self.vertical)
        self.assertEqual(result.ruleset_version, "therapy-rules-1")
        self.assertEqual(
            [(line["line_number"], line["regimen_key"],
              line["first_occurred"], line["last_occurred"])
             for line in result.lines],
            [(1, "statin", "2026-05-03", "2026-05-10")])


if __name__ == "__main__":
    unittest.main()
