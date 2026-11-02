"""Real browser acceptance for fictional evidence permissions in Composer.

Uses the existing app, SQLite, loopback HTTP and recorded replay. No external
model or medical data is requested. The HTTP unit tests separately stub the
provider boundary to inspect the actual constructed prompt.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen

from browser_journey import ChromeSession, free_port, wait_for
from open_intelligence.__main__ import seed
from open_intelligence.store import CaseStore

ROOT = Path(__file__).resolve().parents[1]


def fictional_evidence(db):
    seed(db)
    store = CaseStore(db)
    try:
        question = store.add_question(
            "CASE-ALPHA", "Which independently fictional findings conflict?")
        store.add_question("CASE-BETA", "What is documented for fictional Beta?")
        allowed = {use: "allowed" for use in ("store", "display", "ml_use")}
        entries = []
        for key, relation, excerpt, permissions in (
            ("FICTIONAL-SUPPORT", "supports", "FICTIONAL SUPPORT PASSAGE",
             {"metadata": allowed, "full_text": allowed}),
            ("FICTIONAL-COUNTER", "contradicts", "FICTIONAL COUNTER PASSAGE",
             {"metadata": allowed, "full_text": allowed}),
            ("FICTIONAL-METADATA", "context", None, {"metadata": allowed}),
            ("FICTIONAL-DISPLAY", "context", "DISPLAY ONLY FICTIONAL PASSAGE",
             {"metadata": allowed, "full_text": {
                 "store": "allowed", "display": "allowed", "ml_use": "denied"}}),
        ):
            rights_id = store.register_rights_source(
                key, "Independent fictional author", "v1", "2026-11-02",
                permissions)["rights_source_id"]
            link_id = store.create_broker_link(
                "CASE-ALPHA", question, rights_id, relation, "limited",
                "Independently authored fictional review; clinical applicability is unproven.",
                citation_title="Fictional bibliography <img src=x onerror=alert(1)>",
                excerpt=excerpt)["broker_link_id"]
            entries.append((rights_id, link_id))
        return entries
    finally:
        store.close()


def main():
    chrome = next((path for name in (
        "google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
        if (path := shutil.which(name))), None)
    if chrome is None:
        raise AssertionError("No Chrome/Chromium executable; broker UI not verified")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    with tempfile.TemporaryDirectory(prefix="oi-broker-browser-") as directory:
        db = str(Path(directory) / "fictional-broker.sqlite")
        entries = fictional_evidence(db)
        app_port, debug_port = free_port(), free_port()
        server = subprocess.Popen(
            [sys.executable, "-m", "open_intelligence", "serve", "--db", db,
             "--port", str(app_port)], cwd=ROOT, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        browser, session = None, None
        try:
            url = f"http://127.0.0.1:{app_port}/"
            wait_for(lambda: urlopen(url, timeout=1).status == 200, "fictional broker server")
            browser = subprocess.Popen([
                chrome, "--headless=new", "--disable-gpu", "--disable-dev-shm-usage",
                "--disable-background-networking", "--no-first-run", "--disable-extensions",
                "--no-default-browser-check", "--remote-allow-origins=*",
                f"--remote-debugging-port={debug_port}",
                f"--user-data-dir={directory}/chrome", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            targets = wait_for(lambda: json.load(urlopen(
                f"http://127.0.0.1:{debug_port}/json/list", timeout=1)), "broker browser target")
            page = next(item for item in targets if item.get("type") == "page")
            session = ChromeSession(page["webSocketDebuggerUrl"])
            session.command("Page.enable")
            session.command("Runtime.enable")
            session.command("Page.navigate", {"url": url})
            session.wait(
                "document.querySelectorAll('.composer-evidence-item').length === 4 && "
                "!document.querySelector('#model-investigation-run').disabled",
                "per-question evidence preview")
            assert session.evaluate(
                "document.querySelector('.composer-external-evidence').textContent.includes('Relation: contradicts')")
            assert session.evaluate(
                "document.querySelectorAll('.composer-evidence-item[data-model-eligible=true]').length === 2")
            assert session.evaluate(
                "document.querySelectorAll('.composer-evidence-item[data-model-eligible=false]').length === 2")
            assert session.evaluate(
                "document.querySelector('.composer-external-evidence').textContent.includes('DISPLAY ONLY FICTIONAL PASSAGE')")
            assert session.evaluate(
                "document.querySelector('.composer-external-evidence img') === null"), "Source title became executable markup"
            assert session.evaluate(
                "document.querySelector('#model-investigation-mode').value === 'replay'")
            session.evaluate("document.querySelector('#model-investigation-form').requestSubmit()")
            session.wait(
                "document.querySelector('#model-investigation-list').textContent.includes('Recorded external inputs:')",
                "persisted replay and external input receipts")
            assert session.evaluate(
                "document.querySelector('#model-investigation-list').textContent.includes('Review: pending')")
            assert session.evaluate(
                "document.querySelectorAll('#model-investigation-list .model-claim').length > 0"), "Replay did not render its recorded claims"
            session.wait("!document.querySelector('#model-investigation-run').disabled", "refreshed preview")
            token = session.evaluate("document.querySelector('#composer-context-fingerprint').value")

            rights_id, link_id = entries[0]
            revoke = Request(url + f"api/rights/sources/{rights_id}/revoke",
                data=json.dumps({"reason": "Fictional author withdrew permission."}).encode(),
                headers={"Content-Type": "application/json"})
            with urlopen(revoke, timeout=5) as response:
                assert response.status == 200
            assert session.evaluate("document.querySelector('#composer-context-fingerprint').value") == token
            session.evaluate("document.querySelector('#model-investigation-form').requestSubmit()")
            session.wait(
                "document.querySelector('#notice').textContent.includes('stale Composer context')",
                "stale source permission denied")
            session.wait(
                "document.querySelector('#model-investigation-list').textContent.includes('Output withheld:')",
                "derived text withheld after revocation")
            session.wait(
                "/^[a-f0-9]{64}$/.test(document.querySelector('#composer-context-fingerprint').value) && "
                "!document.querySelector('#model-investigation-run').disabled && "
                "document.querySelectorAll('.composer-evidence-item').length === 4 && "
                "document.querySelector('#composer-context-fingerprint').value !== " + json.dumps(token),
                "new rights-qualified context")
            assert session.evaluate(
                "document.querySelectorAll('#model-investigation-list .snapshot').length === 1"), "Stale request saved a second output"
            assert session.evaluate(
                "document.querySelectorAll('#model-investigation-list .model-claim').length === 0"), "Revoked output remained visible"
            revoked_selector = json.dumps(f'.composer-evidence-item[data-broker-id="{link_id}"]')
            assert not session.evaluate(
                "document.querySelector(" + revoked_selector + ").textContent.includes('FICTIONAL SUPPORT PASSAGE')")
            assert session.evaluate(
                "document.querySelector(" + revoked_selector + ").dataset.modelEligible === 'false'")

            session.evaluate("""(() => {
                const picker = document.querySelector('#case-picker');
                picker.value = 'CASE-BETA';
                picker.dispatchEvent(new Event('change'));
            })()""")
            session.wait(
                "document.querySelector('#case-heading').textContent === 'Fictional case Beta' && "
                "!document.querySelector('#model-investigation-run').disabled", "Beta scoped preview")
            assert session.evaluate("document.querySelectorAll('.composer-evidence-item').length === 0")
            assert not session.evaluate(
                "document.querySelector('#composer-context').textContent.includes('FICTIONAL-COUNTER')")
            print("PASS: question-scoped support/counterevidence, metadata and display-only exclusion, "
                  "safe source text rendering, replay receipt persistence, stale permission denial, "
                  "derived-output withholding and patient isolation")
        finally:
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
