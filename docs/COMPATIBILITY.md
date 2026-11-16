# macOS compatibility

Codex Signal targets Apple Silicon Macs with macOS 14+ and Codex desktop. Python 3.10+ is required; Python is not bundled. Intel source builds are not a validated distribution target.

Version 0.2.14 supports desktop streams v11 and v13. Version 0.2.9 supports v11 only. Read v3, archive v2 and unarchive v1 are unchanged. Unrecognized stream versions report a protocol mismatch rather than guessing task status. The observer projects current local and desktop-connected remote chat metadata; it never starts/resumes tasks or scrapes transcripts.

Signal follows Codex’s recognized, unambiguous account/host unread metadata even for chats not yet in the stream. Remote unread badges require a connected host observed through Codex desktop. When no task snapshot is available, Signal shows **Unread**, not **Completed**; a remote chat title may remain unavailable until the desktop supplies it. When the production desktop index has a workspace for that exact host and chat, Signal can use it to show the existing remote project name before a snapshot arrives. Standalone sessions in other clients are outside this scope.

New connections receive current followed-chat replay and reacquire saved/recent identity hints. Missing snapshots retry without claiming completion or deletion. Full desktop quit/reopen and clean-download trust remain separate device acceptance items.

Archive/unarchive broadcasts are host-scoped. A read-only query of observed and explicitly unread local IDs in the same profile index reconciles confirmed lifecycle changes. An unavailable index or remote host is unknown, not deletion; an offline remote archive inventory is not exposed by this observer.

The helper is ad-hoc signed, not Developer ID notarized. Do not weaken macOS trust settings. A freshly installed Mac must verify the actual plugin page, Python startup and native menu before installation is considered complete.
