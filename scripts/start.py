#!/usr/bin/env python3
"""Launch the plugin with the user's Python. Never install prerequisites."""
import json,os,platform,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if sys.version_info < (3,10):raise SystemExit('Codex Signal requires Python 3.10+. See docs/INSTALL.md; no runtime is installed automatically.')
spec=json.loads((ROOT/'platform.json').read_text())
if sys.platform=='darwin':
    if spec['os']!='macOS':raise SystemExit('Download the macOS package, not the Ubuntu beta.')
    if platform.machine()!=spec['architecture']:raise SystemExit('Wrong Mac architecture. Download the matching release; Rosetta is not installed automatically.')
    if int(platform.mac_ver()[0].split('.')[0])<14:raise SystemExit('This build targets macOS 14 or newer.')
    if not (ROOT/'bin/codex-menu-bar').is_file():raise SystemExit('Missing renderer. Download a release package or run scripts/build-release.sh in a source checkout.')
elif sys.platform.startswith('linux'):
    if spec['os']!='Linux':raise SystemExit('Download the Ubuntu beta package, not the macOS package.')
else:raise SystemExit('Only macOS and the GNOME 42 Ubuntu beta are implemented.')
os.execv(sys.executable,[sys.executable,str(ROOT/'server/main.py'),*sys.argv[1:]])
