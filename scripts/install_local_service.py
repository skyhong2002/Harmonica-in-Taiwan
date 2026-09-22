#!/usr/bin/env python3
"""Install the current checkout's loopback web service as a macOS LaunchAgent."""
from __future__ import annotations
import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'tw.observe.harmonica.web'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--public-origin', default='https://harmonica.observe.tw')
    parser.add_argument('--port', type=int, default=8330)
    parser.add_argument('--install', action='store_true', help='Install and start; otherwise print the generated plist path')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    # Reuse serve.py validation before persisting configuration.
    from urllib.parse import urlsplit
    origin = urlsplit(args.public_origin)
    if origin.scheme != 'https' or not origin.hostname or origin.path or origin.query or origin.fragment or origin.username:
        parser.error('--public-origin must be an https origin without a path')
    python = ROOT / '.venv/bin/python'
    if not python.is_file():
        parser.error('Create .venv and install requirements.txt first')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    data = {
        'Label': LABEL,
        'ProgramArguments': [str(python), str(ROOT / 'scripts/serve.py'), '--host', '127.0.0.1', '--port', str(args.port)],
        'WorkingDirectory': str(ROOT),
        'EnvironmentVariables': {'HARMONICA_PUBLIC_ORIGIN': args.public_origin,
                                 'HARMONICA_TRUST_PROXY': '1', 'PYTHONUNBUFFERED': '1'},
        'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 5,
        'StandardOutPath': str(logs / 'web.log'), 'StandardErrorPath': str(logs / 'web.err.log'),
    }
    generated = ROOT / 'state' / (LABEL + '.plist')
    generated.parent.mkdir(exist_ok=True)
    generated.write_bytes(plistlib.dumps(data))
    if args.install:
        if sys.platform != 'darwin':
            parser.error('--install requires macOS; run serve.py directly or use systemd')
        destination = Path.home() / 'Library/LaunchAgents' / generated.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(generated.read_bytes())
        service = f'gui/{os.getuid()}/{LABEL}'
        subprocess.run(['launchctl', 'bootout', service], capture_output=True)
        subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(destination)], check=True)
        print(f'Installed {LABEL}: http://localhost:{args.port}')
    else:
        print(generated)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
