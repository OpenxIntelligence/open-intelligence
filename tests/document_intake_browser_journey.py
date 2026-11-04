"""Actual browser journey from a fictional .txt upload to a reviewable amendment.

Uses the existing standard-library CDP harness and first-party local app. The
files are independently authored here; no model, patient data or remote source
is used. Screenshots and a bounded receipt go to composer-broker-artifacts/.
"""
from __future__ import annotations

import base64
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
from open_intelligence.store import CaseStore

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "composer-broker-artifacts"
DOCUMENT_ID = "DOC-TEXT-INTAKE"
ORIGINAL_QUOTE = "Observation: amber placeholder; review remains pending."
AMENDED_QUOTE = "Observation: blue placeholder; review remains pending."
LITERAL_MARKUP = '<img src=x onerror="window.oiIntakeMarkupExecuted=true">'
ORIGINAL = ("\ufeffIndependently fictional text record: café\r\n" + ORIGINAL_QUOTE +
            "\r\n" + LITERAL_MARKUP + "\r\n").encode("utf-8")
AMENDED = ORIGINAL.replace(b"amber placeholder", b"blue placeholder")
# #140-stack-only: Composer (#composer-context) is absent from main 2451983.
# Both Composer gates below skip by design when it is absent. No Composer shim.
COMPOSER_ABSENT_SKIP = "skipped: #composer-context absent on main (#140-stack-only)"


def ledger(db: str) -> str:
    store = CaseStore(db)
    try:
        return "\n".join(store.db.iterdump())
    finally:
        store.close()


def state(url: str, case_id: str = "CASE-ALPHA") -> dict:
    with urlopen(url + "api/cases/" + case_id + "/state", timeout=5) as response:
        return json.load(response)


def screenshot(session: ChromeSession, name: str, selector: str | None = None) -> None:
    params = {"format": "png", "captureBeyondViewport": True}
    if selector:
        clip = session.evaluate("""(selector => {
          const element = document.querySelector(selector);
          element.scrollIntoView({block: 'start'});
          const rect = element.getBoundingClientRect();
          return {x: rect.left + window.scrollX, y: rect.top + window.scrollY,
                  width: rect.width, height: rect.height, scale: 1};
        })(""" + json.dumps(selector) + ")")
        if clip["width"] > 0 and clip["height"] > 0:
            params["clip"] = clip
    encoded = session.command("Page.captureScreenshot", params)["data"]
    (ARTIFACTS / name).write_bytes(base64.b64decode(encoded))


def set_fields(session: ChromeSession, fields: dict) -> None:
    session.evaluate("""(fields => {
      for (const [id, value] of Object.entries(fields)) {
        const element = document.getElementById(id);
        element.value = String(value);
        element.dispatchEvent(new Event('input', {bubbles: true}));
        element.dispatchEvent(new Event('change', {bubbles: true}));
      }
    })(""" + json.dumps(fields) + ")")


def switch_case(session: ChromeSession, case_id: str) -> None:
    set_fields(session, {"case-picker": case_id})


def upload_preview(session: ChromeSession, path: Path, raw: bytes) -> None:
    root = session.command("DOM.getDocument")["root"]["nodeId"]
    node_id = session.command("DOM.querySelector", {
        "nodeId": root, "selector": "#intake-file",
    })["nodeId"]
    session.command("DOM.setFileInputFiles", {"nodeId": node_id, "files": [str(path)]})
    session.wait("document.querySelector('#intake-file').files.length === 1",
                 "actual local file selected")
    session.evaluate("document.querySelector('#intake-upload-form').requestSubmit()")
    digest = hashlib.sha256(raw).hexdigest()
    session.wait(
        "!document.querySelector('#intake-review').hidden && "
        "document.querySelector('#intake-source-hash').textContent.includes(" +
        json.dumps(digest) + ")", "original-byte preview")
    assert session.evaluate("document.querySelector('#intake-original-lines').textContent.includes(" +
                            json.dumps(LITERAL_MARKUP) + ")"), "Preview lost literal source text"
    assert session.evaluate(
        "document.querySelector('#intake-original-lines img, #intake-original-lines script') === null && "
        "window.oiIntakeMarkupExecuted !== true"), "Preview executed source markup"


