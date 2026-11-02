#!/usr/bin/env python3
"""Start the connected local Open Intelligence workspace without installing packages.

Original fictional data only. No accounts, PHI authorization or clinical release.
Live scientific/model services are not enabled by this launcher.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--db',type=Path,default=ROOT/'.local'/'workspace.sqlite')
    parser.add_argument('--with-examples',action='store_true',help='Explicitly import the existing original fictional Alpha/Beta examples')
    args=parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Choose an unprivileged port from 1024 to 65535.')
    if sys.version_info < (3,10):
        parser.error('Python 3.10 or newer is required.')
    for key in list(os.environ):
        if key.startswith(('META_API_', 'OPENAI_API_', 'ANTHROPIC_API_')):
            os.environ.pop(key)
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
