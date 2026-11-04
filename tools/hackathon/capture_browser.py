"""Capture the real synthetic H1 browser journey without changing application code.

Isolated video-production wrapper. Reuses the existing browser/API/PG acceptance
journey, starts capture only after synthetic patient access, pauses at existing
screenshot checkpoints, and stops before browser teardown. No provider keys.
"""
from __future__ import annotations
import base64
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "verification-web" / "video"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "tests"))
from browser_journey import ChromeSession as OriginalSession

FPS = 8
recorder = None
events = []
sessions = []

class Recorder:
    def __init__(self, url):
        self.url = url
        self.frames = 0
        self.failures = []
        self.ended = threading.Event()
        self.started_at = time.monotonic()
        self.log = (OUT / "ffmpeg.txt").open("wb")
        self.process = subprocess.Popen([
            "ffmpeg", "-hide_banner", "-loglevel", "warning", "-y",
            "-f", "image2pipe", "-vcodec", "mjpeg", "-framerate", str(FPS),
            "-i", "-", "-an", "-vf",
            "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0xeff4f1,setsar=1",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(OUT / "actual-platform-raw.mp4")
        ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self.log)
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        camera = None
        try:
            camera = OriginalSession(self.url)
            camera.command("Page.enable")
            while not self.ended.is_set():
                tick = time.monotonic()
                # Never record a credential-entry page. Only this local test app.
                safe = camera.evaluate(
                    "location.origin==='http://127.0.0.1:4173' && "
                    "!document.querySelector('#credential')"
                )
                if safe:
                    data = camera.command("Page.captureScreenshot", {
                        "format": "jpeg", "quality": 88,
                        "captureBeyondViewport": False
                    })
                    self.process.stdin.write(base64.b64decode(data["data"]))
                    self.frames += 1
                self.ended.wait(max(0, 1 / FPS - (time.monotonic() - tick)))
        except Exception as error:
            if not self.ended.is_set():
                self.failures.append(type(error).__name__)
        finally:
            if camera:
                camera.close()

    def stop(self):
        self.ended.set()
        self.thread.join(timeout=15)
        if self.thread.is_alive():
            raise RuntimeError("Capture thread did not stop")
        self.process.stdin.close()
        result = self.process.wait(timeout=60)
        self.log.close()
        (OUT / "capture.json").write_text(json.dumps({
            "source_commit": os.environ.get("GITHUB_SHA"),
            "base_application_commit": "02f920c40959d26937df0f737e17e5392d041d26",
            "fps": FPS, "frames": self.frames,
            "video_seconds": self.frames / FPS,
            "wall_seconds": time.monotonic() - self.started_at,
            "events": events, "capture_errors": self.failures,
            "data": "independently fictional acceptance fixtures",
            "model_execution": False,
            "note": "Actual browser capture; timing is sampled and edited, not a performance benchmark."
        }, indent=2))
        if result or self.failures or self.frames < FPS * 10:
            raise RuntimeError("Capture failed or was too short")

class CapturedSession(OriginalSession):
    def __init__(self, url):
        super().__init__(url)
        self.capture_url = url
        sessions.append(self)

    def wait(self, expression, label):
        global recorder
        result = super().wait(expression, label)
        if label == "seeded patient" and recorder is None:
            OriginalSession.command(self, "Emulation.setDeviceMetricsOverride", {
                "width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False
            })
            recorder = Recorder(self.capture_url)
        stages = {
            "seeded patient": (None, 8),
            "seeded exact original": ("[data-testid=server-original]", 10),
            "question editor": ("[data-testid=question-draft]", 5),
            "persisted question": ("[data-testid=saved-source-question]", 10),
            "evidence import": ("[data-testid=evidence-file]", 4),
            "preserved report": ("[data-testid=evidence-report-body]", 12),
            "recorded follow-up": ("[data-testid=followthrough-task]", 12),
        }
        if recorder and not recorder.ended.is_set() and label in stages:
            selector, seconds = stages[label]
            if selector:
                OriginalSession.command(self, "Runtime.evaluate", {
                    "expression": "document.querySelector(" + json.dumps(selector) + ").scrollIntoView({block:'center'})"
                })
            image = OriginalSession.command(self, "Page.captureScreenshot", {"format":"png"})
            raw = base64.b64decode(image["data"])
            filename = label.replace(" ", "-") + ".png"
            (OUT / filename).write_bytes(raw)
            event = {"label": label, "at": recorder.frames / FPS,
                     "sha256": hashlib.sha256(raw).hexdigest(), "file": filename}
            events.append(event)
            time.sleep(seconds)
            event["end"] = recorder.frames / FPS
            if label == "recorded follow-up":
                recorder.stop()
        return result

    def command(self, method, params=None):
        result = super().command(method, params)
        if recorder and not recorder.ended.is_set() and method == "Runtime.evaluate":
            expression = (params or {}).get("expression", "")
            if ".click()" in expression or "dispatchEvent" in expression:
                time.sleep(0.4)
        if recorder and not recorder.ended.is_set() and method == "Page.captureScreenshot":
            frame = inspect.currentframe().f_back
            event = {
                "at": recorder.frames / FPS,
                "frame": recorder.frames,
                "caller": str(Path(frame.f_code.co_filename).relative_to(ROOT)),
                "line": frame.f_lineno,
                "sha256": hashlib.sha256(base64.b64decode(result["data"])).hexdigest()
            }
            events.append(event)
            # A production hold at existing, already selected screenshot points.
            # No DOM manipulation, invented output, or application write.
            time.sleep(4)
            event["end"] = recorder.frames / FPS
        return result

def main():
    source = ROOT / "apps/web/tools/demo_journey.py"
    sys.path.insert(0, str(source.parent))
    spec = importlib.util.spec_from_file_location("oi_h1_recorded_journey", source)
    journey = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(journey)
    journey.ChromeSession = CapturedSession
    # Stop before browser shutdown; the acceptance journey otherwise stays intact.
    original_close = CapturedSession.close
    def close(self):
        global recorder
        if recorder and not recorder.ended.is_set():
            recorder.stop()
        original_close(self)
    CapturedSession.close = close
    journey.main()
    if recorder is None:
        raise RuntimeError("Patient access was never established; no recording created")
    print("CAPTURE COMPLETE: actual React/FastAPI/PostgreSQL browser journey, synthetic only.")

if __name__ == "__main__":
    main()
