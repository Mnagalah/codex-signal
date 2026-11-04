# Package for Codex, not as a separate app

## Build the lightweight artifacts

Python is deliberately **not bundled**. Users or their Codex assistant prepare Python 3.10+ themselves. Tomli's pure-Python source/license is included for Python 3.10; newer Python uses its standard TOML parser. No Python package manager is needed at runtime.

```sh
# On the matching Mac build host:
./scripts/build-release.sh
python3 scripts/package.py --target macos
# Pure-source Linux beta, packageable on either platform:
python3 scripts/generate-linux.py
python3 scripts/package.py --target ubuntu22.04-beta
```

Outputs for 0.2.1:

- `dist/codex-signal-v0.2.1-macos-arm64.zip`: root plugin/marketplace manifests, backend, prebuilt native helper, source, docs, MIT and dependency notices.
- `dist/codex-signal-v0.2.1-ubuntu22.04-beta-noarch.zip`: Linux platform manifest, Python backend, socket bridge and GNOME 42 companion. **No Mach-O binary.** `noarch` describes the pure-source payload, not validated hardware coverage.
- `dist/codex-signal-v0.2.1-gnome42-companion-beta.zip`: the same companion alone, in GNOME's extension ZIP layout, for explicit manual installation.

No `.app`, DMG, systemd service, LaunchAgent or login item. Each main ZIP is an extracted-folder marketplace; its installer uses official Codex marketplace commands. Root `plugin.json` and `mcp.json` follow [OpenAI's packaging guide](https://developers.openai.com/plugins/build/plugins).

The packager uses an allowlist, rejects symlinks/private home paths/live-style IDs/runtime-data filenames, verifies version alignment and disables public diagnostic capture. Mac builds remap private source paths and strip debug info, then sign the helper locally. Inventories are saved beside each ZIP. Keep development evidence outside the public repository.

## Mac distribution trust is separate from Python setup

The current helper has an ad-hoc signature. No Developer ID identity was available on the build Mac, so notarization and a genuine quarantined-download test have **not** been completed. This does not prevent local development or the lightweight code/package handoff. It does prevent claiming a frictionless trusted download on every clean Mac.

Before promoting this candidate as a generally trusted Mac download, arrange Developer ID signing/notarization for the native helper and test the chosen archive/container through the actual browser-download route. Do not bundle credentials or remove quarantine automatically. Follow [Apple's notarization documentation](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution) for the chosen distribution container.

## GitHub release arrangement

Repository name: **`codex-signal`**. Display name: **Codex Signal**. License: **MIT**. Keep the stable internal plugin ID `codex-menu-status` and marketplace `codex-signal`.

Create a version/tag such as `v0.2.1` and attach the Mac candidate and the two clearly named **beta** Linux assets together. GitHub's release-level prerelease flag applies to the whole Release, not an individual attachment: while Mac clean-download trust is still unverified, start with a prerelease; once Mac is accepted, the Release can be normal and Linux remains explicitly beta by filenames and notes. [GitHub releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

For Git-backed installation, the release commit must contain the matching Mac helper. Ubuntu uses the separately generated platform ZIP. A Release attachment is not fetched by a local `source.path` entry automatically. No GitHub repository, tag, upload or public release has been created by the packaging scripts.

## Official directory is an additional route

GitHub distribution and the public OpenAI Plugin Directory are different. Current official local-MCP submission is limited to approved partner organizations with allowlisting, identity verification, package review and clean-desktop workflow testing. It cannot be promised simply by open-sourcing. [Desktop-only submission](https://developers.openai.com/plugins/deploy/desktop-only).
