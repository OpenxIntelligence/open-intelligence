"""Real Chromium journey for the synthetic report/follow-through connection.

Uses the existing standard-library CDP harness. No browser package is added to
the application. Set OI_BROWSER_BINARY to an already installed Chrome executable
when it is not on PATH. Only independently authored local synthetic records are
used; the browser and application communicate over loopback.
"""

from __future__ import annotations

import base64
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

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "verification-artifacts"
TASK_TITLE = "Prepare questions for the next visit"
OWNER = "Fictional coordinator"
TRIGGER = "When the revised pathology report arrives"

# Capture actual server responses, and hold/fail selected report reads to
# exercise asynchronous UI correctness. Normal record mutations remain real.
REPORT_PROBE = r"""
(() => {
  const originalFetch = window.fetch.bind(window);
  window.__oiReportProbe = {latest: {}, responses: [], holdCase: null, held: null,
                            failCase: null, released: false, printCalls: 0,
                            holdEvidenceWrite: false, heldEvidenceWrite: null};
  window.fetch = async (...args) => {
    const target = String(args[0]);
    const probe = window.__oiReportProbe;
    if (target === '/api/evidence/imports' && args[1]?.method === 'POST' &&
        probe.holdEvidenceWrite) {
      probe.holdEvidenceWrite = false;
      await new Promise(resolve => { probe.heldEvidenceWrite = {release: resolve}; });
      return new Response(JSON.stringify({error: 'Injected evidence write rejection'}), {
        status: 503, headers: {'Content-Type': 'application/json'},
      });
    }
    const match = target.match(/^\/api\/cases\/([^/]+)\/patient-report$/);
    if (!match) return originalFetch(...args);
    const caseId = decodeURIComponent(match[1]);
    if (probe.failCase === caseId) {
      probe.failCase = null;
      return new Response(JSON.stringify({error: 'Injected report retrieval failure'}), {
        status: 503, headers: {'Content-Type': 'application/json'},
      });
    }
    const response = await originalFetch(...args);
    const payload = await response.clone().json();
    if (probe.holdCase === caseId && !probe.held) {
      probe.holdCase = null;
      await new Promise(resolve => { probe.held = {caseId, release: resolve}; });
      probe.released = true;
    }
    probe.latest[caseId] = payload;
    probe.responses.push({caseId, payload});
    return response;
  };
  window.print = () => {
    const probe = window.__oiReportProbe;
    probe.printCalls += 1;
    const display = selector => getComputedStyle(document.querySelector(selector)).display;
    probe.printSnapshot = {
      report: display('#patient-report'),
      overview: display('#overview'),
      tasks: display('#followthrough'),
      rail: display('.rail'),
      reportOnly: document.body.classList.contains('printing-patient-report'),
    };
  };
})();
"""


def report_ready(session: ChromeSession, case_id: str, text: str | None = None):
    expected = json.dumps(case_id)
    session.wait(
        f"document.querySelector('#patient-report').dataset.caseId === {expected} && "
        "!document.querySelector('#report-print').disabled && "
        "document.querySelector('#report-text-link').getAttribute('href')?.startsWith('blob:')",
        f"accepted {case_id} report",
    )
    if text:
        session.wait(
            "document.querySelector('[data-section-id=followthrough]')?.textContent.includes("
            + json.dumps(text) + ")",
            f"report contains {text}",
        )


def report_blocked(session: ChromeSession):
    assert session.evaluate("document.querySelector('#report-print').disabled"), (
        "print remained available without a current accepted report"
    )
    assert session.evaluate(
        "document.querySelector('#report-text-link').getAttribute('aria-disabled') === 'true'"
    ), "download did not announce its disabled state"
    assert not session.evaluate(
        "document.querySelector('#report-text-link').getAttribute('href')"
    ), "a stale download URL remained available"
    assert not session.evaluate(
        "document.querySelector('#report-sections').textContent.includes('Prepare questions for the next visit')"
    ), "the previous task remained visible while the report was unavailable"


