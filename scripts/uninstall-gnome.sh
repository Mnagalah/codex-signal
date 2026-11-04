#!/bin/bash
# Explicit companion-only uninstall; move its files to recovery storage, keep data.
set -euo pipefail
[[ "$(uname -s)" == Linux && "${1:-}" == --confirm ]] || { echo 'Usage on Linux: ./scripts/uninstall-gnome.sh --confirm'; exit 2; }
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/codex-signal@local"
[[ -d "$DEST" && ! -L "$DEST" ]] || { echo 'No ordinary Codex Signal companion directory found.'; exit 1; }
python3 - "$DEST/metadata.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['uuid']=='codex-signal@local','Refusing unrelated extension'
PY
gnome-extensions disable codex-signal@local
BASE="${XDG_STATE_HOME:-$HOME/.local/state}/codex-signal/extension-backups";mkdir -p "$BASE"
BACKUP="$(mktemp -d "$BASE/removed.XXXXXX")";mv "$DEST" "$BACKUP/"
echo "Companion disabled and moved to $BACKUP. Chat IDs, records and plugin settings retained."
