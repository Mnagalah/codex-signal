# State machines and recovery contracts

This is the authoritative state-machine map for Codex Signal. It covers the Python service, the native menu interface, setup, and the boundaries between them. Update the relevant transitions, invariants and regression references whenever behavior changes.

The audit baseline is commit `364ab0e2716bba6749b1b083320786b213fbd90b` (after the v0.2.9 documentation updates). The fixes below are **implemented in the unreleased 0.2.10 candidate**. The published download remains v0.2.9; a distinct numeric candidate directory preserves the immutable installed v0.2.9 payload during hot replacement. They do not change the persisted record format, host/chat keys, visible numbering rule, released assets or tags.

## Execution and ownership

- The Python primary processes events and mutates application state on one loop. IPC, MCP and renderer reader threads only enqueue messages. Multiple MCP clients compete for one file lock; a standby does not own another renderer or mutate the registry.
- Each IPC event carries its originating transport object; each UI event carries its child-process object. The event loop rejects obsolete sources after reconnect or replacement.
- Native model changes, timers and animation callbacks run on the main actor. The stdin reader extracts complete JSON lines under a lock and dispatches their interpretation to that actor.
- Installer processes use a separate, profile-scoped installation lock. It serializes source/catalogue/cache mutations without taking the live service's monitor lock.
- Individual JSON records are atomically replaced. The slots, recovery hints and status files are separate records, not a multi-file transaction. Recovery hints are discovery context, never restored task truth.

Source: [service](../server/main.py), [IPC](../server/desktop.py), [native entry point](../native/Sources/MenuBar/Main.swift), [installer](../scripts/install.py).

### Shared invariants

| ID | Invariant |
| --- | --- |
| I1 | A chat key is `(hostId, threadId)`: existing local IDs stay unchanged; remote keys retain the host prefix. Titles and visible numbers are never identities. |
| I2 | A task phase is authoritative only after a snapshot, or a contiguous patch chain from the current owner in the current IPC session. Saved phases are presentation/recovery context. |
| I3 | An invalid stream, disconnected owner or adapter failure cannot manufacture a task completion, a read acknowledgement or an automatic alert. |
| I4 | Only the primary writes slots, preferences and status or owns the renderer. Old transports, renderers and native animation completions cannot overwrite newer intent. |
| I5 | A read acknowledgement applies to one known terminal turn. It cannot silence a different or future turn; only an explicit unread edge can rearm that acknowledged turn. |
| I6 | Hidden, ephemeral and child chats are not visible tracked chats. Late follower/read/stream messages cannot undo retirement. |
| I7 | Display numbers are consecutive `1…N` within each visible project. Historical slots, first-seen ordering and acknowledgements remain independent of those numbers. |
| I8 | Global pause, project pause, compact presentation and alert preferences are separate controls. Presentation/alert choices do not change owner tasks or approve anything. |
| I9 | Writes to plugin-owned IPC/renderer channels have deadlines. A partially written frame is never retried on that channel. Ordinary receive idleness is not disconnection. |
| I10 | A setup registration result is not proof of activation. Ready requires the expected enabled version plus a fresh primary receipt, a ready native renderer and synchronized desktop health. |

## 1. Setup and Python selection

Ownership: [python.sh](../scripts/python.sh), [install-python.sh](../scripts/install-python.sh), [install.py](../scripts/install.py), [start.py](../scripts/start.py).

States: `runtime-unresolved`, `runtime-selected`, `prerequisite-needed`, `package-rejected`, `registration-needed`, `installed-needs-activation`, `ready`, and a stage-specific failure. These are distinct from the service's enabled preference.

| From | Input / guard | To / effect |
| --- | --- | --- |
| runtime-unresolved | Explicit interpreter is valid Python 3.10+ with required standard-library modules | runtime-selected; privately pin its absolute real executable path |
| runtime-unresolved | Explicit interpreter invalid | Failure; do not silently select another interpreter |
| runtime-unresolved | No override; valid saved pin or discovered interpreter | runtime-selected; repair stale pins using an available compatible interpreter |
| runtime-unresolved | No compatible interpreter | prerequisite-needed; provide opt-in installation guidance, not an automatic privileged install |
| runtime-selected | OS, architecture, helper or signature preflight fails | package-rejected; no success claim |
| registration-needed | Another enabled edition / conflicting source / changed immutable payload | Failure with a corrective action; preserve the existing source and live payloads |
| registration-needed | Acquire profile lock; stage complete payload; atomically publish it and catalogue; CLI confirms expected installation | installed-needs-activation |
| installed-needs-activation | Invoke installed service; `--verify` receives current nonce/version and all readiness conditions hold | ready |
| installed-needs-activation | No receipt, wrong version, paused, UI unready or health not ready | Corresponding failure; registration may still exist and can be verified again |
| Retry after registration failure | Existing payload bytes match | Reuse immutable payload, retry registration; do not replace a live version directory |
| Two installers | Same Codex profile | Serialize the full registration/cache-preservation operation; later caller rechecks current state |

