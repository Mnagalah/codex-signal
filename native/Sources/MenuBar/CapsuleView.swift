import AppKit

@MainActor
final class ChatAccessibilityElement: NSAccessibilityElement {
    nonisolated let onPress: @MainActor @Sendable () -> Void
    init(onPress: @escaping @MainActor @Sendable () -> Void) {
        self.onPress = onPress
        super.init()
    }
    nonisolated override func accessibilityPerformPress() -> Bool {
        Task { @MainActor [onPress] in onPress() }
        return true
    }
}

@MainActor
private struct BadgeVisual {
    var chat: Chat
    var rect: CGRect
    var color: NSColor
    var alpha: CGFloat = 1
    var scale: CGFloat = 1
}

@MainActor
final class CapsuleView: NSView, NSViewToolTipOwner {
    private(set) var project: Project
    private(set) var language: InterfaceLanguage
    private(set) var connectionDetail: String
    let onEvent: (String, String?) -> Void
    var onShowPopover: ((CapsuleView, Bool) -> Void)?
    var onWidthChange: ((CGFloat) -> Void)?
    var animationsEnabled = true
    var monitorEnabled = true
    var projectControls: [Project] = []
    var globalEnabled = true
    var compactMenuBar = false
    var statusEmoji = EmojiPickerButton.defaultEmoji
    var notificationStates = Set(Layout.specification.alertTypes)
    var displayName: String { project.displayName(in: language) }
    private var geometryReady = false
    private var hostSignature:[CGFloat]=[]
    private var geometrySignature:[CGFloat] {
        let grid=layout;return [frame.height,grid.width,grid.nameWidth,grid.badgeDiameter,grid.centerY]
    }
    private let motion = MotionDriver()
    private var badges: [BadgeVisual] = []
    private(set) var pillColor = NSColor.black
    private var opacity: CGFloat = 1
    private var visible = true
    private var pressedID: String?
    private var tips: [NSView.ToolTipTag: String] = [:]
    private(set) var targetWidth: CGFloat = 0
    var isAnimating: Bool { motion.isRunning }
    var badgePresentation:[[String:Any]] {
        badges.map { badge in
            let c=badge.color.usingColorSpace(.sRGB) ?? badge.color
            return ["id":badge.chat.id,"status":badge.chat.status,"rgb":[c.redComponent,c.greenComponent,c.blueComponent],
                    "alpha":badge.alpha*opacity,"dashed":badge.chat.status == "unknown"]
        }
    }
    var visibilitySnapshot:[String:Any] { ["visible":visible,"alpha":opacity,"width":frame.width,"targetWidth":targetWidth,"animating":isAnimating] }

    var layout: CapsuleLayout {
        let natural = (displayName as NSString).size(withAttributes: [.font: Layout.font("menu")]).width
        let screenWidth = (window?.screen ?? NSScreen.main)?.frame.width ?? .greatestFiniteMagnitude
        return CapsuleLayout(height: frame.height, nameWidth: min(Layout.value("name-max", forWidth: screenWidth), ceil(natural)), count: project.threads.count, globalEntry: project.kind == "global-control", controlLabel: project.isStatusControl && project.kind != "global-control")
    }

    init(project: Project, height: CGFloat, detail: String, language: InterfaceLanguage = .chinese, onEvent: @escaping (String, String?) -> Void) {
        self.project = project
        self.language = language
        self.connectionDetail = detail
        self.onEvent = onEvent
        super.init(frame: CGRect(x: 0, y: 0, width: 100, height: height))
        targetWidth = layout.width
        frame.size.width = targetWidth
        badges = targetBadges()
        pillColor = targetPillColor
        geometryReady = true
        hostSignature=geometrySignature
        rebuildAccessibility()
        setAccessibilityElement(true)
        setAccessibilityRole(.group)
    }

    required init?(coder: NSCoder) { nil }
    override var isFlipped: Bool { true }
    override var acceptsFirstResponder: Bool { true }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override func setFrameSize(_ newSize: NSSize) {
        let oldHeight = frame.height
        super.setFrameSize(newSize)
        guard geometryReady, abs(oldHeight - newSize.height) > 0.1 else { return }
        refreshHostLayout()
    }

    func refreshHostLayout() {
        guard geometryReady else { return }
        let signature=geometrySignature
        // AppKit can deliver deferred backing/window notifications while a new
        // status item is entering. Repainting the same geometry must not finish
        // that 200ms transition or fire its removal callback early.
        guard signature != hostSignature else { needsDisplay=true;onWidthChange?(frame.width);return }
        hostSignature=signature
        // The native host may resize when the display/menu bar changes. Stored
        // animated badge rectangles must follow that height, not the first screen.
        motion.finish()
        badges = targetBadges()
        pressedID = nil
        targetWidth = visible ? layout.width : 1
        super.setFrameSize(NSSize(width: targetWidth, height: frame.height))
        rebuildAccessibility()
        onWidthChange?(targetWidth)
        needsDisplay = true
    }

