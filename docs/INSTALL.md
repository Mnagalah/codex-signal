# Install and update Codex Signal on macOS

For a first installation, use the [0.2.9 prebuilt macOS ZIP](https://github.com/Mnagalah/codex-signal/releases/download/v0.2.9/codex-signal-v0.2.9-macos-arm64.zip). Download and extract with the built-in macOS tools shown in [Install through Codex](INSTALL-WITH-CODEX.md); Git and Xcode are not installation prerequisites. Existing Git-managed editions retain their original source. Keep the same desktop profile and marketplace identity. Python 3.10+ and macOS 14+ are required; the native helper is prebuilt.

Run `/bin/sh scripts/install.sh` and follow the installation instructions. The bootstrap discovers and privately pins a compatible interpreter. Local/downloaded packages are copied into an immutable managed source before registration, so removing the download folder cannot remove the marketplace; existing Git-managed sources retain their upgrade tracking.

The installer returns `installed-needs-activation` until the host starts the service. Run `/bin/sh scripts/install.sh --verify` after invoking the plugin's get_status tool. Only `stage: ready` is full completion: the correct profile must list the enabled version and the live service must answer a new nonce with connected/renderer readiness. Missing Python follows [runtime preparation](PYTHON-SETUP.md), with authorization for installation.

Verify the actual installed/enabled plugin entry and live menu readiness. Preparing a folder or completing registration is not full first-setup acceptance. See [Codex installation](INSTALL-WITH-CODEX.md) and the repository README for the current flow.

Update only the same Signal edition. A separately named development marketplace is a different installation sharing the same data store: request explicit plugin-only migration before enabling another edition. Keep the data directory, historical slots, acknowledgements and preferences intact; never restore old state over newer chat activity.

Use the plugin's own reload action after a newer payload is installed. Installed versions remain immutable, and prior payloads may still be referenced by live host clients. Do not restart Codex or interrupt tasks merely to apply a plugin update.

Removal uses `codex plugin remove codex-menu-status@codex-signal` for that exact edition. It does not authorize deleting user records. The current helper is ad-hoc signed, not notarized; preserve macOS trust protections and report actual trust failures.
