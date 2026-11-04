#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/scripts/generate-layout.py"
swift build -c release --disable-sandbox --package-path "$ROOT/native" -Xswiftc -debug-prefix-map -Xswiftc "$ROOT=/src/codex-signal" -Xswiftc -file-prefix-map -Xswiftc "$ROOT=/src/codex-signal"
BIN="$(swift build -c release --disable-sandbox --package-path "$ROOT/native" --show-bin-path)"
mkdir -p "$ROOT/bin"
cp "$BIN/codex-menu-bar" "$ROOT/bin/codex-menu-bar"
# Remove debug info before producing a public candidate; preserve executable code.
strip -S "$ROOT/bin/codex-menu-bar"
# Local preview signing only. Public distribution needs the signing gate in docs/PACKAGING.md.
codesign --force --sign - "$ROOT/bin/codex-menu-bar"
python3 - "$ROOT/platform.json" <<'PY'
import json,pathlib,platform,sys
p=pathlib.Path(sys.argv[1]);s=json.loads(p.read_text());s['architecture']=platform.machine();p.write_text(json.dumps(s,indent=2)+'\n')
PY
