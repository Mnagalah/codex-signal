# Ubuntu 22.04 implementation decision

Updated 2026-11-04. The original feasibility study led to a **GNOME Shell 42 companion**, not an independent application and not an AppIndicator-only reduction. The complete beta source is now in `linux/gnome/codex-signal@local` and `server/linux_renderer.py`. Current install and acceptance instructions are in [UBUNTU-BETA.md](UBUNTU-BETA.md).

## Why a Shell companion

The design needs several colored project capsules, independent chat-number click targets, a retained rightmost aggregate entry and a matching anchored custom popup. A normal StatusNotifier/AppIndicator menu does not give the same layout control. GNOME's PanelMenu/St/Clutter path does; it requires explicit separate system-extension installation. No GTK/Electron status application, systemd service or task executor is introduced. [GNOME architecture](https://gjs.guide/extensions/overview/architecture.html), [StatusNotifierItem specification](https://specifications.freedesktop.org/status-notifier-item/latest-single/).

GNOME 42 uses legacy GJS modules, unlike GNOME 45+'s ESM extensions. Shell UI imports St/Clutter; a separate GTK 4 preference process hosts `Gtk.EmojiChooser`. Actors, signals, transport callbacks and timer sources are cleaned up on disable. [Legacy GJS](https://gjs.guide/extensions/upgrading/legacy-documentation.html), [GNOME 42 changes](https://gjs.guide/extensions/upgrading/gnome-shell-42.html), [GTK EmojiChooser](https://docs.gtk.org/gtk4/class.EmojiChooser.html), [extension lifecycle](https://gjs.guide/extensions/review-guidelines/review-guidelines.html).

## What is reused and what remains a target-host dependency

The existing observer, project/remote identity, read semantics, numbering, alert edge tracking and persistence stay in the Python backend. XDG paths and a private same-user Unix bridge replace Mac-specific paths/renderer invocation. HTML generates GNOME's actual grid metrics, motion constants, bilingual copy and vector icons. Pango/St supplies native Linux typography.

The Mac-observed stream v11/read v3 interface is version-bound, not a public universal observer API. The beta implements that same protocol with explicit path overrides and visible failure; it has not proved that an arbitrary 22.04 Codex desktop exposes it. A separate app-server cannot be assumed to observe other processes; starting/resuming tasks to get a status stream is outside this plugin's contract. [OpenAI App Server documentation](https://learn.chatgpt.com/docs/app-server).

Current official desktop Linux support lists Ubuntu 24.04/26.04, not 22.04. The 22.04 target is therefore an explicitly experimental adapter for an already-working desktop build, not an OS-upgrade instruction. [Official Linux distributions](https://learn.chatgpt.com/docs/linux/linux-app).

## Delivery decision

A clearly marked Linux beta asset accompanies the Mac candidate, with complete code for Ubuntu testers. Python is user-managed, not bundled; the pure Python/GJS payload is `noarch`, with no Mac binary. Native desktop IPC/read/deep-link integration, Xorg/Wayland, display scaling and fonts are tester dependencies. They are not marked passed by syntax or synthetic UI tests.

The beta retains master/project controls, compact hierarchy, rightmost entry, interruptible popup and settings transitions, selective six-second clickable cards, emoji chooser, bilingual rule and original IDs. See the [tester checklist](UBUNTU-BETA.md#tester-checklist) for observable acceptance and recovery.
