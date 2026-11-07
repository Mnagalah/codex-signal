# Install and update Codex Signal on macOS

Use the macOS Apple Silicon package or the project repository. Keep the same desktop profile and marketplace identity. Python 3.10+ and macOS 14+ are required; the native helper is prebuilt.

Run the package installer and verify the actual installed/enabled plugin entry and live menu readiness. Preparing a folder or completing registration is not full first-setup acceptance. See [Codex installation](INSTALL-WITH-CODEX.md) and the repository README for the current flow.

Update only the same Signal edition. A separately named development marketplace is a different installation sharing the same data store: request explicit plugin-only migration before enabling another edition. Keep the data directory, historical slots, acknowledgements and preferences intact; never restore old state over newer chat activity.

Use the plugin's own reload action after a newer payload is installed. Installed versions remain immutable, and prior payloads may still be referenced by live host clients. Do not restart Codex or interrupt tasks merely to apply a plugin update.

Removal uses `codex plugin remove codex-menu-status@codex-signal` for that exact edition. It does not authorize deleting user records. The current helper is ad-hoc signed, not notarized; preserve macOS trust protections and report actual trust failures.
