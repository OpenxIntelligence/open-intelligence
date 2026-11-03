"""Run with PYTHONPATH=src python -m open_intelligence serve/seed."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
from threading import Lock
from time import monotonic
from urllib.parse import parse_qs, urlsplit

from tools.crossref_metadata import MetadataInputError, fetch_public_doi, project_work

from .case_search import list_cases
from .changes import changes_since_review
from .followthrough import followthrough_view
from .investigation import (
    TEMPLATES,
    InvestigationError,
    ValidatedInvestigation,
    build_prompt,
    call_meta_api,
    meta_api_key,
    validate_output,
)
from .clinician_overview import build_clinician_overview
from .mission import build_patient_mission
from .provenance import case_provenance
from .patient_report import build_patient_report, render_text
from .owned_questions import question_gap_rollup
from .store import CaseStore, InvalidInput, MAX_SOURCE_BYTES
from .synthetic_metrics import fixture_run
from .timeline import case_timeline

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
SYNTHETIC = ROOT / "examples" / "synthetic"
ID_PART = r"([A-Z][A-Z0-9-]{1,39})"

# B-01 fictional-actor grants: workflow governance for the synthetic case
# workspace. The header carries a FICTIONAL actor id only — this is not
# identity proofing, not credential verification, and not a
# production-security control. Every case route requires purpose
# "individual-access" (the only purpose patient_access.py accepts); grants
# with any other stated purpose authorize no case route in this slice.
FICTIONAL_ACTOR_HEADER = "X-Fictional-Actor"
FICTIONAL_ACTOR_PURPOSE = "individual-access"
DEMO_ACTOR = "FICTIONAL-NAVIGATOR-A"
GRANT_DENIAL_MESSAGE = "Access denied: no active fictional-actor grant for this case"


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
        if n <= 0:
            raise InvalidInput("Request body is required")
        if n > MAX_SOURCE_BYTES + 8192:
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

    def _fictional_actor(self) -> str | None:
        """Presented fictional actor id, or None when missing/unparseable.

        Any non-None value matches the synthetic-id alphabet; the grant
        lookup decides authorization. Malformed values are unknown actors,
        not 422s: behavior item 1 denies them with 403."""
        raw = self.headers.get(FICTIONAL_ACTOR_HEADER)
        if raw is None:
            return None
        actor = raw.strip()
        if not re.fullmatch(ID_PART, actor):
            return None
        return actor

    def _actor_label(self) -> str:
        """Access-log actor field: the presented value, or "missing"."""
        raw = self.headers.get(FICTIONAL_ACTOR_HEADER)
        if raw is None or not raw.strip():
            return "missing"
        return raw.strip()[:128]

    @staticmethod
    def _case_route_id(path: str) -> str | None:
        """Well-formed /api/cases/{ID}/... case id, else None.

        Only well-formed ids are gated here; malformed segments fall through
        to the existing 404 contract, and /api/cases itself is the global
        list route with its own item-7 filtering."""
        parts = path.split("/")
        if len(parts) >= 5 and parts[1] == "api" and parts[2] == "cases" \
                and parts[4] != "" and re.fullmatch(ID_PART, parts[3]):
            return parts[3]
        return None

    def _grant_denial(self) -> None:
        # One fixed shape with zero case-content fields, identical for
        # missing/unknown actors, cross-case reads, and expired, revoked,
        # or wrong-purpose grants.
        return self._json(403, {"error": GRANT_DENIAL_MESSAGE})

    def _require_case_grant(self, store: CaseStore, case_id: str, path: str) -> bool:
        """Gate one case-scoped route. Returns True when allowed (and the
        decision is logged); otherwise sends the denial and returns False.

        Unknown case ids raise InvalidInput (422 "Unknown case") BEFORE the
        grant check, preserving the existing contract with no new existence
        oracle beyond what /api/cases already lists on this demo."""
        label = self._actor_label()
        route = path[:256]
        try:
            store.require_case(case_id)
        except InvalidInput:
            store.record_access(label, case_id, route, "denied")
            raise
        actor = self._fictional_actor()
        if actor is None or not store.has_active_grant(actor, case_id, FICTIONAL_ACTOR_PURPOSE):
            store.record_access(label, case_id, route, "denied")
            self._grant_denial()
            return False
        store.record_access(actor, case_id, route, "allowed")
        return True

    def do_GET(self) -> None:  # noqa: N802
        if not self._host_allowed():
            return self._json(403, {"error": "Unexpected Host for loopback-only demo"})
        path = urlsplit(self.path).path
        try:
            if path in ("/", "/index.html"):
                return self._static("index.html", "text/html; charset=utf-8")
            if path == "/app.js":
                return self._static("app.js", "text/javascript; charset=utf-8")
            if path == "/mission.js":
                return self._static("mission.js", "text/javascript; charset=utf-8")
            if path == "/case_search.js":
                return self._static("case_search.js", "text/javascript; charset=utf-8")
            if path == "/provenance.js":
                return self._static("provenance.js", "text/javascript; charset=utf-8")
            if path == "/consent.js":
                return self._static("consent.js", "text/javascript; charset=utf-8")
            if path == "/clinician-overview.js":
                return self._static("clinician-overview.js", "text/javascript; charset=utf-8")
            if path == "/report.js":
                return self._static("report.js", "text/javascript; charset=utf-8")
            if path == "/style.css":
                return self._static("style.css", "text/css; charset=utf-8")
            if path == "/tokens.css":
                return self._static("tokens.css", "text/css; charset=utf-8")
            if path == "/base.css":
                return self._static("base.css", "text/css; charset=utf-8")
            if path == "/api/examples/amendment":
                return self._json(200, {"text": (SYNTHETIC / "alpha-pathology-amended.txt").read_text()})
            if path == "/api/examples/evidence":
                return self._json(200, {"text": (SYNTHETIC / "demo-evidence.txt").read_text()})
            if path == "/api/examples/wrong-patient":
                return self._json(200, {"text": (SYNTHETIC / "wrong-patient.txt").read_text()})
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
                actor = self._fictional_actor()
                if actor is None:
                    return self._grant_denial()
                query = parse_qs(urlsplit(self.path).query)
                if "search" not in query and "sort" not in query:
                    return self._json(200, store.granted_cases(actor, FICTIONAL_ACTOR_PURPOSE))
                granted = store.granted_cases(actor, FICTIONAL_ACTOR_PURPOSE)
                search = query.get("search", [""])[0]
                sort = query.get("sort", ["id"])[0]
                return self._json(200, list_cases(
                    store, search=search, sort=sort,
                    allowed_ids={c["case_id"] for c in granted}))
            gated_case = self._case_route_id(path)
            if gated_case is not None and not self._require_case_grant(store, gated_case, path):
                return None
            if path == "/api/discovery":
                return self._json(200, store.list_discovery())
            discovery_links = re.fullmatch(rf"/api/cases/{ID_PART}/discovery", path)
            if discovery_links:
                return self._json(200, store.case_discovery_links(discovery_links[1]))
            if path == "/api/rights/sources":
                return self._json(200, store.rights_sources())
            evidence_text = re.fullmatch(r"/api/evidence/([0-9]+)", path)
            if evidence_text:
                return self._json(200, {"text": store.synthetic_evidence_text(int(evidence_text[1]))})
            case_state = re.fullmatch(rf"/api/cases/{ID_PART}/state", path)
            if case_state:
                return self._json(200, store.state(case_state[1]))
            case_options = re.fullmatch(rf"/api/cases/{ID_PART}/options", path)
            if case_options:
                query = parse_qs(urlsplit(self.path).query)
                snapshot_raw = query.get("snapshot_id", [None])[0]
                if snapshot_raw is not None and not snapshot_raw.isdigit():
                    raise InvalidInput("snapshot_id must be a positive integer")
                snapshot_id = int(snapshot_raw) if snapshot_raw is not None else None
                return self._json(200, store.option_view(case_options[1], snapshot_id))
            case_portfolio = re.fullmatch(rf"/api/cases/{ID_PART}/portfolio", path)
            if case_portfolio:
                return self._json(200, store.option_portfolio(case_portfolio[1]))
            case_mission = re.fullmatch(rf"/api/cases/{ID_PART}/mission", path)
            if case_mission:
                return self._json(200, build_patient_mission(store.state(case_mission[1])))
            case_provenance_route = re.fullmatch(rf"/api/cases/{ID_PART}/provenance", path)
            if case_provenance_route:
                return self._json(200, case_provenance(store, case_provenance_route[1]))
            case_overview = re.fullmatch(rf"/api/cases/{ID_PART}/clinician-overview", path)
            if case_overview:
                return self._json(200, build_clinician_overview(store.state(case_overview[1])))
            case_report = re.fullmatch(rf"/api/cases/{ID_PART}/patient-report", path)
            if case_report:
                payload = build_patient_report(store.state(case_report[1]))
                if parse_qs(urlsplit(self.path).query).get("format", [None])[0] == "text":
                    return self._send(200, render_text(payload).encode("utf-8"),
                                      "text/plain; charset=utf-8")
                return self._json(200, payload)
            changes = re.fullmatch(rf"/api/cases/{ID_PART}/changes-since-review", path)
            if changes:
                raw_since = parse_qs(urlsplit(self.path).query).get("since_event_id", [None])[0]
                since = None
                if raw_since is not None:
                    if not raw_since.isdigit():
                        raise InvalidInput("since_event_id must be a positive integer")
                    since = int(raw_since)
                return self._json(200, changes_since_review(store, changes[1], since_event_id=since))
            timeline = re.fullmatch(rf"/api/cases/{ID_PART}/timeline", path)
            if timeline:
                return self._json(200, case_timeline(store, timeline[1]))
            evidence_quality = re.fullmatch(rf"/api/cases/{ID_PART}/evidence-quality", path)
            if evidence_quality:
                return self._json(200, store.evidence_quality(evidence_quality[1]))
            followthrough = re.fullmatch(rf"/api/cases/{ID_PART}/followthrough", path)
            if followthrough:
                return self._json(200, followthrough_view(store, followthrough[1]))
            review_queue = re.fullmatch(rf"/api/cases/{ID_PART}/review-queue", path)
            if review_queue:
                return self._json(200, store.review_queue(review_queue[1]))
            inv_list = re.fullmatch(rf"/api/cases/{ID_PART}/investigations", path)
            if inv_list:
                return self._json(200, {"investigations": store.list_investigations(inv_list[1])})
            inv_one = re.fullmatch(rf"/api/cases/{ID_PART}/investigations/([0-9]+)", path)
            if inv_one:
                return self._json(200, store.get_investigation(inv_one[1], int(inv_one[2])))
            workspace_list = re.fullmatch(rf"/api/cases/{ID_PART}/workspace-questions", path)
            if workspace_list:
                return self._json(200, {"workspace_questions": store.list_workspace_questions(workspace_list[1])})
            question_rollup = re.fullmatch(rf"/api/cases/{ID_PART}/questions/([0-9]+)/rollup", path)
            if question_rollup:
                return self._json(200, question_gap_rollup(store, question_rollup[1], int(question_rollup[2])))
            if path == "/api/investigations/templates":
                return self._json(200, {"templates": [
                    {"id": template_id, "description": text[:160]}
                    for template_id, text in TEMPLATES.items()]})
            consent_list = re.fullmatch(rf"/api/cases/{ID_PART}/consents", path)
            if consent_list:
                return self._json(200, {"consents": store.list_consents(consent_list[1])})
            qualifier_list = re.fullmatch(rf"/api/cases/{ID_PART}/identity-qualifiers", path)
            if qualifier_list:
                return self._json(200, {"identity_qualifiers": store.list_identity_qualifiers(qualifier_list[1])})
            source = re.fullmatch(rf"/api/cases/{ID_PART}/sources/([0-9]+)", path)
            if source:
                return self._json(200, {"text": store.source_text(source[1], int(source[2]))})
            exported = re.fullmatch(rf"/api/cases/{ID_PART}/snapshots/([0-9]+)/export", path)
            if exported:
                contents = store.export_markdown(exported[1], int(exported[2])).encode("utf-8")
                return self._send(200, contents, "text/markdown; charset=utf-8")
            question_synthesis = re.fullmatch(rf"/api/cases/{ID_PART}/questions/([0-9]+)/synthesis", path)
            if question_synthesis:
                return self._json(200, store.question_synthesis(question_synthesis[1], int(question_synthesis[2])))
            snapshot_synthesis = re.fullmatch(rf"/api/cases/{ID_PART}/snapshots/([0-9]+)/synthesis", path)
            if snapshot_synthesis:
                return self._json(200, store.snapshot_synthesis(snapshot_synthesis[1], int(snapshot_synthesis[2])))
            synthesis_report = re.fullmatch(rf"/api/cases/{ID_PART}/snapshots/([0-9]+)/synthesis-report", path)
            if synthesis_report:
                contents = store.synthesis_report(synthesis_report[1], int(synthesis_report[2])).encode("utf-8")
                return self._send(200, contents, "text/markdown; charset=utf-8")
            synthesis_patient = re.fullmatch(rf"/api/cases/{ID_PART}/snapshots/([0-9]+)/synthesis-report-patient", path)
            if synthesis_patient:
                contents = store.synthesis_patient_report(synthesis_patient[1], int(synthesis_patient[2])).encode("utf-8")
                return self._send(200, contents, "text/markdown; charset=utf-8")
            metrics = re.fullmatch(r"/api/metrics/synthetic", path)
            if metrics:
                query = parse_qs(urlsplit(self.path).query)

                def _manifest(values: list[str] | None) -> list[str]:
                    names: list[str] = []
                    for value in values or []:
                        names.extend(part.strip() for part in value.split(","))
                    return [name for name in names if name]

                return self._json(200, fixture_run(
                    store, _manifest(query.get("dev")), _manifest(query.get("held_out"))))
            re_review_list = re.fullmatch(rf"/api/cases/{ID_PART}/re-review-tasks", path)
            if re_review_list:
                return self._json(200, store.list_re_review_tasks(re_review_list[1]))
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
        store = CaseStore(self.db_path)
        try:
            # The grant gate runs before body validation: a missing or
            # unknown actor on a case route is denied (403) even when the
            # body is malformed, and unknown cases stay 422 either way.
            gated_case = self._case_route_id(path)
            if gated_case is not None and not self._require_case_grant(store, gated_case, path):
                return None
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
                correction = re.fullmatch(rf"/api/cases/{ID_PART}/quarantine/([0-9]+)/correct", path)
                if correction:
                    return self._json(200, store.correct_quarantined_delivery(
                        correction[1], int(correction[2]),
                        data.get("destination_case_id"), data.get("actor_label")))
                questions = re.fullmatch(rf"/api/cases/{ID_PART}/questions", path)
                if questions:
                    owner = data.get("owner_label")
                    if isinstance(owner, str) and not owner.strip():
                        owner = None
                    return self._json(201, {"question_id": store.add_question(
                        questions[1], data.get("question"), owner)})
                workspace_create = re.fullmatch(rf"/api/cases/{ID_PART}/workspace-questions", path)
                if workspace_create:
                    return self._json(201, {"workspace_question_id": store.create_workspace_question(
                        workspace_create[1], data.get("question"))})
                workspace_link = re.fullmatch(rf"/api/cases/{ID_PART}/workspace-questions/([0-9]+)/links", path)
                if workspace_link:
                    return self._json(201, {"link_id": store.link_workspace_source(
                        workspace_link[1], int(workspace_link[2]),
                        data.get("source_version_id"), data.get("reason"))})
                workspace_unlink = re.fullmatch(rf"/api/cases/{ID_PART}/workspace-questions/([0-9]+)/links/([0-9]+)/unlink", path)
                if workspace_unlink:
                    return self._json(200, store.unlink_workspace_source(
                        workspace_unlink[1], int(workspace_unlink[2]),
                        int(workspace_unlink[3]), data.get("reason")))
                workspace_status = re.fullmatch(rf"/api/cases/{ID_PART}/workspace-questions/([0-9]+)/status", path)
                if workspace_status:
                    return self._json(200, store.set_workspace_question_status(
                        workspace_status[1], int(workspace_status[2]),
                        data.get("status"), data.get("reason"), data.get("answer")))
                followthrough_create = re.fullmatch(rf"/api/cases/{ID_PART}/followthrough-tasks", path)
                if followthrough_create:
                    task_id = store.create_followthrough_task(
                        followthrough_create[1], data.get("title"),
                        detail=data.get("detail"), due_date=data.get("due_date"),
                        review_trigger=data.get("review_trigger"),
                        question_id=data.get("question_id"),
                        source_version_id=data.get("source_version_id"),
                        actor_label=data.get("actor_label"), reason=data.get("reason"))
                    return self._json(201, {"task_id": task_id})
                followthrough_status = re.fullmatch(
                    rf"/api/cases/{ID_PART}/followthrough-tasks/([0-9]+)/status", path)
                if followthrough_status:
                    kwargs: dict = {}
                    if "due_date" in data:
                        kwargs["due_date"] = data.get("due_date")
                    return self._json(200, store.update_followthrough_task(
                        followthrough_status[1], int(followthrough_status[2]),
                        data.get("status"), actor_label=data.get("actor_label"),
                        reason=data.get("reason"), owner_label=data.get("owner_label"),
                        **kwargs))
                question_owner = re.fullmatch(rf"/api/cases/{ID_PART}/questions/([0-9]+)/owner", path)
                if question_owner:
                    history_id = store.assign_question_owner(
                        question_owner[1], int(question_owner[2]), data.get("owner_label"))
                    return self._json(200, {"history_id": history_id})
                question_triage = re.fullmatch(rf"/api/cases/{ID_PART}/questions/([0-9]+)/triage", path)
                if question_triage:
                    store.set_question_triage(question_triage[1], int(question_triage[2]), data.get("triage"))
                    return self._json(200, {"result": "triage_updated"})
                question_note = re.fullmatch(rf"/api/cases/{ID_PART}/questions/([0-9]+)/evidence-notes", path)
                if question_note:
                    note_id = store.add_question_evidence_note(
                        question_note[1], int(question_note[2]), data.get("note"))
                    return self._json(201, {"note_id": note_id})
                evidence_assessment = re.fullmatch(rf"/api/cases/{ID_PART}/evidence-assessments", path)
                if evidence_assessment:
                    return self._json(201, {"assessment_id": store.assess_synthetic_evidence(
                        evidence_assessment[1], data.get("question_id"), data.get("evidence_version_id"),
                        data.get("relation"), data.get("applicability"), data.get("rationale"))})
                evidence_quality = re.fullmatch(rf"/api/cases/{ID_PART}/evidence-quality", path)
                if evidence_quality:
                    return self._json(201, {"assessment_id": store.record_evidence_quality(
                        evidence_quality[1], data.get("source_version_id"), data.get("assessor_label"),
                        data.get("date_recorded"), data.get("completeness_note"),
                        data.get("limitations_text"), data.get("conflict_note"))})
                if path == "/api/discovery/imports":
                    raw = data.get("text")
                    if not isinstance(raw, str):
                        raise InvalidInput("Fictional discovery text required")
                    return self._json(200, store.import_discovery(
                        raw.encode("utf-8"), rights_source_id=data.get("rights_source_id")))
                discovery_link = re.fullmatch(rf"/api/cases/{ID_PART}/discovery-links", path)
                if discovery_link:
                    return self._json(201, {"link_id": store.link_discovery(
                        discovery_link[1], data.get("question_id"), data.get("discovery_id"),
                        data.get("applicability"), data.get("rationale"),
                        data.get("broker_link_ids"))})
                rights_register = path == "/api/rights/sources"
                if rights_register:
                    return self._json(201, store.register_rights_source(
                        data.get("source_key"), data.get("owner"), data.get("version_label"),
                        data.get("retrieved_at"), data.get("permissions"),
                        data.get("attribution"), data.get("retention")))
                rights_revoke = re.fullmatch(r"/api/rights/sources/([0-9]+)/revoke", path)
                if rights_revoke:
                    return self._json(200, store.revoke_rights_source(
                        int(rights_revoke[1]), data.get("reason")))
                rights_correct = re.fullmatch(r"/api/rights/sources/([0-9]+)/correct", path)
                if rights_correct:
                    return self._json(200, store.correct_rights_source(
                        int(rights_correct[1]), data.get("version_label"), data.get("permissions"),
                        data.get("reason"), data.get("retrieved_at")))
                broker_link = re.fullmatch(rf"/api/cases/{ID_PART}/broker-links", path)
                if broker_link:
                    return self._json(201, store.create_broker_link(
                        broker_link[1], data.get("question_id"), data.get("rights_source_id"),
                        data.get("relation"), data.get("applicability"), data.get("rationale"),
                        data.get("citation_title"), data.get("excerpt")))
                broker_review = re.fullmatch(rf"/api/cases/{ID_PART}/broker-links/([0-9]+)/review", path)
                if broker_review:
                    return self._json(200, store.review_broker_link(
                        broker_review[1], int(broker_review[2]), data.get("relation"),
                        data.get("applicability"), data.get("rationale")))
                limitation_note = re.fullmatch(rf"/api/cases/{ID_PART}/limitation-notes", path)
                if limitation_note:
                    return self._json(201, {"note_id": store.add_limitation_note(
                        limitation_note[1], data.get("question_id"),
                        assessment_id=data.get("assessment_id"),
                        broker_link_id=data.get("broker_link_id"),
                        note=data.get("note"), author_label=data.get("author_label"))})
                bio_assets = re.fullmatch(rf"/api/cases/{ID_PART}/biological-assets", path)
                if bio_assets:
                    return self._json(201, {"biological_asset_id": store.add_biological_asset(
                        bio_assets[1], data.get("asset_id"), data.get("kind"), data.get("episode_id"),
                        data.get("observed_date"), data.get("anchor_source_version_id"),
                        data.get("specimen_state", "unknown"), data.get("specimen_id"),
                        data.get("parent_asset_id"), data.get("pointer_label"))})
                inventory = re.fullmatch(rf"/api/cases/{ID_PART}/biological-assets/([0-9]+)/inventory-assertions", path)
                if inventory:
                    return self._json(201, {"inventory_assertion_id": store.add_inventory_assertion(
                        inventory[1], int(inventory[2]), data.get("source_version_id"),
                        data.get("asserted_by"),
                        location_state=data.get("location_state"), location_value=data.get("location_value"),
                        quantity_state=data.get("quantity_state"), quantity_value=data.get("quantity_value"),
                        custody_state=data.get("custody_state"), custody_value=data.get("custody_value"),
                        consent_state=data.get("consent_state"), consent_value=data.get("consent_value"),
                        rights_state=data.get("rights_state"), rights_value=data.get("rights_value"))})
                bio_explanations = re.fullmatch(rf"/api/cases/{ID_PART}/bio-explanations", path)
                if bio_explanations:
                    return self._json(201, {"bio_explanation_id": store.add_bio_explanation(
                        bio_explanations[1], data.get("question_id"), data.get("label"),
                        data.get("mechanism_text"), data.get("episode_id"),
                        data.get("source_version_id"),
                        specimen_state=data.get("specimen_state", "unknown"),
                        specimen_id=data.get("specimen_id"),
                        lesion_state=data.get("lesion_state", "unknown"),
                        lesion_id=data.get("lesion_id"),
                        clinical_context_state=data.get("clinical_context_state", "unknown"),
                        clinical_context_value=data.get("clinical_context_value"))})
                bio_assays = re.fullmatch(rf"/api/cases/{ID_PART}/bio-explanations/([0-9]+)/assay-observations", path)
                if bio_assays:
                    return self._json(201, {"bio_assay_observation_id": store.record_bio_assay_observation(
                        bio_assays[1], int(bio_assays[2]), data.get("method_label"),
                        data.get("result_note"), data.get("source_version_id"),
                        data.get("reference_kind"),
                        tissue_block_state=data.get("tissue_block_state", "unknown"),
                        tissue_block_asset_id=data.get("tissue_block_asset_id"),
                        matched_control_state=data.get("matched_control_state", "unknown"),
                        matched_control_specimen=data.get("matched_control_specimen"))})
                drafts = re.fullmatch(rf"/api/cases/{ID_PART}/snapshots", path)
                if drafts:
                    return self._json(201, {"snapshot_id": store.create_snapshot(
                        drafts[1], data.get("question_id"), data.get("summary"), data.get("source_ids"),
                        data.get("evidence_assessment_ids"), data.get("broker_link_ids"))})
                review = re.fullmatch(rf"/api/cases/{ID_PART}/snapshots/([0-9]+)/review", path)
                if review:
                    store.acknowledge_demo_review(review[1], int(review[2]), data.get("reviewer_label"))
                    return self._json(200, {"result": "acknowledged_in_demo"})
                queue_receipt = re.fullmatch(rf"/api/cases/{ID_PART}/review-queue/receipts", path)
                if queue_receipt:
                    return self._json(201, store.add_review_receipt(
                        queue_receipt[1], data.get("queue_key"), data.get("action"),
                        data.get("reviewer_label"), data.get("reason")))
                scoped_decision = re.fullmatch(rf"/api/cases/{ID_PART}/snapshots/([0-9]+)/scoped-decisions", path)
                if scoped_decision:
                    return self._json(201, store.record_scoped_decision(
                        scoped_decision[1], int(scoped_decision[2]), data.get("reviewer_label"),
                        data.get("scope"), data.get("note")))
                scoped_dissent = re.fullmatch(rf"/api/cases/{ID_PART}/snapshots/([0-9]+)/scoped-dissents", path)
                if scoped_dissent:
                    return self._json(201, store.record_scoped_dissent(
                        scoped_dissent[1], int(scoped_dissent[2]), data.get("reviewer_label"),
                        data.get("claim_ref"), data.get("rationale")))
                scoped_handoff = re.fullmatch(rf"/api/cases/{ID_PART}/snapshots/([0-9]+)/scoped-handoffs", path)
                if scoped_handoff:
                    return self._json(201, store.record_scoped_handoff(
                        scoped_handoff[1], int(scoped_handoff[2]), data.get("from_reviewer"),
                        data.get("to_reviewer")))
                re_review_close = re.fullmatch(rf"/api/cases/{ID_PART}/re-review-tasks/([0-9]+)/close", path)
                if re_review_close:
                    return self._json(200, store.close_re_review_task(
                        re_review_close[1], int(re_review_close[2]),
                        data.get("closing_snapshot_id"), data.get("no_change_note")))
                option_create = re.fullmatch(rf"/api/cases/{ID_PART}/options", path)
                if option_create:
                    option_id = store.create_option(
                        option_create[1], data.get("snapshot_id"), data.get("label"),
                        data.get("description"), data.get("epistemic_status"))
                    return self._json(201, {"option_id": option_id})
                option_dep = re.fullmatch(rf"/api/cases/{ID_PART}/options/([0-9]+)/dependencies", path)
                if option_dep:
                    dependency_id = store.add_option_dependency(
                        option_dep[1], int(option_dep[2]), data.get("kind"),
                        source_version_id=data.get("source_version_id"),
                        evidence_assessment_id=data.get("evidence_assessment_id"),
                        preparation_task_id=data.get("preparation_task_id"),
                        depends_on_option_id=data.get("depends_on_option_id"),
                        lead_time_days=data.get("lead_time_days"),
                        deadline_date=data.get("deadline_date"),
                        deadline_basis=data.get("deadline_basis", "unknown"),
                        anchor=data.get("anchor", ""))
                    return self._json(201, {"dependency_id": dependency_id})
                option_task = re.fullmatch(rf"/api/cases/{ID_PART}/options/([0-9]+)/tasks", path)
                if option_task:
                    task_id = store.add_preparation_task(
                        option_task[1], int(option_task[2]), data.get("label"),
                        data.get("owner_label"), data.get("lead_time_days"))
                    return self._json(201, {"task_id": task_id})
                task_status = re.fullmatch(rf"/api/cases/{ID_PART}/tasks/([0-9]+)/status", path)
                if task_status:
                    # B-09: acting label is optional and recorded only on done.
                    outcome = store.set_preparation_task_status(
                        task_status[1], int(task_status[2]), data.get("status"),
                        acting_label=data.get("acting_label"))
                    payload: dict = {"result": "task_status_updated"}
                    if outcome is not None:
                        payload["receipt_id"] = outcome["receipt_id"]
                    return self._json(200, payload)
                option_threat = re.fullmatch(rf"/api/cases/{ID_PART}/options/([0-9]+)/threats", path)
                if option_threat:
                    threat_id = store.add_optionality_threat(
                        option_threat[1], int(option_threat[2]), data.get("kind"),
                        data.get("description"), data.get("threat_date"),
                        data.get("threat_basis", "unknown"), data.get("anchor", ""))
                    return self._json(201, {"threat_id": threat_id})
                option_counter = re.fullmatch(rf"/api/cases/{ID_PART}/options/([0-9]+)/counterevidence", path)
                if option_counter:
                    counterevidence_id = store.add_option_counterevidence(
                        option_counter[1], int(option_counter[2]), data.get("effect"),
                        data.get("reason"),
                        source_version_id=data.get("source_version_id"),
                        evidence_assessment_id=data.get("evidence_assessment_id"))
                    return self._json(201, {"counterevidence_id": counterevidence_id})
                option_safety = re.fullmatch(rf"/api/cases/{ID_PART}/options/([0-9]+)/safety-flags", path)
                if option_safety:
                    safety_flag_id = store.add_option_safety_flag(
                        option_safety[1], int(option_safety[2]), data.get("category"),
                        data.get("detail"),
                        source_version_id=data.get("source_version_id"),
                        evidence_assessment_id=data.get("evidence_assessment_id"))
                    return self._json(201, {"safety_flag_id": safety_flag_id})
                option_review = re.fullmatch(rf"/api/cases/{ID_PART}/options/([0-9]+)/review", path)
                if option_review:
                    return self._json(200, store.review_option(
                        option_review[1], int(option_review[2]), data.get("reviewer_label"),
                        data.get("action"), data.get("scope"), data.get("snapshot_id")))
                goal_create = re.fullmatch(rf"/api/cases/{ID_PART}/patient-goals", path)
                if goal_create:
                    return self._json(201, store.add_patient_goal(
                        goal_create[1], data.get("statement"), data.get("stated_date"),
                        data.get("review_trigger"), data.get("review_date")))
                goal_amend = re.fullmatch(rf"/api/cases/{ID_PART}/patient-goals/([0-9]+)/amendments", path)
                if goal_amend:
                    return self._json(201, store.amend_patient_goal(
                        goal_amend[1], int(goal_amend[2]), data.get("statement"),
                        data.get("stated_date"), data.get("review_trigger"),
                        data.get("review_date")))
                goal_status = re.fullmatch(rf"/api/cases/{ID_PART}/patient-goals/([0-9]+)/status", path)
                if goal_status:
                    return self._json(201, store.set_patient_goal_status(
                        goal_status[1], int(goal_status[2]), data.get("status"),
                        data.get("reason")))
                note_create = re.fullmatch(rf"/api/cases/{ID_PART}/patient-notes", path)
                if note_create:
                    return self._json(201, store.add_patient_note(
                        note_create[1], data.get("kind"), data.get("text"),
                        data.get("noted_date")))
                note_amend = re.fullmatch(rf"/api/cases/{ID_PART}/patient-notes/([0-9]+)/amendments", path)
                if note_amend:
                    return self._json(201, store.amend_patient_note(
                        note_amend[1], int(note_amend[2]), data.get("text"),
                        data.get("noted_date")))
                option_flag = re.fullmatch(rf"/api/cases/{ID_PART}/options/([0-9]+)/flags", path)
                if option_flag:
                    flag_id = store.add_option_flag(
                        option_flag[1], int(option_flag[2]), data.get("kind"),
                        data.get("label"), data.get("reason"), data.get("author_label"),
                        source_version_id=data.get("source_version_id"),
                        evidence_assessment_id=data.get("evidence_assessment_id"))
                    return self._json(201, {"flag_id": flag_id})
                flag_resolve = re.fullmatch(rf"/api/cases/{ID_PART}/flags/([0-9]+)/resolve", path)
                if flag_resolve:
                    return self._json(200, store.resolve_option_flag(
                        flag_resolve[1], int(flag_resolve[2]), data.get("reviewer_label"),
                        data.get("action"), data.get("scope")))
                option_dimension = re.fullmatch(rf"/api/cases/{ID_PART}/options/([0-9]+)/dimension-notes", path)
                if option_dimension:
                    note_id = store.add_option_dimension_note(
                        option_dimension[1], int(option_dimension[2]), data.get("dimension"),
                        data.get("note"), data.get("anchor"), data.get("reviewer_label"),
                        source_version_id=data.get("source_version_id"),
                        evidence_assessment_id=data.get("evidence_assessment_id"))
                    return self._json(201, {"dimension_note_id": note_id})
                dimension_ack = re.fullmatch(rf"/api/cases/{ID_PART}/dimension-notes/([0-9]+)/acknowledge", path)
                if dimension_ack:
                    return self._json(200, store.acknowledge_option_dimension_note(
                        dimension_ack[1], int(dimension_ack[2]), data.get("reviewer_label"),
                        data.get("scope")))
                inv_create = re.fullmatch(rf"/api/cases/{ID_PART}/investigations", path)
                if inv_create:
                    case_id = inv_create[1]
                    template = data.get("template")
                    mode = data.get("mode", "live")
                    if template not in TEMPLATES:
                        raise InvalidInput("Unknown investigation template")
                    if mode not in ("live", "replay"):
                        raise InvalidInput("Mode must be live or replay")
                    question_id = data.get("question_id")
                    if type(question_id) is not int:
                        raise InvalidInput("question_id must be an integer")
                    facts = store.investigation_facts(case_id, question_id)
                    if mode == "replay":
                        fixture = json.loads((SYNTHETIC / "demo-investigation.json").read_text())
                        # Replace placeholders with real current ids, then
                        # validate exactly like live output.
                        first_source = next(iter(facts["valid_sources"]), None)
                        first_assessment = next(iter(facts["valid_assessments"]), None)
                        for claim in fixture.get("claims", []):
                            for cite in claim.get("citations", []):
                                if cite.get("id") == "FIRST_SOURCE" and first_source is not None:
                                    cite["id"] = first_source
                                if cite.get("id") == "FIRST_ASSESSMENT" and first_assessment is not None:
                                    cite["id"] = first_assessment
                        validated = validate_output(fixture, facts["valid_sources"], facts["valid_assessments"])
                        validated.model = "recorded-replay"
                        validated.mode = "replay"
                    else:
                        prompt = build_prompt(template, facts["question"]["question"],
                                              facts["assertions"], facts["assessments"])
                        payload = call_meta_api(prompt, meta_api_key())
                        validated = validate_output(payload, facts["valid_sources"], facts["valid_assessments"])
                    investigation_id = store.save_investigation(
                        case_id, question_id, template, validated, mode)
                    return self._json(201, store.get_investigation(case_id, investigation_id))
                consent_create = re.fullmatch(rf"/api/cases/{ID_PART}/consents", path)
                if consent_create:
                    consent_id = store.record_consent(
                        consent_create[1], data.get("scope_text"),
                        data.get("date_recorded"),
                        data.get("anchor_source_version_id"))
                    return self._json(201, {"consent_id": consent_id})
                consent_withdraw = re.fullmatch(
                    rf"/api/cases/{ID_PART}/consents/([0-9]+)/withdraw", path)
                if consent_withdraw:
                    version = store.withdraw_consent(
                        consent_withdraw[1], int(consent_withdraw[2]),
                        data.get("reason"), data.get("date_recorded"))
                    return self._json(200, {"consent_id": int(consent_withdraw[2]),
                                            "version": version, "status": "withdrawn"})
                qualifier_create = re.fullmatch(
                    rf"/api/cases/{ID_PART}/identity-qualifiers", path)
                if qualifier_create:
                    qualifier_id = store.add_identity_qualifier(
                        qualifier_create[1], data.get("qualifier_text"),
                        data.get("anchor_source_version_id"),
                        data.get("date_recorded"), data.get("anchor_line"))
                    return self._json(201, {"qualifier_id": qualifier_id})
                so_request = re.fullmatch(rf"/api/cases/{ID_PART}/second-opinion-requests", path)
                if so_request:
                    return self._json(201, {"request_id": store.create_second_opinion_request(
                        so_request[1], data.get("question_id"), data.get("question_text"),
                        data.get("source_version_ids"), data.get("snapshot_id"))})
                so_response = re.fullmatch(rf"/api/cases/{ID_PART}/second-opinion-requests/([0-9]+)/response", path)
                if so_response:
                    return self._json(201, {"response_id": store.record_second_opinion_response(
                        so_response[1], int(so_response[2]), data.get("responder_label"),
                        data.get("response_text"), data.get("anchor_source_version_id"))})
                so_review = re.fullmatch(rf"/api/cases/{ID_PART}/second-opinion-requests/([0-9]+)/review", path)
                if so_review:
                    return self._json(200, store.review_second_opinion(
                        so_review[1], int(so_review[2]), data.get("reviewer_label"), data.get("scope")))
                surv_plan = re.fullmatch(rf"/api/cases/{ID_PART}/survivorship-plans", path)
                if surv_plan:
                    return self._json(201, {"plan_id": store.create_survivorship_plan(
                        surv_plan[1], data.get("title"))})
                surv_item = re.fullmatch(rf"/api/cases/{ID_PART}/survivorship-plans/([0-9]+)/items", path)
                if surv_item:
                    return self._json(201, {"item_id": store.add_survivorship_item(
                        surv_item[1], int(surv_item[2]), data.get("kind"), data.get("description"),
                        data.get("anchor_source_version_id"), data.get("recorded_date"))})
                surv_review = re.fullmatch(rf"/api/cases/{ID_PART}/survivorship-items/([0-9]+)/review", path)
                if surv_review:
                    return self._json(200, store.review_survivorship_item(
                        surv_review[1], int(surv_review[2]), data.get("reviewer_label"), data.get("scope")))
                surv_trigger = re.fullmatch(rf"/api/cases/{ID_PART}/survivorship-items/([0-9]+)/trigger", path)
                if surv_trigger:
                    return self._json(200, store.mark_survivorship_trigger(
                        surv_trigger[1], int(surv_trigger[2]), data.get("reason")))
                return self._json(404, {"error": "Route not found"})
            finally:
                store.close()
        except InvalidInput as error:
            return self._json(422, {"error": str(error)})
        except InvestigationError as error:
            # Missing operator key is a configuration state, not a bug:
            # offer replay instead of a generic failure.
            status = 503 if "META_API_KEY is not set" in str(error) else 502
            return self._json(status, {"error": str(error)})
        except (OverflowError, UnicodeEncodeError):
            return self._json(422, {"error": "Invalid text or identifier"})
        finally:
            # The gate and bibliography branches return before the inner
            # try/finally; sqlite close() is idempotent, so closing here as
            # well keeps every path clean without touching route code.
            store.close()


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
            # B-01: the demo actor holds a fictional grant on each seeded demo
            # case, so the deny-by-default gate leaves the local demo usable.
            # Re-seeding never duplicates a live grant; seed is an explicit
            # operator action, so it grants anew when no live grant exists.
            if not store.has_active_grant(DEMO_ACTOR, case_id, FICTIONAL_ACTOR_PURPOSE):
                store.create_grant(DEMO_ACTOR, case_id, FICTIONAL_ACTOR_PURPOSE,
                                   "2020-01-01", "2999-12-31")
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
