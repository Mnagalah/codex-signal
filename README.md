# Codex Signal

**Chat status at a glance, in your Mac menu bar.** A Codex desktop plugin for the chats you are using now, grouped by project. No separate app, cloud service or API key.

[简体中文](README.zh-CN.md) · [Install](docs/INSTALL.md) · [Privacy](docs/PRIVACY.md)

## Install on macOS

Use `codex-signal-v0.2.7-macos-arm64.zip`, macOS 14+, Python 3.10+ and Codex desktop. Extract to a persistent folder and run `/bin/sh scripts/install.sh`. Verify the current desktop's installed/enabled entry and live menu bar rather than relying on an installation message. [Installation](docs/INSTALL.md).

First-install reliability is being improved; a CLI registration alone is not a completed fresh-Mac acceptance.

## Know when a chat needs you

| Color | State |
| --- | --- |
| Blue | Working |
| Orange | Needs approval |
| Purple | Needs your reply |
| Green | Completed, not yet viewed |
| Red | Failed |
| Gray | Stopped |
| Gray, dashed | Unknown or disconnected |

Project capsules retain original icons/names and a colored number per chat. The rightmost status entry stays in place as projects retract.

- Click a capsule to open its panel and again to close it. Numbered circles, chat rows and notice bodies open the original chat; approvals stay in Codex.
- Choose all project capsules or **Status button only**. The single entry still has an aggregate status color; compact panels group detailed chats under projects.
- Pause all updates or one project without stopping tasks. Re-enable with a fresh-state handoff; startup/reconnection reacquire local and desktop-connected remote chats rather than treating cached colors as truth.
- Select which states trigger a six-second notice. × only dismisses the card. Recovery establishes a quiet baseline before later changes alert.
- Customize the entry with the system emoji picker; default 🔦.
- UI follows Codex: Simplified Chinese uses Chinese; other languages use English. Project/chat names are never translated.
- Each project's currently visible chats are numbered continuously from 1. Original IDs, historical slots and acknowledgements remain separate.
- Archive removes a chat from display; unarchive reacquires fresh state. Confirmed local deletion is reconciled read-only. Remote unavailability is not deletion.

## Data and trust

Settings and records stay under `~/Library/Application Support/CodexMenuStatus/`. Frames can contain text; the observer immediately projects needed metadata and discards bodies. It does not approve or start/resume tasks, send chat messages or write Codex read receipts. Private records and screenshots are not distributed.

Python is not bundled; Tomli is included, so no pip packages or Xcode are needed by users. The native helper currently has an ad-hoc signature, not Developer ID notarization. Clean-Mac download trust and complete quit/reopen acceptance remain separate checks; keep macOS security protections enabled. [Compatibility](docs/COMPATIBILITY.md).

## Build and test

```sh
python3 -m unittest discover -s tests -v
python3 scripts/generate-layout.py --check
swift test --disable-sandbox --no-parallel --package-path native
./scripts/build-release.sh
python3 scripts/package.py --target macos
```

Mac source builds need Swift 6.2+ and Apple command-line tools. AppKit tests share the main run loop and run serially. Layout, motion and bilingual copy are generated from `codex-status-layout.html`; named markers use `project-icons.json`. Keep this repository as the single business source; local marketplace deployments are generated exports.

[MIT](LICENSE) · [Third-party notices](THIRD-PARTY-NOTICES.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Release checklist](docs/RELEASE-CHECKLIST.md)

Community project; not affiliated with OpenAI. GitHub distribution does not imply acceptance in the official plugin directory.
