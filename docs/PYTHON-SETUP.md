# Prepare Python once, then finish Signal setup

Signal needs Python 3.10+ with its standard library. Tomli is already included; no pip packages, Xcode or virtual environment are needed for the prebuilt Mac plugin. The MCP entry uses `/bin/sh` and resolves a private absolute interpreter pin, so it does not depend on Finder and the terminal having the same PATH.

## Reuse an installed interpreter

Run `/bin/sh scripts/python.sh`. It validates the existing pin, the current PATH, common Homebrew/Python.framework locations and an existing Codex runtime if present. It saves the validated real executable in the plugin's private `python-path` file. A removed interpreter is repaired using another compatible installed interpreter; an explicit `CODEX_SIGNAL_PYTHON` selection must itself validate.

To choose a known interpreter, run `CODEX_SIGNAL_PYTHON=/absolute/path/to/python3 /bin/sh scripts/install.sh`. No global PATH/config change is needed. Do not choose Apple's Python 3.9 or its developer-tools stub.

## Install only when no compatible runtime exists

Ask for permission to prepare Python. On Mac, `/bin/sh scripts/install-python.sh --plan` identifies a pinned official Python.org universal2 installer. With permission, `--download` fetches it over verified HTTPS and checks the Apple installer signature and Python Software Foundation publisher. No downloaded installer is executed by the MCP launcher.

Authorize the verified package through the macOS system installer or an approved administrative command. The script's `--install` supports an already-authorized administrator environment; otherwise it reports the required operation and stops. Credentials belong in the system's authorization UI, never in a Codex message. Do not disable Gatekeeper, strip quarantine or install Homebrew solely to obtain Python.

After installation, rerun Signal setup as the original user. It discovers and pins the runtime before registration/activation. The installer does not claim completion until the live verification passes.


Official Mac installer source: https://www.python.org/downloads/macos/
