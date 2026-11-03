"""Additive entry host for the existing local source/investigation application.

Reuses Handler, CaseStore and the original page unchanged. The first-party entry
partial and scripts add UI onboarding only, with no new patient authority.
"""
from __future__ import annotations
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .__main__ import Handler, WEB


def workspace_html() -> str:
    """Compose trusted first-party assets; fail if the owner's anchors changed."""
    html=(WEB/'index.html').read_text(encoding='utf-8')
    edits={
        '<link rel="stylesheet" href="/style.css">': '<link rel="stylesheet" href="/style.css">\n  <link rel="stylesheet" href="/intake.css">\n  <link rel="stylesheet" href="/views.css">',
        '<script src="/app.js" defer></script>': '<script src="/intake.js" defer></script>\n  <script src="/app.js" defer></script>',
        '<script src="/literature.js" defer></script>': '<script src="/literature.js" defer></script>\n  <script src="/workspace-entry.js" defer></script>\n  <script src="/views.js" defer></script>',
        '<body>': '<body data-workspace-state="loading">',
        '<p class="muted tiny">Fictional case data stays': '<button class="button secondary" type="button" id="new-workspace-button">Create workspace</button>\n      <p class="muted tiny">Fictional case data stays',
        '<a href="#sources">Sources and findings</a>': '<a href="#source-intake">Add original records</a>\n          <a href="#sources">Sources and findings</a>',
        '      <div class="metrics" id="metrics" aria-live="polite"></div>': (WEB/'workspace-entry.html').read_text(encoding='utf-8')+'      <div class="metrics" id="metrics" aria-live="polite"></div>',
    }
    for old,new in edits.items():
        if html.count(old)!=1:
            raise ValueError('Workspace owner template changed; entry requires reconciliation.')
        html=html.replace(old,new,1)
    return html


def workspace_handler(db_path: str) -> type[Handler]:
    class WorkspaceHandler(Handler):
        def _static(self,name: str,mime: str) -> None:
            if name=='index.html':
                return self._send(200,workspace_html().encode('utf-8'),mime)
            return super()._static(name,mime)

        def do_GET(self) -> None:  # noqa: N802
            assets={'/intake.js':('intake.js','text/javascript; charset=utf-8'),
                    '/workspace-entry.js':('workspace-entry.js','text/javascript; charset=utf-8'),
                    '/intake.css':('intake.css','text/css; charset=utf-8'),
                    '/views.js':('views.js','text/javascript; charset=utf-8'),
                    '/views.css':('views.css','text/css; charset=utf-8')}
            path=urlsplit(self.path).path
            if path in assets:
                if not self._host_allowed():
                    return self._json(403,{'error':'Unexpected Host for loopback-only workspace'})
                return self._static(*assets[path])
            return super().do_GET()
    WorkspaceHandler.db_path=db_path
    WorkspaceHandler.allow_crossref_live=False
    WorkspaceHandler.allow_literature_live=False
    return WorkspaceHandler


def serve_workspace(db_path: str,port: int) -> None:
    # No public interface, real authentication, production data use or live
    # source permission is added by this loopback composition.
    server=ThreadingHTTPServer(('127.0.0.1',port),workspace_handler(db_path))
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
