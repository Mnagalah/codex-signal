# Contributing

Develop and test on macOS. Use fictional fixtures or the HTML demo; keep real chat bodies, titles, IDs and user records private.

Run the Python suite, shared-resource check and serial Swift tests shown in README. Mac source builds require Swift 6.2+ and Apple command-line tools; users of the prebuilt package do not need Xcode.

Edit grid, typography, motion and bilingual copy in `codex-status-layout.html` and regenerate the native resources. Keep AppKit tests serial because they share the main run loop and motion preference override. Test reduced motion separately from normal interpolation.

Retain original chat/host identity, project-local visible numbering, historical slots, acknowledgements, read semantics and click targets. Cover global/project switches, compact hierarchy, six-second notices, emoji selection and interruptible open/close transitions.

Keep one canonical business source. Export local deployments with `scripts/stage-deployment.py`; do not edit installed caches. Environment installation needs explicit permission, and product installation is not complete until the registered plugin and live menu readiness are verified. Separate automated checks, actual native inspection and clean-Mac acceptance.
