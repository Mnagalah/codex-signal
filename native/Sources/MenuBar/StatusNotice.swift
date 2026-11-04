import AppKit
import QuartzCore

struct NoticeConfiguration: Decodable, Sendable {
    let width: CGFloat
    let safeInset: CGFloat
    let border: CGFloat
    let radius: CGFloat
    let holdSeconds: Double
    let motionSeconds: Double
    let offset: CGFloat
}

struct NoticePayload: Codable, Sendable {
    let id: String
    let source: String
    let createdAt: Double
    var project: Project
    var chat: Chat
}

struct NoticeMessage: Decodable { let kind: String; let notice: NoticePayload }

struct NoticeLifetime: Sendable {
    private(set) var activeID: String?
    private(set) var shownAt = 0.0
    private(set) var deadline = 0.0
    private(set) var lastID: String?
    @discardableResult mutating func present(_ id: String, now: Double) -> Bool {
        guard id != lastID else { return false }
        lastID = id
        activeID = id; shownAt = now; deadline = now + Layout.specification.notice.holdSeconds
        return true
    }
    func shouldExpire(_ id: String, now: Double) -> Bool { activeID == id && now >= deadline }
    mutating func clear() { activeID = nil }
}

struct NoticeLayout: Sendable {
    let width: CGFloat
    static var height: CGFloat { Layout.grid("notice").intrinsicSize().height + 2 * Layout.specification.notice.border }
    private var root: PlacedGrid {
        Layout.grid("notice").place(in: CGRect(x: 0, y: 0, width: width, height: Self.height).insetBy(dx: Layout.specification.notice.border, dy: Layout.specification.notice.border))
    }
    var header: CGRect { root.cell(0, 0) }
    var body: CGRect { root.cell(0, 2) }
    var meter: CGRect { root.cell(0, 4) }
    private var head: PlacedGrid { Layout.grid("noticeHeader").place(in: header) }
    private var row: PlacedGrid { Layout.grid("noticeBody").place(in: body) }
    var icon: CGRect { Layout.square(head.cell(0).width, in: head.cell(0)) }
    var project: CGRect { head.cell(1) }
    var close: CGRect { head.cell(2) }
    var badge: CGRect { Layout.square(row.cell(0).width, in: row.cell(0)) }
    var copy: CGRect { row.cell(1) }
    var status: CGRect { Layout.grid("noticeCopy").place(in: copy).cell(0, 0) }
    var title: CGRect { Layout.grid("noticeCopy").place(in: copy).cell(0, 1) }
    static func placement(in visibleScreen: CGRect) -> CGRect {
        let config = Layout.specification.notice
        let width = min(config.width, max(0, visibleScreen.width - 2 * config.safeInset))
        return CGRect(x: visibleScreen.maxX - config.safeInset - width, y: visibleScreen.maxY - config.safeInset - height, width: width, height: height)
    }
}

@MainActor
final class StatusNoticeView: NSView {
    private(set) var payload: NoticePayload
    private(set) var language: InterfaceLanguage
    var onDismiss: () -> Void
    var onOpen: ((NoticePayload) -> Void)?
    private var pressed: (id: String, close: Bool)?
    var canOpen: Bool { payload.source == "automatic" && onOpen != nil }
    private var hover = false
    private var tracking: NSTrackingArea?
    private let progress = CALayer()
    private var badgeColor: NSColor
    private let colorMotion = MotionDriver()
    var grid: NoticeLayout { NoticeLayout(width: bounds.width) }
    var projectName: String {
        switch payload.project.kind {
        case "chat-bucket": language.text("chatBucket")
        case "pending": language.text("pendingProject")
        default: payload.project.name
        }
    }
    var projectText: String {
        language.text("noticeProject", ["project": projectName, "n": String(payload.chat.index)]) +
        (payload.source == "diagnostic" ? " · " + language.text("noticeDemoBadge") : "")
    }
    var stateText: String { if payload.chat.status == "completed" { return language.text("noticeCompleted") }; return language.text(["running", "approval", "input", "completed", "failed", "stopped"].contains(payload.chat.status) ? payload.chat.status : "unknown") }

