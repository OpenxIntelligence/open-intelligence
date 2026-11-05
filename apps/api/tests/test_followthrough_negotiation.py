"""Representation selection for the existing follow-through list, without a database."""
import unittest

from starlette.requests import Request

from oi_api.followthrough_routes import V2_MEDIA_TYPE, _accepts_v2


def selects_v2(*headers):
    request = Request({"type": "http", "headers": [(b"accept", h.encode("ascii")) for h in headers]})
    return _accepts_v2(request)


class FollowthroughNegotiationTests(unittest.TestCase):
    def test_compares_explicit_weights_across_headers_and_in_either_order(self):
        for headers in (
            ("application/json, " + V2_MEDIA_TYPE + ";q=0.1",),
            (V2_MEDIA_TYPE + ";q=0.1", "application/json"),
        ):
            with self.subTest(headers=headers):
                self.assertFalse(selects_v2(*headers))
        self.assertTrue(selects_v2(V2_MEDIA_TYPE + ", application/json;q=0.9"))
        self.assertTrue(selects_v2("application/json;q=0.4, " + V2_MEDIA_TYPE + ";q=0.4"))

    def test_wildcards_set_the_legacy_weight_but_cannot_opt_into_lab_tasks(self):
        self.assertFalse(selects_v2("application/*, */*;q=0.8"))
        self.assertFalse(selects_v2("application/json;q=0, */*"))
        self.assertFalse(selects_v2("*/*, " + V2_MEDIA_TYPE + ";q=0.3"))
        self.assertTrue(selects_v2("*/*, application/*;q=0.2, " + V2_MEDIA_TYPE + ";q=0.3"))
        self.assertTrue(selects_v2("*/*, application/json;q=0, " + V2_MEDIA_TYPE + ";q=0.1"))

    def test_an_explicit_zero_never_opts_in(self):
        self.assertFalse(selects_v2("application/json;q=0, */*, " + V2_MEDIA_TYPE + ";q=0"))

    def test_missing_malformed_and_oversized_values_fall_back_to_text(self):
        self.assertFalse(selects_v2())
        for value in ("", V2_MEDIA_TYPE + ";q=garbage", V2_MEDIA_TYPE + ";q=1.1",
                      V2_MEDIA_TYPE + ";q=1e0", V2_MEDIA_TYPE + ";q=0.0001",
                      'text/plain;note="example, ' + V2_MEDIA_TYPE + ', example"',
                      "a" * 8192 + ", " + V2_MEDIA_TYPE):
            with self.subTest(prefix=value[:100]):
                self.assertFalse(selects_v2(value))
