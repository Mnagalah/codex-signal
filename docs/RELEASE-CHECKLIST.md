# Release checklist

## Settled decisions

- [x] Name **Codex Signal**, repository `codex-signal`, MIT; retain internal plugin ID `codex-menu-status`.
- [x] Lightweight Python 3.10+ prerequisite, user-managed. No bundled runtime or silent environment changes.
- [x] Mac asset and explicitly named Ubuntu/GNOME 42 **beta** assets may share a Release; Linux remains beta until native acceptance.
- [x] Initial public-repository publication authorized; packaging itself does not perform remote publication.

## Candidate evidence

- [x] Allowlist export, private path/live-ID checks, no local records/evidence or diagnostic capture enabled in assets.
- [x] English/Chinese READMEs, install/update/removal/recovery, AI install prompt, compatibility, MIT/Tomli notices.
- [x] Shared Python regression/platform/bridge tests and deterministic Linux model/UI harness run locally.
- [x] Optimized Mac arm64 helper built; native suite run locally. 100 Python tests, 74 native tests and 13 Linux synthetic checks passed for this candidate.
- [ ] Clean Mac download/quarantine trust check; current helper has only ad-hoc signing, not Developer ID notarization.
- [ ] Ubuntu 22.04 real GNOME installation, exact desktop protocol/read state, links, high-DPI/multi-screen, lock/exit/disable acceptance. Beta may be distributed **for these tests**, with gaps explicit.
- [ ] Linux peer credential path verified on Linux itself (Mac tests inject credentials and do not prove SO_PEERCRED behavior).
- [ ] Any migration of an existing development install has separate approval, private backup and before/after ID/slot/acknowledgement comparison. Preparing this candidate leaves it unchanged.

## Publishing and follow-up

- [ ] Create the chosen repository; publish only the reviewed tree, never workspace/user-data dumps. Preserve helper source and actual release binary for the default Mac Git marketplace.
- [ ] Tag the accepted candidate and attach platform assets; mark the whole release prerelease while Mac clean-download trust is not accepted. Clearly label Linux beta in filenames and notes even when Mac becomes normal/stable.
- [ ] Check README URLs, release download/install route and effective plugin version after publication. CI artifacts are not public Releases.
- [ ] Enable private vulnerability reporting where available. Review CI action versions/immutable pins before enabling public workflows.
- [ ] Official public directory: confirm local-MCP allowlisting and submission eligibility, then clean-desktop testing/review. GitHub publication does not imply directory approval.
