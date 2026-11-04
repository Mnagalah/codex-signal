import AppKit
import ImageIO

// Offline, explicitly illustrative previews. This route creates no status item,
// panel, desktop subscription, chat or approval; it renders the production views.
@MainActor
private final class PreviewCanvas: NSView {
    var caption = "原生样式预览 · 示例对话"
    var panelImage: NSImage?
    var panelOrigin = CGPoint.zero
    var panelOpacity: CGFloat = 1
    override var isFlipped: Bool { true }
    override func draw(_ rect: NSRect) {
        NSColor(srgbRed: 0.12, green: 0.13, blue: 0.15, alpha: 1).setFill()
        bounds.fill()
        NSColor(srgbRed: 0.20, green: 0.21, blue: 0.23, alpha: 1).setFill()
        CGRect(x: 0, y: 0, width: bounds.width, height: 42).fill()
        if let panelImage {
            panelImage.draw(in: CGRect(origin: panelOrigin, size: panelImage.size), from: .zero, operation: .sourceOver,
                            fraction: panelOpacity, respectFlipped: true, hints: nil)
        }
        Drawing.text(caption, rect: CGRect(x: 20, y: bounds.height - 28, width: bounds.width - 40, height: 18),
                     size: 12, color: .white.withAlphaComponent(0.72), alignment: .center)
    }
}

@MainActor
enum NativePreview {
    private static func input() -> MonitorState? {
        guard let line = readLine(), let data = line.data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode(MonitorState.self, from: data)
    }

    static func renderNotice(to path: String) {
        guard let state = input(), let project = state.projects.first, let chat = project.threads.first else { return }
        let payload = NoticePayload(id: "offline-notice", source: "automatic", createdAt: Date().timeIntervalSince1970, project: project, chat: chat)
        let view = StatusNoticeView(payload: payload, language: state.language, onDismiss: {})
        view.countdown(remaining: Layout.specification.notice.holdSeconds, animated: false)
        writePNG(view, to: path)
    }

    static func render(to path: String, settings: Bool = false) {
        guard let state = input(), let first = state.projects.first else { return }
        let canvas = PreviewCanvas(frame: CGRect(x: 0, y: 0, width: 560, height: settings ? 530 : 530))
        let views = state.projects.map { CapsuleView(project: $0, height: 22, detail: state.detail, language: state.language, onEvent: { _, _ in }) }
        var x = (canvas.bounds.width - views.reduce(0) { $0 + $1.frame.width } - CGFloat(max(0, views.count - 1)) * 10) / 2
        for view in views {
            // Exercise the production transparent button host, including its
            // selected state, rather than previewing the pill in isolation.
            let button = NSButton(frame: CGRect(x: x, y: 11, width: view.frame.width, height: view.frame.height))
            StatusItemHost.configure(button, content: view)
            button.highlight(true)
            canvas.addSubview(button)
            x += view.frame.width + 10
        }
        let content = ProjectPanelView(project: first, detail: state.detail, enabled: state.enabled ?? true, language: state.language, onEvent: { _, _ in })
        content.notificationStates=Set(state.notificationStates ?? Layout.specification.alertTypes);content.compactMenuBar=state.compactMenuBar ?? false;content.statusEmoji=state.statusEmoji ?? EmojiPickerButton.defaultEmoji
        content.setProjectControls(state.projectControls ?? [])
        content.update(first, detail: state.detail, animated: false)
        if settings { content.setShowingAlerts(true,animated:false) }
        let anchor = views[0].convert(views[0].bounds, to: canvas)
        content.frame.origin = CGPoint(x: max(16, anchor.midX - PopupLayout.width / 2), y: 34)
        content.arrowX = anchor.midX - content.frame.minX
        canvas.addSubview(content)
        writePNG(canvas, to: path)
    }