    init(payload: NoticePayload, language: InterfaceLanguage, onDismiss: @escaping () -> Void, onOpen: ((NoticePayload) -> Void)? = nil) {
        self.payload = payload; self.language = language; self.onDismiss = onDismiss; self.onOpen = onOpen
        badgeColor = Palette.background(payload.chat.status)
        super.init(frame: CGRect(x: 0, y: 0, width: Layout.specification.notice.width, height: NoticeLayout.height))
        appearance = NSAppearance(named: .darkAqua)
        wantsLayer = true
        progress.backgroundColor = NSColor.white.withAlphaComponent(0.44).cgColor
        progress.anchorPoint = CGPoint(x: 0, y: 0.5)
        layer?.addSublayer(progress)
        setAccessibilityElement(true); setAccessibilityRole(.group)
        update(payload, language: language)
    }
    required init?(coder: NSCoder) { nil }
    override var isFlipped: Bool { true }
    override var acceptsFirstResponder: Bool { false }
    override var needsPanelToBecomeKey: Bool { false }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    func update(_ value: NoticePayload, language: InterfaceLanguage) {
        let changed = payload.chat.status != value.chat.status, start = badgeColor
        payload = value; self.language = language
        if changed {
            let target = Palette.background(value.chat.status)
            colorMotion.start(duration: Motion.color, frame: { [weak self] p in
                self?.badgeColor = Motion.mix(start, target, p); self?.needsDisplay = true
            })
        }
        toolTip = value.chat.title + (canOpen ? "\n" + language.text("openNotice") : "")
        setAccessibilityLabel(language.text("noticeAria", ["project": projectName, "n": String(value.chat.index), "title": value.chat.title, "state": stateText]))
        let displayedID = value.id
        var children: [NSAccessibilityElement] = []
        if canOpen {
            let open = ChatAccessibilityElement(onPress: { [weak self] in
                guard let self, self.payload.id == displayedID, self.canOpen else { return }
                self.onOpen?(self.payload)
            })
            open.setAccessibilityRole(.button); open.setAccessibilityLabel(language.text("openNotice"))
            open.setAccessibilityHelp(accessibilityLabel())
            open.setAccessibilityParent(self); children.append(open)
        }
        let close = ChatAccessibilityElement(onPress: { [weak self] in
            guard let self, self.payload.id == displayedID else { return }
            self.onDismiss()
        })
        close.setAccessibilityRole(.button); close.setAccessibilityLabel(language.text("dismissNotice"))
        close.setAccessibilityParent(self); children.append(close)
        setAccessibilityChildren(children); updateAccessibilityFrames()
        window?.invalidateCursorRects(for: self)
        needsDisplay = true; needsLayout = true
    }

    private func updateAccessibilityFrames() {
        let children = accessibilityChildren() as? [NSAccessibilityElement] ?? []
        if canOpen {
            children.first?.setAccessibilityFrameInParentSpace(CGRect(x: 0, y: 0, width: grid.close.minX, height: bounds.height))
        }
        children.last?.setAccessibilityFrameInParentSpace(grid.close)
    }

