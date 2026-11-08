# Codex Signal project guidance

Codex Signal is a macOS Codex desktop plugin with a Python backend and a Swift/AppKit menu bar component. Keep this repository as the implementation source; local marketplace deployments are generated exports.

## Documentation and release work

Before writing or modifying README, CHANGELOG, Release text, installation documentation or commit messages, read [Documentation and release writing](CONTRIBUTING.md#documentation-and-release-writing). Follow its consistency check before completing the work.

When adding features, changing dependencies, installation or update behavior, distribution platforms, or publishing a version, proactively check and synchronize the affected documentation in the same task. Verify current code, scripts, configuration, tags and assets rather than assuming an older document is current.

## Implementation and verification

Read [Contributing](CONTRIBUTING.md) before implementation changes; it defines the structure, commands and behavior to preserve. Keep original chat identities and local user records intact. Use fictional fixtures and keep private data out of source, documentation and distribution artifacts.

Use new, purpose-focused commits. Preserve published history, tags and assets. Documentation-only work uses content, link and metadata checks; runtime changes also require the project's applicable tests.
