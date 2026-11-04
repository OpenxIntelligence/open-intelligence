"""Exercise actual loopback HTTP without an extra client dependency."""

import contextlib
import json
import socket
import threading
import time
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import uvicorn


@contextlib.contextmanager
def running_server(app):
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(
        app, log_config=None, access_log=False, lifespan="on", log_level="error",
    ))
    failures = []

    def run():
        try:
            server.run(sockets=[listener])
        except BaseException as exc:
            failures.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    try:
        while not server.started:
            if failures:
                raise failures[0]
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("Test HTTP server failed to start")
            time.sleep(0.01)
        yield f"http://127.0.0.1:{listener.getsockname()[1]}"
    finally:
        server.should_exit = True
        thread.join(5)
        listener.close()
        if thread.is_alive():
            raise RuntimeError("Test HTTP server failed to stop")


def get_json(base, path, headers=None):
    # Loopback must not be routed through the host's outbound proxy.
    opener = build_opener(ProxyHandler({}))
    try:
        response = opener.open(Request(base + path, headers=headers or {}), timeout=5)
    except HTTPError as exc:
        response = exc
    with response:
        return response.status, json.load(response), response.headers
