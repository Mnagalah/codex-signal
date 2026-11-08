# Codex Signal

Codex Signal is a macOS menu bar plugin for Codex desktop. It groups current conversations by project and shows running tasks, approval requests, pending replies, and completed work.

[简体中文](README.zh-CN.md) · [Releases](https://github.com/Mnagalah/codex-signal/releases) · [Installation](docs/INSTALL.md)

## Features

- View the status of local conversations and remote conversations connected through Codex desktop.
- Open conversations from the menu bar and choose which status changes trigger an alert.
- Keep completion reminders and the conversation list in sync with read status, archiving, and confirmed local deletions.
- Pause status updates globally or by project. The interface supports English and Simplified Chinese.

## Installation

The prebuilt package supports Apple Silicon Macs running macOS 14 or later and requires Codex desktop and Python 3.10 or later.

To install through Codex, send the repository URL with this request:

> Install Codex Signal: https://github.com/Mnagalah/codex-signal

Codex can follow the [installation instructions](docs/INSTALL-WITH-CODEX.md) to download the prebuilt package, prepare the environment, and verify the plugin. The installer reuses a compatible Python interpreter; setup for a missing runtime is available with your approval.

The current prerelease is [v0.2.9](https://github.com/Mnagalah/codex-signal/releases/tag/v0.2.9). Its native component uses ad-hoc signing. See [Compatibility](docs/COMPATIBILITY.md) for platform and signing details.

## Implementation

The Python backend provides a stdio MCP service and reads conversation state through Codex desktop's local IPC connection. Remote conversation state is supplied by the desktop application.

A native Swift/AppKit component presents the menu bar interface. It exchanges state updates and user actions with the backend as line-delimited JSON over standard input and output.

The launcher uses a validated Python interpreter path recorded during setup. Fresh ZIP installations are copied into managed, versioned storage. Settings, conversation identifiers, and reminder records are stored locally; conversation bodies are excluded from these records. See [Privacy](docs/PRIVACY.md).

## Development

Source builds require macOS, Swift 6.2 or later, Python 3.10 or later, and Apple command-line tools. See [Contributing](CONTRIBUTING.md) for the repository structure, tests, and build commands, and [Packaging](docs/PACKAGING.md) for distribution details.

## License

An independent community project released under the [MIT License](LICENSE). See [third-party notices](THIRD-PARTY-NOTICES.md).
