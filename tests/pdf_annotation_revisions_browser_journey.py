"""Actual browser PDF passage correction through the existing patient workflow.

The two-page source is authored here. Screenshots and the machine-readable
receipt describe software behavior only, never clinical validation or a live
model run. The original PDF, frozen extraction and selection revisions keep
their separate identities throughout intake, correction, review and restart.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
from urllib.request import urlopen

from browser_journey import ChromeSession, free_port, wait_for
from document_annotation_revisions_browser_journey import (
    annotations, narrative_values, save_revision, wait_revised_composer,
)
from document_intake_browser_journey import (
    ARTIFACTS, assert_mobile_intake, confirm_metadata, ledger, patient_record_ready,
    screenshot, set_fields, state, submit_record,
)
from open_intelligence.store import CaseStore
from pdf_fixtures import text_pdf


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_ID = "PDF-PASSAGE-CORRECTION"
AMBER = "Amber observation remains pending."
BLUE = "Blue observation was not assessed."
ORIGINAL = text_pdf([["Independently fictional PDF correction record."], [AMBER, BLUE]])


def select_pdf_passage(session: ChromeSession, *, revised=False) -> None:
    quote, page_line = (BLUE, 2) if revised else (AMBER, 1)
    label = "Select passage from page 2, extracted line " + str(page_line)
    selector = "#intake-original-lines button[aria-label=" + json.dumps(label) + "]"
    session.evaluate("document.querySelector(" + json.dumps(selector) + ").click()")
    assert session.evaluate("document.querySelector('#intake-quote').value") == quote
    assert session.evaluate("document.querySelector('#intake-passage-location').textContent.includes(" +
                            json.dumps("page 2, extracted line " + str(page_line)) + ")")
    set_fields(session, {"intake-key": "blue_tag" if revised else "amber_tag",
                         "intake-status": "not-assessed" if revised else "pending"})
    session.evaluate("document.querySelector('#intake-passage-form').requestSubmit()")
    session.wait("document.querySelectorAll('#intake-passages .intake-passage').length === 1",
                 "one exact passage selected from the frozen physical page")


def open_pdf_editor(session: ChromeSession, source_id: int, revision: int) -> None:
    selector = '.edit-source-passages[data-source-id="' + str(source_id) + '"]'
    session.evaluate("document.querySelector(" + json.dumps(selector) + ").click()")
    session.wait("!document.querySelector('#intake-review').hidden && "
                 "document.querySelector('#intake-revision-summary').textContent.includes(" +
                 json.dumps("Selection revision " + str(revision)) + ")",
                 "saved PDF opens the existing passage revision editor")
    assert session.evaluate("document.querySelector('#intake-original-lines').textContent.includes(" +
                            json.dumps(AMBER) + ")")
    assert session.evaluate("document.querySelector('#intake-original-lines').textContent.includes(" +
                            json.dumps(BLUE) + ")")
    assert session.evaluate("document.querySelector('#intake-extraction-details').textContent.length > 0")


def check_selected_source(session: ChromeSession, source_id: int, *, revised=False) -> None:
    quote, line, page_line = (BLUE, 3, 2) if revised else (AMBER, 2, 1)
    selector = ('#patient-findings button[data-source-id="' + str(source_id) +
                '"][data-source-line="' + str(line) + '"]')
    session.evaluate("document.querySelector(" + json.dumps(selector) + ").click()")
    session.wait("document.querySelector('#source-dialog').open && "
                 "document.querySelector('mark.source-highlight')?.dataset.page === '2'",
                 "patient finding opens its exact frozen PDF page")
    assert session.evaluate("document.querySelector('mark.source-highlight').textContent") == quote
    assert session.evaluate("document.querySelector('mark.source-highlight').dataset.pageLine") == str(page_line)
    assert session.evaluate("document.querySelector('#dialog-context').textContent.includes('manually selected')")
    session.evaluate("document.querySelector('#dialog-close').click()")


def main() -> None:
    chrome = next((path for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
                   if (path := shutil.which(name))), None)
    if chrome is None:
        raise AssertionError("No Chrome/Chromium executable; PDF correction browser journey NOT verified")
    ARTIFACTS.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    receipt = {"status": "running", "fictional_inputs_only": True,
               "model_invoked": False, "clinical_validation": False,
               "original_sha256": hashlib.sha256(ORIGINAL).hexdigest()}
    with tempfile.TemporaryDirectory(prefix="oi-pdf-annotation-browser-") as directory:
        work = Path(directory)
        db = str(work / "fictional-pdf-corrections.sqlite")
        source_file = work / "fictional-pdf-corrections.pdf"
        source_file.write_bytes(ORIGINAL)
        downloads = work / "downloads"
        downloads.mkdir()
        store = CaseStore(db)
        try:
            store.add_case("CASE-ALPHA", "Fictional case Alpha")
        finally:
            store.close()
        app_port, debug_port = free_port(), free_port()
        server_args = [sys.executable, "-m", "open_intelligence", "serve", "--db", db, "--port", str(app_port)]

        def start_server():
            return subprocess.Popen(server_args, cwd=ROOT, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        server, browser, session = start_server(), None, None
        try:
            url = f"http://127.0.0.1:{app_port}/"
            wait_for(lambda: urlopen(url, timeout=1).status == 200, "local PDF correction server")
            browser = subprocess.Popen([
                chrome, "--headless=new", "--disable-gpu", "--disable-dev-shm-usage",
                "--disable-background-networking", "--no-first-run", "--disable-extensions",
                "--no-default-browser-check", "--remote-allow-origins=*",
                f"--remote-debugging-port={debug_port}", f"--user-data-dir={work / 'chrome'}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            targets = wait_for(lambda: json.load(urlopen(
                f"http://127.0.0.1:{debug_port}/json/list", timeout=1)), "Chrome PDF correction target")
            page = next(target for target in targets if target.get("type") == "page")
            session = ChromeSession(page["webSocketDebuggerUrl"])
            for domain in ("Page", "Runtime", "DOM"):
                session.command(domain + ".enable")
            session.command("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(downloads)})
            session.command("Emulation.setDeviceMetricsOverride", {
                "width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False,
            })
            session.command("Page.navigate", {"url": url})
            session.wait("document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'",
                         "empty fictional PDF workspace")

            before = ledger(db)
            document_root = session.command("DOM.getDocument")["root"]["nodeId"]
            node_id = session.command("DOM.querySelector", {
                "nodeId": document_root, "selector": "#intake-file",
            })["nodeId"]
            session.command("DOM.setFileInputFiles", {"nodeId": node_id, "files": [str(source_file)]})
            session.evaluate("document.querySelector('#intake-upload-form').requestSubmit()")
            session.wait("!document.querySelector('#intake-review').hidden && "
                         "document.querySelector('#intake-source-hash').textContent.includes(" +
                         json.dumps(receipt["original_sha256"]) + ")", "actual PDF file preview")
            assert ledger(db) == before, "PDF preview wrote persistent case state"
            select_pdf_passage(session)
            confirm_metadata(session, document_id=DOCUMENT_ID)
            submit_record(session, 1, DOCUMENT_ID)
            saved = state(url)
            source_id = saved["sources"][0]["id"]
            original_annotation = annotations(url, source_id)
            extraction_hash = original_annotation["extraction_sha256"]
            page_hash = original_annotation["pages"][1]["sha256"]
            assert original_annotation["current_revision"]["revision"] == 1
            patient_record_ready(session, AMBER)
            check_selected_source(session, source_id)

            set_fields(session, {"question-text": "Which fictional PDF passage needs review after a correction?"})
            session.evaluate("document.querySelector('#question-form').requestSubmit()")
            session.wait("document.querySelectorAll('#question-list .question').length === 1", "durable question saved")
            session.wait("document.querySelector('#composer-context').textContent.includes('User-selected: pending')",
                         "Composer sees the same initial manual selection")
            old_context = session.evaluate("document.querySelector('#composer-context-fingerprint').value")
            set_fields(session, {"draft-observations": AMBER,
                                 "draft-summary": "Independent fictional PDF passage review; no clinical conclusion.",
                                 "draft-assumptions": "A manual selection is not a clinical interpretation."})
            session.evaluate("document.querySelector('#draft-form').requestSubmit()")
            session.wait("document.querySelectorAll('#snapshot-list .snapshot').length === 1", "source-bound report saved")
            session.evaluate("[...document.querySelectorAll('#snapshot-list button')].find(button => button.textContent === 'Demo review acknowledgment').click()")
            session.wait("document.querySelector('#snapshot-list .pill').textContent === 'reviewed_in_demo'",
                         "initial report explicitly acknowledged in demonstration")
            snapshot_id = state(url)["snapshots"][0]["id"]

            # Keep unfinished narrative bound to revision 1 while the current
            # PDF passage selection moves to revision 2.
            set_fields(session, {"draft-observations": "Earlier manual passage: " + AMBER,
                                 "draft-summary": "Unsubmitted fictional narrative still based on the initial selection.",
                                 "draft-assumptions": "These fictional user selections have not been clinically reviewed."})
            unfinished_narrative = narrative_values(session)
            assert session.evaluate("document.querySelector('#source-choice input').dataset.annotationRevision") == "1"
            before = ledger(db)
            open_pdf_editor(session, source_id, 1)
            assert ledger(db) == before, "Opening saved PDF revisions wrote persistent state"
            session.evaluate("document.querySelector('#intake-passages .intake-passage button').click()")
            select_pdf_passage(session, revised=True)
            session.evaluate("""(() => {
              const originalFetch = window.fetch;
              window.oiRestorePdfRevisionFetch = () => {window.fetch = originalFetch;};
              window.fetch = function(input, options) {
                const path = typeof input === 'string' ? input : input.url;
                if (path.endsWith('/annotations') && options?.method === 'POST')
                  window.oiPdfRevisionRequest = JSON.parse(options.body);
                return originalFetch.call(this, input, options);
              };
            })()""")
            session.evaluate("document.querySelector('#intake-annotation-history').open = true")
            screenshot(session, "pdf-annotation-revisions-desktop.png", "#import")
            assert_mobile_intake(session)
            screenshot(session, "pdf-annotation-revisions-mobile.png", "#import")
            session.command("Emulation.setDeviceMetricsOverride", {
                "width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False,
            })
            save_revision(session, 2)
            sent = session.evaluate("window.oiPdfRevisionRequest")
            assert sent["expected_sha256"] == receipt["original_sha256"]
            assert sent["expected_extraction_sha256"] == extraction_hash
            assert sent["expected_revision"] == 1
            assert sent["findings"][0]["line"] == 3 and sent["findings"][0]["quote"] == BLUE
            session.evaluate("window.oiRestorePdfRevisionFetch()")
            patient_record_ready(session, BLUE)
            session.wait("document.querySelector('#snapshot-list .pill-alert')?.textContent === 'stale'",
                         "correction invalidates the old report")
            wait_revised_composer(session, old_context, source_id,
                DOCUMENT_ID + "@1, page 2, extracted line 2 · User-selected: not-assessed")
            assert not session.evaluate("document.querySelector('#patient-findings').textContent.includes(" + json.dumps(AMBER) + ")")
            assert session.evaluate("document.querySelector('#patient-findings').textContent.includes('Selection revision 2')")
            check_selected_source(session, source_id, revised=True)
            corrected = state(url)
            assert len(corrected["sources"]) == 1 and corrected["sources"][0]["version"] == 1
            assert corrected["questions"][0]["state"] == "open"
            assert corrected["assertions"][0]["annotation_revision"] == 2
            assert corrected["assertions"][0]["extraction_sha256"] == extraction_hash

            session.evaluate("[...document.querySelectorAll('#snapshot-list button')].find(button => button.textContent === 'Export with sources').click()")
            exported = downloads / f"synthetic-investigation-{snapshot_id}.md"
            wait_for(lambda: exported.exists() and "Annotation revision: 1" in exported.read_text(),
                     "historical PDF report downloads with its captured revision")
            report = exported.read_text()
            selected = report.split("User-selected annotations captured with this report:", 1)[1].split(
                "PDF extracted text below", 1)[0]
            assert AMBER in selected and BLUE not in selected
            assert "Physical page: 2 | Page line: 1" in selected and page_hash in selected
            assert "**stale**" in report and extraction_hash in report and receipt["original_sha256"] in report
            session.evaluate("document.querySelector('#source-list a[download]').click()")
            downloaded = downloads / source_file.name
            wait_for(lambda: downloaded.exists() and downloaded.read_bytes() == ORIGINAL,
                     "original PDF browser download remains byte-identical")

            assert session.evaluate("document.querySelector('#source-choice input').dataset.annotationRevision") == "1"
            before = ledger(db)
            session.evaluate("document.querySelector('#draft-form').requestSubmit()")
            session.wait("document.querySelector('#notice').classList.contains('error') && "
                         "document.querySelector('#notice').textContent.includes('annotations changed')",
                         "unfinished PDF narrative cannot silently adopt revised selections")
            assert ledger(db) == before, "Rejected stale PDF narrative changed the ledger"
            assert narrative_values(session) == unfinished_narrative, "Correction or rejected save changed unfinished PDF narrative fields"

            # A real process restart reads the same immutable page rendition,
            # current annotation revision, history and stale earlier report.
            server.terminate()
            server.wait(timeout=5)
            server = start_server()
            wait_for(lambda: urlopen(url, timeout=1).status == 200, "restarted PDF correction server")
            session.evaluate("window.oiPdfBeforeReload = true")
            session.command("Page.reload")
            session.wait("window.oiPdfBeforeReload !== true && "
                         "document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'",
                         "fictional workspace reloads after process restart")
            patient_record_ready(session, BLUE)
            current = annotations(url, source_id)
            assert [entry["revision"] for entry in current["history"]] == [1, 2]
            assert current["history"][0]["findings"][0]["quote"] == AMBER
            assert current["current_revision"]["findings"][0]["quote"] == BLUE
            assert current["pages"] == original_annotation["pages"]
            assert current["extraction_sha256"] == extraction_hash
            assert state(url)["snapshots"][0]["state"] == "stale"
            check_selected_source(session, source_id, revised=True)
            screenshot(session, "pdf-annotation-revisions-patient-record.png", "#patient-view")
            open_pdf_editor(session, source_id, 2)
            session.evaluate("document.querySelector('#intake-annotation-history').open = true")
            assert session.evaluate("document.querySelector('#intake-annotation-history').textContent.includes(" + json.dumps(AMBER) + ")")
            assert session.evaluate("document.querySelector('#intake-annotation-history').textContent.includes(" + json.dumps(BLUE) + ")")
            assert session.evaluate("document.querySelector('#intake-annotation-history').textContent.includes('page 2')")
            screenshot(session, "pdf-annotation-revisions-history.png", "#import")
            session.evaluate("document.querySelector('#intake-discard').click()")

            # Reloaded source choices bind the current revision. An explicitly
            # new report can now continue the same question and review flow.
            assert session.evaluate("document.querySelector('#source-choice input').dataset.annotationRevision") == "2"
            set_fields(session, {"draft-observations": BLUE,
                                 "draft-summary": "Current fictional PDF selection inspected; no clinical conclusion."})
            session.evaluate("document.querySelector('#draft-form').requestSubmit()")
            session.wait("document.querySelectorAll('#snapshot-list .snapshot').length === 2", "replacement report saved against current revision")
            session.evaluate("[...document.querySelectorAll('#snapshot-list button')].find(button => button.textContent === 'Demo review acknowledgment').click()")
            session.wait("document.querySelector('#snapshot-list .pill').textContent === 'reviewed_in_demo'",
                         "replacement report explicitly acknowledged in demonstration")
            final = state(url)
            assert final["snapshots"][0]["state"] == "reviewed_in_demo"
            assert final["snapshots"][1]["state"] == "stale"
            assert final["questions"][0]["state"] == "addressed"
            receipt.update(status="passed", source_versions=1, annotation_revisions=2,
                           original_download_exact=True, extraction_sha256=extraction_hash,
                           physical_page=2, current_page_line=2, historical_page_line=1,
                           current_annotation_revision=2, historical_export_annotation_revision=1,
                           historical_snapshot_state="stale", stale_narrative_rejected=True,
                           unfinished_narrative_preserved=True, revised_composer_context_ready=True,
                           process_restart_preserved=True, replacement_report_demo_acknowledged=True,
                           mobile_width=390, dual_hash_save=True)
            print("PASS: actual PDF upload, page-two passage, manual correction with both hashes, current patient record, "
                  "source jump, old report staleness and captured page/revision export, exact original download, "
                  "stale narrative rejection, process restart, preserved history and replacement demonstration review")
        except BaseException as error:
            receipt.update(status="failed", failure=str(error))
            if session is not None:
                try:
                    screenshot(session, "pdf-annotation-revisions-failure.png")
                except Exception as capture_error:
                    receipt["screenshot_error"] = str(capture_error)
            raise
        finally:
            (ARTIFACTS / "pdf-annotation-revisions-receipt.json").write_text(json.dumps(receipt, indent=2))
            if session is not None:
                session.close()
            if browser is not None:
                try:
                    os.killpg(browser.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    browser.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(browser.pid, signal.SIGKILL)
                    browser.wait(timeout=5)
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__ == "__main__":
    main()
