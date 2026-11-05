# Contributing

Use synthetic fixtures or the HTML demo. Never publish chat bodies, real titles/IDs or local state files.

Python 3.10+ runs the backend suite. Node runs `tests/linux-ui.cjs`, a deterministic model/GJS API harness—not native GNOME acceptance. Mac builds additionally need Swift 6.2+ and Apple command-line tools. Run the README checks and build the actual platform package before proposing a release.

Keep `--no-parallel` in the native test command. These AppKit tests share the main run loop and a process-wide reduced-motion override; nested run-loop animation checks must not run unrelated tests reentrantly. Do not weaken animation assertions or extend arbitrary sleeps to compensate for concurrent test interference.

Change shared grid/copy/motion values in `codex-status-layout.html`, then regenerate Swift and Linux resources with both generators. Do not maintain unrelated coordinates for each renderer. The GNOME renderer uses St/Pango and its own adapter for logical sizing; Swift uses AppKit text metrics.

Retain original chat/host identity, project-local visible numbering, persisted slots/acknowledgements, read semantics and click targets. Preserve global versus project switches, compact hierarchy, six-second alerts, emoji chooser, bilingual rules and interruptible open/close transitions. Cover reversals, disconnects, extension disable and stale callbacks.

Do not add a model request, independent daemon, log scraper, approval action, silent environment installation or unrequested migration. Record automated, native UI and clean-device evidence separately. Discuss adapter changes before widening compatibility claims. Use minimal redacted reproductions with exact versions.

The repository is the single business source. `scripts/stage-deployment.py` exports a local marketplace deployment without a source fork; change behavior here, not in an installed cache or generated deployment.
