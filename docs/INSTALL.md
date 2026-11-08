# Install and update Codex Signal

## Requirements

- Apple Silicon Mac running macOS 14 or later.
- Codex desktop.
- Python 3.10 or later with its standard library.

The prebuilt package includes the native menu bar component and TOML parsing support. The installer detects a compatible Python interpreter and records its absolute path. If Python is missing, follow [Python setup](PYTHON-SETUP.md).

The native component uses ad-hoc signing. See [Compatibility](COMPATIBILITY.md) for the current signing and platform status.

## Install

1. Download [codex-signal-v0.2.9-macos-arm64.zip](https://github.com/Mnagalah/codex-signal/releases/download/v0.2.9/codex-signal-v0.2.9-macos-arm64.zip) from the release assets.
2. Extract the package and open a terminal in its directory.
3. Run the installer:

```sh
/bin/sh scripts/install.sh
```

The result `installed-needs-activation` confirms that the expected plugin version has been registered in the selected desktop profile.

4. In the current Codex desktop, invoke the installed Codex Signal `get_status` tool. If the tool becomes available in the next conversation turn, continue there. For an older running Signal instance, use its `control_monitor` reload action after installing the update.
5. From the package directory, verify the running installation:

```sh
/bin/sh scripts/install.sh --verify
```

A successful check returns `stage: ready` with the expected version, desktop connection, and menu bar readiness. Also check the Codex Signal entry in the plugin list and the visible menu bar.

Fresh ZIP installations are copied into managed, versioned storage in the current desktop profile. Their original download folder can be removed after setup. Existing local-source and Git-managed installations retain their original source directories.

For installation through Codex, see [Install through Codex](INSTALL-WITH-CODEX.md).

## Select the desktop CLI

The installer first checks `CODEX_CLI`, then looks for the bundled CLI in its parent desktop application's directory. It also checks the standard Codex and ChatGPT application locations.

If the desktop application cannot be identified or several candidates are available, set `CODEX_CLI` to the executable bundled with the desktop you are using. For example:

```sh
CODEX_CLI="/Applications/Codex.app/Contents/Resources/codex" /bin/sh scripts/install.sh
```

Use the same desktop profile and CLI for installation and verification.

## Update

Use the existing Signal marketplace and desktop profile. Install the newer package, activate the installed tool, reload an older running instance if necessary, and run the new package's verification command.

A Git-managed installation should be updated through its original marketplace and matching checkout. If the installer reports another enabled edition or a different registered source, follow the returned `nextAction` to update that source or arrange a plugin-source migration.

Settings, conversation identifiers, and reminder records stay in the existing local data directory.

## Troubleshooting

Python bootstrap errors appear as `SIGNAL_PYTHON_*` messages. Other expected setup failures return JSON with a `stage` and `nextAction`.

| Result or stage | Action |
| --- | --- |
| `SIGNAL_PYTHON_REQUIRED` or `SIGNAL_PYTHON_INVALID` | Follow [Python setup](PYTHON-SETUP.md), then rerun the installer. |
| `desktop` | Set `CODEX_CLI` to the current desktop application's bundled executable. |
| `package` | Check the platform, complete release package, and native signature. |
| `identity` or `source` | Use the existing installation source or resolve the reported edition conflict. |
| `registration` | Check the selected profile, plugin version, enabled state, and CLI result. |
| `activation` | Invoke the installed `get_status` tool; reload an older instance if reported. |
| `interface` or `connection` | Resolve the reported menu bar or desktop connection issue, then verify again. |
| `paused` | Status updates are paused by a saved preference. Resume them if desired, then verify again. |

The verification timeout defaults to 15 seconds. It can be adjusted with `--timeout` when needed.

## Remove

Use the same bundled Codex CLI and desktop profile selected during installation. Replace this example with the actual executable path:

```sh
"/Applications/Codex.app/Contents/Resources/codex" plugin remove codex-menu-status@codex-signal
```

Local settings and records remain in `~/Library/Application Support/CodexMenuStatus/`.