Invariants: no resident setup skill; no detached substitute service; setup does not restart Codex or clear chat records. A fresh-device test is separate from the private-profile setup tests in [test_setup.py](../tests/test_setup.py).

## 2. MCP ownership and hot replacement

Ownership: `Plugin.elect`, `Plugin.run`, `Plugin.control`, `serve`, [lifecycle.py](../server/lifecycle.py).

| From | Event / guard | To / effect |
| --- | --- | --- |
| standby | Monitor lock busy | standby; retry election at one-second intervals |
| standby | Lock acquired; same-source newer complete payload exists | reloading, before starting an obsolete renderer |
| standby | Lock acquired; no pending adoption | primary; reload preferences/slots/context, establish notice baseline, start renderer and recovery |
| primary | Explicit reload | Publish current records, queue context/read-intent handoff, stop old child and IPC; retain lock and the single MCP stdin queue |
| reloading | New version-scoped class loads | New primary instance; refetch task truth |
| reloading | Import/construction fails | Previous implementation with `updateError`; avoid repeated automatic adoption loop |
| standby or primary | MCP EOF / termination / bounded diagnostic end | stopped; release owned resources and monitor lock unless handing it onward |

Invariant: namespaces are replaced, not reloaded in place under active reader callbacks. Handoff includes identities, project context and explicit read intents, not saved task status. Cold startup does not restore owner/revision/turn truth from disk. Regression: [test_control.py](../tests/test_control.py), [test_convergence.py](../tests/test_convergence.py), [test_recovery.py](../tests/test_recovery.py).

## 3. Renderer supervision and channel writes

Ownership: `Plugin.ensure_renderer`, `renderer_failed`, `write_renderer`, [transport.py](../server/transport.py).

States: `absent`, `starting` (child alive, no ready event), `ready`, `broken`, `backoff`, `stopped`. `--no-ui` intentionally bypasses this machine.

| From | Event / guard | To / effect |
| --- | --- | --- |
| absent / backoff | Primary, UI enabled, retry deadline reached | starting; spawn only the plugin's native child; force full-state delivery |
| starting | Ready from the current, unbroken child | ready; clear UI error and record layout metadata |
| starting / ready | Spawn error, child exit, matching EOF or write failure | broken; clear readiness and click authorization; preserve service/IPC/records |
| broken | Supervisor tick | Retire/reap only that child, close its streams; backoff |
| backoff | Retry | Delays `1, 2, 4, 8, 16, 30…` seconds; one child at a time |
| ready | Ten seconds of child uptime observed ready | Reset launch-failure count |
| any | Obsolete child's ready/EOF event | No transition |
| any | Service shutdown/reload | stopped; close input and reap child |

Both socket and pipe writes use nonblocking descriptors and a monotonic, one-second total write deadline. Short writes advance within the same frame. Timeout/error abandons the channel rather than retrying the frame suffix as a new message. IPC close skips unfollow messages after a write failure; a new IPC session resubscribes. Renderer failure is repaired by a new child receiving a complete state.

