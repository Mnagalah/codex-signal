# Install through Codex

When given https://github.com/Mnagalah/codex-signal to install, complete the steps below in the current Codex desktop profile. The result is a visible enabled plugin and a live menu bar. No permanent setup skill is needed.

## Get the prebuilt package

Use an Apple Silicon Mac with macOS 14+ and Codex desktop. For a fresh install, download the **0.2.9 release ZIP**, not GitHub's automatic source archive. It includes the native helper and needs neither Git nor Xcode. From a shell:

```sh
work=$(mktemp -d "${TMPDIR:-/tmp}/codex-signal.XXXXXX")
/usr/bin/curl --fail --location --proto '=https' --tlsv1.2 \
  'https://github.com/Mnagalah/codex-signal/releases/download/v0.2.9/codex-signal-v0.2.9-macos-arm64.zip' \
  --output "$work/codex-signal.zip"
/usr/bin/ditto -x -k "$work/codex-signal.zip" "$work/package"
cd "$work/package"
/bin/sh scripts/install.sh
```

Keep the current `CODEX_HOME` and any existing Signal marketplace identity. For an existing Git-managed edition, upgrade that original marketplace and run its matching installer instead of adding a second edition. Resolve a reported source conflict using the existing source or an explicitly approved plugin-only migration.

## Prepare Python only if missing

The bootstrap validates Python 3.10+ and its standard library, privately pins the real interpreter and checks the native package before registration. If it reports `SIGNAL_PYTHON_REQUIRED` or `SIGNAL_PYTHON_INVALID`, follow [Python preparation](PYTHON-SETUP.md), obtain permission for installation, then rerun `/bin/sh scripts/install.sh` from the extracted folder. Passwords belong in the system authorization UI. Tomli is included; no pip packages or global PATH edits are needed.

## Activate and verify the installed plugin

1. `installed-needs-activation` confirms registration only. Invoke this installed plugin's `get_status` tool so Codex starts its MCP service and native menu renderer. For an existing older Signal process, use its `control_monitor` reload action. If tools are not yet discovered in the current turn, continue in the next Codex turn and find Signal's status tool. Keep the service host-owned; a detached server, Codex restart or plugin-detail setup button is not part of this flow.
2. From the extracted folder, run `/bin/sh scripts/install.sh --verify`. Only `stage: ready` completes installation: the correct enabled version must be listed, and its live service must answer a fresh nonce with desktop connection and menu readiness. Resolve the returned failed stage before reporting completion. Confirm that the Codex plugin list shows **Codex Signal** and the menu bar shows its entry.
3. Report the installed version, `stage: ready` and actual visible result. If activation is still pending, report that stage and its next action instead of saying installation succeeded. Once ready, the downloaded folder can be removed: first installs keep their package in the profile's managed source.

## Keep existing records and tasks

Preserve the Mac data directory, chat IDs, numbering, acknowledgements, hidden markers and settings. Retain a saved paused preference and ask before enabling it. Never approve, start, stop, resume or mark a chat read as part of installation. Keep system trust protections enabled.

Version 0.2.9 is a prerelease for fresh-Mac installation testing. The helper is ad-hoc signed, not Developer ID notarized; browser-download trust, a genuinely missing Python runtime and full normal/force-quit Codex reopen need separate fresh-device acceptance. Report only redacted versions and reproduction steps, not private chats, local paths or raw records.