    func countdown(remaining: Double, animated: Bool) {
        progress.removeAnimation(forKey: "remaining")
        CATransaction.begin(); CATransaction.setDisableActions(true)
        progress.transform = animated && !Motion.reduced ? CATransform3DMakeScale(0, 1, 1) : CATransform3DIdentity
        progress.opacity = Motion.reduced ? 0.35 : 1
        CATransaction.commit()
        if animated && !Motion.reduced {
            let animation = CABasicAnimation(keyPath: "transform.scale.x")
            animation.fromValue = 1; animation.toValue = 0; animation.duration = remaining
            animation.timingFunction = CAMediaTimingFunction(name: .linear)
            progress.add(animation, forKey: "remaining")
        }
    }
    override func layout() {
        super.layout()
        updateAccessibilityFrames()
        CATransaction.begin(); CATransaction.setDisableActions(true)
        progress.bounds = CGRect(origin: .zero, size: grid.meter.size)
        progress.position = CGPoint(x: grid.meter.minX, y: grid.meter.midY)
        CATransaction.commit()
    }
    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        if let tracking { removeTrackingArea(tracking) }
        let next = NSTrackingArea(rect: grid.close, options: [.mouseEnteredAndExited, .activeAlways], owner: self)
        tracking = next; addTrackingArea(next)
    }
    override func mouseEntered(with event: NSEvent) { hover = true; needsDisplay = true }
    override func mouseExited(with event: NSEvent) { hover = false; needsDisplay = true }
    override func resetCursorRects() {
        super.resetCursorRects()
        if canOpen { addCursorRect(bounds, cursor: .pointingHand) }
        addCursorRect(grid.close, cursor: .pointingHand)
    }
    override func mouseDown(with event: NSEvent) {
        let point = convert(event.locationInWindow, from: nil)
        pressed = bounds.contains(point) ? (payload.id, grid.close.contains(point)) : nil
    }
    override func mouseUp(with event: NSEvent) {
        defer { pressed = nil }
        let point = convert(event.locationInWindow, from: nil)
        guard let pressed, pressed.id == payload.id, bounds.contains(point),
              pressed.close == grid.close.contains(point) else { return }
        if pressed.close { onDismiss() }
        else if canOpen { onOpen?(payload) }
    }

    override func draw(_ dirtyRect: NSRect) {
        let config = Layout.specification.notice, grid = grid
        let path = NSBezierPath(roundedRect: bounds.insetBy(dx: 0.5, dy: 0.5), xRadius: config.radius, yRadius: config.radius)
        NSColor(srgbRed: 0.02, green: 0.02, blue: 0.02, alpha: 1).setFill(); path.fill()
        NSColor.white.withAlphaComponent(0.15).setStroke(); path.lineWidth = config.border; path.stroke()
        Drawing.icon(payload.project, rect: grid.icon)
        Drawing.label(projectText, rect: grid.project, role: "noticeProject")
        Drawing.badge(payload.chat, rect: grid.badge, color: badgeColor, alpha: 1)
        Drawing.label(stateText, rect: grid.status, role: "noticeState")
        Drawing.label(payload.chat.title, rect: grid.title, role: "noticeTitle", color: .white.withAlphaComponent(0.72))
        NSColor.white.withAlphaComponent(0.08).setFill(); NSBezierPath(roundedRect: grid.meter, xRadius: 1, yRadius: 1).fill()
        if hover { NSColor.white.withAlphaComponent(0.09).setFill(); NSBezierPath(roundedRect: grid.close, xRadius: 6, yRadius: 6).fill() }
        let x = grid.close.insetBy(dx: 8, dy: 8), cross = NSBezierPath()
        cross.move(to: CGPoint(x: x.minX, y: x.minY)); cross.line(to: CGPoint(x: x.maxX, y: x.maxY))
        cross.move(to: CGPoint(x: x.maxX, y: x.minY)); cross.line(to: CGPoint(x: x.minX, y: x.maxY))
        NSColor.white.withAlphaComponent(hover ? 1 : 0.62).setStroke(); cross.lineWidth = 1.3; cross.stroke()
    }
}

@MainActor private final class NoticePanel: NSPanel {
    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

struct NoticeReceipt: Encodable, Sendable {
    let event: String
    let noticeId: String
    let source: String
    let reason: String
    let dwellMs: Double
    let uiLanguage: String
    let becameKey: Bool
    let activatedApplication: Bool
}

@MainActor
final class StatusNoticeController: NSObject {
    private var panel: NoticePanel?
    private var content: StatusNoticeView?
    private(set) var lifetime = NoticeLifetime()
    private var expiry: DispatchWorkItem?
    private let motion = MotionDriver()
    private var progress: CGFloat = 0
    private var screen: NSScreen?
    private var capturedAutomatic = false
    private var activeBeforeShow = false
    let onReceipt: (NoticeReceipt) -> Void
    let onOpen: (NoticePayload) -> Void
    var isVisible: Bool { panel?.isVisible ?? false }

