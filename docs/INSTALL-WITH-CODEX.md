# Install through Codex

Use this guide when asked to install https://github.com/Mnagalah/codex-signal.

## Package and environment

For a fresh installation, use the [v0.2.9 macOS arm64 release ZIP](https://github.com/Mnagalah/codex-signal/releases/download/v0.2.9/codex-signal-v0.2.9-macos-arm64.zip). It includes the native menu bar component. The target is an Apple Silicon Mac running macOS 14 or later with Codex desktop.

Use the current desktop profile. For an existing Git-managed installation, update its original marketplace and use the matching checkout. The [installation guide](INSTALL.md) covers source conflicts and CLI selection.

## Install and activate

1. Extract the release package and run `/bin/sh scripts/install.sh` from its directory.
2. If Python is missing or invalid, follow [Python setup](PYTHON-SETUP.md). Obtain the user's authorization for a runtime installation and complete any administrator authorization through the system installer. Then rerun Signal's installer as the original user.
3. When the result is `installed-needs-activation`, invoke the installed Signal `get_status` tool in Codex. Continue in a new turn if the current turn has not discovered the tool. Use `control_monitor` with the reload action for an older running Signal instance.
4. Run `/bin/sh scripts/install.sh --verify` from the matching package directory.
5. Check `stage: ready`, the installed version, the plugin-list entry, and the visible menu bar. If a check returns another stage, report that stage and follow its `nextAction`.

Retain the saved status-update preference and local records. A paused preference can be resumed when the user wants status updates enabled.

Fresh ZIP installations use managed source storage; their original download directory can be removed after successful setup. Existing local and Git-managed sources remain in use.

See [Compatibility](COMPATIBILITY.md) for signing details and device checks.
