# Compatibility

| Target | Implemented | Evidence / gap |
| --- | --- | --- |
| macOS Apple Silicon | Native renderer + shared backend | 0.2.1 native build, automated suites and isolated package installation; clean-download trust remains unverified |
| macOS 14+ | Deployment target | Not a claim that every older OS build was exercised |
| Intel Mac | Source can be built separately | No Intel asset or runtime acceptance in this release |
| Ubuntu 22.04, GNOME Shell 42 | Complete Python bridge + GJS top-panel/popup/settings/notice companion | Beta code and synthetic tests; native GNOME, desktop IPC/read state and installation need tester validation |
| GNOME 43+ / KDE / other desktops | Not ported | Do not edit metadata to force-enable the GNOME 42 extension |
| Independent CLI / IDE / other machines | Outside current scope | Only remote chats connected through this desktop runtime are included |

Python 3.10+ is required and not bundled. Both platform launchers fail clearly on a mismatched package. The Linux pure-source payload is architecture-independent; x86_64/aarch64 support is not claimed as device-tested.

The shared adapter targets desktop **stream v11/read v3**. Linux reuses that explicit version-bound observer, not a guaranteed public cross-platform API. Its default Codex home/file/socket locations can be overridden explicitly; an incompatible build displays a connection/protocol error. It never starts/resumes chats or scrapes whole session logs to fabricate status. [Beta setup and acceptance](UBUNTU-BETA.md).

The current official Linux desktop preview lists Ubuntu **24.04/26.04**, not 22.04. The beta targets a user's already-working 22.04 desktop build; it does not supply or upgrade that app. [Official Linux support](https://learn.chatgpt.com/docs/linux/linux-app).