    static func record(to path: String) {
        guard let state = input(), var project = state.projects.first, var first = project.threads.first else { return }
        Motion.reduceMotionOverride = false
        let canvas = PreviewCanvas(frame: CGRect(x: 0, y: 0, width: 440, height: 310))
        first.status = "running"; first.detail = "进行中"; first.canMarkSeen = false
        project.threads = [first]
        let view = CapsuleView(project: project, height: 22, detail: state.detail, language: state.language, onEvent: { _, _ in })
        view.frame.origin = CGPoint(x: 150, y: 11)
        canvas.addSubview(view)
        let content = ProjectPanelView(project: project, detail: state.detail, language: state.language, onEvent: { _, _ in })
        content.frame.origin = CGPoint(x: view.frame.midX - PopupLayout.width / 2, y: 34)
        content.arrowX = view.frame.midX - content.frame.minX
        canvas.panelOpacity = 0
        var followAnchor = true
        let opening = PopoverSpringMotion()
        func setPanelOpen(_ open: Bool) {
            opening.start(to: open ? 1 : 0, frame: { p in
                canvas.panelOpacity = min(1, max(0, p))
                content.frame.origin.y = 34 - Layout.specification.popoverMotion.offset * (1 - p)
            })
        }
        view.onWidthChange = { _ in
            if followAnchor {
                content.frame.origin.x = view.frame.midX - PopupLayout.width / 2
                content.arrowX = view.frame.midX - content.frame.minX
            }
        }
        var second = first
        second.id = "preview-second"; second.index = 2; second.title = "检查另一项任务"
        let steps: [(Int, String, () -> Void)] = [
            (3, "单击展开 · 弹簧接续", { setPanelOpen(true) }),
            (9, "再次单击收起 · 保留当前速度", { setPanelOpen(false) }),
            (11, "中途反向展开 · 不跳回起点", { setPanelOpen(true) }),
            (17, "进行中 → 等待授权", { project.threads[0].status = "approval"; project.threads[0].detail = "等待授权" }),
            (32, "新增聊天 · 胶囊展开", { project.threads.append(second) }),
            (47, "本轮完成 · 保留提醒", { project.threads[0].status = "completed"; project.threads[0].detail = "完成未看"; project.threads[0].canMarkSeen = true }),
            (62, "已看后移除 · 编号 2 保持不变", { project.threads.removeFirst() }),
            (72, "最后一个对话完成", { project.threads[0].status = "completed"; project.threads[0].detail = "完成未看"; project.threads[0].canMarkSeen = true }),
            (77, "项目全部结束 · 面板与胶囊退出", { followAnchor = false; view.setVisible(false); setPanelOpen(false) }),
            (93, "项目重新出现 · 可中断的过渡", { project.threads = [second]; view.update(project, detail: state.detail) })
        ]
        guard let destination = CGImageDestinationCreateWithURL(URL(fileURLWithPath: path) as CFURL, "com.compuserve.gif" as CFString, 112, nil) else { return }
        CGImageDestinationSetProperties(destination, [kCGImagePropertyGIFDictionary: [kCGImagePropertyGIFLoopCount: 0]] as CFDictionary)
        let frameProperties = [kCGImagePropertyGIFDictionary: [kCGImagePropertyGIFDelayTime: 1.0 / 30, kCGImagePropertyGIFUnclampedDelayTime: 1.0 / 30]] as CFDictionary
        let start = Date()
        for i in 0..<112 {
            if let step = steps.first(where: { $0.0 == i }) {
                canvas.caption = step.1 + " · 示例"
                step.2()
                if ![3, 9, 11, 77, 93].contains(i) {
                    view.update(project, detail: state.detail)
                    content.update(project, detail: state.detail)
                }
            }
            RunLoop.main.run(until: start.addingTimeInterval(Double(i + 1) / 30))
            if let rep = bitmap(content, scale: 1) {
                let image = NSImage(size: content.bounds.size)
                image.addRepresentation(rep)
                canvas.panelImage = image
                canvas.panelOrigin = content.frame.origin
            }
            canvas.needsDisplay = true
            if let bitmap = bitmap(canvas, scale: 1), let image = bitmap.cgImage { CGImageDestinationAddImage(destination, image, frameProperties) }
        }
        CGImageDestinationFinalize(destination)
        view.finishAnimation()
        content.finishAnimation()
        opening.finish()
        Motion.reduceMotionOverride = nil
    }

    private static func bitmap(_ view: NSView, scale: CGFloat = 2) -> NSBitmapImageRep? {
        view.layoutSubtreeIfNeeded()
        guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(view.bounds.width * scale), pixelsHigh: Int(view.bounds.height * scale),
            bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { return nil }
        bitmap.size = view.bounds.size
        view.cacheDisplay(in: view.bounds, to: bitmap)
        return bitmap
    }

    private static func writePNG(_ view: NSView, to path: String) {
        let scale: CGFloat = ProcessInfo.processInfo.environment["CODEX_MENU_PREVIEW_SCALE"] == "1" ? 1 : 2
        if let data = bitmap(view, scale: scale)?.representation(using: .png, properties: [:]) { try? data.write(to: URL(fileURLWithPath: path)) }
    }
}
