import AppKit

@MainActor
final class MenuController {
    var items: [String: NSStatusItem] = [:]
    var views: [String: CapsuleView] = [:]
    var order: [String] = []
    private var exiting: Set<String> = []
    var latestState:MonitorState?
    var compactPresentationOverride:Bool?
    private var captureScheduled = false
    var exercising = false
    var cancelMenuExercise:(()->Void)?
    let popover = ProjectPopover(onEvent: MenuController.send)
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
        global.healthDetail = state.health?.requiresAttention == true ? state.health?.detail : nil
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
            let detail = state.presentationDetail
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