def task_transition(session: ChromeSession, status: str, reason: str, owner: str = ""):
    session.evaluate("""(() => {
      document.querySelector('#ft-status').value = %s;
      document.querySelector('#ft-owner').value = %s;
      document.querySelector('#ft-update-actor').value = 'Fictional recorder';
      document.querySelector('#ft-update-reason').value = %s;
      document.querySelector('#followthrough-update-form').requestSubmit();
    })()""" % (json.dumps(status), json.dumps(owner), json.dumps(reason)))


def download_report(session: ChromeSession, directory: Path, case_id: str) -> str:
    report_ready(session, case_id)
    expected = session.evaluate(
        "fetch(document.querySelector('#report-text-link').href).then(r => r.text())"
    )
    assert isinstance(expected, str) and expected, "accepted response omitted report text"
    # Identify the exact received payload behind the bound Blob. A stale
    # response may arrive last; arrival order is not an acceptance signal.
    assert session.evaluate("""(() => {
      const response = window.__oiReportProbe.responses.find(item =>
        item.caseId === %s && item.payload.text === %s);
      if (!response) return false;
      return response.payload.sections.every(section => {
        const block = [...document.querySelectorAll('.report-section')]
          .find(element => element.dataset.sectionId === section.id);
        return block && block.textContent.includes(section.summary) &&
          section.items.every(item => [item.text, item.detail, item.citation]
            .every(value => block.textContent.includes(value)));
      });
    })()""" % (json.dumps(case_id), json.dumps(expected))), (
        "download Blob and displayed sections do not correspond to one server report snapshot"
    )
    filename = session.evaluate("document.querySelector('#report-text-link').download")
    assert filename.startswith(case_id) and Path(filename).name == filename
    target = directory / filename
    target.unlink(missing_ok=True)
    session.evaluate("document.querySelector('#report-text-link').click()")
    wait_for(lambda: target.exists() and target.stat().st_size > 0, "actual report download")
    downloaded = target.read_text()
    assert downloaded == expected, "download did not match the accepted displayed report snapshot"
    return downloaded


