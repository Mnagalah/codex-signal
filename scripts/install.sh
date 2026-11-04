#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WITH_GNOME=0
if [[ "${1:-}" == --with-gnome ]]; then WITH_GNOME=1; shift; fi
[[ $# -eq 0 ]] || { echo 'Usage: ./scripts/install.sh [--with-gnome]' >&2; exit 2; }
command -v python3 >/dev/null || { echo 'Python 3.10+ is required. Ask Codex to help set up Python; see docs/INSTALL.md.' >&2; exit 1; }
python3 - "$ROOT" <<'PY'
import json,os,pathlib,platform,sys
if sys.version_info<(3,10):raise SystemExit('Python 3.10+ is required. No runtime will be installed automatically.')
r=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(r/'server'))
from localization import tomllib
s=json.loads((r/'platform.json').read_text())
if sys.platform=='darwin':
    assert s['os']=='macOS' and platform.machine()==s['architecture'],'Wrong platform package.'
    assert int(platform.mac_ver()[0].split('.')[0])>=14,'macOS 14+ required.'
    assert os.access(r/'bin/codex-menu-bar',os.X_OK),'Prebuilt renderer missing; use a release ZIP.'
elif sys.platform.startswith('linux'):assert s['os']=='Linux','Use the Ubuntu beta ZIP.'
else:raise SystemExit('Unsupported platform.')
p=pathlib.Path(os.environ.get('CODEX_HOME',str(pathlib.Path.home()/'.codex')))/'config.toml'
config=tomllib.loads(p.read_text()) if p.exists() else {}
legacy=config.get('plugins',{}).get('codex-menu-status@codex-menu-status-local',{})
if legacy.get('enabled') is True:raise SystemExit('The local development edition is enabled. See docs/INSTALL.md for plugin-only migration; this installer will not remove it or touch records.')
PY
if [[ "$(uname -s)" == Darwin ]]; then codesign --verify --strict "$ROOT/bin/codex-menu-bar"; fi
CLI="${CODEX_CLI:-}"
if [[ -z "$CLI" ]]; then
  for CANDIDATE in /Applications/Codex.app/Contents/Resources/codex /Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex; do
    if [[ -x "$CANDIDATE" ]]; then CLI="$CANDIDATE"; break; fi
  done
  if [[ -z "$CLI" ]]; then CLI="$(command -v codex || true)"; fi
fi
[[ -n "$CLI" && -x "$CLI" ]] || { echo 'Set CODEX_CLI to the Codex CLI executable bundled with your desktop app (or on PATH).' >&2; exit 1; }
if [[ "$WITH_GNOME" == 1 ]]; then "$ROOT/scripts/install-gnome.sh"; fi
"$CLI" plugin marketplace add "$ROOT" --json
"$CLI" plugin add codex-menu-status@codex-signal --json
printf '\nInstalled Codex Signal. Continue in a new chat turn, enable the plugin if required, then ask Codex Signal for status. No desktop restart or task command was sent.\n'
if [[ "$(uname -s)" == Linux && "$WITH_GNOME" == 0 ]]; then echo 'Ubuntu UI needs its explicit companion: ./scripts/install-gnome.sh'; fi
