# Contributing

Development requires macOS, Swift 6.2 or later, Python 3.10 or later, and Apple command-line tools.

## Repository structure

| Path | Purpose |
| --- | --- |
| `native/` | Swift/AppKit menu bar interface and native tests |
| `server/` | Python MCP service, desktop state adapter, and local records |
| `scripts/` | Installation, runtime setup, code generation, and packaging |
| `tests/` | Python regression tests |
| `docs/` | Installation, compatibility, privacy, and release documentation |
| `bin/` | Prebuilt macOS menu bar component |
| `.github/workflows/` | Automated validation |
| `.agents/plugins/marketplace.json` | Local plugin marketplace catalogue |
| `plugin.json` | Plugin identity, version, and interface metadata |
| `mcp.json` | MCP launch command and environment |
| `platform.json` | Distribution platform and runtime requirements |
| `codex-status-layout.html` | Shared interface layout and copy definitions |
| `project-icons.json` | Project icon mappings |

## Test and build

```sh
python3 -m unittest discover -s tests -v
python3 scripts/generate-layout.py --check
swift test --disable-sandbox --no-parallel --package-path native
./scripts/build-release.sh
python3 scripts/package.py --target macos
```

AppKit tests run serially because they share the main run loop and motion settings. Use fictional fixtures for conversation content, identifiers, paths, and user records.

Shared layout and bilingual copy are maintained in `codex-status-layout.html`. Regenerate the corresponding resources after changing their definitions. Project icon mappings are maintained in `project-icons.json`.

Local marketplace deployments are exported with `scripts/stage-deployment.py`. Keep the repository as the source for implementation changes.

## Implementation changes

Preserve host/chat identities, project-local visible numbering, historical slots, acknowledgements, read semantics and click targets. Changes to native interactions should cover global and project controls, compact views, alerts, emoji selection and interruptible open/close transitions. Check normal and reduced motion separately.

Install runtime prerequisites with user authorization. Keep installed version payloads intact for live clients, and distinguish automated checks, actual native inspection and fresh-device acceptance.

## Documentation and release writing

Read this section before writing or modifying README, CHANGELOG, Release text, installation documentation or commit messages. Base factual statements on the current implementation, configuration, installation scripts, tags and actual distribution assets. Integrate later valid changes rather than restoring an older document wholesale.

Use concise, objective language with accurate verbs and concrete objects. Keep review notes, execution checklists, chat history and internal discussion in development records, separate from public project copy.

### README

- Introduce the project, its intended users and operating environment briefly. Describe implemented core capabilities through their practical value.
- Explain the main components and their relationships at a level sufficient to understand the project structure.
- Keep the installation entry short and link to detailed installation, development, compatibility and license information.
- Put colors, geometry, motion timings and button layouts in design or development material. Put test procedures, acceptance history and development-task requirements in development records.
- State platform, dependency, signing and compatibility conditions that affect use accurately and briefly, with a link to details.
- Keep English and Chinese versions aligned on capabilities, requirements and installation entry points; use natural wording in each language.
- Give each section one clear purpose and remove repeated introductions or conditions.

### Releases

Use the title `Codex Signal vX.Y.Z`. Describe the version's changes relative to the previous actually published version; for an initial release, describe its delivered scope. Verify historical claims against that version's tag and diff, and attribute later capabilities to their actual release.

- Match the length to the change: a single fix may need one sentence; ordinary updates usually need only a few bullets.
- Name the concrete change and, when useful, its user impact. Fix descriptions should identify the original problem rather than say only “improve stability” or “optimize the experience.”
- Keep English and Chinese bullets in one-to-one factual correspondence. The Chinese summary must describe this version's actual changes.
- Link to centrally maintained installation, privacy and compatibility information. State a dependency, migration requirement or compatibility change introduced by this version directly in its notes.
- Keep test counts, complete verification commands, implementation chronology and development-environment details in development records or the release checklist.
- Distinguish implemented behavior, passing automated checks and actual device acceptance; make each claim at the strength supported by its evidence.

### CHANGELOG and version consistency

Organize changes by actual released versions. Put current unpublished work under `Unreleased` and move it to the corresponding version at publication. Consolidate intermediate development changes into the version that shipped them, and follow the actual record when version numbers skip. Identify retained historical drafts as drafts.

Keep CHANGELOG and Release facts and version attribution consistent. Before publication, check version identifiers, the tag, installation assets, README download entry, CHANGELOG and Release together. Treat prose-only revisions as documentation changes; use the project's version policy for a changed distribution package. Preserve published tags and assets when editing release text.

### Commit messages and the GitHub file list

GitHub's file list shows each path's most recent content-changing commit subject. Describe the current change in the subject; explain file purposes in the repository structure table above.

Use the intended contributor's GitHub-linked name and commit email, preferably the account's GitHub-provided `noreply` address. Verify the effective author and committer before committing; use an account identity rather than a project label, while keeping personal email addresses private.

- Use a short, specific first line with an action verb. Omit repeated project names or version numbers when they add no useful distinction.
- Put reasons, implementation details and verification results in the body when needed.
- Group related files by the purpose of the change, and review the staged diff so the subject matches the actual content.
- Commit meaningful content changes. Unchanged paths retain their existing history and summaries.

Examples:

- `Clarify project overview and installation`
- `Summarize release history`
- `Document repository structure and contribution workflow`
- `Fix remote unread reminder synchronization`

Release text is saved through GitHub's publishing interface and does not create a file commit. Verify those updates separately from repository commits.

### Consistency check

When adding a feature, adjusting dependencies, changing installation or update behavior, changing distribution platforms, or releasing a version, check the related documentation in the same task and correct inconsistencies directly.

Before completing a documentation or release change, check:

- Every described capability has a corresponding implementation; platform, dependencies, commands and update paths match it.
- Version identifiers, tags, download URLs and actual assets agree.
- English and Chinese agree on facts and scope; README, installation guides, CHANGELOG and Release do not contradict one another.
- Current instructions replace stale ones, without repeated installation, privacy, limitation or acceptance paragraphs.
- Public documents contain reader-facing material rather than chat history, editing-process notes or internal execution requirements. Necessary compatibility conditions remain clear.
- Commit subjects describe their actual diffs. Saved repository documents and Release text match the intended result; existing release tags, assets and publication states remain intact.

For prose-only work, verify content, links and metadata. When runtime code changes, also follow the existing test requirements above. Keep detailed verification evidence in development records or the [release checklist](docs/RELEASE-CHECKLIST.md), not in README or Release prose.

See [Packaging](docs/PACKAGING.md) and [Compatibility](docs/COMPATIBILITY.md).