The receive loop waits for readability without interpreting quiet periods as EOF. This follows the [Python socket nonblocking model](https://docs.python.org/3/library/socket.html#notes-on-socket-timeouts); changing a socket-wide timeout underneath a concurrent reader is not used as a send deadline.

Regression: `RendererRecoveryTests` and `IPCWriteTests` in [test_state_machines.py](../tests/test_state_machines.py), including real socketpair/pipe backpressure and the production event loop.

## 4. Desktop transport, adapter health and snapshot retries

Ownership: `Plugin.connect`, `disconnect`, `consume_ipc`, `consume_client_lifecycle`, `adapter_health`, [Recovery](../server/recovery.py).

| From | Event / guard | To / effect |
| --- | --- | --- |
| disconnected | Enabled and retry due | initializing; connect observer transport (three-second connect bound), send initialize |
| initializing | Successful acknowledgement from current transport | connected; invalidate retained sources, reset session tombstones, request baseline snapshots, allow one-second presence replay |
| initializing | No acknowledgement within five seconds | disconnected; drop only observer session, retry after three seconds |
| connecting | Connect fails | disconnected; retry after five seconds, not an endless loading phase |
| connected | EOF, logical reset or I/O failure | disconnected; invalidate sources and notice routes; retain identities/acknowledgements; retry after three seconds (immediately for logical reset/manual reconnect) |
| connected | Owner disconnect | Tombstone owner for this session; invalidate only its chats and request new baselines |
| connected | Replacement owner snapshot | Fresh replacement source; disconnected old owner remains fenced |
| connected | Explicit owner reconnect | Remove that owner's tombstone; reannounce relevant follows, without invalidating unrelated live tasks |
| any | Event from replaced transport | Ignore |

Per-key recovery states are `not-pending`, `awaiting`, `unavailable`, `cancelled`. `required` controls visible health; `baseline` controls alert seeding.

| From | Event | To / effect |
| --- | --- | --- |
| not-pending | Discovery, source invalidation or requery | awaiting; coalesce repeats without resetting start time/backoff |
| awaiting | Due | Send at most eight follows per tick; next delays `1, 2, 4, 8, 16, 30…` seconds |
| awaiting | Valid snapshot/contiguous stream update | not-pending; first recovered sample is a silent baseline |
| awaiting | Required source still missing after five seconds | unavailable; keep retrying |
| awaiting / unavailable | Project pause / retirement / global disconnect | cancelled; stop that retry scope |
| unavailable | Valid source returns | not-pending; recompute health |

Health is a derived state with precedence: `paused` → `protocol-error` → connected recovery (`syncing`, `unavailable`, `ready`) → `connecting` → `disconnected`. Protocol errors are keyed by chat/channel; a valid stream cannot erase an unrelated read-protocol error. An inactive context hint is not proof that a chat is running. Regression: [test_recovery.py](../tests/test_recovery.py), [test_convergence.py](../tests/test_convergence.py).

## 5. Thread freshness and task phase

Ownership: [ThreadState](../server/state.py). Freshness is the tuple `(session, host, thread, owner, revision)`; `valid` is separate from phase.

| Freshness state | Frame / guard | Result |
| --- | --- | --- |
| invalid / fresh | Snapshot from eligible owner | Replace metadata-only projection; set owner/revision and valid |
| fresh | Older snapshot from the same owner | Ignore its data; retain current revision |
| fresh | Patch, same owner and exact base revision | Apply selected metadata patches and advance revision, including text-only frames whose content is discarded |
| fresh / invalid | Patch gap, owner mismatch or invalid selected patch | invalid; request a fresh baseline |
| any | Disconnected-owner frame / obsolete transport / hidden chat | Ignore before accepting task data |

The phase table is evaluated top to bottom; these are projections of desktop facts, not a locally simulated task lifecycle.

| Condition | Phase |
| --- | --- |
| Not valid | `unknown` |
| Active runtime + approval flag or outstanding approval request | `approval` |
| Active runtime + input flag or outstanding input/elicitation request | `input` |
| Other active runtime | `running` |
| Runtime system error | `failed` |
| Latest turn completed / failed / interrupted | `completed` / `failed` / `stopped` |
| In-progress latest turn but idle/not-loaded runtime | `unknown` |
| Not-loaded runtime | `unknown` |
| Otherwise | `idle` |

Active phases may move directly between running/approval/input; desktop snapshots can skip intermediate phases. Terminal → active is a new/resumed turn, not a forbidden UI transition. Unknown is a freshness/availability outcome, not a terminal task event. The latest turn is ordered by timestamp and turn ID, not canonical dictionary order. Only whitelisted metadata survives projection; tool-item completion is not turn completion. Regression: [test_state.py](../tests/test_state.py), [test_adapter.py](../tests/test_adapter.py).

## 6. Visibility, read intent, numbering and retirement

Ownership: `WatchRegistry`, `Plugin.remember_read`, `hide_thread`, `restore_thread`, [LocalThreadAvailability](../server/availability.py).

States are `absent`, `active-visible`, `terminal-unseen`, `acknowledged`, `retained-unknown`, `excluded`, `hidden-archived`, `hidden-deleted`. Project pause freezes the saved registry rather than inventing a task phase.

| From | Event / condition | To / effect |
| --- | --- | --- |
| absent / acknowledged | Fresh active phase | active-visible |
| active-visible | Fresh terminal and unread, not acknowledged for that turn | terminal-unseen |
| visible | Fresh idle or read terminal | absent |
| visible | Source becomes invalid/unknown | retained-unknown; do not infer completion |
| any visible | Ephemeral or child metadata becomes true | excluded; remove entry, notice baseline and undelivered card |
| excluded | Root/non-ephemeral snapshot returns | Evaluate as a new baseline, not a replayed alert |
| terminal-unseen | Explicit read with fresh known terminal turn | acknowledged; remove immediately |
| Any known chat | Explicit read during invalidity/project pause, with a previously known terminal turn | Store exact-turn read intent only; no acknowledgement yet |
| Pending read intent | Fresh terminal confirms the same turn | acknowledged; clear pending intent |
| Pending read intent | Different turn or active runtime confirmed | Discard intent; leave new completion eligible |
| Pending read intent | Explicit unread | Cancel read intent; rearm known matching acknowledgement now or on fresh confirmation |
| acknowledged | Repeated stale unread snapshot for same turn | Remain acknowledged |
| acknowledged | New terminal turn is unread | terminal-unseen |
| any tracked | Archive event, confirmed local archive/deletion | hidden; remove entry, retries, notices, read intents and own follow |
| hidden | Late snapshot/read/follower event | Remain hidden |
| hidden | Explicit unarchive or confirmed active local row | Clear retirement, invalidate and refetch before display |

Local deletion checks query only known local IDs. Missing remote/cloud summaries or a failed/locked database read cannot prove deletion. A missing local row requires prior persistence evidence or a legacy terminal entry. Archived context is retained for restoration; deleted task metadata is not retained.

Read intent is scoped by host and exact turn ID. It survives payload handoff in memory, but is not a new durable task snapshot. A cold crash before confirmation does not promise to retain an unconfirmed read edge; fresh desktop snapshots still determine state. An acknowledgement already saved in slots does survive restart.

Numbering: sort retained entries by first-seen time, then emit `1…N` independently per visible project. Historical allocation fields do not become displayed ordinals. Removing/reordering visible rows never changes chat IDs. Regression: [test_read_sync.py](../tests/test_read_sync.py), [test_archive_sync.py](../tests/test_archive_sync.py), [test_remote.py](../tests/test_remote.py), `StateMachineTests` in [test_state_machines.py](../tests/test_state_machines.py).

### Project identity resolution is separate from chat visibility

Ownership: `DesktopMetadata.poll`, `DesktopMetadata.identities` and `WatchRegistry.update`. States are `unresolved-project`, `chat-bucket`, `resolved-local` and `resolved-remote`.

| From | Metadata / event | Result |
| --- | --- | --- |
| Unresolved | Project workspace without a usable registered descriptor/name | Per-chat pending project; do not invent a name from a directory basename |
| Unresolved | Non-project workspace without a registered assignment | Local or host-scoped Chat bucket |
| Any | Local assignment to a named local project | resolved-local; preserve extracted name/appearance |
| Any | Named remote descriptor on the same host | resolved-remote; use explicit remote assignment first, otherwise longest registered parent path for project workspaces |
| Resolved | Project rename/icon change | Update presentation without changing chat identity or manufacturing a task alert |
| Resolved / pending | Assignment resolves or moves to another project | Regroup the same chat key; allocate the target project's historical slot and recompute its visible ordinals |
| Any | Metadata file unavailable/malformed | Retain last successfully read context; do not infer read/deletion from absence |

Only known stream identities are reconciled; opaque account/read buckets are change signals, not discovery inventories. Host-scoped project identity prevents equal local/remote IDs or root names from merging. Regression: [test_adapter.py](../tests/test_adapter.py), [test_remote.py](../tests/test_remote.py), [test_state.py](../tests/test_state.py).

## 7. Scope controls, handoff and aggregate entry

Ownership: `Plugin.control`, `set_project_updates`, `publish`, native `MonitorState.summaryStatus`, [MenuBarPresentation](../native/Sources/MenuBar/MenuBarPresentation.swift).

| Control state | Input | Result |
| --- | --- | --- |
| Global enabled | Disable | Disconnect observer, cancel retries/notices, hide project capsules; retain global recovery entry and saved project choices/records |
| Global paused | Enable | Start new observer session and bounded snapshot handoff; preserve IDs and slots |
| Project enabled | Disable project | Freeze its saved entries; cancel its retry/notice scope; remove only Signal's follows; leave other projects live |
| Project paused | Enable project | Invalidate frozen source; await fresh snapshots for up to five seconds; seed baseline silently |
| Resuming project | Partial fresh snapshots | Gate the whole project's capsule until handoff settles; expose syncing rows in controls without stale elapsed/seen actions |
| Resuming project | Deadline expires | End loading gate; show genuine unknown/unavailable state while recovery continues |
| Expanded | Compact on | Remove project status items; keep global item; global panel shows projects plus detailed chat rows |
| Compact | Compact off | Recreate project items to the left of the existing global item; global panel shows project controls only |
| Any presentation mode | Alert preference changes | No effect on capsule visibility or aggregate priority |

Aggregate color uses the shared status priority, excludes paused projects, and distinguishes syncing from task unknown. Adapter attention does not override an already known failed/approval/input task. No task color is shown while globally paused. Regression: [test_global_controls.py](../tests/test_global_controls.py), [test_project_controls.py](../tests/test_project_controls.py), native [AdapterHealthTests](../native/Tests/MenuBarTests/AdapterHealthTests.swift), [GlobalHandoffTests](../native/Tests/MenuBarTests/GlobalHandoffTests.swift).

## 8. Automatic alerts and six-second native notices

Ownership: [NoticeTracker](../server/notifications.py), `Plugin.emit_notice`, native [StatusNotice](../native/Sources/MenuBar/StatusNotice.swift).

| Alert tracking state | Event | Result |
| --- | --- | --- |
| No baseline | First valid sample / recovery / unpause | Store phase silently |
| Baseline | Valid phase changes to an enabled alert type | Candidate; coalesce to one card per publish |
| Baseline | Disabled phase edge | Advance baseline, but do not replace an eligible concurrent candidate |
| Any | Unknown/invalid sample | No fabricated task edge |
| Candidate | UI not ready | Keep latest pending card; a later eligible edge replaces it |
| Pending | Complete write to current renderer succeeds | Delivered to pipe; authorize only this automatic notice's `(noticeId, chatKey)` |
| Any | Global/project/phase disabled, owner loss, retirement or disconnect | Cancel affected pending/click authorization; native state refresh dismisses disabled cards |
| Delivered | User clicks body with matching current IDs | Open corresponding `codex://` chat once; do not approve, send or mark seen implicitly |
| Delivered | Close / expiry / replacement | Close that notice; old receipt cannot clear a newer click target |

Concurrent eligible edges intentionally coalesce: the last eligible edge in the processing order wins; this is not a durable queue of every intermediate task event. Unselected edges still advance their baselines so enabling a preference later does not replay history.

Native notice states are `hidden`, `entering`, `holding`, `exiting`. A new ID replaces the card and starts a fresh six-second deadline. Duplicate last ID does not restart time. An expiry only acts on its active ID; a close completion only hides the matching, still-inactive card. Body and × presses must begin and end on the same notice and hit region. Language/title/ordinal refreshes retain the original event's phase and deadline, even when the completed chat leaves the registry. Diagnostic cards cannot open chats. Notices do not activate the app or take keyboard focus.

Pipe delivery is best effort, not a native display receipt or durable alarm guarantee. Automatic notices are not replayed after cold restart/reconnect. Regression: [test_notifications.py](../tests/test_notifications.py), `test_selected_alert_is_not_lost_behind_a_simultaneous_disabled_edge`, native [NoticeTests](../native/Tests/MenuBarTests/NoticeTests.swift).

## 9. Native status items, popover and settings route

Ownership: [Controller](../native/Sources/MenuBar/Controller.swift), [CapsuleView](../native/Sources/MenuBar/CapsuleView.swift), [ProjectPopover](../native/Sources/MenuBar/ProjectPopover.swift), [PopoverMotion](../native/Sources/MenuBar/PopoverMotion.swift), [MotionDriver](../native/Sources/MenuBar/Motion.swift).

| Machine | From + event | To / invariant |
| --- | --- | --- |
| Native application | Prelaunch + state | Buffer latest model; launch creates interface once; stdin EOF terminates child |
| Status item | Absent + desired project | Create item and enter; global item is created first so it stays at the right edge of this group |
| Status item | Visible + no longer desired | Exiting; immediately disable interaction; remove after current exit completes |
| Status item | Exiting + project desired again | Reverse from current width/opacity; cancel old removal; identity/view guard prevents stale deletion |
| Badges/rows | Add/remove/status change | Animate from current geometry/color; removed targets lose input/accessibility before visual exit finishes |
| Popover intent | Closed + capsule click | Open, increment revision, attach anchor, install monitors and animate in |
| Popover intent | Open + same capsule click | Closed, increment revision, disable input/remove monitors; animate out before ordering out |
| Popover intent | Closing + same capsule click | Reopen from current position and velocity; stale close completion is replaced |
| Popover anchor | Click different capsule | Close old attachment immediately, bind new content/anchor, then open |
| Focus guard | Deferred focus loss | Close only if intent revision still matches, panel is not key, no anchor gesture and no active emoji selection |
| Settings route | List + settings | Disable body during fade-out; swap/resize to settings; fade in; enable only live controls; settings icon becomes back |
| Settings route | Settings + back / interrupted reversal | Retarget current presentation; route revision rejects stale swap/enable callbacks; preserve per-route scroll position |
| Native motion | Running + new target | Cancel old completion and interpolate from current presentation; popover spring also retains velocity |
| Reduced motion | Any transition | Keep appropriate fade/deadline semantics, remove spatial bounce/sliding; keyboard open/close is immediate |

Transient input state also matters: a capsule badge press stores its chat ID and opens only if release still hits that ID. Status-button pointer actions are not allowed to toggle a second time on release. Notice press state additionally stores its notice ID and close/body region. Native controls check current live IDs before enabling accessibility targets.

Regression: native [MenuBarPresentationTests](../native/Tests/MenuBarTests/MenuBarPresentationTests.swift), [PopoverMotionTests](../native/Tests/MenuBarTests/PopoverMotionTests.swift), [ProjectControlTests](../native/Tests/MenuBarTests/ProjectControlTests.swift), [ResumeColorTests](../native/Tests/MenuBarTests/ResumeColorTests.swift), [GridContractTests](../native/Tests/MenuBarTests/GridContractTests.swift). These existing guards held under the reviewed interruption paths; no native rewrite was needed for this audit.

## 10. Emoji selection and interface language

| Machine | From + event | To / invariant |
| --- | --- | --- |
| Emoji | Idle + icon click | Choosing; activate owning panel/application and establish this button's text-input context |
| Emoji | Choosing + application activation | Present system palette once, only after input context is ready |
| Emoji | Choosing + valid single grapheme insertion | Commit emoji, clear observer/marked text, emit preference event |
| Emoji | Choosing + invalid insertion | No preference change |
| Emoji | Choosing + Esc/panel dismiss | Idle; detach activation observer and discard marked text |
| Language | Valid explicit `zh-CN` / `zh-Hans` | Chinese interface |
| Language | Other locale, automatic or absent | English interface |
| Language | Unreadable/malformed configuration | Retain last valid selection and expose language error metadata; retry polling |

The palette targets its native icon button, not a hidden text field or the front Codex chat. Names extracted from Codex are never translated. Source: [EmojiPickerButton](../native/Sources/MenuBar/EmojiPickerButton.swift), [localization.py](../server/localization.py). Regression: native [EmojiDrawingTests](../native/Tests/MenuBarTests/EmojiDrawingTests.swift), [LocalizationTests](../native/Tests/MenuBarTests/LocalizationTests.swift), Python [test_localization.py](../tests/test_localization.py).

## 11. Command delivery and diagnostic exercises

Ownership: [control.py](../server/control.py), `Plugin.consume_commands`, [resume_probe.py](../server/resume_probe.py).

| From | Event | To / contract |
| --- | --- | --- |
| Created | Atomic per-ticket file write | Queued; simultaneous clients cannot overwrite each other |
| Queued | Primary scans valid enum requests | Claim up to 16 in timestamp/name order by removing each queued file before execution |
| Claimed | Action applied and result written | Receipt with acceptance/readiness facts for that nonce |
| Queued / claimed | Caller times out | Unconfirmed: may still be queued, may have executed, or may have been claimed before a crash; inspect actual status before retry |
| Reload action | Host replacement | Persist handoff and receipt while retaining MCP queue; subsequent queued commands remain independent |
| Diagnostic project exercise | Initial → off → resume → first-ready → rapid-off → rapid-resume → second-ready | Complete only after two fresh recoveries |
| Diagnostic exercise | User interaction, control change, disconnect, missing project or 13-second timeout | Abort, restore only the project preference owned by the exercise, record result |
| Native menu-layout exercise | Expanded → collapsed → expanding → interrupted collapse/expand → expanded again | Use a temporary presentation override only; completion/user cancellation clears it and restores the latest preference |
| Native popover exercise | Open → focus-loss/close → rapid open/close/reopen → final close | Use only plugin-owned handlers; a completion guard rejects stale scheduled steps; four-second deadline ends capture |

The native exercise owner and guards are in [MenuController+Diagnostics](../native/Sources/MenuBar/MenuController+Diagnostics.swift). Offline [NativePreview](../native/Sources/MenuBar/NativePreview.swift) renders fictional input and a finite animation timeline; it does not own desktop subscriptions or persist user preferences.

Command delivery is not an exactly-once transaction across crashes. Enable/disable set an explicit preference and can be retried after checking current state; a timeout is never described as proof of successful execution or guaranteed queue retention. Diagnostics require explicit development capture mode and are not run against user conversations by the regression suite. Regression: [test_control.py](../tests/test_control.py), [test_resume_probe.py](../tests/test_resume_probe.py), `CommandReceiptTests`.

## Confirmed issues, ordered by impact

The IDs below are local audit issue groups, not claims that GitHub issues were opened. Each group records a reachable baseline failure, its fix and an executable regression. P1 can corrupt current task presentation or disable the service; P2 loses expected tracking/alert behavior or installation progress; P3 misreports recovery state.

### SM-01 · P1 · A disconnected owner can replace its replacement — fixed

Evidence: baseline [main.py:406](https://github.com/Mnagalah/codex-signal/blob/364ab0e2716bba6749b1b083320786b213fbd90b/server/main.py#L406) intersected offline owners with current state owners. `A disconnect → B snapshot → delayed A snapshot` removed A's fence and accepted A as authoritative again. An owner disconnected before its first observed snapshot was not fenced at all. This can restore obsolete completion/approval state and interfere with alert baselines (I2–I3).

Fix: retain every disconnected-owner tombstone for the IPC session; clear only on that owner's explicit reconnect or a new initialized session. Both local and remote keys use the same guard.

Regression: `test_offline_owner_stays_fenced_after_replacement_snapshot`, `test_disconnected_owner_cannot_publish_its_first_late_snapshot`; existing reconnect and unrelated-owner tests remain applicable.

### SM-02 · P1 · Renderer failure has no self-recovery — fixed

Evidence: baseline [launch](https://github.com/Mnagalah/codex-signal/blob/364ab0e2716bba6749b1b083320786b213fbd90b/server/main.py#L194) raised an unhandled `OSError` out of the production loop. After [UI EOF](https://github.com/Mnagalah/codex-signal/blob/364ab0e2716bba6749b1b083320786b213fbd90b/server/main.py#L984), the primary remained elected with no renderer; election's early return prevented relaunch. Deterministic baseline tests produced `OSError: launch failed` and zero replacement `Popen` calls after EOF (I4).

Fix: primary-owned supervision with bounded backoff, child retirement, stale-source rejection, fresh full-state delivery and readiness reset. Launch/UI faults no longer relinquish the backend's identities, connection or primary ownership.

Regression: `RendererRecoveryTests`, particularly both `test_real_service_loop_*` tests and stable-ready/backoff/stale-callback coverage.

### SM-03 · P1 · Channel backpressure blocks all recovery and controls — fixed

Evidence: baseline [desktop.py:46](https://github.com/Mnagalah/codex-signal/blob/364ab0e2716bba6749b1b083320786b213fbd90b/server/desktop.py#L46) used blocking `sendall`; renderer writes also ran synchronously without a bound. Real private socketpair and pipe peers that stopped reading left the writing worker blocked beyond the test deadline. While blocked, the primary cannot process reads, pause, reconnect or MCP requests. A retirement-time follow failure also escaped `hide_thread` and could terminate the loop (I9).

Fix: shared deadline-bounded nonblocking writes; idle-safe receive waits; discard failed channels, including their partial frames; recover renderer or observer session independently. Retirement and paused-project cleanup handle transport failure without undoing their local changes.

Regression: `IPCWriteTests`, `test_nonreading_renderer_does_not_block_state_service`, `test_transport_failure_while_retiring_a_chat_keeps_the_retirement`; fragmented/partial-frame and host-aware unfollow tests use real transport pairs.

### SM-04 · P2 · Read edges disappear during invalidity or project pause — fixed

Evidence: baseline read handlers discarded `hasUnreadTurn=false` during [project pause](https://github.com/Mnagalah/codex-signal/blob/364ab0e2716bba6749b1b083320786b213fbd90b/server/main.py#L376) and only acknowledged a [currently valid terminal sample](https://github.com/Mnagalah/codex-signal/blob/364ab0e2716bba6749b1b083320786b213fbd90b/server/main.py#L425). `known terminal A → revision gap/pause → user reads A → stale-unread fresh A snapshot` kept/recreated the reminder. Baseline regression found no acknowledgement after confirmation on both hosts (I5).

Fix: keep exact-turn read intent separately, including hot handoff; acknowledge only after fresh terminal confirmation of the same turn. Unread cancels it; a different/active turn discards it; retirement clears it. Invalid samples still cannot acknowledge immediately.

Regression: read-during-gap, paused-project, different-turn, unread-reversal and reload tests in `StateMachineTests`, plus all existing read-sync tests.

### SM-05 · P2 · Excluded chats leave ghost capsules and stale alert baselines — fixed

Evidence: baseline [state.py:235](https://github.com/Mnagalah/codex-signal/blob/364ab0e2716bba6749b1b083320786b213fbd90b/server/state.py#L235) skipped ephemeral/child states without removing an existing registry entry. A valid metadata patch on a previously visible chat left its old row visible. Notice tracking similarly retained its old phase across exclusion (I6).

Fix: remove excluded entries, forget their notice subject/phase and cancel undelivered cards. A subsequent eligible root snapshot establishes a baseline.

Regression: `test_visible_chat_becoming_excluded_leaves_no_ghost_or_notice_baseline` and `test_excluded_chat_cancels_undelivered_notice`, for both ephemeral and parent-thread metadata.

### SM-06 · P2 · A disabled concurrent alert suppresses an enabled one — fixed

Evidence: baseline [main.py:602–603](https://github.com/Mnagalah/codex-signal/blob/364ab0e2716bba6749b1b083320786b213fbd90b/server/main.py#L602) filtered preferences after `NoticeTracker` selected the last edge. In one publish, `A → input (enabled), B → running (disabled)` selected B, discarded it, and permanently advanced A's baseline without emitting its card (I8).

Fix: advance all baselines, but filter eligibility before coalescing candidates. This preserves the one-card design and does not replay old disabled phases when preferences change.

Regression: `test_selected_alert_is_not_lost_behind_a_simultaneous_disabled_edge`; existing concurrent coalescing and six-second native notice tests remain unchanged.

### SM-07 · P2 · Concurrent first setup races on immutable payload publication — fixed

Evidence: two private-profile installers can both see a missing version directory, stage it, then race at baseline [install.py:183](https://github.com/Mnagalah/codex-signal/blob/364ab0e2716bba6749b1b083320786b213fbd90b/scripts/install.py#L183). A barrier-controlled probe produced one success and one `OSError: Directory not empty`; the regression observed two simultaneous publication attempts. Subsequent catalogue/CLI/cache preservation operations also lacked a single owner (I10).

Fix: hold one separate, private, profile-scoped installation lock across registration and cache preservation. A second setup rechecks/reuses the completed immutable payload after acquiring the lock. The live monitor lock is not involved.

Regression: `ConcurrentSetupTests.test_simultaneous_setups_share_one_complete_immutable_payload` in [test_setup.py](../tests/test_setup.py).

### SM-08 · P3 · Timeout promises a queue entry that may no longer exist — fixed

Evidence: [control.py:76](https://github.com/Mnagalah/codex-signal/blob/364ab0e2716bba6749b1b083320786b213fbd90b/server/control.py#L76) removes a request before execution, but its [timeout message](https://github.com/Mnagalah/codex-signal/blob/364ab0e2716bba6749b1b083320786b213fbd90b/server/control.py#L124) claimed it had been retained. A claim followed by failure/no receipt reaches that contradiction.

Fix: report unconfirmed delivery and tell callers to check actual state before retrying. No exactly-once promise or speculative persistent transaction layer was added.

Regression: `CommandReceiptTests.test_claimed_request_without_receipt_is_not_reported_as_safely_queued`.

## Verification and maintenance

The audit used fictional IDs and private temporary profiles. Baseline failures were reproduced against an exported copy of the baseline commit, not by modifying the installed plugin or real chat state. Regression definitions live in the repository; they are the durable reproduction evidence, rather than private machine logs.

Run the maintained checks:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/generate-layout.py --check
swift test --disable-sandbox --no-parallel --package-path native
```

Verified source candidate: **176 Python tests (23 added regressions)** and **79 native tests** passed. Generated-layout consistency, modified documentation references, `git diff --check` and the public package inventory/privacy scan passed; the inventory includes this map, the transport helper and the regression tests. Native tests exercise AppKit and both motion modes; they do not substitute for a fresh-Mac installation or quitting/reopening a user's Codex session. Hot-update validation on an existing Mac is recorded separately from the synthetic audit. No Codex restart/force-quit, new Release publication or tag change is part of the candidate rollout.

### Existing-Mac hot-update validation

The unreleased 0.2.10 candidate was installed under the existing plugin identity and hot-loaded without restarting Codex. A fresh installer nonce check confirmed the expected installed/enabled version, desktop health `ready` and native renderer readiness. Both local and connected remote sources were present after recovery.

The before/after comparison retained chat identities, historical slots, first-seen values, acknowledgements, retirement markers, settings and the pinned interpreter. Actual menu capsules and the global popover were inspected; native host attachment and slot dimensions matched. A single termination of Signal's own renderer recovered automatically in about 1.4 seconds while the backend and desktop host processes remained unchanged, with records and settings preserved. No owner task or chat was stopped or modified.

This is existing-device acceptance of hot replacement and renderer recovery, not a fresh-install or Codex quit/reopen test. No tag, Release or release asset was created or changed. Public publication remains on hold.

For a state-machine change, update this file in the same change: name its owner and stored/derived state, adjust the transition/priority table, explain any changed invariant, and add the shortest regression reaching the faulty interleaving. Keep issue status at the level demonstrated: source fixed, automated checks passed, installed-device acceptance, and released are different milestones. The candidate uses internal version 0.2.10; public release remains on hold pending explicit authorization and the remaining device checks; do not replace the published v0.2.9 payload in place.
