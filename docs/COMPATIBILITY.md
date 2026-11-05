# Compatibility

| Target | Implemented | Evidence / gap |
| --- | --- | --- |
| macOS Apple Silicon | Native renderer + shared backend | 0.2.7 backend/native automated suites, rebuilt signed helper and live local/remote observer recovery; full host quit/reopen and clean-download trust remain unverified |
| macOS 14+ | Deployment target | Not a claim that every older OS build was exercised |
| Intel Mac | Source can be built separately | No Intel asset or runtime acceptance in this release |
| Ubuntu 22.04, GNOME Shell 42 | Complete Python bridge + GJS top-panel/popup/settings/notice companion | Beta code and synthetic tests; native GNOME, desktop IPC/read state and installation need tester validation |
| GNOME 43+ / KDE / other desktops | Not ported | Do not edit metadata to force-enable the GNOME 42 extension |
| Independent CLI / IDE / other machines | Outside current scope | Only remote chats connected through this desktop runtime are included |

Python 3.10+ is required and not bundled. Both platform launchers fail clearly on a mismatched package. The Linux pure-source payload is architecture-independent; x86_64/aarch64 support is not claimed as device-tested.

The shared adapter targets desktop **stream v11/read v3/archive v2/unarchive v1**. Linux reuses that explicit version-bound observer, not a guaranteed public cross-platform API. Its default Codex home/file/socket locations can be overridden explicitly; an incompatible build displays a connection/protocol error. It never starts/resumes chats or scrapes whole session logs to fabricate status. [Beta setup and acceptance](UBUNTU-BETA.md).

## Archive/delete availability

Both local and remote archive/unarchive broadcasts are host-scoped. The current desktop delete UI acts on archived chats, so their already-retired Signal entries remain hidden when permanently deleted. The observer does not expose an independent permanent-delete broadcast or an authoritative archive inventory for an offline remote host. Remote lifecycle changes missed while disconnected cannot be inferred from silence or from a missing local database row; a retained unknown entry needs a fresh desktop lifecycle signal. No history scan or remote task operation is used as a substitute.

For local native chats, a read-only query of already-known IDs in the same profile's `state_5.sqlite` reconciles archives, restored rows and deletions of previously confirmed persisted rows. It also retires pre-upgrade finished local records whose persisted index row is gone. A missing, locked or incompatible database leaves availability unknown; new unsaved active chats are not removed. `CODEX_SIGNAL_STATE_DB` can explicitly select this index; by default it is beside `CODEX_SIGNAL_DESKTOP_STATE` in the current Codex profile.

## Startup and reconnect freshness

On a new observer connection the matching desktop router tells existing clients that a client connected. Native stream coordinators replay the host-scoped chats they currently follow to that client; Signal follows those IDs for fresh snapshots. This includes remote owners connected through the same desktop. It is current runtime presence, not an all-history list and not a guarantee that an offline remote host has an owner available.

Signal also rechecks visible saved IDs and up to 128 recent inactive identity/project hints across process exits. Historical slots, acknowledgements and visible identities are not evicted by that hint limit. A new session or lost owner invalidates old runtime truth; first recovered snapshots establish a notification baseline. Missing snapshots retry with bounded batches/backoff rather than silently replaying old colors. Five-second handoff timeout exposes unknown/unavailable, not task completion or deletion. A successful IPC handshake alone is not data-ready.

The plugin remains a host-launched stdio MCP component, not a separate Login Item or daemon. Automatic activation by the desktop after a full quit/reopen and the exact remote build's presence replay need real host acceptance. Current local observer startup/reconnect evidence does not substitute for that test; 0.2.7 is a prerelease with that acceptance still pending.

The current official Linux desktop preview lists Ubuntu **24.04/26.04**, not 22.04. The beta targets a user's already-working 22.04 desktop build; it does not supply or upgrade that app. [Official Linux support](https://learn.chatgpt.com/docs/linux/linux-app).
