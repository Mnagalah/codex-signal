# macOS 0.2.9 release checks

- [x] Codex Signal, MIT, stable internal ID `codex-menu-status`; macOS-only source, documentation, CI and packaging.
- [x] Python detection/pinning and opt-in official runtime guidance; no resident setup skill.
- [x] 153 Python tests and 79 native tests passed; shared HTML/native grid is current. Native inputs are unchanged by the installer update.
- [x] Real isolated desktop CLI/App Server first-install flow: minimal PATH, removed download folder, discovered status tool, no skill installed. Stable managed source also passed an isolated version upgrade.
- [x] Existing local edition hot-loaded to 0.2.9 and live verification returned `ready`; user confirmed the plugin-list entry. IDs, numbering, settings and acknowledgements retained.
- [x] Final public allowlist/privacy scan and native architecture/ad-hoc signature checks passed; no private records or captures are included.
- [ ] Fresh Mac: install a genuinely missing Python runtime, verify browser-download trust and visible plugin/menu startup.
- [ ] Fresh Mac: normal/force-quit Codex reopen and state recovery.

Publication is authorized for a macOS prerelease so another Mac can run these remaining checks. Verify the public tag, README/install instructions and downloadable ZIP after upload. Keep automated, actual native visual and fresh-device evidence separate; the helper is not Developer ID notarized.
