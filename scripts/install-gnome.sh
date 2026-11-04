#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[[ "$(uname -s)" == Linux ]] || { echo 'GNOME companion is for Linux only.' >&2; exit 1; }
for TOOL in gnome-shell gnome-extensions glib-compile-schemas; do command -v "$TOOL" >/dev/null || { echo "Missing $TOOL. See docs/UBUNTU-BETA.md; nothing was installed." >&2; exit 1; }; done
[[ "$(gnome-shell --version)" == *' 42.'* ]] || { echo 'This beta targets GNOME Shell 42 only. Other versions need a port, not a forced enable.' >&2; exit 1; }
UUID=codex-signal@local
BASE="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions"
DEST="$BASE/$UUID"
mkdir -p "$BASE"
# Stage in the destination filesystem; compile before touching the installed copy.
STAGE="$(mktemp -d "$BASE/.codex-signal-stage.XXXXXX")"
trap 'if [[ -d "$STAGE" ]]; then python3 - "$STAGE" <<'"'"'PY'"'"'
import pathlib,shutil,sys
p=pathlib.Path(sys.argv[1])
if p.name.startswith(".codex-signal-stage."):shutil.rmtree(p)
PY
fi' EXIT
cp -R "$ROOT/linux/gnome/$UUID/." "$STAGE/"
glib-compile-schemas --strict "$STAGE/schemas"
if [[ -e "$DEST" || -L "$DEST" ]]; then
  [[ -d "$DEST" && ! -L "$DEST" ]] || { echo 'Refusing to replace a symlink or unrelated extension path.' >&2; exit 1; }
  python3 - "$DEST/metadata.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['uuid']=='codex-signal@local','Unrelated extension; stopping.'
PY
  gnome-extensions disable "$UUID" >/dev/null 2>&1 || true
  BACKUP="${XDG_STATE_HOME:-$HOME/.local/state}/codex-signal/extension-backups"
  mkdir -p "$BACKUP"
  mv "$DEST" "$(mktemp -d "$BACKUP/update.XXXXXX")/$UUID"
fi
mv "$STAGE" "$DEST"
if gnome-extensions enable "$UUID"; then echo 'GNOME companion enabled. Existing chats and plugin data were not changed.'
else echo 'Companion installed but this GNOME session has not registered it. Log out/in when convenient, then run: gnome-extensions enable codex-signal@local. This script will NOT restart Shell or Codex.' >&2; fi
