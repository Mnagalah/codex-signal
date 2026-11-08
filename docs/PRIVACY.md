# Privacy and local data

Signal connects to the current Mac desktop's local, version-bound IPC stream. Frames can contain transcript payloads; Signal immediately projects only needed metadata/lifecycle fields, discards bodies and never persists/logs the transcript.

Private data stays in `~/Library/Application Support/CodexMenuStatus/`: settings, chat/host IDs, original titles/project association, numbering history and local acknowledgements. `recovery.json` keeps minimal recent identity/project hints, not task truth. The desktop's explicit locale selects Chinese or English; unrelated configuration and account data are not exported.

No analytics, external status service, API key or inference call is used. Following/unfollowing changes only Signal's observer. Signal never approves, resumes/stops tasks, sends chat messages or writes Codex read receipts. Opening a chat lets Codex apply its normal read behavior; Signal's checkmark acknowledges only its own reminder.

Archive/deletion markers prevent late frames from reviving retired entries. Local index reads are scoped to already-known local IDs; the database and rollouts are never written. Missing replies are not proof of deletion.

Public diagnostic capture is off. Never publish status/slots/recovery files, account/config data, screenshots or raw socket frames. Publish only the packager's allowlist with fictional tests and the required licenses.

The private `python-path` file stores the validated absolute interpreter path; it is not shipped or uploaded. First setup copies only the public package allowlist into the current profile's managed source and preserves prior installed payloads. The live readiness check uses a nonce receipt, not a cached status file.

Setup uses an empty, private `plugins/codex-signal-install.lock` under the selected Codex profile to serialize Signal installation attempts. It contains no chat data and is separate from the live service lock.
