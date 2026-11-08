#!/bin/sh
# Explicit opt-in only. No runtime installation occurs during an MCP launch.
set -eu
umask 077
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ACTION=${1:---plan}
case "$ACTION" in --plan|--download|--install) ;; *) echo 'Usage: install-python.sh [--plan|--download|--install]' >&2; exit 2 ;; esac
if [ "$ACTION" = --install ] && /bin/sh "$ROOT/scripts/python.sh" >/dev/null 2>&1; then
  echo 'Python is already configured; no installation was needed.'
  exit 0
fi
if [ "$(uname -s)" != Darwin ]; then
  echo 'Codex Signal supports macOS only.' >&2
  exit 78
fi
VERSION=3.14.10
URL="https://www.python.org/ftp/python/$VERSION/python-$VERSION-macos11.pkg"
if [ "$ACTION" = --plan ]; then
  printf '%s\n' "Python runtime required: official CPython $VERSION universal2." \
    "Source: $URL" 'With permission, run this script with --download. It verifies the Apple installer signature before any installation.'
  exit 0
fi
DIR=$(mktemp -d "${TMPDIR:-/tmp}/codex-signal-python.XXXXXX")
PKG="$DIR/python-$VERSION-macos11.pkg"
/usr/bin/curl --fail --location --proto '=https' --tlsv1.2 --output "$PKG" "$URL"
/usr/sbin/pkgutil --check-signature "$PKG" > "$DIR/signature.txt"
if ! /usr/bin/grep -F 'Developer ID Installer: Python Software Foundation' "$DIR/signature.txt" >/dev/null; then
  echo 'SIGNAL_PYTHON_SIGNATURE: Installer publisher did not match the Python Software Foundation.' >&2
  exit 1
fi
printf '%s\n' 'Verified official Python installer:' "$PKG"
if [ "$ACTION" = --download ]; then exit 0; fi
if [ "$(id -u)" != 0 ]; then
  printf '%s\n' 'SIGNAL_PYTHON_ADMIN_REQUIRED: Authorize the verified package through the system installer. Do not send a password in chat.' \
    "Approved-admin command: /usr/sbin/installer -pkg \"$PKG\" -target /" >&2
  exit 77
fi
/usr/sbin/installer -pkg "$PKG" -target /
echo 'Python installed. Rerun Signal setup as the original user to pin the interpreter and activate the plugin.'
