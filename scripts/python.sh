#!/bin/sh
# A Python-free runtime resolver. stdout is exactly one executable path.
set -eu
umask 077
if [ -n "${CODEX_MENU_STATUS_DATA:-}" ]; then
  CONFIG=$CODEX_MENU_STATUS_DATA
elif [ "$(uname -s)" = Darwin ]; then
  CONFIG="$HOME/Library/Application Support/CodexMenuStatus"
else
  echo "Codex Signal supports macOS only." >&2; exit 78
fi
PIN="$CONFIG/python-path"
check_python() {
  [ -n "$1" ] && [ -x "$1" ] || return 1
  # Apple's developer-tools stub can open an unrelated tools installer and is
  # below our minimum on supported baseline systems. Never launch that stub.
  case "$1" in /usr/bin/python3) return 1 ;; esac
  "$1" -I -c 'import sys,os,json,sqlite3,socket,threading
if sys.version_info < (3,10): raise SystemExit(1)
print(os.path.realpath(sys.executable))' 2>/dev/null
}
save_python() {
  case "$1" in /*) ;; *) return 1 ;; esac
  mkdir -p "$CONFIG"
  if [ ! -f "$PIN" ] || [ "$(cat "$PIN")" != "$1" ]; then
    tmp=$(mktemp "$CONFIG/.python-path.XXXXXX")
    printf '%s\n' "$1" > "$tmp"
    chmod 600 "$tmp"
    mv -f "$tmp" "$PIN"
  fi
  printf '%s\n' "$1"
}
try_python() {
  chosen=$(check_python "$1") || return 1
  save_python "$chosen"
}
if [ -n "${CODEX_SIGNAL_PYTHON:-}" ]; then
  if try_python "$CODEX_SIGNAL_PYTHON"; then exit 0; fi
  printf '%s\n' 'SIGNAL_PYTHON_INVALID: CODEX_SIGNAL_PYTHON must select Python 3.10+ with its standard library.' >&2
  exit 78
fi
if [ -f "$PIN" ]; then
  IFS= read -r previous < "$PIN" || previous=''
  if try_python "$previous"; then exit 0; fi
fi
candidate=$(command -v python3 2>/dev/null || true)
if try_python "$candidate"; then exit 0; fi
for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 \
  "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/python3" \
  "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/python3" \
  /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
  /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 /usr/bin/python3; do
  if try_python "$candidate"; then exit 0; fi
done
printf '%s\n' 'SIGNAL_PYTHON_REQUIRED: Python 3.10+ was not found. Run Codex Signal setup; it can prepare the official Python runtime with your permission. See docs/PYTHON-SETUP.md.' >&2
exit 78
