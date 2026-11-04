import AppKit

@MainActor
final class MenuController {
    private var items: [String: NSStatusItem] = [:]
    private var views: [String: CapsuleView] = [:]
    private var order: [String] = []
    private var exiting: Set<String> = []
    private var latestState:MonitorState?
    private var compactPresentationOverride:Bool?
    private var captureScheduled = false
    private var exercising = false
    private var cancelMenuExercise:(()->Void)?
    private let popover = ProjectPopover(onEvent: MenuController.send)
    private let notice = StatusNoticeController(onReceipt: MenuController.sendNoticeReceipt, onOpen: MenuController.sendNoticeOpen)
    private var monitoring = true
    private var language = InterfaceLanguage.chinese
    private var pausedProjects: Set<String> = []
    private var notificationStates = Set(Layout.specification.alertTypes)

    func apply(_ state: MonitorState) {
        latestState=state
        let compact=compactPresentationOverride ?? state.compactMenuBar ?? false
        let enabled = state.enabled ?? true
        let language = state.language
        monitoring = enabled; self.language = language
        let controls = state.projectControls ?? state.projects
        notificationStates = Set(state.notificationStates ?? Layout.specification.alertTypes)
        pausedProjects = Set(controls.filter { $0.updatesEnabled == false }.map(\.id))
        notice.refresh(language: language, projects: state.projects, enabled: enabled, pausedProjects: pausedProjects, notificationStates: notificationStates)
        let monitored = enabled ? state.projects : []
        var global = Project(id: "global-control", name: language.text("statusTitle"), markerType: "emoji", marker: state.statusEmoji ?? EmojiPickerButton.defaultEmoji, threads: [], kind: "global-control")
        global.summaryStatus = state.summaryStatus
        global.summaryCount = enabled ? controls.filter { $0.updatesEnabled != false }.reduce(0) { $0 + $1.threads.count } : 0
        global.syncing = controls.contains { $0.syncing == true && $0.updatesEnabled != false }
        let projects = MenuBarPresentation.creationOrder(global:global,projects:monitored,compact:compact)
        let activeIDs = Set(projects.map(\.id))
        for id in order where !activeIDs.contains(id) {
            guard !exiting.contains(id), let view = views[id] else { continue }
            exiting.insert(id)
            if popover.projectID == id { popover.dismiss() }
            view.setVisible(false) { [weak self, weak view] in
                guard let self, self.exiting.contains(id), self.views[id] === view else { return }
                if let item = self.items.removeValue(forKey: id) { NSStatusBar.system.removeStatusItem(item) }
                self.views.removeValue(forKey: id)
                self.order.removeAll { $0 == id }
                self.exiting.remove(id)
            }
        }
        Main.trace("querying status bar")
        let height = NSStatusBar.system.thickness
        Main.trace("status bar height \(height)")
        for project in projects {
            let detail = !enabled ? language.text("monitorDisabled") : (global.syncing == true ? language.text("syncing") : state.connected && state.projects.isEmpty ? language.text("noChats") : state.detail)
            if let view = views[project.id] {
                exiting.remove(project.id)
                view.monitorEnabled = project.isStatusControl ? enabled : (project.updatesEnabled ?? true)
                view.globalEnabled = enabled; view.projectControls = controls
                view.compactMenuBar = compact; view.notificationStates = notificationStates
                view.statusEmoji = state.statusEmoji ?? EmojiPickerButton.defaultEmoji
                view.update(project, detail: detail, language: language)
                popover.update(from: view)
            } else {
                Main.trace("creating native status item")
                let item=NSStatusBar.system.statusItem(withLength:1)
                // The actual button can be shorter than the status-bar metric.
                // Start in its real geometry instead of snapping on attachment.
                let hostHeight=item.button?.bounds.height ?? height
                Main.trace("creating capsule view")
                let view = CapsuleView(project: project, height: hostHeight, detail: detail, language: language, onEvent: { [weak self] event, id in
                    self?.cancelMenuExercise?()
                    if event == "open" { self?.popover.dismiss(animated: NSApp.currentEvent?.type != .keyDown) }
                    Self.send(event, id)
                })
                view.monitorEnabled = project.isStatusControl ? enabled : (project.updatesEnabled ?? true)
                view.globalEnabled = enabled; view.projectControls = controls
                view.compactMenuBar = compact; view.notificationStates = notificationStates
                view.statusEmoji = state.statusEmoji ?? EmojiPickerButton.defaultEmoji
                if project.id != global.id { view.setVisible(false, animated: false) }
                item.length=view.frame.width
                // Per-project saved system positions can restore a project to
                // the right of the anchor. Stop restoring those old positions;
                // their preference records remain intact for recovery. Chat
                // IDs, numbering and plugin settings do not change.
                if let button = item.button { StatusItemHost.configure(button, content: view) }
                items[project.id] = item
                views[project.id] = view
                order.append(project.id)
                view.onWidthChange = { [weak self, weak item] width in
                    guard let item,abs(item.length-width)>0.01 else { return }
                    item.length=width;self?.popover.reposition()
                }
                view.onShowPopover = { [weak self] view, keyboard in
                    self?.cancelMenuExercise?()
                    self?.popover.toggle(from: view, keyboard: keyboard)
                }
                view.setVisible(true,animated:project.id != global.id)
            }
        }
        Self.send("ready", nil)
        if !captureScheduled, !state.projects.isEmpty,
           let directory = ProcessInfo.processInfo.environment["CODEX_MENU_UI_CAPTURE_DIR"] {
            captureScheduled = true
            // Development-only capture of our own live status views, not the
            // Codex window or the desktop. No screen-control APIs are used.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { [weak self] in
                self?.captureOwnViews(in: directory)
            }
        }
    }

    func receiveNotice(_ payload: NoticePayload) {
        guard monitoring, !pausedProjects.contains(payload.project.id), payload.source != "automatic" || notificationStates.contains(payload.chat.status) else { return }
        let screen = views[payload.project.id]?.window?.screen ?? NSScreen.main
        notice.show(payload, language: language, screen: screen)
    }

    nonisolated private static func sendNoticeOpen(_ value: NoticePayload) {
        let event = ["event": "notice_open", "noticeId": value.id, "threadId": value.chat.id]
        guard let data = try? JSONEncoder().encode(event) else { return }
        FileHandle.standardOutput.write(data + Data([10]))
    }

    nonisolated private static func sendNoticeReceipt(_ receipt: NoticeReceipt) {
        guard let data = try? JSONEncoder().encode(receipt) else { return }
        FileHandle.standardOutput.write(data + Data([10]))
    }

    private func captureOwnViews(in directory: String) {
        let root = URL(fileURLWithPath: directory, isDirectory: true)
        try? FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        var evidence: [[String: Any]] = []
        for (id, view) in views {
            let safe = id.replacingOccurrences(of: "[^A-Za-z0-9_-]", with: "-", options: .regularExpression)
            if let bitmap = view.bitmapImageRepForCachingDisplay(in: view.bounds) {
                view.cacheDisplay(in: view.bounds, to: bitmap)
                try? bitmap.representation(using: .png, properties: [:])?.write(to: root.appendingPathComponent(safe + ".png"))
            }
            evidence.append(["project": view.project.name, "windowAttached": view.window != nil,
                             "windowVisible": view.window?.isVisible ?? false,
                             "occlusionVisible": view.window?.occlusionState.contains(.visible) ?? false,
                             "width": view.frame.width, "height": view.frame.height,
                             "screenFrame": view.window.map { LayoutDiagnostics.rect($0.convertToScreen(view.convert(view.bounds, to: nil))) } ?? [:],
                             "kind": view.project.kind ?? "project",
                             "numberedChats": view.project.threads.count,
                             "contentTargetWidth": view.layout.width,
                             "itemLength": items[id]?.length ?? 0,
                             "buttonFrame": NSStringFromRect(items[id]?.button?.frame ?? .zero),
                             "viewFrameInButton": NSStringFromRect(view.frame),
                             "hosting": "transparent-native-button", "grid": LayoutDiagnostics.capsule(view)])
        }
        MenuStripCapture.write(views:Array(views.values),directory:root)
        if let data = try? JSONSerialization.data(withJSONObject: evidence, options: [.prettyPrinted, .sortedKeys]) {
            try? data.write(to: root.appendingPathComponent("live-views.json"), options: .atomic)
        }
    }

    // An explicit diagnostic request to our renderer, not an OS event injection.
    // Uses the real status item/window and production popup; never opens a chat,
    // marks anything seen, changes the monitor switch or alters saved numbering.
    func inspectLayout(requestID: String) {
        guard requestID.range(of: "^[0-9a-f]{32}$", options: .regularExpression) != nil,
              let directory = ProcessInfo.processInfo.environment["CODEX_MENU_UI_CAPTURE_DIR"],
              let view = popover.projectID.flatMap({ views[$0] }) ?? views["global-control"] ?? order.compactMap({ views[$0] }).first else { return }
        captureOwnViews(in: directory)
        popover.inspect(from: view, directory: directory, requestID: requestID) { [weak self] popup in
            guard let self else { return }
            let report: [String: Any] = ["requestId": requestID, "contract": LayoutDiagnostics.contract,
                "capsules": self.order.compactMap { self.views[$0] }.map(LayoutDiagnostics.capsule), "popup": popup]
            let path = URL(fileURLWithPath: directory).appendingPathComponent("inspection-" + requestID + ".json")
            if let data = try? JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]) {
                try? data.write(to: path, options: .atomic)
            }
        }
    }

    func chooseEmoji(requestID:String) {
        guard requestID.range(of:"^[0-9a-f]{32}$",options:.regularExpression) != nil,
              let directory=ProcessInfo.processInfo.environment["CODEX_MENU_UI_CAPTURE_DIR"],let view=views["global-control"] else { return }
        popover.chooseEmoji(from:view,directory:directory,requestID:requestID)
    }

    func inspectSettings(requestID:String) {
        guard requestID.range(of:"^[0-9a-f]{32}$",options:.regularExpression) != nil,
              let directory=ProcessInfo.processInfo.environment["CODEX_MENU_UI_CAPTURE_DIR"],let view=views["global-control"] else { return }
        captureOwnViews(in:directory)
        popover.inspectSettings(from:view,directory:directory,requestID:requestID)
    }

    // Presentation-only round trip through the production apply path. No
    // settings, IPC subscription, chat identity or local seen state is changed.
    func exerciseMenuLayout(requestID:String) {
        guard requestID.range(of:"^[0-9a-f]{32}$",options:.regularExpression) != nil,
              let directory=ProcessInfo.processInfo.environment["CODEX_MENU_UI_CAPTURE_DIR"] else { return }
        let path=URL(fileURLWithPath:directory).appendingPathComponent("menu-layout-"+requestID+".json")
        guard !exercising,!popover.isShown,latestState?.projects.isEmpty == false,let original=items["global-control"] else {
            if let data=try? JSONSerialization.data(withJSONObject:["requestId":requestID,"completed":false,"reason":"popover-open-or-no-live-projects"]) { try? data.write(to:path) };return
        }
        exercising=true
        let began=CACurrentMediaTime()
        var steps:[[String:Any]]=[],samples:[[String:Any]]=[],finished=false
        let sampler=MotionDriver()
        @MainActor func snapshot(_ label:String) -> [String:Any] {
            var result:[String:Any]=["step":label,"time":CACurrentMediaTime()-began,"sameGlobalHost":items["global-control"] === original,
                "compactPresentation":compactPresentationOverride ?? latestState?.compactMenuBar ?? false]
            result["views"]=order.compactMap { id -> [String:Any]? in
                guard let view=views[id],let window=view.window else { return nil }
                return ["id":id,"kind":view.project.kind ?? "project","frame":LayoutDiagnostics.rect(window.convertToScreen(view.convert(view.bounds,to:nil))),
                    "occlusionVisible":window.occlusionState.contains(.visible),"motion":view.visibilitySnapshot,
                    "visual":LayoutDiagnostics.capsule(view)]
            }
            return result
        }
        @MainActor func setCompact(_ value:Bool?) {
            compactPresentationOverride=value
            if let latestState { apply(latestState) }
        }
        @MainActor func mark(_ label:String) {
            steps.append(snapshot(label))
            if ["expanded","collapsed","expanded-again","restored"].contains(label) {
                captureOwnViews(in:directory)
                let root=URL(fileURLWithPath:directory),source=root.appendingPathComponent("live-menu-strip.png")
                let target=root.appendingPathComponent("menu-layout-"+requestID+"-"+label+".png")
                if let data=try? Data(contentsOf:source) { try? data.write(to:target,options:.atomic) }
            }
        }
        @MainActor func finish(cancelled:Bool=false) {
            guard !finished else { return };finished=true;sampler.stop();cancelMenuExercise=nil
            setCompact(nil);mark("restored")
            exercising=false;captureOwnViews(in:directory)
            let report:[String:Any]=["requestId":requestID,"completed":!cancelled,"input":"plugin-owned-presentation-override","settingsChanged":false,
                "steps":steps,"samples":samples,"sameGlobalHost":items["global-control"] === original,"menuMotionSeconds":Layout.specification.menuMotion.transition]
            if let data=try? JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]) { try? data.write(to:path,options:.atomic) }
        }
        cancelMenuExercise={ finish(cancelled:true) }
        setCompact(false)
        sampler.start(duration:3,frame: { _ in
            if !finished && samples.count<180 { samples.append(snapshot("frame")) }
        })
        DispatchQueue.main.asyncAfter(deadline:.now()+0.35) {
            guard !finished else { return };mark("expanded");setCompact(true);mark("collapse-begin")
            DispatchQueue.main.asyncAfter(deadline:.now()+0.30) {
                guard !finished else { return };mark("collapsed");setCompact(false);mark("expand-begin")
                DispatchQueue.main.asyncAfter(deadline:.now()+0.06) {
                    guard !finished else { return };mark("before-interrupt-collapse");setCompact(true);mark("after-interrupt-collapse")
                    DispatchQueue.main.asyncAfter(deadline:.now()+0.06) {
                        guard !finished else { return };mark("before-interrupt-expand");setCompact(false);mark("after-interrupt-expand")
                        DispatchQueue.main.asyncAfter(deadline:.now()+0.30) {
                            guard !finished else { return };mark("expanded-again");setCompact(nil)
                            DispatchQueue.main.asyncAfter(deadline:.now()+0.30) { finish() }
                        }
                    }
                }
            }
        }
    }

    func exerciseToggle(requestID: String) {
        guard requestID.range(of: "^[0-9a-f]{32}$", options: .regularExpression) != nil,
              let directory = ProcessInfo.processInfo.environment["CODEX_MENU_UI_CAPTURE_DIR"],
              !exercising, !popover.isShown,
              let view = order.compactMap({ views[$0] }).first(where: { $0.project.id != "control" }),
              let window = view.window else { return }
        exercising = true
        var steps: [[String: Any]] = [], samples: [[String: Any]] = [], finished = false
        let began = CACurrentMediaTime()
        popover.onMotionSample = { sample in
            if samples.count < 240 { samples.append(sample.merging(["time": CACurrentMediaTime() - began]) { _, new in new }) }
        }
        func capture(_ label: String) { steps.append(popover.motionSnapshot.merging(["step": label]) { _, new in new }) }
        func click() {
            let point = view.convert(CGPoint(x: view.layout.name.isEmpty ? view.layout.icon.midX : view.layout.name.midX, y: view.layout.centerY), to: nil)
            guard let down = NSEvent.mouseEvent(with: .leftMouseDown, location: point, modifierFlags: [],
                timestamp: ProcessInfo.processInfo.systemUptime, windowNumber: window.windowNumber,
                context: nil, eventNumber: 1, clickCount: 1, pressure: 1),
                  let up = NSEvent.mouseEvent(with: .leftMouseUp, location: point, modifierFlags: [],
                timestamp: ProcessInfo.processInfo.systemUptime, windowNumber: window.windowNumber,
                context: nil, eventNumber: 2, clickCount: 1, pressure: 0) else { return }
            // Calls only our own native handlers, never posts an OS mouse event.
            view.mouseDown(with: down); view.mouseUp(with: up)
        }
        func finish(_ timedOut: Bool = false) {
            guard !finished else { return }; finished = true
            exercising = false; popover.onMotionSample = nil
            let report: [String: Any] = ["requestId": requestID, "project": view.project.name,
                "contract": LayoutDiagnostics.contract, "timedOut": timedOut,
                "steps": steps, "samples": samples, "final": popover.motionSnapshot,
                "input": "plugin-owned-native-handlers"]
            if let data = try? JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]) {
                try? data.write(to: URL(fileURLWithPath: directory).appendingPathComponent("toggle-" + requestID + ".json"), options: .atomic)
            }
        }
        click(); capture("first-click-target-open")
        popover.whenSettled { [self] in
            guard !finished else { return }; capture("first-click-settled-open")
            popover.resignKeyForInspection() // The problematic real-window event order.
            click(); capture("second-click-after-resign-target-closed")
            popover.whenSettled { [self] in
                guard !finished else { return }; capture("second-click-settled-closed")
                click()
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.06) { [self] in
                    guard !finished else { return }; capture("before-rapid-close")
                    click(); capture("after-rapid-close")
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.06) { [self] in
                        guard !finished else { return }; capture("before-rapid-reopen")
                        click(); capture("after-rapid-reopen")
                        popover.whenSettled { [self] in
                            guard !finished else { return }; capture("rapid-reopen-settled-open")
                            click()
                            popover.whenSettled { guard !finished else { return }; capture("final-settled-closed"); finish() }
                        }
                    }
                }
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 4) { finish(true) }
    }

    nonisolated private static func send(_ event: String, _ threadID: String?) {
        var value = ["event": event]
        if event == "ready" {
            value["layoutSource"] = Layout.specification.source
            value["layoutVersion"] = String(Layout.specification.version)
            value["layoutEngine"] = "shared-native-grid"
        }
        if let threadID { value[event.hasPrefix("project_") ? "projectId" : event.hasPrefix("notification_") ? "status" : event == "set_status_emoji" ? "emoji" : "threadId"] = threadID }
        guard let data = try? JSONEncoder().encode(value) else { return }
        FileHandle.standardOutput.write(data + Data([10]))
    }
}
