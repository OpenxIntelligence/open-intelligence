"""Run with PYTHONPATH=src python -m open_intelligence serve/seed."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

from tools.crossref_metadata import MetadataInputError, fetch_public_doi, project_work

from .store import CaseStore, InvalidInput, MAX_SOURCE_BYTES

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
SYNTHETIC = ROOT / "examples" / "synthetic"
ID_PART = r"([A-Z][A-Z0-9-]{1,39})"


class Handler(BaseHTTPRequestHandler):
    # Purely local synthetic demonstration, with no authenticated user concept.
    db_path: str
    allow_crossref_live = False
    crossref_contact: str | None = None
    metadata_request_lock = Lock()
    metadata_last_request = 0.0

    def log_message(self, fmt: str, *args: object) -> None:
        # Avoid logging source text, patient-like fields or query strings.
        print("[local demo]", fmt % args)

    def _headers(self, status: int, kind: str, size: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def _send(self, status: int, body: bytes, kind: str) -> None:
        self._headers(status, kind, len(body))
        self.wfile.write(body)

    def _json(self, status: int, payload: dict | list) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _static(self, name: str, mime: str) -> None:
        self._send(200, (WEB / name).read_bytes(), mime)

    def _body(self) -> dict:
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            raise InvalidInput("Only application/json is accepted")
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise InvalidInput("Invalid Content-Length") from None
        if not 0 < n <= MAX_SOURCE_BYTES + 8192:
            raise InvalidInput("Request body exceeds local-demo limit")
        try:
            data = json.loads(self.rfile.read(n))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise InvalidInput("Invalid JSON body") from None
        if not isinstance(data, dict):
            raise InvalidInput("JSON object required")
        return data

    def _host_allowed(self) -> bool:
        # Host validation prevents a remote-controlled domain resolving to
        # 127.0.0.1 from reading this unauthenticated local demo via rebinding.
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if origin:
            return origin == f"http://127.0.0.1:{self.server.server_port}"
        # A foreign webpage may omit Origin in some requests. Modern browser
        # metadata provides an additional barrier; this is NOT authentication.
        return self.headers.get("Sec-Fetch-Site", "none") in {"none", "same-origin"}

    def do_GET(self) -> None:  # noqa: N802
        if not self._host_allowed():
            return self._json(403, {"error": "Unexpected Host for loopback-only demo"})
        path = urlsplit(self.path).path
        try:
            if path in ("/", "/index.html"):
                return self._static("index.html", "text/html; charset=utf-8")
            if path == "/app.js":
                return self._static("app.js", "text/javascript; charset=utf-8")
            if path == "/style.css":
                return self._static("style.css", "text/css; charset=utf-8")
            if path == "/api/examples/amendment":
                return self._json(200, {"text": (SYNTHETIC / "alpha-pathology-amended.txt").read_text()})
            if path == "/api/examples/evidence":
                return self._json(200, {"text": (SYNTHETIC / "demo-evidence.txt").read_text()})
            if path == "/api/bibliography/status":
                return self._json(200, {"live_enabled": bool(self.allow_crossref_live)})
            if path == "/api/bibliography/example":
                # Original fictional metadata, not a publication or live lookup.
                data = json.loads((SYNTHETIC / "crossref-metadata-fixture.json").read_text())
                return self._json(200, project_work(data, "10.5555/oi-synthetic-001"))
        except OSError:
            return self._json(404, {"error": "Resource unavailable"})
        # Each request uses a separate SQLite connection; never share a
        # connection between ThreadingHTTPServer's request threads.
        store = CaseStore(self.db_path)
        try:
            if path == "/api/cases":
                return self._json(200, store.cases())
            evidence_text = re.fullmatch(r"/api/evidence/([0-9]+)", path)
            if evidence_text:
                return self._json(200, {"text": store.synthetic_evidence_text(int(evidence_text[1]))})
            case_state = re.fullmatch(rf"/api/cases/{ID_PART}/state", path)
            if case_state:
                return self._json(200, store.state(case_state[1]))
            source = re.fullmatch(rf"/api/cases/{ID_PART}/sources/([0-9]+)", path)
            if source:
                return self._json(200, {"text": store.source_text(source[1], int(source[2]))})
            exported = re.fullmatch(rf"/api/cases/{ID_PART}/snapshots/([0-9]+)/export", path)
            if exported:
                contents = store.export_markdown(exported[1], int(exported[2])).encode("utf-8")
                return self._send(200, contents, "text/markdown; charset=utf-8")
            return self._json(404, {"error": "Route not found"})
        except InvalidInput as error:
            return self._json(422, {"error": str(error)})
        finally:
            store.close()

    def do_POST(self) -> None:  # noqa: N802
        if not self._host_allowed():
            return self._json(403, {"error": "Unexpected Host for loopback-only demo"})
        if not self._origin_allowed():
            return self._json(403, {"error": "Cross-origin writes prohibited"})
        path = urlsplit(self.path).path
        try:
            data = self._body()
            if path == "/api/bibliography/lookup":
                if not self.allow_crossref_live:
                    return self._json(403, {"error": "Live Crossref lookup disabled by default; use explicit local server option"})
                if not self.metadata_request_lock.acquire(blocking=False):
                    return self._json(429, {"error": "Only one public DOI lookup can run at a time"})
                try:
                    current = monotonic()
                    if current - type(self).metadata_last_request < 1.0:
                        return self._json(429, {"error": "Public metadata lookup is rate limited; retry later"})
                    type(self).metadata_last_request = current
                    try:
                        record = fetch_public_doi(data.get("doi"), contact=self.crossref_contact)
                    except MetadataInputError as error:
                        return self._json(422, {"error": str(error)})
                    return self._json(200, record)
                finally:
                    self.metadata_request_lock.release()
            store = CaseStore(self.db_path)
            try:
                if path == "/api/cases":
                    store.add_case(data.get("case_id"), data.get("label"))
                    return self._json(201, {"result": "created"})
                if path == "/api/evidence/imports":
                    raw = data.get("text")
                    if not isinstance(raw, str):
                        raise InvalidInput("Fictional evidence text required")
                    return self._json(200, store.import_synthetic_evidence(raw.encode("utf-8")))
                withdrawal = re.fullmatch(r"/api/evidence/([0-9]+)/withdraw", path)
                if withdrawal:
                    return self._json(200, store.withdraw_synthetic_evidence(
                        int(withdrawal[1]), data.get("reason")))
                imports = re.fullmatch(rf"/api/cases/{ID_PART}/imports", path)
                if imports:
                    raw = data.get("text")
                    if not isinstance(raw, str):
                        raise InvalidInput("Report text required")
                    return self._json(200, store.import_report(imports[1], raw.encode("utf-8")))
                questions = re.fullmatch(rf"/api/cases/{ID_PART}/questions", path)
                if questions:
                    return self._json(201, {"question_id": store.add_question(questions[1], data.get("question"))})
                evidence_assessment = re.fullmatch(rf"/api/cases/{ID_PART}/evidence-assessments", path)
                if evidence_assessment:
                    return self._json(201, {"assessment_id": store.assess_synthetic_evidence(
                        evidence_assessment[1], data.get("question_id"), data.get("evidence_version_id"),
                        data.get("relation"), data.get("applicability"), data.get("rationale"))})
                drafts = re.fullmatch(rf"/api/cases/{ID_PART}/snapshots", path)
                if drafts:
                    return self._json(201, {"snapshot_id": store.create_snapshot(
                        drafts[1], data.get("question_id"), data.get("summary"), data.get("source_ids"),
                        data.get("evidence_assessment_ids"))})
                review = re.fullmatch(rf"/api/cases/{ID_PART}/snapshots/([0-9]+)/review", path)
                if review:
                    store.acknowledge_demo_review(review[1], int(review[2]), data.get("reviewer_label"))
                    return self._json(200, {"result": "acknowledged_in_demo"})
                return self._json(404, {"error": "Route not found"})
            finally:
                store.close()
        except InvalidInput as error:
            return self._json(422, {"error": str(error)})
        except (OverflowError, UnicodeEncodeError):
            return self._json(422, {"error": "Invalid text or identifier"})


def seed(db_path: str) -> None:
    store = CaseStore(db_path)
    try:
        for case_id, label, files in (
            ("CASE-ALPHA", "Fictional case Alpha", ["alpha-pathology-original.txt", "alpha-imaging.txt"]),
            ("CASE-BETA", "Fictional case Beta", ["beta-pathology.txt"]),
        ):
            if not any(x["case_id"] == case_id for x in store.cases()):
                store.add_case(case_id, label)
            for file in files:
                outcome = store.import_report(case_id, (SYNTHETIC / file).read_bytes())
                print(case_id, file, outcome["result"])
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Open Intelligence synthetic-only workflow")
    parser.add_argument("operation", choices=["seed", "serve"])
    parser.add_argument("--db", default=".local/open-intelligence.sqlite")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--enable-crossref-live", action="store_true",
                        help="Allow explicit public DOI-only metadata requests; disabled by default")
    parser.add_argument("--crossref-contact", default=None,
                        help="Optional operator email for Crossref polite pool, never patient email")
    args = parser.parse_args()
    if args.operation == "seed":
        seed(args.db)
        return
    print(f"Synthetic-only Open Intelligence demo: http://127.0.0.1:{args.port}")
    print("No authentication; localhost only. Do not import real patient data.")
    print("Crossref DOI-only live lookup:", "ENABLED (explicit)" if args.enable_crossref_live else "DISABLED (default)")
    server_type = type("LocalOIHTTPServer", (ThreadingHTTPServer,), {"allow_reuse_address": True})
    bound_handler = type("BoundHandler", (Handler,), {
        "db_path": args.db, "allow_crossref_live": args.enable_crossref_live,
        "crossref_contact": args.crossref_contact,
    })
    httpd = server_type(("127.0.0.1", args.port), bound_handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
