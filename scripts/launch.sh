#!/bin/sh
# The host always has /bin/sh; Python discovery and pinning happen before MCP.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=$(/bin/sh "$ROOT/scripts/python.sh")
exec "$PYTHON" -I "$ROOT/scripts/start.py" "$@"
