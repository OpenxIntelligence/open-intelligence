#!/usr/bin/env python3
"""Start the connected local Open Intelligence workspace without installing packages.

Original fictional data only. No accounts, PHI authorization or clinical release.
Live scientific/model services are not enabled by this launcher unless the
operator passes --enable-meta-live (Meta Model API investigations only).
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent


def clear_model_credentials(environ, allow_meta_live: bool = False) -> None:
    """Remove inherited model-API credentials. With allow_meta_live, keep only
    META_API_KEY (the documented Meta Model API investigation key)."""
    for key in list(environ):
        if allow_meta_live and key == 'META_API_KEY':
            continue
        if key.startswith(('META_API_', 'OPENAI_API_', 'ANTHROPIC_API_')):
            environ.pop(key)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--db',type=Path,default=ROOT/'.local'/'workspace.sqlite')
    parser.add_argument('--with-examples',action='store_true',help='Explicitly import the existing original fictional Alpha/Beta examples')
    parser.add_argument('--enable-meta-live',action='store_true',
                        help='Keep the operator META_API_KEY so Live investigations call the Meta Model API (fictional data only); off by default')
    args=parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Choose an unprivileged port from 1024 to 65535.')
    if sys.version_info < (3,11):
        parser.error('Python 3.11 or newer is required.')
    clear_model_credentials(os.environ, args.enable_meta_live)
    if args.enable_meta_live:
        print('Meta Model API live investigations:', 'ENABLED (explicit)' if os.environ.get('META_API_KEY')
              else 'requested, but META_API_KEY is not set; Live runs will report it', flush=True)
    else:
        print('Meta Model API live investigations: DISABLED (default; Replay only)', flush=True)
    sys.path.insert(0,str(ROOT/'src'))
    from open_intelligence.__main__ import seed
    from open_intelligence.workspace_host import serve_workspace
    if args.with_examples:
        seed(str(args.db))
    print(f'Open Intelligence: http://127.0.0.1:{args.port}',flush=True)
    print('Use Create workspace, then import an authored fictional .txt report. No real patient records.',flush=True)
    serve_workspace(str(args.db),args.port)
    return 0
if __name__=='__main__': raise SystemExit(main())
