"""Actual browser correction of manual source selections with preserved history.

Uses the existing CDP harness, the actual local app and independently authored
fictional text. No model, external source or real patient record is involved.
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
from document_intake_browser_journey import (
    ARTIFACTS, assert_mobile_intake, ledger, screenshot, set_fields, state, switch_case,
)
from open_intelligence.store import CaseStore

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_ID = "DOC-PASSAGE-REVISION"
AMBER = "Amber observation; status remains pending."
BLUE = "Blue observation; status was not assessed."
MARKUP = '<img src=x onerror="window.oiAnnotationMarkupExecuted=true">'
ORIGINAL = ("\ufeffIndependently fictional selection record: café\r\n" + AMBER +
            "\r\n" + BLUE + "\r\n" + MARKUP + "\r\n").encode("utf-8")


def annotations(url: str, source_id: int) -> dict:
    with urlopen(url + f"api/cases/CASE-ALPHA/sources/{source_id}/annotations", timeout=5) as response:
        return json.load(response)


def narrative_values(session: ChromeSession) -> dict:
    return session.evaluate("Object.fromEntries(['draft-observations', 'draft-summary', 'draft-assumptions']"
                            ".map(id => [id, document.getElementById(id).value]))")


def wait_revised_composer(session: ChromeSession, previous_fingerprint: str,
                          source_id: int, anchor_label: str) -> None:
    selector = '#composer-context button[data-source-id="' + str(source_id) + '"]'
    session.wait("/^[a-f0-9]{64}$/.test(document.querySelector('#composer-context-fingerprint').value) && "
                 "document.querySelector('#composer-context-fingerprint').value !== " +
                 json.dumps(previous_fingerprint) + " && "
                 "[...document.querySelectorAll(" + json.dumps(selector) + ")].some(button => "
                 "button.textContent === " + json.dumps(anchor_label) + ")",
                 "Composer loads a usable new fingerprint and the corrected source anchor")


def open_editor(session: ChromeSession, source_id: int, revision: int) -> None:
    session.evaluate("document.querySelector('.edit-source-passages[data-source-id=\"" +
                     str(source_id) + "\"]').click()")
    session.wait("!document.querySelector('#intake-review').hidden && "
                 "document.querySelector('#intake-revision-summary').textContent.includes(" +
                 json.dumps("Selection revision " + str(revision)) + ")",
                 "saved source selections opened for revision")
    assert session.evaluate("document.querySelector('#intake-original-lines').textContent.includes(" +
                            json.dumps(MARKUP) + ")")
    assert session.evaluate("document.querySelector('#intake-original-lines img, #intake-original-lines script') === null && "
                            "window.oiAnnotationMarkupExecuted !== true")


def select_passage(session: ChromeSession, *, revised: bool = False) -> None:
    line = 3 if revised else 2
    session.evaluate("document.querySelector('#intake-original-lines button[aria-label=\"Select passage from line " +
                     str(line) + "\"]').click()")
    assert session.evaluate("document.querySelector('#intake-quote').value") == (BLUE if revised else AMBER)
    set_fields(session, {"intake-key": "blue_tag" if revised else "amber_tag",
                         "intake-status": "not-assessed" if revised else "pending"})
    session.evaluate("document.querySelector('#intake-passage-form').requestSubmit()")
    session.wait("document.querySelectorAll('#intake-passages .intake-passage').length === 1",
                 "exact original passage selected")


def save_revision(session: ChromeSession, revision: int) -> None:
    set_fields(session, {"intake-revision-reason":
        "Correct the fictional manually selected passage after reading the original."})
    session.evaluate("document.querySelector('#intake-confirm').click()")
    assert session.evaluate("document.querySelector('#intake-confirm').checked")
    session.evaluate("document.querySelector('#intake-metadata-form').requestSubmit()")
    session.wait("document.querySelector('#intake-review').hidden && "
                 "document.querySelector('#intake-message').textContent.includes(" +
                 json.dumps("Selection revision " + str(revision) + " saved") + ")",
                 "annotation revision saved through original intake form")


def main() -> None:
    chrome = next((path for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
                   if (path := shutil.which(name))), None)
    if chrome is None:
        raise AssertionError("No Chrome/Chromium executable; annotation browser journey NOT verified")
    ARTIFACTS.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    receipt = {"status": "running", "fictional_inputs_only": True, "model_invoked": False,
               "clinical_validation": False, "original_sha256": hashlib.sha256(ORIGINAL).hexdigest()}
    with tempfile.TemporaryDirectory(prefix="oi-annotation-browser-") as directory:
        work = Path(directory)
        db = str(work / "fictional-annotations.sqlite")
        source_file = work / "fictional-selections.txt"
        source_file.write_bytes(ORIGINAL)
        downloads = work / "downloads"
        downloads.mkdir()
        store = CaseStore(db)
        try:
            store.add_case("CASE-ALPHA", "Fictional case Alpha")
            store.add_case("CASE-BETA", "Fictional case Beta")
        finally:
            store.close()
        app_port, debug_port = free_port(), free_port()
        server = subprocess.Popen(
            [sys.executable, "-m", "open_intelligence", "serve", "--db", db, "--port", str(app_port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        browser, session = None, None
        try:
            url = f"http://127.0.0.1:{app_port}/"
            wait_for(lambda: urlopen(url, timeout=1).status == 200, "local fictional annotation server")
            browser = subprocess.Popen([
                chrome, "--headless=new", "--disable-gpu", "--disable-dev-shm-usage",
                "--disable-background-networking", "--no-first-run", "--disable-extensions",
                "--no-default-browser-check", "--remote-allow-origins=*",
                f"--remote-debugging-port={debug_port}", f"--user-data-dir={work / 'chrome'}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            targets = wait_for(lambda: json.load(urlopen(
                f"http://127.0.0.1:{debug_port}/json/list", timeout=1)), "Chrome annotation target")
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
                         "empty fictional workspace")

            # Save the original with zero passages, then add selections later.
            before = ledger(db)
            document_root = session.command("DOM.getDocument")["root"]["nodeId"]
            node_id = session.command("DOM.querySelector", {
                "nodeId": document_root, "selector": "#intake-file",
            })["nodeId"]
            session.command("DOM.setFileInputFiles", {"nodeId": node_id, "files": [str(source_file)]})
            session.evaluate("document.querySelector('#intake-upload-form').requestSubmit()")
            session.wait("!document.querySelector('#intake-review').hidden && "
                         "document.querySelector('#intake-source-hash').textContent.includes(" +
                         json.dumps(receipt["original_sha256"]) + ")", "original-only preview")
            assert ledger(db) == before, "File preview wrote case data"
            assert session.evaluate("document.querySelectorAll('#intake-passages .intake-passage').length === 0")
            set_fields(session, {"intake-document-id": DOCUMENT_ID, "intake-kind": "clinical",
                                 "intake-event-date": "2026-09-01", "intake-issued-date": "2026-09-02"})
            session.evaluate("document.querySelector('#intake-confirm').click(); "
                             "document.querySelector('#intake-metadata-form').requestSubmit()")
            session.wait("document.querySelector('#intake-review').hidden && "
                         "document.querySelectorAll('#source-list .source-card').length === 1",
                         "original-only record saved")
            saved = state(url)
            source_id = saved["sources"][0]["id"]
            assert saved["assertions"] == []
            assert annotations(url, source_id)["current_revision"]["revision"] == 1
            before = ledger(db)
            open_editor(session, source_id, 1)
            assert ledger(db) == before, "Viewing revision history wrote case data"
            assert session.evaluate("document.querySelector('#intake-annotation-history').textContent.includes('Original saved without selected passages.')")
            select_passage(session)
            assert session.evaluate("document.querySelector('#intake-revision-reason').labels.length > 0")
            save_revision(session, 2)
            session.wait("document.querySelector('#assertion-list').textContent.includes('User-selected: pending')",
                         "new manual passage appears in the existing record")
            first = annotations(url, source_id)
            assert len(first["history"]) == 2 and first["history"][0]["findings"] == []
            assert first["current_revision"]["findings"][0]["key"] == "amber_tag"

            # Existing question -> source-bound draft -> explicit demo review.
            set_fields(session, {"question-text": "Which fictional source passage needs another review?"})
            session.evaluate("document.querySelector('#question-form').requestSubmit()")
            session.wait("document.querySelectorAll('#question-list .question').length === 1", "existing question created")
            session.wait("document.querySelector('#composer-context').textContent.includes('User-selected: pending')",
                         "Composer consumes revised manual selections")
            fingerprint = session.evaluate("document.querySelector('#composer-context-fingerprint').value")
            set_fields(session, {"draft-observations": AMBER,
                                 "draft-summary": "No clinical conclusion is proposed from this fictional selection.",
                                 "draft-assumptions": "The manual status is unverified and needs human review."})
            session.evaluate("document.querySelector('#draft-form').requestSubmit()")
            session.wait("document.querySelectorAll('#snapshot-list .snapshot').length === 1", "revision-bound draft saved")
            session.evaluate("[...document.querySelectorAll('#snapshot-list button')].find(button => button.textContent === 'Demo review acknowledgment').click()")
            session.wait("document.querySelector('#snapshot-list .pill').textContent === 'reviewed_in_demo'",
                         "demonstration review acknowledged")
            snapshot_id = state(url)["snapshots"][0]["id"]

            # Prepare another narrative against revision 2 before correction.
            set_fields(session, {"draft-observations": "Earlier manually selected passage: " + AMBER,
                                 "draft-summary": "Unsubmitted fictional narrative, still based on selection revision two.",
                                 "draft-assumptions": "These fictional user selections have not been clinically reviewed."})
            unfinished_narrative = narrative_values(session)
            assert session.evaluate("document.querySelector('#source-choice input').dataset.annotationRevision") == "2"
            open_editor(session, source_id, 2)
            session.evaluate("document.querySelector('#intake-passages .intake-passage button').click()")
            select_passage(session, revised=True)
            session.evaluate("document.querySelector('#intake-annotation-history').open = true")
            screenshot(session, "annotation-revisions-desktop.png", "#import")
            assert_mobile_intake(session)
            screenshot(session, "annotation-revisions-mobile.png", "#import")
            session.command("Emulation.setDeviceMetricsOverride", {
                "width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False,
            })
            save_revision(session, 3)
            session.wait("document.querySelector('#snapshot-list .pill-alert')?.textContent === 'stale' && "
                         "document.querySelector('#assertion-list').textContent.includes('User-selected: not-assessed')",
                         "correction updates current facts and makes earlier review historical")
            wait_revised_composer(session, fingerprint, source_id,
                DOCUMENT_ID + "@1, line 3 · User-selected: not-assessed")
            corrected = state(url)
            assert len(corrected["sources"]) == 1 and corrected["sources"][0]["version"] == 1
            assert corrected["sources"][0]["sha256"] == receipt["original_sha256"]
            assert corrected["questions"][0]["state"] == "open"
            assert corrected["assertions"][0]["finding_key"] == "blue_tag"
            assert corrected["snapshots"][0]["state"] == "stale"
            current = annotations(url, source_id)
            assert [item["revision"] for item in current["history"]] == [1, 2, 3]
            assert current["history"][1]["findings"][0]["key"] == "amber_tag"

            # Historical export must use the captured revision, not today's view.
            session.evaluate("[...document.querySelectorAll('#snapshot-list button')].find(button => button.textContent === 'Export with sources').click()")
            exported_path = downloads / f"synthetic-investigation-{snapshot_id}.md"
            wait_for(lambda: exported_path.exists() and "amber_tag" in exported_path.read_text(),
                     "actual historical Markdown download")
            exported = exported_path.read_text()
            assert "Annotation revision: 2" in exported and "blue_tag" not in exported
            assert "stale" in exported
            session.evaluate("document.querySelector('#source-list a[download]').click()")
            downloaded = downloads / source_file.name
            wait_for(lambda: downloaded.exists() and downloaded.read_bytes() == ORIGINAL,
                     "original-byte browser download after two selection revisions")

            # Saving a narrative prepared against revision 2 must fail until
            # the author explicitly selects the current source revision.
            assert session.evaluate("document.querySelector('#source-choice input').dataset.annotationRevision") == "2"
            before = ledger(db)
            session.evaluate("document.querySelector('#draft-form').requestSubmit()")
            session.wait("document.querySelector('#notice').classList.contains('error') && "
                         "document.querySelector('#notice').textContent.includes('annotations changed')",
                         "stale narrative source selection rejected")
            assert ledger(db) == before, "Rejected stale narrative changed the ledger"
            assert narrative_values(session) == unfinished_narrative, "Correction or rejected save changed unfinished narrative fields"
            session.evaluate("document.querySelector('#source-choice input').click(); document.querySelector('#source-choice input').click()")
            assert session.evaluate("document.querySelector('#source-choice input').dataset.annotationRevision") == "3"
            set_fields(session, {"draft-observations": BLUE,
                                 "draft-summary": "The current manually selected passage is unverified and needs review."})
            session.evaluate("document.querySelector('#draft-form').requestSubmit()")
            session.wait("document.querySelectorAll('#snapshot-list .snapshot').length === 2", "explicitly reconciled draft saved")

            # A delayed old-case annotation response must not repopulate a
            # different case after explicit discard. Pending work first blocks
            # the switch; discard is the user's intentional transition.
            session.evaluate("""(() => {
              const originalFetch = window.fetch;
              window.oiAnnotationRestoreFetch = () => { window.fetch = originalFetch; };
              window.oiAnnotationRelease = null;
              window.fetch = function(input, options) {
                const path = typeof input === 'string' ? input : input.url;
                if (path.includes('/api/cases/CASE-ALPHA/sources/') && path.endsWith('/annotations') && !options?.method)
                  return new Promise((resolve, reject) => {
                    window.oiAnnotationRelease = () => originalFetch.call(window, input, options).then(resolve, reject);
                  });
                return originalFetch.call(this, input, options);
              };
            })()""")
            session.evaluate("document.querySelector('.edit-source-passages[data-source-id=\"" + str(source_id) + "\"]').click()")
            session.wait("typeof window.oiAnnotationRelease === 'function'", "annotation history read held")
            switch_case(session, "CASE-BETA")
            assert session.evaluate("document.querySelector('#case-picker').value") == "CASE-ALPHA"
            session.evaluate("document.querySelector('#intake-discard').click()")
            switch_case(session, "CASE-BETA")
            session.wait("document.querySelector('#case-heading').textContent === 'Fictional case Beta'", "explicit discard permits case switch")
            session.evaluate("window.oiAnnotationRestoreFetch(); window.oiAnnotationRelease();")
            session.wait("document.querySelector('#intake-review').hidden && "
                         "document.querySelector('#intake-original-lines').children.length === 0", "late response remains outside the new case")
            beta = state(url, "CASE-BETA")
            assert beta["sources"] == [] and beta["questions"] == [] and beta["snapshots"] == []
            assert len(state(url)["sources"]) == 1
            receipt.update(status="passed", source_versions=1, annotation_revisions=3,
                           original_download_exact=True, historical_snapshot_state="stale",
                           historical_export_annotation_revision=2, stale_narrative_rejected=True,
                           unfinished_narrative_preserved=True, revised_composer_context_ready=True,
                           explicit_reselection_saved=True, snapshots=2,
                           mobile_width=390, delayed_annotation_case_guard=True)
            print("PASS: original-only upload, later manual passages, append-only correction, exact original preservation, "
                  "historical revision export, stale review and draft rejection, explicit source reselection, "
                  "390px layout and delayed annotation case isolation")
        except BaseException as error:
            receipt.update(status="failed", failure=str(error))
            if session is not None:
                try:
                    screenshot(session, "annotation-revisions-failure.png")
                except Exception as capture_error:
                    receipt["screenshot_error"] = str(capture_error)
            raise
        finally:
            (ARTIFACTS / "annotation-revisions-receipt.json").write_text(json.dumps(receipt, indent=2))
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
