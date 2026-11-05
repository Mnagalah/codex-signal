# Install, update and keep records

## Choose the platform ZIP

Download the matching release attachment, not an arbitrary GitHub Source code archive. The Mac arm64 package includes its native helper; the Ubuntu beta includes Python/GJS source and a GNOME 42 companion. Python 3.10+ is a user-managed prerequisite. The pure-Python TOML dependency is included; no `pip install` is needed.

Extract into a dedicated folder you will keep. From that folder:

```sh
python3 --version
./scripts/install.sh                       # macOS Apple Silicon, macOS 14+
# OR, on Ubuntu GNOME 42:
./scripts/install.sh --with-gnome
```

If Python or Codex's CLI is missing, the installer stops and explains the requirement. Ask Codex to help install the prerequisite with your approval; it does not happen silently. `CODEX_CLI=/full/path/to/codex ./scripts/install.sh` selects an existing CLI explicitly. `python3` must also be visible to the desktop plugin's environment, not only to an interactive shell alias. If the desktop reports “python3 not found,” fix its PATH or use your own absolute Python command in the reviewed local `mcp.json` and reinstall that payload.

The script registers the extracted folder as marketplace `codex-signal`, then installs `codex-menu-status@codex-signal`. Enable **Codex Signal** if the host asks, continue with a new chat turn, and check `get_status`: `pluginVersion`, `connected` and `menuBarReady`. No Codex restart or task mutation is requested. Host versions may not immediately discover a first-time plugin; installation success alone is not proof of a loaded process.

Ubuntu requires the separately consented GNOME companion. You can instead install the plugin first and later run `./scripts/install-gnome.sh`. See [Ubuntu beta](UBUNTU-BETA.md) for session-registration limits and recovery. The companion ZIP is also provided for manual `gnome-extensions install`; do not install both copies separately.

For macOS downloaded-file trust failures, stop and report the error. The current helper is ad-hoc signed and not notarized; do not disable Gatekeeper or remove quarantine. [Distribution status](PACKAGING.md).

## Existing local development edition

`codex-menu-status@codex-menu-status-local` and `codex-menu-status@codex-signal` are different installations sharing the established Mac data store. Do not enable both. The installer refuses to replace an enabled development edition.

A migration needs explicit approval: save a private settings/slots backup, disable/remove **only** the old plugin through Codex, retain its data directory, install the new one, and compare original IDs/slot history/acknowledgements before enabling. Never restore an old snapshot over newer chat state. Preparing a package does not migrate a running installation.

## Updates without restarting Codex

Use Codex's marketplace upgrade/add commands to install the intended newer payload from the same source. A pinned Git tag does not advance automatically:

```sh
codex plugin marketplace upgrade codex-signal
codex plugin add codex-menu-status@codex-signal
```

Click Signal's refresh button to hot-load the **already installed** new backend/renderer while retaining its MCP transport and records. Verify the effective version and readiness. This does not restart Codex. The GNOME companion is a separate Shell component; update it explicitly with `install-gnome.sh`, which disables only Signal's extension and keeps a recovery copy. No Shell restart is automated.

Installed version directories are immutable: increment the plugin version before installing changed code. Refreshing an unchanged version reuses its factory. Hot reload transfers recently observed chat identities in memory, including read chats that have left the visible list; it does not scan or persist the account's history.

Maintainers keeping a separate local marketplace identity should generate it with `python3 scripts/stage-deployment.py --destination /path/to/deployment --marketplace sample-local-source`. This exports the same business code and version with only marketplace/diagnostic configuration differences. It does not install, restart anything, or touch user records. Do not enable a second marketplace edition over the existing data store.

After a repository exists, it may be registered with its **actual** URL and `--ref v0.2.7`. Do not run a placeholder repository URL. A Git marketplace release commit must include a platform-appropriate helper/manifest; Mac is the default root package. Ubuntu users should use the beta platform ZIP, whose `platform.json` is generated for Linux. Attaching a ZIP to GitHub does not make a plain Git marketplace entry download it automatically. [Official marketplace guide](https://developers.openai.com/plugins/build/plugins).

## Remove only Signal

```sh
codex plugin remove codex-menu-status@codex-signal
# Optional Linux companion removal, explicitly requested:
./scripts/uninstall-gnome.sh --confirm
```

The companion is moved to a recovery folder, not permanently deleted. Both routes leave user settings, chat IDs, slot history and local acknowledgements intact. To recover a previous payload, reinstall its matching platform package; do not reset the Codex account or erase chat history.