def select_passage(session: ChromeSession, quote: str) -> None:
    session.evaluate(
        "document.querySelector('#intake-original-lines button[aria-label=\"Select passage from line 2\"]').click()")
    assert session.evaluate("document.querySelector('#intake-quote').value") == quote
    set_fields(session, {"intake-key": "color_tag", "intake-status": "pending"})
    session.evaluate("document.querySelector('#intake-passage-form').requestSubmit()")
    session.wait("document.querySelectorAll('#intake-passages .intake-passage').length === 1",
                 "exact passage selected for manual transcription")


def confirm_metadata(session: ChromeSession, *, amendment: bool = False) -> None:
    if amendment:
        session.evaluate("document.querySelector('#intake-amends').closest('details').open = true")
    set_fields(session, {
        "intake-document-id": DOCUMENT_ID, "intake-kind": "clinical",
        "intake-event-date": "2026-08-01",
        "intake-issued-date": "2026-08-03" if amendment else "2026-08-02",
        "intake-amends": "1" if amendment else "",
    })
    session.evaluate("document.querySelector('#intake-confirm').click()")
    assert session.evaluate("document.querySelector('#intake-confirm').checked")


def submit_record(session: ChromeSession, version: int) -> None:
    session.evaluate("document.querySelector('#intake-metadata-form').requestSubmit()")
    expected = DOCUMENT_ID + " @" + str(version)
    session.wait(
        "[...document.querySelectorAll('#source-list .source-card')].some(card => "
        "card.querySelector('.source-title')?.textContent === " + json.dumps(expected) + ") && "
        "document.querySelector('#intake-review').hidden && "
        "document.querySelector('#intake-success-actions').children.length > 0",
        "confirmed original persisted and existing case projections refreshed")


def assert_intake_accessibility(session: ChromeSession) -> None:
    assert session.evaluate("""[...document.querySelectorAll(
      '#intake-upload-form input, #intake-metadata-form input, #intake-metadata-form select, '
      + '#intake-passage-form input, #intake-passage-form select, #intake-passage-form textarea'
    )].every(input => [...input.labels].some(label => label.textContent.trim()))"""), (
        "An intake field has no visible associated label")
    session.command("Accessibility.enable")
    nodes = session.command("Accessibility.getFullAXTree").get("nodes", [])
    names = {(node.get("role", {}).get("value"), node.get("name", {}).get("value", ""))
             for node in nodes}
    assert ("button", "Select passage from line 2") in names, "Source-line button lacks an accessible name"
    assert ("textbox", "Document reference") in names, "Document reference is not exposed as a named field"
    assert any(role == "checkbox" and "I checked that this record belongs" in name
               for role, name in names), "Case/transcription confirmation is not announced"


def assert_mobile_intake(session: ChromeSession) -> None:
    session.command("Emulation.setDeviceMetricsOverride", {
        "width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": False,
    })
    session.wait("window.innerWidth === 390", "390px intake viewport")
    bounds = session.evaluate("""(() => {
      const panel = document.querySelector('#import');
      panel.scrollIntoView({block: 'start'});
      const viewport = document.documentElement.clientWidth;
      const outliers = [...panel.querySelectorAll('*')].filter(element => {
        if (!element.getClientRects().length) return false;
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && (rect.right > viewport + 1 || rect.left < -1);
      }).map(element => element.id || element.tagName).slice(0, 12);
      const overflowing = [...panel.querySelectorAll('*')].filter(element =>
        element.getClientRects().length && element.scrollWidth > element.clientWidth + 1
      ).map(element => ({id: element.id || element.tagName,
        client: element.clientWidth, scroll: element.scrollWidth})).slice(0, 12);
      return {client: panel.clientWidth, scroll: panel.scrollWidth, outliers, overflowing};
    })()""")
    assert bounds["scroll"] <= bounds["client"] + 1 and not bounds["outliers"], (
        "New intake panel overflows the 390px viewport: " + json.dumps(bounds))


