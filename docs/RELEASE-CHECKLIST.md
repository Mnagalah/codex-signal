# Release and candidate checks

## 0.2.14 release checks

- [x] 192 Python tests passed. The AppKit helper is the one verified with the 81 native tests in the 0.2.13 candidate.
- [x] Compared the new resolver with Codex desktop’s current listing on an observed remote host. It matched 13 assigned chats and left four genuinely unassigned chats in Chat. Seven project assignments were missing in the previous resolver without a live snapshot.
- [x] Hot-loaded 0.2.14 without restarting Codex. The live installer receipt confirmed readiness, and a remote unread chat with an explicit assignment appeared in the matching native project item. Existing slots, settings and recovery hints were retained.
- [x] On the existing Mac, marking a remote chat unread without opening it or refreshing Signal showed its unread badge in the expected native project capsule. The chat had no explicit assignment; the desktop index supplied the matching workspace.
- [ ] Fresh Mac: verify clean-download trust, first installation and normal/force-quit desktop recovery.

## Prior 0.2.13 candidate checks

- [x] 190 Python tests and 81 native tests passed. Coverage includes unread membership for never-followed chats, read-before-file-flush ordering, stale owner snapshots, host isolation, retirement, pause and payload recovery. Native tests cover bilingual unread labels and the expanded-menu overflow route.
- [x] 0.2.12 hot-loaded on the existing Mac without restarting Codex. The installed plugin reported ready and projected all six unread badges from an observed remote host; no task owner supplied their snapshots. Two previously running chats retained their identities and slots, and all 23 prior recovery hints and settings were retained.
- [x] 0.2.13 hot-loaded and the installer verified the expected desktop session and ready menu. The actual strip rendered six unread badges, and the main popover exposed a running chat whose project item AppKit reported fully occluded. Existing tracked sessions, slots and settings were retained.
- [x] User confirmed that marking two local chats unread adds both without refreshing, and opening one clears only its badge.

## Prior 0.2.11 candidate checks

- [x] 180 Python tests passed. Stream v11/v13 snapshots, contiguous patches and read synchronization are covered for both local and remote hosts, including host isolation and refresh after desktop read-metadata changes. Unsupported stream versions are still rejected.
- [x] Verified against ChatGPT desktop build 27194: live v13 deltas applied for both host types; a remote terminal chat's unread flag cleared in a refreshed snapshot. Local read/unread passed fixture replay; no matching local terminal read transition was captured live.
- [x] Existing Signal installation updated without restarting the desktop. Fresh installer verification returned ready; actual menu items and the status panel rendered. Existing chat identities, historical numbering, recovery keys and settings were retained.
- [ ] Fresh-Mac installation and full Codex quit/reopen acceptance.

## Prior 0.2.10 candidate checks

- [x] 176 Python tests and 79 native tests passed; shared layout contract remains current. Native source and helper are unchanged from the audited build.
- [x] Existing plugin hot-loaded without restarting Codex; fresh installer verification confirmed the expected version, connection health and menu readiness.
- [x] Local and connected remote state recovered; chat identities, historical numbering, acknowledgements, retirement markers and settings were retained across hot replacement.
- [x] Actual capsules/popover inspected; plugin renderer automatically recovered after its own child exited, without replacing the backend or desktop host.
- [x] Public source/package allowlist and privacy checks passed. Private before/after snapshots, captures and logs stay outside the repository.
- [ ] Fresh-Mac installation and normal/force-quit Codex reopen acceptance.

See [State machines and recovery contracts](STATE-MACHINES.md) for the transition tables, issue groups and regression references.

## Published 0.2.9

- [x] Codex Signal, MIT, stable internal ID `codex-menu-status`; macOS-only source, documentation, CI and packaging.
- [x] Python detection/pinning and opt-in official runtime guidance; no resident setup skill.
- [x] 153 Python tests and 79 native tests passed; shared HTML/native grid is current. Native inputs are unchanged by the installer update.
- [x] Real isolated desktop CLI/App Server first-install flow: minimal PATH, removed download folder, discovered status tool, no skill installed. Stable managed source also passed an isolated version upgrade.
- [x] Existing local edition hot-loaded to 0.2.9 and live verification returned `ready`; user confirmed the plugin-list entry. IDs, numbering, settings and acknowledgements retained.
- [x] Final public allowlist/privacy scan and native architecture/ad-hoc signature checks passed; no private records or captures are included.
- [ ] Fresh Mac: install a genuinely missing Python runtime, verify browser-download trust and visible plugin/menu startup.
- [ ] Fresh Mac: normal/force-quit Codex reopen and state recovery.

Version 0.2.9 was published as a macOS prerelease for additional device testing. Its release notes and installation assets remain unchanged. Keep automated, actual native visual and fresh-device evidence separate; the helper is not Developer ID notarized.
