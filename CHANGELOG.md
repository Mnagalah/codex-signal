# Changelog

## 0.2.9

- Improve Python detection and startup by validating and reusing an installed interpreter, with setup guidance for missing runtimes.
- Store fresh ZIP installations in managed directories so the plugin remains available after the original download folder is removed.
- Add live installation checks for the plugin version, desktop connection, and menu bar readiness.
- Focus source code, packaging, and CI on macOS.

## 0.2.7

- Restore local and connected remote conversation status after the status service starts, reconnects, or detects a desktop connection change.
- Synchronize archived and restored conversations, and remove confirmed deleted local conversations from the menu bar.
- Refresh the notification baseline after recovery so subsequent status changes trigger the configured alerts.

## 0.2.5

- Improve completion reminders when conversations are marked unread, including changes made while project status updates are paused.
- Improve conversation state synchronization during hot updates.
- Show connection and protocol issues separately from task status.

## 0.2.4

- Fix outdated component loading when a background instance takes over. The replacement loads the latest complete installed version while preserving the connection and local records.

## 0.2.3

- Automatically restore reminders when a previously observed, completed remote conversation is marked unread again.

## 0.2.2

- Automatically clear completion reminders after the corresponding conversation is viewed.
- Fix stale snapshots causing cleared reminders to reappear.

## 0.2.1

- Fix processing order for plugin commands issued in rapid succession.
- Improve detection of language setting changes.

## 0.2.0 (draft)

- Package the project as Codex Signal under the MIT license.
- Provide a prebuilt macOS menu bar component, prerequisite checks, and installation documentation.
- Bundle TOML parsing support for Python 3.10.
