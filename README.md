# Codex Signal

**Chat status at a glance.** A Codex desktop plugin for the chats you are using now, grouped by project. No separate application, cloud service or API key.

[简体中文](README.zh-CN.md) · [Install](docs/INSTALL.md) · [Ubuntu beta](docs/UBUNTU-BETA.md) · [Privacy](docs/PRIVACY.md)

## Know when a chat needs you

Each project gets a black capsule with its original icon/name and a colored number for each chat. The rightmost status entry stays in place as project capsules retract.

| Color | State |
| --- | --- |
| Blue | Working |
| Orange | Needs approval |
| Purple | Needs your reply |
| Green | Completed, not yet viewed |
| Red | Failed |
| Gray | Stopped |
| Gray, dashed | Unknown or disconnected |

- Click a project to open its panel, then again to close it. Numbered circles and chat rows open the original chat. Approvals stay in Codex.
- Keep all capsules visible or choose **Status button only**. The single entry still indicates the highest-priority state; its panel then includes chat details under each project.
- Pause all updates, or just one project. Neither switch stops tasks. Resuming syncs fresh state before showing task colors.
- Choose which states trigger a **six-second alert**. Click its body to open the chat; **×** only closes the alert.
- Choose an entry emoji with the system picker. Default: 🔦.
- UI follows Codex: Simplified Chinese uses Chinese; other languages use English. Names remain exactly as Codex supplies them.
- Visible chats are numbered continuously from 1 within each project. Original IDs, historical slots and acknowledgements remain separate.

## Install a platform package

| Asset | Requirements | Validation |
| --- | --- | --- |
| `codex-signal-v0.2.3-macos-arm64.zip` | Apple Silicon, macOS 14+, Python 3.10+, Codex desktop | Built/tested on the development Mac; clean-download trust check outstanding |
| `codex-signal-v0.2.3-ubuntu22.04-beta-noarch.zip` | GNOME Shell 42, Python 3.10+, an already-working compatible Codex desktop | Full beta implementation; Ubuntu desktop validation pending |

Extract the platform ZIP to a folder you will keep, then run:

```sh
./scripts/install.sh                       # macOS
./scripts/install.sh --with-gnome          # Ubuntu; explicitly installs the companion
```

**Python is not bundled.** The installer checks prerequisites; it does not silently install Python, system packages, a different desktop app or background services. Using the release package on Mac requires no Xcode. [Ask Codex to install it](docs/INSTALL-WITH-CODEX.md), or follow [manual installation](docs/INSTALL.md).

Installation uses Codex's local marketplace commands. Continue in a new chat turn and check Signal's actual status; no Codex restart is requested. An existing loaded Signal can hot-reload an already installed newer payload using its refresh button. First-time desktop plugin discovery can depend on the host version.

The Mac helper currently has an **ad-hoc signature**, not Developer ID notarization. A downloaded copy may be blocked by macOS trust policy. Do not disable Gatekeeper or strip quarantine; see [distribution status](docs/PACKAGING.md). Version 0.2.3 is distributed as a prerelease with these limitations.

Ubuntu 22.04 is not in the desktop app's current official supported distribution list. Its private observer protocol must match the beta adapter. The beta does not install, replace or upgrade Codex. [Compatibility and limits](docs/COMPATIBILITY.md).

## Local data, local control

Signal follows the current desktop runtime, including remote chats connected through that desktop—not your entire account history or independent CLI/IDE processes. It reduces desktop snapshots to metadata/lifecycle fields and discards transcript bodies. It never approves commands, sends chat messages or writes Codex read receipts. A click can let Codex apply its usual read behavior; Signal's checkmark acknowledges only its own reminder.

Mac data stays in the established `~/Library/Application Support/CodexMenuStatus/` location. Linux uses XDG configuration/state directories. No personal data is shipped. [Details](docs/PRIVACY.md).

## Build and test

```sh
python3 -m unittest discover -s tests -v
node tests/linux-ui.cjs                    # deterministic model/GJS API harness
python3 scripts/generate-layout.py --check
python3 scripts/generate-linux.py --check
# macOS only:
swift test --disable-sandbox --package-path native
./scripts/build-release.sh
python3 scripts/package.py --target macos
# Architecture-independent Python/GJS source package:
python3 scripts/package.py --target ubuntu22.04-beta
```

Python 3.10+ is needed for development; Mac builds also need Swift 6+/Apple command-line tools. Shared layout, motion and bilingual copy come from `codex-status-layout.html`. The HTML uses fictional data, never real chats.

[MIT](LICENSE) · [Third-party notices](THIRD-PARTY-NOTICES.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Release checklist](docs/RELEASE-CHECKLIST.md)

Community project; not affiliated with OpenAI. GitHub distribution does not imply acceptance in the official plugin directory.
