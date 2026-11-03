"""Headless Chromium: persisted Composer work survives reload and source amendment."""
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from open_intelligence.__main__ import seed
from open_intelligence.store import CaseStore


def report(doc, date, value, amended=False):
    lines = [
        "OI-SYNTHETIC-REPORT/1","Patient: CASE-ALPHA",
        f"Document: {doc}","Type: laboratory",
        f"Event-Date: {date}",f"Issued-At: {date}",
        "Specimen: BLOOD-ALPHA"
    ]
    if amended:
        lines.append("Amends: LAB-A2@1")
    lines.append(f"Finding: hemoglobin|reported|OI-LAB-VALUE/1;value={value};unit=g/dL;qc=passed")
    return "\n".join(lines)+"\n"


def main():
    chrome=next((p for name in (
        "google-chrome","google-chrome-stable","chromium","chromium-browser"
    ) if (p:=shutil.which(name))),None)
    if not chrome:
        raise AssertionError("Chromium missing; cannot claim real browser verification")
    env=dict(os.environ,PYTHONPATH=str(ROOT/"src"))
    with tempfile.TemporaryDirectory(prefix="oi-durable-composer-") as directory:
        db=str(Path(directory)/"synthetic.sqlite")
        seed(db)
        store=CaseStore(db)
        try:
            store.import_report("CASE-ALPHA",report("LAB-A1","2026-05-01","10.2").encode())
            store.import_report("CASE-ALPHA",report("LAB-A2","2026-06-01","9.8").encode())
            store.add_question("CASE-ALPHA","Compute a source-bound numerical comparison")
        finally:
            store.close()
        app_port,debug_port=free_port(),free_port()
        server=subprocess.Popen([
            sys.executable,"-m","open_intelligence","serve",
            "--db",db,"--port",str(app_port)
        ],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
          start_new_session=True)
        browser,session=None,None
        try:
            url=f"http://127.0.0.1:{app_port}/"
            wait_for(lambda:urlopen(url,timeout=1).status==200,
                     "synthetic durable Composer server")
            browser=subprocess.Popen([
                chrome,"--headless=new","--disable-gpu","--disable-dev-shm-usage",
                "--disable-background-networking","--no-first-run","--disable-extensions",
                "--no-default-browser-check","--remote-allow-origins=*",
                f"--remote-debugging-port={debug_port}",
                f"--user-data-dir={directory}/chrome","about:blank"
            ],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            targets=wait_for(lambda:json.load(urlopen(
                f"http://127.0.0.1:{debug_port}/json/list",timeout=1)),
                "synthetic Chromium DevTools")
            pages=[x for x in targets if x.get("type")=="page"]
            if not pages:
                raise AssertionError("No Chromium page")
            session=ChromeSession(pages[0]["webSocketDebuggerUrl"])
            session.command("Page.enable")
            session.command("Runtime.enable")
            session.command("Page.navigate",{"url":url})
            session.wait(
                "document.querySelector('#case-heading')?.textContent === 'Fictional case Alpha'",
                "Alpha patient selected")
            session.wait(
                "document.querySelector('.composer-save-run')?.disabled === false && " +
                "document.querySelector('#composer-context-fingerprint')?.value.length===64",
                "version-bound saved work control")
            session.evaluate("document.querySelector('.composer-save-run').click()")
            session.wait(
                "document.querySelector('.composer-saved-runs')?.textContent.includes('Run #1') && " +
                "document.querySelector('.composer-saved-runs')?.textContent.includes('completed')",
                "durable numerical result")
            assert session.evaluate(
                "document.querySelector('.composer-saved-runs').textContent.includes('-0.4 g/dL')")
            session.command("Page.navigate",{"url":url})
            session.wait(
                "document.querySelector('.composer-saved-runs')?.textContent.includes('Run #1') && " +
                "document.querySelector('.composer-saved-runs')?.textContent.includes('completed')",
                "saved work survived reload")
            request=Request(
                url+"api/cases/CASE-ALPHA/imports",
                data=json.dumps({"text":report("LAB-A2","2026-06-01","8.5",amended=True)}).encode(),
                headers={"Content-Type":"application/json"})
            with urlopen(request,timeout=5) as response:
                assert response.status==200
            session.evaluate("document.dispatchEvent(new Event('oi:composer-refresh'))")
            session.wait(
                "document.querySelector('.composer-saved-runs')?.textContent.includes('Run #1') && " +
                "document.querySelector('.composer-saved-runs')?.textContent.includes('stale')",
                "historical work marked stale after amendment")
            session.evaluate("""(() => {
              const picker=document.querySelector('#case-picker');
              picker.value='CASE-BETA';picker.dispatchEvent(new Event('change'));
            })()""")
            session.wait(
                "document.querySelector('#case-heading')?.textContent === 'Fictional case Beta'",
                "unrelated case selected")
            assert not session.evaluate(
                "document.querySelector('#composer-context')?.textContent.includes('Run #1')")
            print("PASS: saved work, persisted result, reload, stale-source hold, patient isolation")
        finally:
            if session is not None:
                session.close()
            if browser is not None:
                try: os.killpg(browser.pid,signal.SIGTERM)
                except ProcessLookupError: pass
                try: browser.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try: os.killpg(browser.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                    browser.wait(timeout=5)
            try: os.killpg(server.pid,signal.SIGTERM)
            except ProcessLookupError: pass
            try: server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try: os.killpg(server.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                server.wait(timeout=5)


if __name__=="__main__":
    main()