def main() -> None:
    chrome = os.environ.get("OI_BROWSER_BINARY") or next((
        path for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
        if (path := shutil.which(name))
    ), None)
    if not chrome or not Path(chrome).is_file():
        raise AssertionError("No Chrome/Chromium executable; report/follow-through UI NOT verified")
    version = subprocess.check_output([chrome, "--version"], text=True).strip()
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    ARTIFACTS.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="oi-report-followthrough-") as temporary:
        directory = Path(temporary)
        downloads = directory / "downloads"
        downloads.mkdir()
        db = str(directory / "case.sqlite")
        subprocess.run(
            [sys.executable, "-m", "open_intelligence", "seed", "--db", db],
            cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL,
        )
        app_port, debug_port = free_port(), free_port()
        server = subprocess.Popen(
            [sys.executable, "-m", "open_intelligence", "serve", "--db", db, "--port", str(app_port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        browser = None
        session = None
        try:
            url = f"http://127.0.0.1:{app_port}/"
            wait_for(lambda: urlopen(url, timeout=1).status == 200, "local synthetic server")
            flags = [
                chrome, "--headless=new", "--disable-gpu", "--disable-dev-shm-usage",
                "--disable-background-networking", "--no-first-run", "--disable-extensions",
                "--no-default-browser-check", "--remote-allow-origins=*",
                f"--remote-debugging-port={debug_port}", f"--user-data-dir={directory}/chrome",
            ]
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                flags.append("--no-sandbox")
            browser = subprocess.Popen(
                flags + ["about:blank"], stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True,
            )
            targets = wait_for(
                lambda: json.load(urlopen(f"http://127.0.0.1:{debug_port}/json/list", timeout=1)),
                "Chrome DevTools target",
            )
            page = next((item for item in targets if item.get("type") == "page"), None)
            assert page is not None, "Chrome did not expose a page target"
            session = ChromeSession(page["webSocketDebuggerUrl"])
            session.command("Page.enable")
            session.command("Runtime.enable")
            session.command("Browser.setDownloadBehavior", {
                "behavior": "allow", "downloadPath": str(downloads),
            })
            session.command("Emulation.setDeviceMetricsOverride", {
                "width": 1440, "height": 1080, "deviceScaleFactor": 1, "mobile": False,
            })
            session.command("Page.addScriptToEvaluateOnNewDocument", {"source": REPORT_PROBE})
            session.command("Page.navigate", {"url": url})
            session.wait(
                "document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'",
                "Alpha workspace",
            )
            report_ready(session, "CASE-ALPHA")

            session.evaluate("""(() => {
              document.querySelector('#question-text').value =
                'What changed in the fictional pathology report?';
              document.querySelector('#question-form').requestSubmit();
            })()""")
            session.wait("document.querySelector('#ft-question').options.length === 2", "linked question")
            source_id = session.evaluate("""[...document.querySelector('#ft-source').options]
              .find(option => option.textContent.startsWith('PATH-ALPHA@1')).value""")
            assert source_id, "original pathology source was not selectable"
            session.evaluate("""(() => {
              document.querySelector('#ft-title').value = %s;
              document.querySelector('#ft-detail').value =
                'Bring the earlier pathology report and note what changed.';
              document.querySelector('#ft-due').value = '2026-01-01';
              document.querySelector('#ft-trigger').value = %s;
              document.querySelector('#ft-question').selectedIndex = 1;
              document.querySelector('#ft-source').value = %s;
              document.querySelector('#ft-actor').value = 'Fictional caregiver';
              document.querySelector('#ft-reason').value =
                'Prepare the next fictional consultation.';
              document.querySelector('#followthrough-form').requestSubmit();
            })()""" % (json.dumps(TASK_TITLE), json.dumps(TRIGGER), json.dumps(source_id)))
            session.wait("document.querySelector('#ft-open').textContent.includes('Prepare questions for the next visit')",
                         "persisted task in workspace")
            report_ready(session, "CASE-ALPHA", TASK_TITLE)
            created = download_report(session, downloads, "CASE-ALPHA")
            assert "PATH-ALPHA@1" in created and TRIGGER in created
            assert "Fictional caregiver" in created and "2026-01-01" in created
            assert "created" in created.lower()

            task_transition(session, "assigned", "Coordinator agreed to gather the records.", OWNER)
            session.wait("document.querySelector('#ft-open').textContent.includes('assigned')", "task assignment")
            report_ready(session, "CASE-ALPHA", OWNER)
            task_transition(session, "completed", "Trying completion before acknowledgment.")
            session.wait(
                "document.querySelector('#notice').textContent.includes('completion requires a recorded acknowledgment')",
                "premature completion rejected",
            )
            current = session.evaluate("fetch('/api/cases/CASE-ALPHA/state').then(r => r.json())")
            task = current["followthrough"]["tasks"][0]
            assert task["status"] == "assigned" and len(task["history"]) == 2

            task_transition(session, "acknowledged", "Coordinator recorded seeing this request.")
            session.wait("document.querySelector('#ft-open').textContent.includes('acknowledged')", "acknowledgment")
            report_ready(session, "CASE-ALPHA", "acknowledged")
            acknowledged = download_report(session, downloads, "CASE-ALPHA")
            assert "Coordinator recorded seeing this request." in acknowledged
            source = next(item for item in current["sources"] if str(item["id"]) == source_id)
            assert source["sha256"] in acknowledged, "report lost original source hash"

            session.evaluate("document.querySelector('#example-button').click()")
            session.wait("document.querySelector('#report-text').value.includes('Amends: PATH-ALPHA@1')",
                         "synthetic amendment loaded")
            session.evaluate("document.querySelector('#import-form').requestSubmit()")
            session.wait("document.querySelector('#ft-open').textContent.includes('linked source amended')",
                         "task source amendment flag")
            report_ready(session, "CASE-ALPHA", "superseded")
            amended = download_report(session, downloads, "CASE-ALPHA")
            assert "PATH-ALPHA@1" in amended and "PATH-ALPHA@2" in amended
            assert source["sha256"] in amended, "amendment overwrote the task's source provenance"
            assert "recheck" in amended.lower() or "another look" in amended.lower()
            assert "Coordinator agreed to gather the records." in amended
            assert session.evaluate(
                "Boolean(window.__oiReportProbe.latest['CASE-ALPHA'].as_of.due_evaluated_on)"
            ), "due-date evaluation day was omitted"

            section = session.evaluate("""(() => {
              const block = document.querySelector('[data-section-id=followthrough]');
              block.scrollIntoView({block: 'start'});
              const r = block.getBoundingClientRect();
              return {x: r.x + scrollX, y: r.y + scrollY, width: r.width, height: r.height, scale: 1};
            })()""")
            png = session.command("Page.captureScreenshot", {
                "format": "png", "clip": section, "captureBeyondViewport": True,
            })["data"]
            (ARTIFACTS / "patient-report-followthrough.png").write_bytes(base64.b64decode(png))

            session.command("Emulation.setEmulatedMedia", {"media": "print"})
            session.evaluate("document.querySelector('#report-print').click()")
            printed = session.evaluate("window.__oiReportProbe.printSnapshot")
            assert printed["reportOnly"] and printed["report"] != "none"
            assert printed["overview"] == printed["tasks"] == printed["rail"] == "none", (
                "Print this report included the surrounding workspace"
            )
            assert not session.evaluate("document.body.classList.contains('printing-patient-report')")
            session.evaluate("document.body.classList.add('printing-patient-report')")
            pdf = session.command("Page.printToPDF", {"printBackground": True, "preferCSSPageSize": True})
            (ARTIFACTS / "patient-report-followthrough.pdf").write_bytes(base64.b64decode(pdf["data"]))
            session.evaluate("document.body.classList.remove('printing-patient-report')")
            session.command("Emulation.setEmulatedMedia", {"media": "screen"})

            task_transition(session, "completed", "Fictional questions prepared for discussion.")
            session.wait("document.querySelector('#ft-completed').textContent.includes('Prepare questions for the next visit')",
                         "completed task retained")
            report_ready(session, "CASE-ALPHA", "completed")
            completed = download_report(session, downloads, "CASE-ALPHA")
            assert "Fictional questions prepared for discussion." in completed
            assert source["sha256"] in completed and "superseded" in completed
            current = session.evaluate("fetch('/api/cases/CASE-ALPHA/state').then(r => r.json())")
            task = current["followthrough"]["tasks"][0]
            assert task["status"] == "completed" and task["human_action_recorded"]
            assert not task["needs_recheck"] and not task["is_overdue"]
            assert [event["new_status"] for event in task["history"]] == [
                "created", "assigned", "acknowledged", "completed",
            ]

            # A slow prior-case response must not restore its content/actions.
            session.evaluate("""(() => {
              window.__oiReportProbe.holdCase = 'CASE-ALPHA';
              document.dispatchEvent(new CustomEvent('oi:case-state-updated', {detail: {caseId: 'CASE-ALPHA'}}));
            })()""")
            session.wait("Boolean(window.__oiReportProbe.held)", "held Alpha report response")
            report_blocked(session)
            session.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-BETA'; picker.dispatchEvent(new Event('change'));
            })()""")
            report_ready(session, "CASE-BETA")
            beta = download_report(session, downloads, "CASE-BETA")
            assert TASK_TITLE not in beta and OWNER not in beta and "PATH-ALPHA" not in beta
            session.evaluate("window.__oiReportProbe.held.release()")
            session.wait("window.__oiReportProbe.released", "delayed Alpha response released")
            session.evaluate("new Promise(resolve => setTimeout(resolve, 0))")
            report_ready(session, "CASE-BETA")
            assert not session.evaluate(
                "document.querySelector('#report-sections').textContent.includes('PATH-ALPHA')"
            ), "delayed Alpha response leaked into Beta"

            # Failed current-case refresh removes content and export capability.
            session.evaluate("""(() => {
              window.__oiReportProbe.failCase = 'CASE-BETA';
              document.dispatchEvent(new CustomEvent('oi:case-state-updated', {detail: {caseId: 'CASE-BETA'}}));
            })()""")
            session.wait("document.querySelector('#report-meta').textContent.includes('unavailable')",
                         "report refresh failure")
            report_blocked(session)
            before = session.evaluate("window.__oiReportProbe.printCalls")
            session.evaluate("document.querySelector('#report-print').click()")
            assert session.evaluate("window.__oiReportProbe.printCalls") == before
            session.evaluate("document.dispatchEvent(new CustomEvent('oi:case-state-updated', {detail: {caseId: 'CASE-BETA'}}))")
            report_ready(session, "CASE-BETA")
            assert download_report(session, downloads, "CASE-BETA") == beta

            # Exercise the actual global-write host path, not dispatched test
            # events: the form calls api('/api/evidence/imports', ...). A held
            # rejected response keeps every case report unavailable until the
            # attempted write settles, without changing the synthetic ledger.
            evidence = (ROOT / "examples/synthetic/demo-evidence.txt").read_text()
            previous_reads = session.evaluate("window.__oiReportProbe.responses.length")
            session.evaluate("""(() => {
              window.__oiReportProbe.holdEvidenceWrite = true;
              document.querySelector('#evidence-text').value = %s;
              document.querySelector('#evidence-import-form').requestSubmit();
            })()""" % json.dumps(evidence))
            session.wait("Boolean(window.__oiReportProbe.heldEvidenceWrite)", "pending global evidence write")
            report_blocked(session)
            assert session.evaluate("document.querySelector('#report-refresh').disabled"), (
                "manual refresh remained available during a pending global write"
            )
            session.evaluate("""(() => {
              const picker = document.querySelector('#case-picker');
              picker.value = 'CASE-ALPHA'; picker.dispatchEvent(new Event('change'));
            })()""")
            session.wait("document.querySelector('#case-heading').textContent === 'Fictional case Alpha'",
                         "case switch during pending global evidence write")
            report_blocked(session)
            assert session.evaluate("document.querySelector('#report-refresh').disabled")
            session.evaluate("document.querySelector('#report-refresh').click()")
            session.evaluate("new Promise(resolve => setTimeout(resolve, 0))")
            assert session.evaluate("window.__oiReportProbe.responses.length") == previous_reads, (
                "a report read bypassed the pending global write guard"
            )
            session.evaluate("window.__oiReportProbe.heldEvidenceWrite.release()")
            session.wait("document.querySelector('#notice').textContent.includes('Injected evidence write rejection')",
                         "rejected global write settled")
            session.wait("!document.querySelector('#report-refresh').disabled", "manual retry enabled after settlement")
            report_blocked(session)
            assert session.evaluate("window.__oiReportProbe.responses.length") == previous_reads
            session.evaluate("document.querySelector('#report-refresh').click()")
            report_ready(session, "CASE-ALPHA", TASK_TITLE)
            assert download_report(session, downloads, "CASE-ALPHA") == completed
            print(f"PASS: report/follow-through browser journey ({version}); actual downloads, scoped print, source amendment, history, stale/failed reads, and global-write blocking verified")
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
                    try:
                        os.killpg(browser.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    browser.wait(timeout=5)
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__ == "__main__":
    main()
