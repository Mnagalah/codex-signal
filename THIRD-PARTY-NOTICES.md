# Third-party notices

Codex Signal source is MIT licensed. The pure-Python TOML parser in `server/vendor/tomli` is Tomli 2.5.0, by Taneli Hukkinen and contributors, under MIT. Its complete license and source provenance are in that folder. It provides TOML support on Python 3.10; Python 3.11+ uses the standard library instead.

The macOS helper links Apple's platform frameworks and the Swift runtime supplied by macOS. The Ubuntu companion uses GNOME Shell's installed GJS, St, Clutter, GTK and GLib interfaces. These system runtimes are not redistributed in this package. GNOME reference implementations informed the API integration; no GNOME Shell implementation files are bundled.

Python itself is not bundled. No home-directory runtime caches, credentials, conversation exports or telemetry SDKs are included.

GNOME project marker SVGs use Lucide 0.468.0, under ISC, with portions originating from Feather under MIT. Their stroke color is adapted for this dark interface. The complete upstream copyright/permission notice and pinned source provenance accompany the vectors in [icons/LICENSE](linux/gnome/codex-signal@local/icons/LICENSE) and [icons/UPSTREAM.json](linux/gnome/codex-signal@local/icons/UPSTREAM.json). No Apple SF Symbol files are redistributed to Linux.