    override func viewDidChangeBackingProperties() {
        super.viewDidChangeBackingProperties()
        refreshHostLayout() // A display change can also change responsive tracks.
    }

    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        NotificationCenter.default.removeObserver(self, name: NSWindow.didChangeScreenNotification, object: nil)
        if let window {
            NotificationCenter.default.addObserver(self, selector: #selector(hostScreenChanged(_:)),
                                                   name: NSWindow.didChangeScreenNotification, object: window)
        }
        refreshHostLayout()
    }

    @objc private func hostScreenChanged(_ notification: Notification) { refreshHostLayout() }

    func update(_ value: Project, detail: String, language: InterfaceLanguage? = nil) {
        let previousLanguage = self.language
        if let language { self.language = language }
        let previous = project
        let wasVisible = visible
        project = value
        connectionDetail = detail
        visible = true
        rebuildAccessibility()
        // Time/detail-only updates must not restart an in-flight transition.
        if previous == value, previousLanguage == self.language, wasVisible { needsDisplay = true; return }
        transition(toVisible: true)
    }

    func setVisible(_ value: Bool, animated: Bool = true, completion: (() -> Void)? = nil) {
        visible = value
        if !value { pressedID = nil }
        rebuildAccessibility()
        transition(toVisible: value, animated: animated, completion: completion)
    }

    func finishAnimation() { motion.finish() }

    private var targetPillColor:NSColor {
        guard project.kind == "global-control",let phase=project.summaryStatus,phase != "syncing" else { return .black }
        return Palette.background(phase)
    }
    var aggregateDetail:String {
        guard project.kind == "global-control" else { return connectionDetail }
        guard globalEnabled else { return language.text("monitorDisabled") }
        if let issue = project.healthDetail { return issue }
        guard let phase=project.summaryStatus else { return language.text("noChats") }
        return language.text("aggregateStatus",["status":language.text(phase),"n":String(project.summaryCount ?? 0)])
    }

    private func targetBadges() -> [BadgeVisual] {
        project.threads.enumerated().map { i, chat in BadgeVisual(chat: chat, rect: layout.badge(i), color: Palette.background(chat.status)) }
    }

    private func transition(toVisible: Bool, animated: Bool = true, completion: (() -> Void)? = nil) {
        // Capture the current presentation, not the previous model target.
        hostSignature=geometrySignature
        let oldWidth = frame.width, oldOpacity = opacity
        let oldPillColor=pillColor,newPillColor=targetPillColor
        targetWidth = toVisible ? layout.width : 1
        let newOpacity: CGFloat = toVisible ? 1 : 0
        var source = badges
        var destination = targetBadges()
        let live = Set(destination.map { $0.chat.id })
        let structural = abs(targetWidth - oldWidth) > 0.1 || Set(source.map { $0.chat.id }) != live
        for badge in destination where !source.contains(where: { $0.chat.id == badge.chat.id }) {
            var entry = badge
            entry.alpha = 0
            entry.scale = Motion.reduced ? 1 : 0.95
            if !Motion.reduced { entry.rect.origin.x += 4 }
            source.append(entry)
        }
        for badge in source where !live.contains(badge.chat.id) {
            var exit = badge
            exit.alpha = 0
            exit.scale = Motion.reduced ? 1 : 0.95
            if !Motion.reduced { exit.rect.origin.x -= 3 }
            destination.append(exit)
        }
        let fromByID = Dictionary(uniqueKeysWithValues: source.map { ($0.chat.id, $0) })
        let to = destination, width = targetWidth
        let duration = !animated || !animationsEnabled ? 0 : (structural ? Layout.specification.menuMotion.transition : Motion.color)
        motion.start(duration: duration, frame: { [weak self] p in
            guard let self else { return }
            self.opacity = Motion.mix(oldOpacity, newOpacity, p)
            self.pillColor = Motion.mix(oldPillColor,newPillColor,p)
            self.frame.size.width = Motion.reduced ? width : Motion.mix(oldWidth, width, p)
            self.badges = to.map { end in
                let start = fromByID[end.chat.id]!
                return BadgeVisual(chat: end.chat, rect: Motion.reduced ? end.rect : Motion.mix(start.rect, end.rect, p),
                    color: Motion.mix(start.color, end.color, p), alpha: Motion.mix(start.alpha, end.alpha, p),
                    scale: Motion.reduced ? 1 : Motion.mix(start.scale, end.scale, p))
            }
            self.onWidthChange?(self.frame.width)
            self.needsDisplay = true
        }, completion: { [weak self] in
            self?.badges.removeAll { $0.alpha == 0 }
            self?.rebuildAccessibility()
            completion?()
        })
    }

    override func draw(_ dirtyRect: NSRect) {
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current?.cgContext.setAlpha(opacity)
        let l = layout
        let pill = CGRect(x: Layout.value("host-inset"), y: l.capsule.minY, width: max(0, bounds.width - Layout.value("host-inset") * 2), height: l.capsuleHeight)
        let path = NSBezierPath(roundedRect: pill, xRadius: pill.height / 2, yRadius: pill.height / 2)
        pillColor.setFill()
        path.fill()
        path.addClip()
        let foreground = project.kind == "global-control" && project.summaryStatus != nil ? Palette.foreground(pillColor) : NSColor.white
        if !l.icon.isEmpty { Drawing.icon(project, rect: l.icon, color:foreground) }
        Drawing.label(displayName, rect:l.name,role:"menu",color:foreground)
        if project.kind == "global-control" && project.summaryStatus == "unknown" {
            let edge=NSBezierPath(roundedRect:pill.insetBy(dx:1.5,dy:1.5),xRadius:pill.height/2,yRadius:pill.height/2)
            edge.lineWidth=1;edge.setLineDash([2,2],count:2,phase:0);NSColor.black.setStroke();edge.stroke()
        }
        for badge in badges {
            let rect = badge.rect.insetBy(dx: badge.rect.width * (1 - badge.scale) / 2, dy: badge.rect.height * (1 - badge.scale) / 2)
            Drawing.badge(badge.chat, rect: rect, color: badge.color, alpha: badge.alpha * opacity, pressed: pressedID == badge.chat.id)
        }
        NSGraphicsContext.restoreGraphicsState()
    }

    // Hit-test the animated presentation by stable chat identity. An outgoing
    // circle is immediately noninteractive; list changes cannot open its neighbour.
    func chatID(at point: CGPoint) -> String? {
        guard visible else { return nil }
        let live = Set(project.threads.map(\.id))
        return badges.first { live.contains($0.chat.id) && $0.alpha > 0.45 && $0.rect.insetBy(dx: -1, dy: -2).contains(point) }?.chat.id
    }

    private func rebuildAccessibility() {
        removeAllToolTips()
        tips.removeAll()
        setAccessibilityElement(visible)
        guard visible else { setAccessibilityChildren([]);return }
        tips[addToolTip(CGRect(x: 0, y: 0, width: layout.firstBadgeX - 2, height: bounds.height), owner: self, userData: nil)] = ""
        var children: [NSAccessibilityElement] = []
        let manage = ChatAccessibilityElement(onPress: { [weak self] in
            guard let self,self.visible else { return }; self.onShowPopover?(self, true)
        })
        manage.setAccessibilityRole(.button)
        manage.setAccessibilityLabel(language.text("expandProject", ["project": displayName, "source": project.locationLabel(in: language)]) + (project.kind == "global-control" ? " · " + aggregateDetail : ""))
        manage.setAccessibilityParent(self)
        manage.setAccessibilityFrameInParentSpace(CGRect(x: 0, y: 0, width: layout.firstBadgeX - 2, height: bounds.height))
        children.append(manage)
        for (i, chat) in project.threads.enumerated() {
            tips[addToolTip(layout.badge(i).insetBy(dx: -1, dy: -2), owner: self, userData: nil)] = chat.id
            let element = ChatAccessibilityElement(onPress: { [weak self] in
                guard let self,self.visible,self.project.threads.contains(where: { $0.id == chat.id }) else { return };self.onEvent("open",chat.id)
            })
            element.setAccessibilityRole(.button)
            element.setAccessibilityLabel(language.text("openBadge", ["project": displayName, "n": String(chat.index), "title": chat.title, "status": chat.detail]))
            element.setAccessibilityParent(self)
            element.setAccessibilityFrameInParentSpace(layout.badge(i))
            children.append(element)
        }
        setAccessibilityLabel(displayName)
        setAccessibilityChildren(children)
    }

    func view(_ view: NSView, stringForToolTip tag: NSView.ToolTipTag, point: NSPoint, userData: UnsafeMutableRawPointer?) -> String {
        guard let id = tips[tag], let chat = project.threads.first(where: { $0.id == id }) else {
            return displayName + " · " + (project.isStatusControl ? language.text("allProjects") : project.locationLabel(in: language)) + "\n" + aggregateDetail + "\n" + language.text("openPanelHint")
        }
        return "\(project.name) · \(chat.index) · \(project.locationLabel(in: language))\n\(chat.title)\n\(chat.detail) · \(chat.elapsed(in: language))\n\(language.text("backToChatHint"))"
    }

    override func mouseDown(with event: NSEvent) {
        guard visible else { return }
        pressedID = chatID(at: convert(event.locationInWindow, from: nil))
        if pressedID == nil { onShowPopover?(self, false) }
        needsDisplay = true
    }

    override func mouseUp(with event: NSEvent) {
        let hit = chatID(at: convert(event.locationInWindow, from: nil))
        if let pressedID, hit == pressedID { onEvent("open", pressedID) }
        pressedID = nil
        needsDisplay = true
    }

    override func rightMouseDown(with event: NSEvent) { guard visible else { return };onShowPopover?(self, false) }

    @objc func openFromStatusButton(_ sender: NSButton) {
        // Pointer-down is already handled by this child view. Some status-button
        // hosts also deliver a button action on release; that must not toggle a
        // second time. Preserve keyboard and accessibility/performClick entry.
        guard visible,NSApp.currentEvent == nil || NSApp.currentEvent?.type == .keyDown else { return }
        onShowPopover?(self, true)
    }

    override func keyDown(with event: NSEvent) {
        guard visible else { return }
        if event.characters == " " || event.keyCode == 36 { onShowPopover?(self, true) }
        else { super.keyDown(with: event) }
    }
}