    init(onReceipt: @escaping (NoticeReceipt) -> Void, onOpen: @escaping (NoticePayload) -> Void) {
        self.onReceipt = onReceipt; self.onOpen = onOpen; super.init()
        NotificationCenter.default.addObserver(self, selector: #selector(screenChanged), name: NSApplication.didChangeScreenParametersNotification, object: nil)
    }

    func show(_ value: NoticePayload, language: InterfaceLanguage, screen: NSScreen?) {
        guard value.id != lifetime.lastID else { return }
        if let previous = content?.payload, lifetime.activeID != nil {
            receipt(previous, event: "notice_closed", reason: "replaced", dwell: (CACurrentMediaTime() - lifetime.shownAt) * 1000)
        }
        expiry?.cancel(); self.screen = screen ?? NSScreen.main
        lifetime.present(value.id, now: CACurrentMediaTime())
        if panel == nil {
            let window = NoticePanel(contentRect: .zero, styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
            window.isReleasedWhenClosed = false; window.isOpaque = false; window.backgroundColor = .clear
            window.hasShadow = true; window.hidesOnDeactivate = false; window.becomesKeyOnlyIfNeeded = true
            window.level = .popUpMenu; window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
            panel = window
        }
        if let content { content.update(value, language: language) }
        else {
            let view = StatusNoticeView(payload: value, language: language, onDismiss: { [weak self] in self?.dismiss(reason: "manual") },
                onOpen: { [weak self] payload in self?.open(payload) })
            content = view; panel?.contentView = view
        }
        let key = NSApp.keyWindow
        activeBeforeShow = NSApp.isActive
        panel?.ignoresMouseEvents = false; reposition(); panel?.alphaValue = progress
        panel?.orderFrontRegardless() // Never makeKey, activate, or take first responder.
        content?.countdown(remaining: Layout.specification.notice.holdSeconds, animated: true)
        animate(to: 1)
        let work = DispatchWorkItem { [weak self] in
            guard let self, self.lifetime.shouldExpire(value.id, now: CACurrentMediaTime()) else { return }
            self.dismiss(reason: "expired")
        }
        expiry = work; DispatchQueue.main.asyncAfter(deadline: .now() + Layout.specification.notice.holdSeconds, execute: work)
        onReceipt(NoticeReceipt(event: "notice_shown", noticeId: value.id, source: value.source, reason: "status", dwellMs: 0,
            uiLanguage: language.code, becameKey: NSApp.keyWindow !== key, activatedApplication: !activeBeforeShow && NSApp.isActive))
        if let content {
            NSAccessibility.post(element: content, notification: .announcementRequested,
                userInfo: [.announcement: content.accessibilityLabel() ?? "", .priority: NSAccessibilityPriorityLevel.medium.rawValue])
        }
        capture(value)
    }

    func refresh(language: InterfaceLanguage, projects: [Project], enabled: Bool, pausedProjects: Set<String> = [], notificationStates: Set<String> = Set(Layout.specification.alertTypes)) {
        guard enabled else { dismiss(reason: "disabled", animated: false); return }
        guard let content else { return }
        if pausedProjects.contains(content.payload.project.id) { dismiss(reason: "project-paused", animated: false); return }
        if content.payload.source == "automatic", !notificationStates.contains(content.payload.chat.status) { dismiss(reason:"alert-disabled",animated:false); return }
        var value = content.payload
        if let project = projects.first(where: { $0.threads.contains(where: { $0.id == value.chat.id }) }), let chat = project.threads.first(where: { $0.id == value.chat.id }) {
            value.project = project; value.chat.index = chat.index; value.chat.title = chat.title
        }
        // Keep the displayed event's status and expiry, even if its chat leaves
        // the capsules after Codex marks it read. Only a new event resets time.
        content.update(value, language: language)
    }

    private func open(_ value: NoticePayload) {
        guard lifetime.activeID == value.id, value.source == "automatic" else { return }
        onOpen(value)
        dismiss(reason: "opened")
    }

    func dismiss(reason: String, animated: Bool = true) {
        guard lifetime.activeID != nil, let content else { return }
        let value = content.payload, dwell = (CACurrentMediaTime() - lifetime.shownAt) * 1000
        lifetime.clear(); expiry?.cancel(); expiry = nil; panel?.ignoresMouseEvents = true
        animate(to: 0, animated: animated) { [weak self] in
            guard let self, self.lifetime.activeID == nil, self.content?.payload.id == value.id else { return }
            self.panel?.orderOut(nil)
            self.receipt(value, event: "notice_closed", reason: reason, dwell: dwell)
        }
    }
    private func receipt(_ value: NoticePayload, event: String, reason: String, dwell: Double) {
        onReceipt(NoticeReceipt(event: event, noticeId: value.id, source: value.source, reason: reason, dwellMs: dwell,
            uiLanguage: content?.language.code ?? "en", becameKey: panel?.isKeyWindow ?? false,
            activatedApplication: !activeBeforeShow && NSApp.isActive))
    }
    private func animate(to target: CGFloat, animated: Bool = true, completion: (() -> Void)? = nil) {
        let start = progress
        motion.start(duration: animated ? Layout.specification.notice.motionSeconds : 0, frame: { [weak self] p in
            guard let self else { return }; self.progress = Motion.mix(start, target, p)
            self.panel?.alphaValue = self.progress; self.reposition()
        }, completion: completion)
    }
    @objc private func screenChanged() {
        if !NSScreen.screens.contains(where: { $0 === screen }) { screen = NSScreen.main }
        reposition()
    }
    private func reposition() {
        guard let panel, let screen = screen ?? NSScreen.main else { return }
        var frame = NoticeLayout.placement(in: screen.visibleFrame)
        if !Motion.reduced { frame.origin.y += Layout.specification.notice.offset * (1 - progress) }
        panel.setFrame(frame, display: true); panel.invalidateShadow()
    }

    private func capture(_ value: NoticePayload) {
        guard let directory = ProcessInfo.processInfo.environment["CODEX_MENU_UI_CAPTURE_DIR"], value.source == "diagnostic" || !capturedAutomatic else { return }
        if value.source != "diagnostic" { capturedAutomatic = true }
        DispatchQueue.main.asyncAfter(deadline: .now() + Layout.specification.notice.motionSeconds + 0.05) { [weak self] in
            guard let self, self.lifetime.activeID == value.id, let panel = self.panel, let content = self.content else { return }
            content.layoutSubtreeIfNeeded()
            let name = value.source == "diagnostic" ? "notice-" + value.id : "live-notice"
            let root = URL(fileURLWithPath: directory), safe = name.replacingOccurrences(of: "[^A-Za-z0-9_-]", with: "-", options: .regularExpression)
            if let bitmap = content.bitmapImageRepForCachingDisplay(in: content.bounds) {
                content.cacheDisplay(in: content.bounds, to: bitmap)
                try? bitmap.representation(using: .png, properties: [:])?.write(to: root.appendingPathComponent(safe + ".png"))
            }
            let report: [String: Any] = ["noticeId": value.id, "source": value.source, "uiLanguage": content.language.code,
                "visible": panel.isVisible, "clickable": content.canOpen, "openChatID": content.canOpen ? value.chat.id : "", "becameKey": panel.isKeyWindow, "activatedApplication": !self.activeBeforeShow && NSApp.isActive,
                "project": content.projectText, "title": value.chat.title, "status": content.stateText,
                "frame": LayoutDiagnostics.rect(panel.frame), "screenVisibleFrame": self.screen.map { LayoutDiagnostics.rect($0.visibleFrame) } ?? [:],
                "holdSeconds": Layout.specification.notice.holdSeconds, "remainingSeconds": max(0, self.lifetime.deadline - CACurrentMediaTime()),
                "cells": ["header": LayoutDiagnostics.rect(content.grid.header), "badge": LayoutDiagnostics.rect(content.grid.badge), "title": LayoutDiagnostics.rect(content.grid.title), "meter": LayoutDiagnostics.rect(content.grid.meter)]]
            if let data = try? JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]) {
                try? data.write(to: root.appendingPathComponent(safe + ".json"), options: .atomic)
            }
        }
    }
}
