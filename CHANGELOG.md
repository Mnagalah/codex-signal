# Changelog

## 0.2.7 — startup and reconnect recovery

- Revalidate saved and recently observed host/chat identities after a new observer session; receive the desktop's current local/remote followed-ID replay without scanning history or starting/resuming tasks.
- Handle client/owner connection changes and logical IPC resets. Invalidate lost-owner snapshots, reject their late frames, reannounce follows even when the old local subscription set says they exist, and reject callbacks from replaced sockets.
- Retry missing snapshots in coalesced batches with exponential backoff capped at 30 seconds. Time out missing initialization responses; keep transport connectivity distinct from syncing or unavailable task data. A timeout never means completed, read, archived or deleted.
- Retain up to 128 recent inactive identity/project hints in private `recovery.json`, in addition to protected visible records. Keep IDs, historical slots, preferences and acknowledgements intact; persist no turns, request payloads or owner truth in the hints.
- Treat the first recovered snapshot as a notification baseline, then alert on later real changes. Respect project/master pause and archived/deleted suppression. Mac/GNOME summaries display recovery health rather than an empty healthy list.
- Distributed as a prerelease with full Codex quit/reopen acceptance still pending. Observer-process startup and its own socket reconnect are independently testable without restarting the host.

## 0.2.6 — archive and deletion lifecycle

- Observe desktop archive v2/unarchive v1 events for local and remote host/chat pairs. Retire the visible entry and only Signal's own follower; late stream/read frames cannot resurrect an archived chat, including after a payload reload.
- Reconcile the same profile's local index in read-only mode, selecting only ID/archive status for already-known local chats. Remove legacy finished/deleted remnants and observe deletion of previously confirmed rows. Missing/locked/incompatible databases and remote IDs are not successful local deletion queries.
- Restore archived chats only from an explicit unarchive or affirmative local-index state, then require a fresh task snapshot. Preserve independent acknowledgements, other chat IDs/slots and project/master preferences. Retire pending alert/click state without inventing a task phase or writing Codex read receipts.
- Keep only a hidden lifecycle ID/reason and minimal archive project context in local state; deleted chat titles/turns are not retained in the hidden marker. The native renderer is unchanged.

## 0.2.5 — convergence fixes

- Rearm the current completed turn on an explicit unread edge, including an edge received before a fresh snapshot or while its project is paused. Keep stale-snapshot/new-turn protection and host separation.
- Hand recent observed identities and project context across payload reloads through the existing internal queue, without persisting a history inventory or replaying old turns.
- Expose adapter protocol/connection health separately from task phase; empty panels and status entries no longer turn a protocol failure into “No active chats”.
- Reuse same-version factories and release obsolete namespaces, including those created by older persistent hosts.
- Export local marketplace deployments from this single business source; generate backend copy from the shared HTML instead of parsing the demo at runtime. Separate native diagnostics from the production controller.
- Require Swift 6.2+ and select Xcode 26.2 explicitly for Mac CI; make animation tests independent of host accessibility settings and use the documented input-first `lipo -verify_arch` order. Share named-marker mappings across Mac/GNOME and ship the complete pinned Lucide SVG set with its license for the Ubuntu beta.

## 0.2.4 — hot-update ownership handoff

- A newly elected standby adopts the newest complete same-source payload before starting the renderer or publishing state. Keep the MCP queue and ownership lock across adoption; failed payloads retain the explicit fallback instead of retrying forever.

## 0.2.3 — remote unread reappearance

- Requery already-observed inactive chats when desktop read metadata changes. A remote finished chat marked unread can return without manual refresh, even when its owner emits no read broadcast. The existing viewed-chat removal path remains automatic.
- Keep reconciliation read-only, scoped to observed host/chat pairs, and respectful of paused projects; do not enumerate history or interpret opaque account buckets.

## 0.2.2 — read-state synchronization

- An explicit desktop read event immediately clears a known finished turn. A stale unread snapshot cannot restore that reminder; a later turn still notifies normally. Reads during running/unknown state do not acknowledge a future completion. Local and remote identities remain separate.

## 0.2.1 — cross-platform ordering and locale fixes

- Preserve rapid plugin command order even when the filesystem gives several request files the same timestamp; older requests remain readable.
- Detect same-length locale edits and atomic config replacements within one filesystem timestamp tick, without retaining other configuration values.
- Make control/deep-link tests independent of the developer machine locale and platform; add coarse-timestamp regressions.
- Retain IDs, historical numbering, acknowledgements and existing installation paths.

## 0.2.0 — distribution candidate and Ubuntu beta

- Adopted Codex Signal and MIT. Lightweight packages require user-managed Python 3.10+; no Python runtime bundled. Pure-Python Tomli is included for Python 3.10 without a pip step.
- Preserved the established Mac data location, internal plugin ID, historical slots and acknowledgements. Installation does not automatically migrate another marketplace edition.
- Added Linux XDG paths, an authenticated same-user private Unix bridge, and a GNOME Shell 42 companion: project capsules, rightmost status entry, compact hierarchy, per-project/master switches, settings, GTK emoji selection and clickable six-second notices.
- Generated GNOME metrics/copy/icons from the same HTML contract. Added interruptible animations and bounded socket/reconnect/disable cleanup.
- Added explicit companion installation/removal with recovery copies, prerequisite doctor, AI installation instructions and platform-specific allowlist packaging.
- Ubuntu is a code-complete testing candidate, not desktop-validated. Mac Developer ID/notarization and clean-download trust remain outstanding. Version 0.2.0 is a prerelease.

## 0.1.23

- Master resume/startup sync fresh snapshots before presenting task states; status entry remains neutral while syncing.
- Compact rapid reversals cancel stale removal callbacks and retain IDs/records.
- Retained rightmost global entry, popup spring transitions and selective clickable six-second alerts.
