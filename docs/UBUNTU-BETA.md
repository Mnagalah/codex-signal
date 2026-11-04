# Ubuntu 22.04 · GNOME 42 beta

The beta includes the complete source path: desktop observer → metadata/state backend → private Unix bridge → GNOME top-panel capsules, popup, settings, emoji chooser and six-second alerts. It has **not** been run on an Ubuntu desktop in this development environment. Use this document for tester acceptance, not as evidence that Linux integration already passed.

## Prerequisites

- Ubuntu 22.04 with **GNOME Shell 42**. KDE and newer GNOME APIs are not implemented.
- Python **3.10+** visible as `python3` to Codex's local executor. Ubuntu 22.04's normal Python 3.10 is sufficient; Tomli is supplied as source, no pip step.
- GNOME extension tools, GLib schema compiler and GTK 4 introspection for its emoji preferences. `xdg-open`/`xdg-mime` are used for chat links. Color emoji needs the system emoji font.
- Your **already-working Codex desktop App**, its CLI/plugin support, and matching desktop observer protocol (stream v11/read v3). Signal does not install a different Codex build. The official current desktop Linux list names Ubuntu 24.04/26.04, not 22.04. [Official support](https://learn.chatgpt.com/docs/linux/linux-app).

If desktop dependencies are missing, review and explicitly approve the appropriate package-manager change. On standard Ubuntu 22.04 the relevant package names are `gnome-shell`, `gnome-shell-extension-prefs`, `libglib2.0-bin`, `gir1.2-gtk-4.0`, `xdg-utils` and `fonts-noto-color-emoji`. Do not reinstall a working desktop session or perform a distribution upgrade for this beta. The installer never runs apt or sudo.

## Install explicitly

Extract `codex-signal-v0.2.0-ubuntu22.04-beta-noarch.zip` into a persistent folder. It is architecture-independent Python/GJS source, not a Mac executable or a bundled Python runtime.

```sh
python3 scripts/doctor.py --json
./scripts/install.sh --with-gnome
```

The doctor is read-only and prints versions/booleans, not chats, IDs, credentials or private paths. Before installation `extensionRegistered` may naturally fail. Missing desktop IPC may mean the App is not running, a different configured path, or an incompatible build—not “no active chats.”

`--with-gnome` explicitly installs `codex-signal@local` under your XDG GNOME extension directory, compiles its GSettings schema and asks GNOME to enable it. Existing Signal extension files are moved into a timestamp-independent unique recovery folder under XDG state before replacement. The installer does not log out, restart Shell, restart Codex or send task commands.

**First install can require a later GNOME logout/login** before Shell discovers a new extension, especially under Wayland. If enable says the extension is unknown, it remains installed; log out when it is safe for your other work, then run `gnome-extensions enable codex-signal@local`. Do not restart your running desktop just to satisfy the installer. The Codex plugin and desktop must also have actually loaded; verify `get_status` on the next chat turn.

Alternatively, install `codex-signal-v0.2.0-gnome42-companion-beta.zip` with `gnome-extensions install` and enable it explicitly. Do not use this route as a second duplicate install over the included script.

## Version-bound desktop adapter

Default inputs are under `CODEX_HOME` (default `~/.codex`): `.codex-global-state.json`, `config.toml`, and `ipc/ipc.sock`. They are explicit assumptions of this adapter, not verified universal Linux paths. For a build exposing the same protocol at different locations, configure these variables **in the plugin executor's environment**, then reload the plugin:

- `CODEX_SIGNAL_DESKTOP_STATE`: desktop metadata file.
- `CODEX_SIGNAL_CONFIG`: desktop settings file, used only for its locale.
- `CODEX_SIGNAL_IPC`: same-runtime observer socket.

Do not guess sockets from another user/process or substitute an independent app-server. A protocol/path failure stays visible. If the target build has no compatible observer/read signal, record that limitation; do not start/resume a chat or scrape transcripts as a workaround. Remote chats preserve both host identity and original chat ID; only remote hosts connected through this desktop are covered.

## Data and lifecycle

- Config: `$XDG_CONFIG_HOME/codex-signal/settings.json`, default `~/.config/codex-signal/settings.json`.
- State/slots/acknowledgements: `$XDG_STATE_HOME/codex-signal/`, default `~/.local/state/codex-signal/`.
- UI transport: `$XDG_RUNTIME_DIR/codex-signal/ui.sock`. Directory mode 0700, socket mode 0600, Linux peer-UID verification, bounded frames and fixed action enums. No TCP listener.
- Codex owns the backend and bridge; no systemd service or login daemon. On disconnect the extension clears live projects/notices and leaves a clearly offline recovery entry. Reconnect sends the latest state, never old alerts.
- Disabling the GNOME extension disconnects transport and removes its actors/timers/signals. It does not approve/stop tasks. The plugin retains business state.
- Settings → entry icon opens a separate GTK 4 preferences/EmojiChooser window. GTK is not loaded into the Shell renderer process. Its language follows the latest Codex setting received by the extension.
- In this beta, state and layout algorithms are shared/generated, but font metrics, emoji artwork, hover behavior and GNOME surface rendering differ from AppKit. High-DPI/multi-monitor alignment needs native review.

## Tester checklist

Record OS, architecture, Shell version, Xorg/Wayland, scaling, Codex desktop source/exact version and Signal version. Do not post a full environment/config dump.

1. Install the actual beta ZIP. Confirm `connected` and `menuBarReady` and that only one backend owns the local store. Test plugin reload and desktop exit/reopen without orphan processes.
2. Run two existing chats in the same project and one in another, including a desktop-connected remote chat if available. Check original names/icons and project-local **1, 2…** numbering. Confirm links open the original local/remote chat.
3. Observe real working → approval/reply → completed/failed/stopped edges. Never use Signal to approve. Open a completed chat without replying; confirm the desktop's read signal clears it. If no read signal exists in that build, report it explicitly.
4. Toggle one project, the master switch and compact mode; reverse quickly. No false unknown during fresh-state handoff, no global-entry jump, no stale row deletion. Re-enable one project without re-enabling paused others.
5. Click each capsule twice; reverse before a spring settles. Test settings/back during motion, keyboard/Escape and GNOME's reduced-animation setting.
6. Select each alert type, then trigger a corresponding real state edge. Notice remains for six seconds after entry, body opens only its chat, × only dismisses. Disable alerts/master/project mid-notice; disconnect/lock/disable must clear it. Reconnect must not replay old cards.
7. Test Simplified Chinese and another Codex locale; names stay untranslated. Choose a compound emoji with the GTK picker. Test long mixed-language names, 4K/scaled display, narrow free panel space and more than one monitor.
8. Remove only the plugin and explicitly disable/remove only the companion. Reinstall and confirm IDs, slot history and acknowledgements survived. Keep any backup private.

Share only redacted findings and `doctor.py --json` output after checking it. The important first result is whether this exact 22.04 desktop build exposes the compatible state/read protocol; synthetic tests do not establish that.

## Recovery

Use `./scripts/uninstall-gnome.sh --confirm` to disable and move only Signal's extension into its recovery folder. The Codex plugin is removed separately with `codex plugin remove codex-menu-status@codex-signal`. Neither command deletes records. A prior extension recovery copy can be restored after disabling Signal; compile schemas and enable it again. Do not restore old chat-state snapshots over newer data.
