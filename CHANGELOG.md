# Changelog

## 0.2.1 — cross-platform ordering and locale fixes

- Preserve rapid plugin command order even when the filesystem gives several request files the same timestamp; older requests remain readable.
- Detect same-length locale edits and atomic config replacements within one filesystem timestamp tick, without retaining other configuration values.
- Make control/deep-link tests independent of the developer machine locale and platform; add coarse-timestamp regressions.
- Retain IDs, historical numbering, acknowledgements and existing installation paths.

## 0.2.0 — distribution candidate and Ubuntu beta

- Adopted Codex Signal and MIT. Lightweight packages require user-managed Python 3.10+; no Python runtime bundled. Pure-Python Tomli is included for Python 3.10 without a pip step.
- Preserved the established Mac data location, internal plugin ID, historical slots and acknowledgements. Installation does not automatically migrate another marketplace edition.
- Added Linux XDG paths, an authenticated same-user private Unix bridge, and a GNOME Shell 42 companion: project capsules, rightmost status entry, compact hierarchy, per-project/master switches, settings, GTK emoji selection and clickable six-second notices.
- Generated GNOME metrics/copy/icons from the same HTML contract. Added interruptible animations and bounded socket/reconnect/disable cleanup.
- Added explicit companion installation/removal with recovery copies, prerequisite doctor, AI installation instructions and platform-specific allowlist packaging.
- Ubuntu is a code-complete testing candidate, not desktop-validated. Mac Developer ID/notarization and clean-download trust remain outstanding. Version 0.2.0 is a prerelease.

## 0.1.23

- Master resume/startup sync fresh snapshots before presenting task states; status entry remains neutral while syncing.
- Compact rapid reversals cancel stale removal callbacks and retain IDs/records.
- Retained rightmost global entry, popup spring transitions and selective clickable six-second alerts.
