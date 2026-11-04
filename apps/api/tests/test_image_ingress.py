"""Real loopback ingress bounds; no source files or database are required."""

import http.client
import json
import unittest
from urllib.parse import urlsplit

from oi_api.app import create_app
from oi_api.config import Settings
from http_support import running_server, get_json


class ImageIngressTests(unittest.TestCase):
    path = ("/v1/patients/PAT-" + "1" * 32
            + "/cases/CASE-ALPHA/sources/SRC-" + "2" * 32 + "/images")

    def test_binary_import_index_and_original_have_explicit_openapi_operations(self):
        with running_server(create_app(Settings())) as base:
            status, schema, _ = get_json(base, "/v1/openapi.json")
        self.assertEqual(status, 200)
        route = "/v1/patients/{patient_id}/cases/{case_id}/sources/{source_id}/images"
        self.assertIn(route, schema["paths"])
        self.assertEqual(schema["paths"][route]["post"]["operationId"], "import_source_image_v1")
        self.assertIn("application/dicom", schema["paths"][route]["post"]["requestBody"]["content"])
        self.assertEqual(schema["paths"][route]["get"]["operationId"], "list_source_images_v1")
        self.assertEqual(schema["paths"][route + "/{image_id}"]["get"]["operationId"],
                         "read_original_source_image_v1")

    def test_declared_and_chunked_binary_limits_precede_parsing(self):
        with running_server(create_app(Settings())) as base:
            address = urlsplit(base)
            for chunked in (False, True):
                with self.subTest(chunked=chunked):
                    client = http.client.HTTPConnection(address.hostname, address.port, timeout=8)
                    try:
                        if chunked:
                            client.request("POST", self.path, body=iter([b"x" * 1_048_576, b"x" * 1_048_576, b"x"]),
                                           headers={"Content-Type": "application/dicom"}, encode_chunked=True)
                        else:
                            client.putrequest("POST", self.path)
                            client.putheader("Content-Type", "application/dicom")
                            client.putheader("Content-Length", "2097153")
                            client.endheaders()
                        response = client.getresponse()
                        self.assertEqual(response.status, 413)
                        self.assertEqual(json.loads(response.read()), {"detail": "Request body too large"})
                        self.assertEqual(response.getheader("Cache-Control"), "no-store")
                    finally:
                        client.close()

    def test_stalled_binary_upload_is_bounded(self):
        with running_server(create_app(Settings())) as base:
            address = urlsplit(base)
            client = http.client.HTTPConnection(address.hostname, address.port, timeout=8)
            try:
                client.putrequest("POST", self.path)
                client.putheader("Content-Type", "application/dicom")
                client.putheader("Content-Length", "1000")
                client.endheaders()
                response = client.getresponse()
                self.assertEqual(response.status, 408)
                self.assertEqual(json.loads(response.read()), {"detail": "Request body timed out"})
            finally:
                client.close()


if __name__ == "__main__":
    unittest.main()
