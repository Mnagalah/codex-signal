# macOS compatibility

Codex Signal targets Apple Silicon Macs with macOS 14+ and Codex desktop. Python 3.10+ is required; Python is not bundled. Intel source builds are not a validated distribution target.

The version-bound desktop observer supports stream v11/read v3/archive v2/unarchive v1. It projects current local and desktop-connected remote chat metadata; independent CLI/IDE processes and other machines are outside scope. It never starts/resumes tasks or scrapes transcripts.

New connections receive current followed-chat replay and reacquire saved/recent identity hints. Missing snapshots retry without claiming completion or deletion. Full desktop quit/reopen and clean-download trust remain separate device acceptance items.

Archive/unarchive broadcasts are host-scoped. A read-only query of already-known local IDs in the same profile index reconciles confirmed lifecycle changes. An unavailable index or remote host is unknown, not deletion; an offline remote archive inventory is not exposed by this observer.

The helper is ad-hoc signed, not Developer ID notarized. Do not weaken macOS trust settings. A freshly installed Mac must verify the actual plugin page, Python startup and native menu before installation is considered complete.
