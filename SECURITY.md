# Security reports

Do not post credentials, raw IPC payloads, chat titles/IDs, local state/config files or desktop screenshots in public issues. Use GitHub's private vulnerability reporting when the repository owner has enabled it. If private reporting is unavailable, ask the maintainer for a private channel without including exploit details or personal data.

Reports should identify the affected version, supported environment and minimal synthetic reproduction. This plugin must not approve Codex actions, start/resume chats, write Codex read receipts, expose its local transport to the network or add background services.

The desktop observer protocol is version-bound. Connection or protocol errors must remain visible; unknown state is preferable to falsely displaying completed or safe.