def main() -> None:
    chrome = next((path for name in (
        "google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
        if (path := shutil.which(name))), None)
    if chrome is None:
        raise AssertionError("No Chrome/Chromium executable; document intake browser journey NOT verified")
    ARTIFACTS.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    receipt = {"status": "running", "fictional_inputs_only": True,
               "model_invoked": False, "clinical_validation": False,
               "original_sha256": hashlib.sha256(ORIGINAL).hexdigest(),
               "amended_sha256": hashlib.sha256(AMENDED).hexdigest(),
               "composer_source_gate": "pending (#140-stack-only)",
               "composer_refresh_gate": "pending (#140-stack-only)"}
    with tempfile.TemporaryDirectory(prefix="oi-document-browser-") as directory:
        work = Path(directory)
        db = str(work / "fictional-intake.sqlite")
        original_path, amended_path = work / "fictional-record.txt", work / "fictional-record-amended.txt"
        original_path.write_bytes(ORIGINAL)
        amended_path.write_bytes(AMENDED)
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
            [sys.executable, "-m", "open_intelligence", "serve", "--db", db,
             "--port", str(app_port)], cwd=ROOT, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        browser, session = None, None
        try:
            url = f"http://127.0.0.1:{app_port}/"
            wait_for(lambda: urlopen(url, timeout=1).status == 200, "local fictional intake server")
            browser = subprocess.Popen([
                chrome, "--headless=new", "--disable-gpu", "--disable-dev-shm-usage",
                "--disable-background-networking", "--no-first-run", "--disable-extensions",
                "--no-default-browser-check", "--remote-allow-origins=*",
                f"--remote-debugging-port={debug_port}",
                f"--user-data-dir={work / 'chrome'}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            targets = wait_for(lambda: json.load(urlopen(
                f"http://127.0.0.1:{debug_port}/json/list", timeout=1)), "Chrome intake target")
            page = next(target for target in targets if target.get("type") == "page")
            session = ChromeSession(page["webSocketDebuggerUrl"])
            session.command("Page.enable")
            session.command("Runtime.enable")
            session.command("DOM.enable")
            session.command("Browser.setDownloadBehavior", {
                "behavior": "allow", "downloadPath": str(downloads),
            })
            session.command("Emulation.setDeviceMetricsOverride", {
                "width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False,
            })
            session.command("Page.navigate", {"url": url})
            session.wait("document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'",
                         "empty Alpha workspace loaded")
            before = ledger(db)
            upload_preview(session, original_path, ORIGINAL)
            assert ledger(db) == before, "Preview persisted source or annotation data"
            switch_case(session, "CASE-BETA")
            assert session.evaluate("document.querySelector('#case-picker').value") == "CASE-ALPHA", (
                "Unfinished intake silently moved to another case")
            assert session.evaluate("!document.querySelector('#intake-review').hidden")
            session.evaluate("document.querySelector('#intake-discard').click()")
            switch_case(session, "CASE-BETA")
            session.wait("document.querySelector('#case-heading').textContent === 'Fictional case Beta'",
                         "discard permits case change")
            assert state(url, "CASE-BETA")["sources"] == []
            assert session.evaluate("document.querySelector('#intake-original-lines').children.length === 0")
            switch_case(session, "CASE-ALPHA")
            session.wait("document.querySelector('#case-heading').textContent === 'Fictional case Alpha'",
                         "Alpha restored after explicit discard")
            upload_preview(session, original_path, ORIGINAL)
            assert ledger(db) == before
            select_passage(session, ORIGINAL_QUOTE)
            confirm_metadata(session)
            assert_intake_accessibility(session)
            screenshot(session, "document-intake-desktop.png", "#import")
            assert_mobile_intake(session)
            screenshot(session, "document-intake-mobile.png", "#import")
            session.command("Emulation.setDeviceMetricsOverride", {
                "width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False,
            })
            submit_record(session, 1)
            saved = state(url)
            original_id = next(source["id"] for source in saved["sources"]
                               if source["document_id"] == DOCUMENT_ID)
            assert saved["assertions"][0]["classification_origin"] == "user_selected"
            session.wait("document.querySelector('#assertion-list').textContent.includes('User-selected: pending')",
                         "manual status is distinct from source authorship")
            assert session.evaluate("document.querySelector('#patient-findings').textContent.includes('User-selected status:')")
            assert session.evaluate("document.querySelector('#assertion-list').textContent.includes('Clinical review not performed')")
            session.evaluate("[...document.querySelectorAll('#intake-success-actions button')].find(button => button.textContent === 'Open original').click()")
            session.wait("document.querySelector('#source-dialog').open", "uploaded original opened through UI")
            assert session.evaluate("document.querySelector('#dialog-text').textContent") == ORIGINAL.decode("utf-8")
            assert session.evaluate("document.querySelector('#dialog-text img, #dialog-text script') === null && window.oiIntakeMarkupExecuted !== true")
            session.evaluate("document.querySelector('#dialog-close').click()")
            session.evaluate("document.querySelector('#source-list a[download]').click()")
            downloaded = downloads / original_path.name
            wait_for(lambda: downloaded.exists() and downloaded.read_bytes() == ORIGINAL,
                     "original-byte browser download")
            assert hashlib.sha256(downloaded.read_bytes()).hexdigest() == receipt["original_sha256"]

            set_fields(session, {"question-text": "What changed in the fictional color tag between these records?"})
            session.evaluate("document.querySelector('#question-form').requestSubmit()")
            session.wait("document.querySelectorAll('#question-list .question').length === 1",
                         "question created through the existing form")
            # #140-stack-only Composer source-inclusion gate: skipped by design
            # on main, where #composer-context is absent. No Composer shim.
            if session.evaluate("document.querySelector('#composer-context') === null"):
                receipt["composer_source_gate"] = COMPOSER_ABSENT_SKIP
                prior_context = None
            else:
                session.wait("document.querySelector('#composer-context button[data-source-id=\"" + str(original_id) + "\"]') !== null && "
                             "document.querySelector('#composer-context').textContent.includes('User-selected: pending')",
                             "existing Composer includes the uploaded source and manual origin (#140-stack-only)")
                assert session.evaluate("document.querySelector('#composer-context').textContent.includes('Clinical review not performed')")
                prior_context = session.evaluate("document.querySelector('#composer-context-fingerprint').value")
                assert len(prior_context) == 64
                receipt["composer_source_gate"] = "checked (#140-stack-only)"
            session.evaluate("[...document.querySelectorAll('#source-choice input')].forEach(input => {input.checked = input.value === " + json.dumps(str(original_id)) + ";})")
            set_fields(session, {
                "draft-observations": "The manually selected fictional passage states: " + ORIGINAL_QUOTE,
                "draft-summary": "No clinical conclusion is proposed from this fictional record.",
                "draft-assumptions": "Source authenticity and clinical meaning have not been assessed.",
            })
            session.evaluate("document.querySelector('#draft-form').requestSubmit()")
            session.wait("document.querySelectorAll('#snapshot-list .snapshot').length === 1",
                         "human-authored source-linked draft persisted")
            session.evaluate("[...document.querySelectorAll('#snapshot-list button')].find(button => button.textContent === 'Demo review acknowledgment').click()")
            session.wait("document.querySelector('#snapshot-list .pill').textContent === 'reviewed_in_demo'",
                         "explicit demonstration acknowledgment recorded")
            snapshot_id = state(url)["snapshots"][0]["id"]
            session.evaluate("[...document.querySelectorAll('#snapshot-list button')].find(button => button.textContent === 'Export with sources').click()")
            export_path = downloads / f"synthetic-investigation-{snapshot_id}.md"
            wait_for(lambda: export_path.exists() and ORIGINAL_QUOTE in export_path.read_text(),
                     "source-linked Markdown downloaded through existing export action")
            assert "reviewed_in_demo" in export_path.read_text()

            before_amendment = ledger(db)
            upload_preview(session, amended_path, AMENDED)
            assert ledger(db) == before_amendment, "Amendment preview changed existing review state"
            select_passage(session, AMENDED_QUOTE)
            confirm_metadata(session, amendment=True)
            submit_record(session, 2)
            session.wait("document.querySelector('#snapshot-list .pill-alert')?.textContent === 'stale'",
                         "amendment makes the earlier acknowledgment historical")
            after = state(url)
            current = next(source for source in after["sources"] if source["state"] == "current")
            assert current["version"] == 2 and current["sha256"] == receipt["amended_sha256"]
            assert after["snapshots"][0]["state"] == "stale"
            assert after["questions"][0]["state"] == "open"
            for source_id, raw in ((original_id, ORIGINAL), (current["id"], AMENDED)):
                with urlopen(url + f"api/cases/CASE-ALPHA/sources/{source_id}/download", timeout=5) as response:
                    assert response.read() == raw, "Amendment replaced a preserved original"
            timeline = "[...document.querySelectorAll('#timeline-events .timeline-entry')].find(entry => entry.querySelector('.timeline-doc')?.textContent === " + json.dumps(DOCUMENT_ID) + ")"
            session.wait(timeline + "?.textContent.includes('2 report versions')", "both original versions on the existing timeline")
            # #140-stack-only Composer amendment-refresh gate: skipped by design
            # on main, where #composer-context is absent. No Composer shim.
            if prior_context is None or session.evaluate("document.querySelector('#composer-context') === null"):
                receipt["composer_refresh_gate"] = COMPOSER_ABSENT_SKIP
            else:
                session.wait("document.querySelector('#composer-context-fingerprint').value !== " + json.dumps(prior_context) +
                             " && document.querySelector('#composer-context button[data-source-id=\"" + str(current["id"]) + "\"]') !== null",
                             "Composer refreshed to amended original source (#140-stack-only)")
                receipt["composer_refresh_gate"] = "checked (#140-stack-only)"
            screenshot(session, "document-intake-amendment.png", "#source-list")

            # Hold the real next-case state read to expose the transition gap.
            # Former-case saved actions must disappear before that read returns.
            session.evaluate("""(() => {
              const originalFetch = window.fetch;
              window.oiIntakeRestoreFetch = () => { window.fetch = originalFetch; };
              window.oiIntakeReleaseBeta = null;
              window.fetch = function(input, options) {
                const path = typeof input === 'string' ? input : input.url;
                if (path.endsWith('/api/cases/CASE-BETA/state'))
                  return new Promise((resolve, reject) => {
                    window.oiIntakeReleaseBeta = () => originalFetch.call(window, input, options).then(resolve, reject);
                  });
                return originalFetch.call(this, input, options);
              };
            })()""")
            switch_case(session, "CASE-BETA")
            session.wait("typeof window.oiIntakeReleaseBeta === 'function'", "next-case response held")
            assert session.evaluate("document.querySelector('#intake-success-actions').children.length === 0 && document.querySelector('#intake-review').hidden"), (
                "Old source actions remained active while another case loaded")
            session.evaluate("window.oiIntakeRestoreFetch(); window.oiIntakeReleaseBeta();")
            session.wait("document.querySelector('#case-heading').textContent === 'Fictional case Beta'",
                         "Beta load finishes after delayed state read")
            beta = state(url, "CASE-BETA")
            assert beta["sources"] == [] and beta["questions"] == [] and beta["snapshots"] == []
            assert not session.evaluate("document.querySelector('#source-list').textContent.includes(" + json.dumps(DOCUMENT_ID) + ")")
            assert session.evaluate("document.querySelector('#intake-original-lines').children.length === 0")
            receipt.update(status="passed", source_versions=2, question_count=1,
                           historical_snapshot_state="stale", original_download_exact=True,
                           mobile_width=390, case_transition_checked=True)
            print("PASS: real text-file upload, read-only preview, exact manual source selection, "
                  "safe original rendering/download, existing question/draft/export "
                  "(Composer gates #140-stack-only, skipped when #composer-context absent), "
                  "amendment staleness, original preservation, 390px intake layout, "
                  "accessible labels and delayed case-switch isolation")
        except BaseException as error:
            receipt.update(status="failed", failure=str(error))
            if session is not None:
                for width, height, name in (
                    (1440, 1000, "document-intake-failure-desktop.png"),
                    (390, 844, "document-intake-failure-mobile.png"),
                ):
                    try:
                        session.command("Emulation.setDeviceMetricsOverride", {
                            "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
                        })
                        screenshot(session, name)
                    except Exception as capture_error:
                        receipt.setdefault("screenshot_errors", []).append(str(capture_error))
            raise
        finally:
            (ARTIFACTS / "document-intake-receipt.json").write_text(json.dumps(receipt, indent=2))
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
