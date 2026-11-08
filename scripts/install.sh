#!/bin/sh
# Bootstrap without requiring Python on the desktop PATH.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=$(/bin/sh "$ROOT/scripts/python.sh")
exec "$PYTHON" -I "$ROOT/scripts/install.py" "$@"
