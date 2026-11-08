# Release and candidate checks

## Unreleased 0.2.10 candidate — publication on hold

- [x] 176 Python tests and 79 native tests passed; shared layout contract remains current. Native source and helper are unchanged from the audited build.
- [x] Existing plugin hot-loaded without restarting Codex; fresh installer verification confirmed the expected version, connection health and menu readiness.
- [x] Local and connected remote state recovered; chat identities, historical numbering, acknowledgements, retirement markers and settings were retained across hot replacement.
- [x] Actual capsules/popover inspected; plugin renderer automatically recovered after its own child exited, without replacing the backend or desktop host.
- [x] Public source/package allowlist and privacy checks passed. Private before/after snapshots, captures and logs stay outside the repository.
- [ ] Fresh-Mac installation and normal/force-quit Codex reopen acceptance.
- [ ] Explicit authorization to create a Release, tag or published installation asset. Source commits alone do not authorize publication.

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

Version 0.2.9 was published as a macOS prerelease for additional device testing. Its release notes and installation assets remain unchanged by the 0.2.10 candidate. Keep automated, actual native visual and fresh-device evidence separate; the helper is not Developer ID notarized.
