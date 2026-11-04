import AppKit
import os

@MainActor
final class MenuApplication: NSObject, NSApplicationDelegate {
    let controller = MenuController()
    private var launched = false
    private var latest = MonitorState(connected: false, detail: "正在连接 Codex", projects: [])

    func applicationDidFinishLaunching(_ notification: Notification) {
        Main.trace("application finished launching")
        start()
    }

    func start() {
        guard !launched else { return }
        Main.trace("starting status interface")
        launched = true
        controller.apply(latest)
        Main.trace("live status items created")
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    func consume(_ state: MonitorState) {
        latest = state
        if launched { controller.apply(state) }
    }
}

@main
struct Main {
    nonisolated static func trace(_ message: String) {
        if ProcessInfo.processInfo.environment["CODEX_MENU_DEBUG"] == "1" {
            FileHandle.standardError.write(Data(("[menu-component] " + message + "\n").utf8))
        }
    }
    @MainActor
    static func main() {
        let app = NSApplication.shared
        trace("application created")
        app.setActivationPolicy(.accessory)
        trace("accessory policy set")
        if CommandLine.arguments.count == 3 && CommandLine.arguments[1] == "--preview" {
            renderPreview(to: CommandLine.arguments[2])
            return
        }
        if CommandLine.arguments.count == 3 && CommandLine.arguments[1] == "--preview-notice" {
            NativePreview.renderNotice(to: CommandLine.arguments[2])
            return
        }
        if CommandLine.arguments.count == 3 && CommandLine.arguments[1] == "--preview-settings" {
            NativePreview.render(to:CommandLine.arguments[2],settings:true);return
        }
        if CommandLine.arguments.count == 3 && CommandLine.arguments[1] == "--preview-popup" {
            NativePreview.render(to: CommandLine.arguments[2])
            return
        }
        if CommandLine.arguments.count == 3 && CommandLine.arguments[1] == "--motion-preview" {
            NativePreview.record(to: CommandLine.arguments[2])
            return
        }
        let delegate = MenuApplication()
        app.delegate = delegate
        trace("delegate installed")
        let buffer = OSAllocatedUnfairLock(initialState: Data())
        FileHandle.standardInput.readabilityHandler = { handle in
            let chunk = handle.availableData
            trace("input bytes: \(chunk.count)")
            if chunk.isEmpty {
                handle.readabilityHandler = nil
                DispatchQueue.main.async { app.terminate(nil) }
                return
            }
            let lines: [Data] = buffer.withLock { pending in
                pending.append(chunk)
                var complete: [Data] = []
                while let newline = pending.firstIndex(of: 10) {
                    complete.append(pending.prefix(upTo: newline))
                    pending.removeSubrange(...newline)
                }
                return complete
            }
            DispatchQueue.main.async {
                for data in lines {
                    if let state = try? JSONDecoder().decode(MonitorState.self, from: data) { delegate.consume(state) }
                    else if let message = try? JSONDecoder().decode(NoticeMessage.self, from: data), message.kind == "status_notice" {
                        delegate.controller.receiveNotice(message.notice)
                    }
                    else if let command = try? JSONSerialization.jsonObject(with: data) as? [String: String],
                            let id = command["requestId"] {
                        if command["kind"] == "exercise_menu_layout" { delegate.controller.exerciseMenuLayout(requestID:id) }
                        else if command["kind"] == "inspect_layout" { delegate.controller.inspectLayout(requestID: id) }
                        else if command["kind"] == "choose_emoji" { delegate.controller.chooseEmoji(requestID:id) }
                        else if command["kind"] == "inspect_settings" { delegate.controller.inspectSettings(requestID:id) }
                        else if command["kind"] == "exercise_toggle" { delegate.controller.exerciseToggle(requestID: id) }
                    }
                }
            }
        }
        // A plugin executable is not launched by NSApplicationMain/LaunchServices.
        // Complete AppKit's launch explicitly before entering its event loop.
        app.finishLaunching()
        DispatchQueue.main.async { delegate.start() }
        trace("enter AppKit run loop")
        app.run()
        trace("AppKit run loop returned")
    }

    @MainActor
    private static func renderPreview(to path: String) {
        guard let line = readLine(), let data = line.data(using: .utf8),
              let state = try? JSONDecoder().decode(MonitorState.self, from: data) else { return }
        let height = NSStatusBar.system.thickness
        let views = state.projects.map { CapsuleView(project: $0, height: height, detail: state.detail, language: state.language, onEvent: { _, _ in }) }
        let width = max(420, views.reduce(40) { $0 + $1.frame.width + 10 })
        let canvas = NSView(frame: CGRect(x: 0, y: 0, width: width, height: 92))
        canvas.wantsLayer = true
        canvas.layer?.backgroundColor = NSColor(srgbRed: 0.08, green: 0.09, blue: 0.11, alpha: 1).cgColor
        var x: CGFloat = 20
        for view in views {
            view.frame.origin = CGPoint(x: x, y: 32)
            canvas.addSubview(view)
            x += view.frame.width + 10
        }
        canvas.layoutSubtreeIfNeeded()
        guard let bitmap = canvas.bitmapImageRepForCachingDisplay(in: canvas.bounds) else { return }
        canvas.cacheDisplay(in: canvas.bounds, to: bitmap)
        if let png = bitmap.representation(using: .png, properties: [:]) {
            try? png.write(to: URL(fileURLWithPath: path))
        }
    }
}
