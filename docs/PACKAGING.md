# Package Codex Signal for macOS

The product is a Codex desktop plugin with a prebuilt native menu helper, not a separate app, DMG, Login Item or background service. Python 3.10+ is user-managed and not bundled; Tomli's pure-Python source/license is included.

Build with Swift 6.2+ on the matching Mac:

```sh
./scripts/build-release.sh
python3 scripts/package.py --target macos
```

Output: `dist/codex-signal-v<version>-macos-<architecture>.zip`, using the version in `plugin.json` and the build architecture. The allowlist includes manifests, backend, native helper/source, shared HTML, docs, tests and licenses. Private records, probes, runtime hints and captures are excluded. Version consistency, archive inventory and native signature are checked; private build paths are remapped and debug data stripped.

Current signing is ad-hoc, not Developer ID notarized. Clean-download trust requires actual acceptance before claiming a frictionless trusted download. Preserve Gatekeeper/quarantine and follow Apple's notarization guidance if arranging public signing.

Use the repository `codex-signal`, stable internal plugin name `codex-menu-status` and existing marketplace identity. Publication is a separate explicit action; packaging never commits, tags or uploads. Preserve prior macOS releases and Git history when narrowing current distribution scope.
