#!/usr/bin/env python3
"""Export one canonical source to an existing marketplace identity. Never install."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from package import ROOT, inventory


def stage(destination, marketplace, *, capture=False):
    destination = Path(destination).resolve()
    if destination == ROOT or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', marketplace):
        raise ValueError('Choose a separate deployment folder and a valid marketplace name')
    manifest = destination / 'plugin.json'
    if manifest.exists() and json.loads(manifest.read_text()).get('name') != 'codex-menu-status':
        raise ValueError('Destination belongs to another plugin')
    platform = json.loads((ROOT / 'platform.json').read_text())
    files = inventory('macos' if platform['os'] == 'macOS' else 'linux')
    for source in files:
        target = destination / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    market_path = destination / '.agents/plugins/marketplace.json'
    market = json.loads(market_path.read_text())
    market['name'] = marketplace
    market_path.write_text(json.dumps(market, indent=2) + '\n')
    mcp_path = destination / 'mcp.json'
    mcp = json.loads(mcp_path.read_text())
    if capture:
        mcp['mcpServers']['menu_status'].setdefault('env', {})['CODEX_MENU_STATUS_CAPTURE'] = '1'
    mcp_path.write_text(json.dumps(mcp, indent=2) + '\n')
    record = {'generated': True, 'sourceRoot': str(ROOT), 'marketplace': marketplace,
              'version': json.loads(manifest.read_text())['version'], 'diagnosticCapture': capture,
              'instruction': 'Edit business code at sourceRoot and rerun stage-deployment.py; do not maintain a deployment fork.'}
    (destination / 'DEPLOYMENT.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--marketplace', required=True)
    parser.add_argument('--capture', action='store_true', help='Explicit development-only renderer diagnostics')
    args = parser.parse_args()
    print(json.dumps(stage(args.destination, args.marketplace, capture=args.capture), indent=2))
