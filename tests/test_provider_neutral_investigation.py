"""Model-provider independence tests on the EXISTING bounded investigation path.

No external provider, model weights, PHI, medical data or network connection.
Both simulated backends must obey identical source/citation/review contracts.
"""
from __future__ import annotations

import unittest

from open_intelligence.investigation import (
    InvestigationError,
    execute_bounded_model,
)


def facts():
    return {
        "question": {"question": "What does a fictional source establish?"},
        "assertions": [
            {"source_version_id": 21, "finding_key": "marker",
             "certainty": "indeterminate",
             "quote": "A fictional source reports an indeterminate marker."}
        ],
        "assessments": [],
        "valid_sources": {21},
        "valid_assessments": set(),
    }


def claim(source=21):
    return {
        "text": "This fictional marker remains indeterminate.",
        "support": "context",
        "citations": [{"type": "source", "id": source}],
        "uncertainty": "high",
        "limits": "Unverified synthetic authorship.",
    }


class ProviderNeutralBoundedInvestigationTest(unittest.TestCase):
    def dispatch(self, callback, **options):
        return execute_bounded_model(
            "evidence-summary", facts(), invoke=callback,
            provider_id=options.pop("provider_id", "simulated-local"),
            model_id=options.pop("model_id", "simulation-v1"),
            **options)

    def test_two_independent_simulated_adapters_use_same_validation(self):
        observed = []

        def local(prompt):
            observed.append(("local", prompt))
            return {"claims": [claim()], "abstentions": []}

        def remote_simulated(prompt):
            observed.append(("remote", prompt))
            return {"claims": [claim(source=999)], "abstentions": [
                {"topic": "missing evidence", "reason": "insufficient_evidence"}]}

        a = self.dispatch(local, provider_id="local-simulator",
                          model_id="fictional-local-v1")
        b = self.dispatch(remote_simulated, provider_id="cloud-simulator",
                          model_id="fictional-cloud-v2")
        self.assertEqual(a.model, "fictional-local-v1")
        self.assertEqual(b.model, "fictional-cloud-v2")
        self.assertEqual(a.mode, b.mode)
        self.assertEqual(a.mode, "live")
        self.assertEqual(a.status, "completed")
        self.assertEqual(a.claims[0]["kind"], "hypothesis")
        self.assertEqual(b.status, "abstained")
        self.assertEqual(b.claims, [])
        self.assertEqual(b.dropped[0]["reason"], "unresolved_citation")
        self.assertEqual(len(observed), 2)
        for _, prompt in observed:
            self.assertIn("source_version_id=21", prompt)
            self.assertIn("No real patient is involved.", prompt)
            self.assertNotIn("Bearer ", prompt)
            self.assertNotIn("API_KEY", prompt)

    def test_clinical_effects_block_before_invoking_any_provider(self):
        invoked = []
        for effects in (
            ("propose_hypothesis", "send_data"),
            ("execute_clinical_order",),
            ("approve_treatment",),
            (),
        ):
            with self.subTest(effects=effects):
                with self.assertRaises(InvestigationError):
                    self.dispatch(lambda prompt: invoked.append(prompt),
                                  allowed_effects=effects)
        self.assertEqual(invoked, [])

    def test_real_patient_data_class_refused_before_provider_contact(self):
        observed = []
        with self.assertRaisesRegex(InvestigationError, "synthetic"):
            self.dispatch(lambda prompt: observed.append(prompt),
                          data_class="patient_phi")
        self.assertEqual(observed, [])

    def test_invalid_template_and_provider_metadata_fail_closed(self):
        for provider_id, model_id in (
            ("https://malicious.example", "model-v1"),
            ("unknown provider", "model-v1"),
            ("demo", "http://malicious.example/key"),
            ("demo", ""),
        ):
            with self.subTest(provider_id=provider_id, model_id=model_id):
                with self.assertRaises(InvestigationError):
                    self.dispatch(lambda prompt: {"claims": [], "abstentions": []},
                                  provider_id=provider_id, model_id=model_id)
        with self.assertRaises(InvestigationError):
            execute_bounded_model(
                "give-medication", facts(),
                invoke=lambda _: {"claims": [], "abstentions": []},
                provider_id="local", model_id="test-v1")

    def test_unexpected_model_action_payload_is_not_saved_as_hypothesis(self):
        with self.assertRaisesRegex(InvestigationError, "unexpected"):
            self.dispatch(lambda prompt: {
                "claims": [claim()], "abstentions": [],
                "clinical_orders": [{"drug": "DO-NOT-EXECUTE"}]
            })

    def test_bad_prompt_scope_and_missing_evidence_set_rejected(self):
        broken = facts()
        broken["valid_sources"] = "21"
        invoked = []
        with self.assertRaises(InvestigationError):
            execute_bounded_model(
                "evidence-summary", broken,
                invoke=lambda p: invoked.append(p),
                provider_id="local", model_id="model-v1")
        self.assertEqual(invoked, [])

    def test_prompt_length_cap_prevents_unbounded_data_transfer(self):
        oversize = facts()
        oversize["assertions"][0]["quote"] = "X" * 70000
        invoked = []
        with self.assertRaisesRegex(InvestigationError, "prompt"):
            execute_bounded_model(
                "evidence-summary", oversize,
                invoke=lambda p: invoked.append(p),
                provider_id="local", model_id="model-v1")
        self.assertEqual(invoked, [])


if __name__ == "__main__":
    unittest.main()
