import AppKit
import QuartzCore

struct PopupLayout: Sendable {
    static var width: CGFloat { Layout.value("panel-w") }
    static var rowHeight: CGFloat { Layout.value("row-h") }
    static var rowsTop: CGFloat {
        let grid = Layout.grid("panel")
        return Layout.value("arrow-h") + grid.intrinsicSize().height - grid.padding[2] + Layout.value("list-top")
    }
    static var headerCenterY: CGFloat { PopupLayout(count: 1, maximumHeight: Layout.value("panel-max-h")).headerFrame.midY }
    let count: Int
    let maximumHeight: CGFloat
    var availableWidth: CGFloat = Layout.value("panel-w")
    var surfaceHeight: CGFloat? = nil
    var documentHeightOverride: CGFloat? = nil
    var isGlobal = false
    var panelWidth: CGFloat { min(Self.width, availableWidth) }
    var documentHeight: CGFloat { documentHeightOverride ?? CGFloat(count) * Self.rowHeight }
    private var bottomPadding: CGFloat { Layout.grid("panel").padding[2] }
    var viewportHeight: CGFloat {
        if let surfaceHeight { return max(0, surfaceHeight - Self.rowsTop - bottomPadding) }
        return min(count == 0 ? Layout.value("empty-h") : documentHeight, max(0, maximumHeight - Self.rowsTop - bottomPadding))
    }
    var height: CGFloat { Self.rowsTop + viewportHeight + bottomPadding }
    var body: CGRect { CGRect(x: 0, y: Layout.value("arrow-h"), width: panelWidth, height: max(0, height - Layout.value("arrow-h"))) }
    var cells: PlacedGrid { Layout.grid("panel").place(in: body) }
    var headerFrame: CGRect { cells.cell(0, 0) }
    private var headerCells: PlacedGrid { Layout.grid(isGlobal ? "globalHeader" : "header").place(in: headerFrame) }
    var icon: CGRect { headerCells.item(0, size: CGSize(width: Layout.value("header-icon"), height: Layout.value("header-icon"))) }
    var headerCopy: CGRect {
        let height = Layout.grid("headerCopy").intrinsicSize().height
        return headerCells.item(1, size: CGSize(width: headerCells.cell(1).width, height: height))
    }
    var title: CGRect { Layout.grid("headerCopy").place(in: headerCopy).cell(0, 0) }
    var source: CGRect { Layout.grid("headerCopy").place(in: headerCopy).cell(0, 1) }
    var settings: CGRect { isGlobal ? headerCells.item(2,size:CGSize(width:Layout.value("control"),height:Layout.value("control"))) : .zero }
    var reload: CGRect { headerCells.item(isGlobal ? 3 : 2, size: CGSize(width: Layout.value("control"), height: Layout.value("control"))) }
    var toggle: CGRect { headerCells.item(isGlobal ? 4 : 3, size: CGSize(width: Layout.value("switch-w"), height: Layout.value("control"))) }
    var divider: CGRect { cells.cell(0, 1).insetBy(dx: Layout.value("divider-inset"), dy: 0) }
    var viewport: CGRect {
        let frame = cells.cell(0, 2), top = Layout.value("list-top")
        return CGRect(x: frame.minX, y: frame.minY + top, width: frame.width, height: max(0, frame.height - top))
    }
    func row(_ i: Int) -> CGRect { CGRect(x: 0, y: CGFloat(i) * Self.rowHeight, width: viewport.width, height: Self.rowHeight) }
    static func headerIcon() -> CGRect { PopupLayout(count: 1, maximumHeight: Layout.value("panel-max-h")).icon }
    static func headerTitle(width: CGFloat) -> CGRect { PopupLayout(count: 1, maximumHeight: Layout.value("panel-max-h"), availableWidth: width).title }
    static func headerGroup(width: CGFloat) -> CGRect { PopupLayout(count: 1, maximumHeight: Layout.value("panel-max-h"), availableWidth: width).headerCopy }
    static func reloadControl(width: CGFloat) -> CGRect { PopupLayout(count: 1, maximumHeight: Layout.value("panel-max-h"), availableWidth: width).reload }
    static func switchControl(width: CGFloat) -> CGRect { PopupLayout(count: 1, maximumHeight: Layout.value("panel-max-h"), availableWidth: width).toggle }

    // AppKit screen coordinates are y-up; the grid itself remains y-down.
    // Only this host boundary converts coordinates. Both surfaces share the arrow
    // height, safe gutter and trigger centre instead of maintaining popup offsets.
    static func placement(anchor: CGRect, screen: CGRect, height: CGFloat, width requested: CGFloat = Layout.value("panel-w")) -> (frame: CGRect, arrowX: CGFloat) {
        let gutter = Layout.value("safe-gap"), arrowInset = Layout.value("arrow-inset")
        let width = min(requested, screen.width - gutter * 2)
        let x = min(screen.maxX - width - gutter, max(screen.minX + gutter, anchor.midX - width / 2))
        return (CGRect(x: x, y: anchor.minY - Layout.value("panel-anchor-gap") - height, width: width, height: height),
                min(width - arrowInset, max(arrowInset, anchor.midX - x)))
    }
}
@MainActor
final class PanelActionButton: NSButton {
    var onActivate: (() -> Void)?
    var onNavigate: ((Int) -> Void)?
    var onDismiss: (() -> Void)?
    var painter: ((PanelActionButton) -> Void)?
    var paintOpacity: CGFloat = 1 { didSet { needsDisplay = true } }
    private var hover = false
    private var area: NSTrackingArea?
    var isHovered: Bool { hover }
    var isKeyboardFocused: Bool { window?.firstResponder === self }

    init(label: String, action: @escaping () -> Void) {
        super.init(frame: .zero)
        isBordered = false
        title = ""
        focusRingType = .none
        target = self
        self.action = #selector(activate)
        onActivate = action
        setAccessibilityLabel(label)
        setButtonType(.momentaryPushIn)
    }
    required init?(coder: NSCoder) { nil }
    override var isFlipped: Bool { true }
    override var acceptsFirstResponder: Bool { true }
    override var needsPanelToBecomeKey: Bool { true }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    @objc private func activate() { onActivate?() }
    override func draw(_ dirtyRect: NSRect) {
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current?.cgContext.setAlpha(paintOpacity)
        painter?(self)
        NSGraphicsContext.restoreGraphicsState()
    }
    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        if let area { removeTrackingArea(area) }
        let next = NSTrackingArea(rect: bounds, options: [.activeAlways, .mouseEnteredAndExited, .inVisibleRect], owner: self)
        area = next
        addTrackingArea(next)
    }
    override func mouseEntered(with event: NSEvent) { hover = true; needsDisplay = true }
    override func mouseExited(with event: NSEvent) { hover = false; needsDisplay = true }
    override func becomeFirstResponder() -> Bool { needsDisplay = true; return super.becomeFirstResponder() }
    override func resignFirstResponder() -> Bool { needsDisplay = true; return super.resignFirstResponder() }
    override func keyDown(with event: NSEvent) {
        switch event.keyCode {
        case 53: onDismiss?()
        case 125: onNavigate?(1)
        case 126: onNavigate?(-1)
        case 36, 76, 49: performClick(nil)
        default: super.keyDown(with: event)
        }
    }

    func drawHighlight(in rect: CGRect, radius: CGFloat = 9) {
        if isHovered || isHighlighted || isKeyboardFocused {
            NSColor.white.withAlphaComponent(isHighlighted ? 0.18 : 0.10).setFill()
            NSBezierPath(roundedRect: rect, xRadius: radius, yRadius: radius).fill()
        }
        if isKeyboardFocused {
            NSColor.white.withAlphaComponent(0.8).setStroke()
            let outline = NSBezierPath(roundedRect: rect.insetBy(dx: 1, dy: 1), xRadius: radius, yRadius: radius)
            outline.lineWidth = 1
            outline.stroke()
        }
    }
}

@MainActor
final class ChatRowView: NSView {
    var grouped = false
    private(set) var chat: Chat
    private(set) var language: InterfaceLanguage
    let openButton: PanelActionButton
    let seenButton: PanelActionButton
    private var color: NSColor
    private let colorMotion = MotionDriver()
    var onNavigate: ((Int) -> Void)? {
        didSet { openButton.onNavigate = onNavigate; seenButton.onNavigate = onNavigate }
    }
    var onDismiss: (() -> Void)? {
        didSet { openButton.onDismiss = onDismiss; seenButton.onDismiss = onDismiss }
    }
    var paintOpacity: CGFloat = 1 {
        didSet { openButton.paintOpacity = paintOpacity; seenButton.paintOpacity = paintOpacity }
    }

    init(chat: Chat, language: InterfaceLanguage = .chinese, onEvent: @escaping (String, String?) -> Void) {
        self.chat = chat
        self.language = language
        color = Palette.background(chat.status)
        openButton = PanelActionButton(label: language.text("openChat")) { onEvent("open", chat.id) }
        seenButton = PanelActionButton(label: language.text("seen")) { onEvent("seen", chat.id) }
        super.init(frame: CGRect(x: 0, y: 0, width: PopupLayout(count: 1, maximumHeight: Layout.value("panel-max-h")).viewport.width, height: PopupLayout.rowHeight))
        setAccessibilityElement(false)
        addSubview(openButton)
        addSubview(seenButton)
        openButton.painter = { [weak self] button in
            guard let self else { return }
            button.drawHighlight(in: button.bounds.insetBy(dx: 0, dy: 2))
            let grid = RowLayout(width: self.bounds.width, height: self.bounds.height, grouped:self.grouped)
            Drawing.badge(self.chat, rect: grid.badge, color: self.color, alpha: button.paintOpacity)
            Drawing.label(self.chat.title, rect: grid.title, role: "title")
            Drawing.label(self.chat.detailLine(in:self.language), rect: grid.detail, role: "detail",
                          color: .white.withAlphaComponent(0.70))
        }
        seenButton.painter = { button in
            button.drawHighlight(in: button.bounds.insetBy(dx: 1, dy: 3), radius: 8)
            let config = NSImage.SymbolConfiguration(pointSize: Layout.value("control-icon"), weight: .medium).applying(.init(paletteColors: [.white]))
            NSImage(systemSymbolName: "checkmark", accessibilityDescription: nil)?.withSymbolConfiguration(config)?
                .draw(in: Layout.square(Layout.value("control-icon"), in: button.bounds))
        }
        seenButton.toolTip = language.text("seen")
        update(chat, animated: false)
    }
    required init?(coder: NSCoder) { nil }
    override var isFlipped: Bool { true }

    func update(_ chat: Chat, animated: Bool = true, language: InterfaceLanguage? = nil) {
        if let language { self.language = language }
        let changed = self.chat.status != chat.status
        self.chat = chat
        seenButton.toolTip = self.language.text("seen")
        seenButton.isHidden = !chat.canMarkSeen
        openButton.toolTip = chat.title + "\n" + chat.detailLine(in:self.language)
        openButton.setAccessibilityLabel(self.language.text("openRow", ["n": String(chat.index), "title": chat.title]))
        seenButton.setAccessibilityLabel(self.language.text("seenLabel", ["n": String(chat.index)]))
        let old = color, new = Palette.background(chat.status)
        if changed && animated {
            colorMotion.start(duration: Motion.color, frame: { [weak self] p in
                self?.color = Motion.mix(old, new, p)
                self?.openButton.needsDisplay = true
            })
        } else if !animated { colorMotion.stop(); color = new }
        needsLayout = true
        openButton.needsDisplay = true
    }

    override func layout() {
        super.layout()
        let grid = RowLayout(width: bounds.width, height: bounds.height, grouped:grouped)
        openButton.frame = grid.open
        seenButton.frame = grid.seen
    }
}

@MainActor
private final class FlippedView: NSView {
    var acceptsInput = true
    override var isFlipped: Bool { true }
    override func hitTest(_ point: NSPoint) -> NSView? { acceptsInput ? super.hitTest(point) : nil }
}

@MainActor
final class ProjectPanelView: NSView {
    private(set) var project: Project
    private(set) var language: InterfaceLanguage
    private(set) var connectionDetail: String
    private(set) var rows: [String: ChatRowView] = [:]
    private(set) var projectControls: [Project] = []
    private(set) var controlRows: [String: ProjectControlRowView] = [:]
    private var controlOrder: [String] = []
    private(set) var groupedRows: [String: ChatRowView] = [:]
    private(set) var settingsDocument: AlertSettingsView?
    private(set) var showingAlerts = false
    private var settingsTarget = false
    private var routeRevision = 0
    private let routeMotion = MotionDriver(), iconMotion = MotionDriver()
    private var iconProgress: CGFloat = 0
    private var routeOffset: CGFloat = 0
    private var bodyInteractive = true
    private var laidOutAlerts: Bool?
    private var routeWaiters: [() -> Void] = []
    var onRouteSample: (([String:Any])->Void)?
    private var routeScroll: [Bool:CGPoint] = [:]
    var notificationStates = Set(Layout.specification.alertTypes)
    var compactMenuBar = false
    var statusEmoji = EmojiPickerButton.defaultEmoji
    var isChoosingEmoji: Bool { settingsDocument?.emojiButton.choosing ?? false }
    let settingsButton: PanelActionButton
    private var positions: [String: CGRect] = [:]
    private var controlTargetFrames: [String: CGRect] = [:]
    private var controlTargetSize: CGSize?
    private var alphas: [String: CGFloat] = [:]
    private let motion = MotionDriver()
    private let scroll = NSScrollView()
    private let document = FlippedView()
    let reloadButton: PanelActionButton
    let monitorSwitch = NSSwitch()
    private(set) var monitorEnabled = true
    private let onEvent: (String, String?) -> Void
    var onHeightChange: (() -> Void)?
    var onDismiss: (() -> Void)?
    var maximumHeight: CGFloat = Layout.value("panel-max-h")
    var availableWidth: CGFloat = PopupLayout.width
    var arrowX: CGFloat = PopupLayout.width / 2 { didSet { needsDisplay = true } }
    var globalFrames: [String: CGRect] {
        var frames: [String: CGRect] = [:], y: CGFloat = 0
        let width = PopupLayout(count:1,maximumHeight:maximumHeight,availableWidth:availableWidth).viewport.width
        for (i,p) in projectControls.enumerated() {
            if i > 0 { y += Layout.value("group-gap") }
            frames["project:"+p.id] = CGRect(x:0,y:y,width:width,height:Layout.value("project-control-h")); y += Layout.value("project-control-h")
            for chat in compactMenuBar ? p.threads : [] {
                frames["chat:"+chat.id] = CGRect(x:0,y:y,width:width,height:PopupLayout.rowHeight); y += PopupLayout.rowHeight
            }
        }
        return frames
    }
    var preferredLayout: PopupLayout {
        if project.isStatusControl {
            let count = showingAlerts ? Layout.specification.alertTypes.count + 1 : globalFrames.count
            let height = showingAlerts ? AlertSettingsView.height : globalFrames.values.map(\.maxY).max() ?? 0
            return PopupLayout(count:count,maximumHeight:maximumHeight,availableWidth:availableWidth,documentHeightOverride:height,isGlobal:true)
        }
        return PopupLayout(count:project.threads.count,maximumHeight:maximumHeight,availableWidth:availableWidth)
    }

    init(project: Project, detail: String, enabled: Bool = true, language: InterfaceLanguage = .chinese, onEvent: @escaping (String, String?) -> Void) {
        self.project = project
        self.language = language
        connectionDetail = detail
        self.onEvent = onEvent
        monitorEnabled = enabled
        settingsButton = PanelActionButton(label:language.text("settings")) {}
        reloadButton = PanelActionButton(label: language.text("productionReload")) { onEvent("reload", nil) }
        super.init(frame: CGRect(x: 0, y: 0, width: PopupLayout.width, height: PopupLayout(count: project.threads.count, maximumHeight: Layout.value("panel-max-h")).height))
        appearance = NSAppearance(named: .darkAqua)
        setAccessibilityElement(false)
        setAccessibilityRole(.group)
        setAccessibilityLabel(self.language.text("projectChats", ["project": project.name]))
        scroll.drawsBackground = false
        scroll.contentView.drawsBackground = false
        scroll.borderType = .noBorder
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        scroll.scrollerStyle = .overlay
        scroll.scrollerKnobStyle = .light
        scroll.documentView = document
        addSubview(scroll)
        document.wantsLayer = true
        settingsButton.onActivate = { [weak self] in
            guard let self else { return }
            self.setShowingAlerts(!self.settingsTarget,animated:NSApp.currentEvent?.type != .keyDown)
        }
        settingsButton.painter = { [weak self] button in
            guard let self else { return }
            button.drawHighlight(in:button.bounds.insetBy(dx:1,dy:1),radius:8)
            let rect=Layout.square(Layout.value("control-icon"),in:button.bounds)
            for (symbol,alpha) in [("slider.horizontal.3",1-self.iconProgress),("chevron.left",self.iconProgress)] {
                let config=NSImage.SymbolConfiguration(pointSize:Layout.value("control-icon"),weight:.medium).applying(.init(paletteColors:[.white.withAlphaComponent(0.85)]))
                NSImage(systemSymbolName:symbol,accessibilityDescription:nil)?.withSymbolConfiguration(config)?.draw(in:rect,from:.zero,operation:.sourceOver,fraction:alpha)
            }
        }
        settingsButton.onDismiss = { [weak self] in self?.onDismiss?() }
        addSubview(settingsButton)
        reloadButton.toolTip = self.language.text("productionReloadHint")
        reloadButton.painter = { button in
            button.drawHighlight(in: button.bounds.insetBy(dx: 1, dy: 1), radius: 8)
            let config = NSImage.SymbolConfiguration(pointSize: Layout.value("control-icon"), weight: .medium).applying(.init(paletteColors: [.white.withAlphaComponent(0.8)]))
            NSImage(systemSymbolName: "arrow.clockwise", accessibilityDescription: nil)?.withSymbolConfiguration(config)?
                .draw(in: Layout.square(Layout.value("control-icon"), in: button.bounds))
        }
        reloadButton.onNavigate = { [weak self] direction in self?.navigate(direction) }
        reloadButton.onDismiss = { [weak self] in self?.onDismiss?() }
        addSubview(reloadButton)
        monitorSwitch.controlSize = .small
        monitorSwitch.target = self
        monitorSwitch.action = #selector(setMonitoring(_:))
        monitorSwitch.setAccessibilityLabel(self.language.text("monitorLabel"))
        addSubview(monitorSwitch)
        setMonitorEnabled(enabled)
        update(project, detail: detail, animated: false)
    }
    required init?(coder: NSCoder) { nil }
    override var isFlipped: Bool { true }
    override var acceptsFirstResponder: Bool { true }
    override var needsPanelToBecomeKey: Bool { true }

    func update(_ value: Project, detail: String, animated: Bool = true, language: InterfaceLanguage? = nil) {
        if let language { self.language = language }
        settingsButton.isHidden = !value.isStatusControl
        settingsButton.setAccessibilityLabel(self.language.text(settingsTarget ? "backToProjects" : "settings"))
        settingsButton.toolTip = self.language.text(settingsTarget ? "backToProjects" : "alertSettingsHint")
        reloadButton.setAccessibilityLabel(self.language.text("productionReload"))
        reloadButton.toolTip = self.language.text("productionReloadHint")
        monitorSwitch.setAccessibilityLabel(self.language.text("monitorLabel"))
        if value.isStatusControl {
            project = value; connectionDetail = detail; setMonitorEnabled(monitorEnabled)
            updateControlRows(animated: animated)
            return
        }
        let previousIDs = project.threads.map(\.id)
        let focused = rows.first { $0.value.openButton.isKeyboardFocused || $0.value.seenButton.isKeyboardFocused }?.key
        project = value
        setMonitorEnabled(monitorEnabled)
        connectionDetail = detail
        setAccessibilityLabel(self.language.text("projectChats", ["project": project.name]))
        let live = Set(value.threads.map(\.id))
        let structureChanged = previousIDs != value.threads.map(\.id) || rows.count != value.threads.count
        let geometryChanged = abs(frame.width - preferredLayout.panelWidth) > 0.1 || abs(frame.height - preferredLayout.height) > 0.1
        let shouldAnimate = animated && (structureChanged || geometryChanged)
        for (i, chat) in value.threads.enumerated() {
            let row: ChatRowView
            if let old = rows[chat.id] {
                row = old
                row.update(chat, animated: animated, language: self.language)
            } else {
                row = ChatRowView(chat: chat, language: self.language, onEvent: onEvent)
                rows[chat.id] = row
                document.addSubview(row)
                positions[chat.id] = preferredLayout.row(i).offsetBy(dx: 0, dy: shouldAnimate && !Motion.reduced ? -4 : 0)
                alphas[chat.id] = shouldAnimate ? 0 : 1
                row.onNavigate = { [weak self] direction in self?.navigate(direction) }
                row.onDismiss = { [weak self] in self?.onDismiss?() }
            }
            row.openButton.isEnabled = true
            row.seenButton.isEnabled = true
            row.setAccessibilityHidden(false)
        }
        for (id, row) in rows where !live.contains(id) {
            row.openButton.isEnabled = false
            row.seenButton.isEnabled = false
            row.setAccessibilityHidden(true)
        }
        if let focused, !live.contains(focused) { window?.makeFirstResponder(self) }
        if !structureChanged && !geometryChanged && animated {
            rebuildKeyChain()
            needsDisplay = true
            return
        }
        let starts = positions, startAlphas = alphas, startHeight = frame.height, startWidth = frame.width
        let targetHeight = preferredLayout.height, layout = preferredLayout
        motion.start(duration: shouldAnimate ? Motion.layout : 0, frame: { [weak self] p in
            guard let self else { return }
            self.frame.size.height = Motion.reduced ? targetHeight : Motion.mix(startHeight, targetHeight, p)
            self.frame.size.width = Motion.reduced ? layout.panelWidth : Motion.mix(startWidth, layout.panelWidth, p)
            self.document.frame.size = CGSize(width: layout.viewport.width, height: max(layout.documentHeight, layout.viewportHeight))
            for (id, row) in self.rows {
                let i = value.threads.firstIndex { $0.id == id }
                let start = starts[id] ?? .zero
                let target = i.map { layout.row($0) } ?? start.offsetBy(dx: 0, dy: Motion.reduced ? 0 : -4)
                let rect = Motion.reduced ? target : Motion.mix(start, target, p)
                let alpha = Motion.mix(startAlphas[id] ?? 1, i == nil ? 0 : 1, p)
                self.positions[id] = rect
                self.alphas[id] = alpha
                row.frame = rect
                row.paintOpacity = alpha
            }
            self.needsLayout = true
            self.needsDisplay = true
            self.onHeightChange?()
        }, completion: { [weak self] in
            guard let self else { return }
            for id in Array(self.rows.keys) where !live.contains(id) {
                self.rows.removeValue(forKey: id)?.removeFromSuperview()
                self.positions.removeValue(forKey: id)
                self.alphas.removeValue(forKey: id)
            }
            self.rebuildKeyChain()
        })
    }

    func setProjectControls(_ projects: [Project]) { projectControls = projects }

    private func updateControlRows(animated: Bool) {
        let frames = globalFrames, live = Set(frames.keys), target = preferredLayout
        // Presentation positions still contain fading-out rows. Compare the
        // previous TARGET instead, so immediate compact→full→compact reversals
        // cancel the old removal even before the first animation frame.
        let targetSize=CGSize(width:target.panelWidth,height:target.height)
        let changed = laidOutAlerts != showingAlerts || controlTargetFrames != frames || controlTargetSize != targetSize
            || (!motion.isRunning && (abs(frame.height-target.height)>0.1 || abs(frame.width-target.panelWidth)>0.1))
        laidOutAlerts = showingAlerts;controlTargetFrames=frames;controlTargetSize=targetSize
        controlOrder = projectControls.map(\.id)
        for value in projectControls {
            if let row=controlRows[value.id] { row.update(value,language:language,globalEnabled:monitorEnabled) }
            else {
                let row=ProjectControlRowView(project:value,language:language,globalEnabled:monitorEnabled,onEvent:onEvent)
                row.singleLine=true
                controlRows[value.id]=row;document.addSubview(row);positions["project:"+value.id]=frames["project:"+value.id];alphas["project:"+value.id]=animated ? 0 : 1
            }
            controlRows[value.id]?.isHidden = showingAlerts
            for chat in compactMenuBar ? value.threads : [] {
                let key="chat:"+chat.id
                if let row=groupedRows[chat.id] { row.update(chat,animated:animated,language:language) }
                else {
                    let row=ChatRowView(chat:chat,language:language,onEvent:onEvent);row.grouped=true
                    groupedRows[chat.id]=row;document.addSubview(row);positions[key]=frames[key];alphas[key]=animated ? 0 : 1
                    row.onNavigate={ [weak self] direction in self?.navigate(direction) };row.onDismiss={ [weak self] in self?.onDismiss?() }
                }
                groupedRows[chat.id]?.isHidden=showingAlerts
            }
        }
        if showingAlerts {
            if settingsDocument == nil {
                let settings=AlertSettingsView(language:language,onEvent:onEvent);settingsDocument=settings;document.addSubview(settings)
            }
            settingsDocument?.isHidden=false
            settingsDocument?.update(compact:compactMenuBar,states:notificationStates,emoji:statusEmoji,language:language)
        } else { settingsDocument?.isHidden=true }
        for (id,row) in controlRows where !live.contains("project:"+id) { row.isHidden=showingAlerts;row.toggle.isEnabled=false;row.setAccessibilityHidden(true) }
        for (id,row) in groupedRows where !live.contains("chat:"+id) { row.isHidden=showingAlerts;row.openButton.isEnabled=false;row.seenButton.isEnabled=false;row.setAccessibilityHidden(true) }
        setBodyInteractive(bodyInteractive)
        if !changed && animated { rebuildKeyChain();needsDisplay=true;return }
        let starts=positions,startAlphas=alphas,startHeight=frame.height,startWidth=frame.width
        motion.start(duration:animated ? Layout.specification.settingsMotion.resize : 0,frame:{ [weak self] p in
            guard let self else { return }
            self.frame.size=CGSize(width:Motion.reduced ? target.panelWidth : Motion.mix(startWidth,target.panelWidth,p),height:Motion.reduced ? target.height : Motion.mix(startHeight,target.height,p))
            self.document.frame.size=CGSize(width:target.viewport.width,height:max(target.documentHeight,target.viewportHeight))
            self.settingsDocument?.frame=CGRect(x:0,y:0,width:target.viewport.width,height:AlertSettingsView.height)
            for key in Set(starts.keys).union(frames.keys) {
                let end=frames[key] ?? (starts[key] ?? .zero).offsetBy(dx:0,dy:Motion.reduced ? 0 : -4)
                let rect=Motion.reduced ? end : Motion.mix(starts[key] ?? end,end,p)
                self.positions[key]=rect
                let alpha=Motion.mix(startAlphas[key] ?? 1,live.contains(key) ? 1 : 0,p);self.alphas[key]=alpha
                if key.hasPrefix("chat:") { let id=String(key.dropFirst(5));self.groupedRows[id]?.frame=rect;self.groupedRows[id]?.paintOpacity=alpha }
                else { let id=String(key.dropFirst(8));self.controlRows[id]?.frame=rect;self.controlRows[id]?.paintOpacity=alpha }
            }
            self.needsLayout=true;self.needsDisplay=true;self.onHeightChange?()
        },completion:{ [weak self] in
            guard let self else { return }
            for id in Array(self.controlRows.keys) where !live.contains("project:"+id) { self.controlRows.removeValue(forKey:id)?.removeFromSuperview();self.positions.removeValue(forKey:"project:"+id);self.alphas.removeValue(forKey:"project:"+id) }
            for id in Array(self.groupedRows.keys) where !live.contains("chat:"+id) { self.groupedRows.removeValue(forKey:id)?.removeFromSuperview();self.positions.removeValue(forKey:"chat:"+id);self.alphas.removeValue(forKey:"chat:"+id) }
            self.rebuildKeyChain();self.notifyRouteSettled()
        })
    }

    private func setBodyInteractive(_ value: Bool) {
        bodyInteractive=value;document.acceptsInput=value
        let liveProjects=Set(projectControls.map(\.id)),liveChats=Set(compactMenuBar ? projectControls.flatMap { $0.threads.map(\.id) } : [])
        for (id,row) in controlRows { let active=liveProjects.contains(id);row.toggle.isEnabled=value && !showingAlerts && active;row.setAccessibilityHidden(showingAlerts || !active) }
        for (id,row) in groupedRows { let active=liveChats.contains(id);row.openButton.isEnabled=value && !showingAlerts && active;row.seenButton.isEnabled=value && !showingAlerts && active;row.setAccessibilityHidden(showingAlerts || !active) }
        settingsDocument?.setBodyEnabled(value && showingAlerts)
        settingsDocument?.setAccessibilityHidden(!showingAlerts)
    }
    func setShowingAlerts(_ target: Bool, animated: Bool = true) {
        guard project.isStatusControl else { return }
        if target != showingAlerts, !routeMotion.isRunning { routeScroll[showingAlerts]=scroll.contentView.bounds.origin }
        settingsTarget=target;routeRevision += 1
        let revision=routeRevision,startIcon=iconProgress
        settingsButton.setAccessibilityLabel(language.text(target ? "backToProjects" : "settings"))
        settingsButton.toolTip=language.text(target ? "backToProjects" : "alertSettingsHint")
        iconMotion.start(duration:animated ? Layout.specification.settingsMotion.icon : 0,frame:{ [weak self] p in
            self?.iconProgress=Motion.mix(startIcon,target ? 1 : 0,p);self?.settingsButton.needsDisplay=true
        })
        window?.makeFirstResponder(settingsButton);setBodyInteractive(false)
        func finish() {
            guard revision == routeRevision else { return }
            setBodyInteractive(true);notifyRouteSettled()
        }
        func reveal() {
            let alpha=document.alphaValue,offset=routeOffset
            routeMotion.start(duration:animated ? Layout.specification.settingsMotion.in : 0,frame:{ [weak self] p in
                guard let self else { return }
                self.document.alphaValue=Motion.mix(alpha,1,p);self.routeOffset=Motion.mix(offset,0,p)
                self.document.layer?.transform=CATransform3DMakeTranslation(self.routeOffset,0,0)
                self.onRouteSample?(["alpha":self.document.alphaValue,"offset":self.routeOffset,"settings":self.showingAlerts,"target":self.settingsTarget,"height":self.frame.height])
            },completion:finish)
        }
        guard target != showingAlerts else { reveal();return }
        let alpha=document.alphaValue,offset=routeOffset
        routeMotion.start(duration:animated ? Layout.specification.settingsMotion.out : 0,frame:{ [weak self] p in
            guard let self else { return }
            self.document.alphaValue=Motion.mix(alpha,0,p);self.routeOffset=Motion.reduced ? 0 : Motion.mix(offset,-Layout.specification.settingsMotion.offset,p)
            self.document.layer?.transform=CATransform3DMakeTranslation(self.routeOffset,0,0)
                self.onRouteSample?(["alpha":self.document.alphaValue,"offset":self.routeOffset,"settings":self.showingAlerts,"target":self.settingsTarget,"height":self.frame.height])
        },completion:{ [weak self] in
            guard let self, self.routeRevision == revision else { return }
            self.showingAlerts=target
            self.update(self.project,detail:self.connectionDetail,animated:animated)
            self.layoutSubtreeIfNeeded()
            let remembered=self.routeScroll[target] ?? .zero
            self.scroll.contentView.scroll(to:CGPoint(x:0,y:min(max(0,remembered.y),max(0,self.document.bounds.height-self.scroll.contentView.bounds.height))))
            self.scroll.reflectScrolledClipView(self.scroll.contentView)
            self.document.alphaValue=0;self.routeOffset=Motion.reduced ? 0 : Layout.specification.settingsMotion.offset
            reveal()
        })
    }
    func finishRouteAnimation() { routeMotion.finish();routeMotion.finish();iconMotion.finish();motion.finish() }
    private func notifyRouteSettled() {
        guard bodyInteractive, !routeMotion.isRunning, !motion.isRunning else { return }
        let waiters=routeWaiters;routeWaiters.removeAll();waiters.forEach { $0() }
    }
    func whenRouteSettled(_ action:@escaping ()->Void) { if routeMotion.isRunning || motion.isRunning { routeWaiters.append(action) } else { action() } }

    func setMonitorEnabled(_ enabled: Bool) {
        monitorEnabled = enabled
        monitorSwitch.state = enabled ? .on : .off
        monitorSwitch.setAccessibilityLabel(language.text(project.isStatusControl ? "monitorLabel" : "projectSwitch", ["project": project.displayName(in: language)]))
        monitorSwitch.toolTip = language.text(project.isStatusControl ? (enabled ? "monitorOff" : "monitorOn") : (enabled ? "projectOff" : "projectOn"))
    }

    @objc func setMonitoring(_ sender: NSSwitch) {
        if project.isStatusControl { onEvent(sender.state == .on ? "enable" : "disable", nil) }
        else { onEvent(sender.state == .on ? "project_enable" : "project_disable", project.id) }
    }

    func finishAnimation() { motion.finish() }
    override func layout() {
        super.layout()
        let grid = currentGrid
        scroll.frame = grid.viewport
        settingsButton.frame = grid.settings
        reloadButton.frame = grid.reload
        // AppKit controls can have asymmetric alignment insets. Centre the
        // control's public alignment rect in the shared grid cell, not its frame
        // (the current NSSwitch frame otherwise puts its visual centre 0.5pt up).
        let alignment = monitorSwitch.alignmentRect(forFrame: CGRect(origin: .zero, size: grid.toggle.size))
        let target = Layout.centered(alignment.size, in: grid.toggle)
        monitorSwitch.frame = monitorSwitch.frame(forAlignmentRect: target)
    }

    var currentGrid: PopupLayout {
        PopupLayout(count:preferredLayout.count,maximumHeight:bounds.height,availableWidth:bounds.width,surfaceHeight:bounds.height,documentHeightOverride:preferredLayout.documentHeight,isGlobal:project.isStatusControl)
    }

    var headerSubtitle:String {
        if project.isStatusControl {
            if showingAlerts { return language.text("preferences") }
            if !monitorEnabled { return language.text("monitorDisabled") }
            if project.healthDetail != nil { return language.text("statusUnavailable") }
            return language.text(project.syncing == true ? "syncing" : "allProjects")
        }
        return project.locationLabel(in:language)
    }

    override func draw(_ dirtyRect: NSRect) {
        let grid = currentGrid
        let radius = Layout.value("radius"), arrow = Layout.value("arrow-h"), half = Layout.value("arrow-half")
        let body = NSBezierPath(roundedRect: grid.body, xRadius: radius, yRadius: radius)
        let pointer = NSBezierPath()
        pointer.move(to: CGPoint(x: arrowX - half, y: arrow))
        pointer.line(to: CGPoint(x: arrowX, y: 0))
        pointer.line(to: CGPoint(x: arrowX + half, y: arrow))
        pointer.close()
        NSColor.black.setFill()
        body.fill()
        pointer.fill()
        Drawing.icon(project, rect: grid.icon)
        Drawing.label(project.displayName(in: language), rect: grid.title, role: "header")
        Drawing.label(headerSubtitle, rect: grid.source, role: "source", color: .white.withAlphaComponent(0.70))
        NSColor.white.withAlphaComponent(0.12).setFill()
        grid.divider.fill()
        if preferredLayout.count == 0 && !showingAlerts {
            Drawing.label(connectionDetail, rect: grid.viewport, role: "empty",
                          color: .white.withAlphaComponent(0.70), alignment: .center)
        }
    }

    private var orderedButtons: [PanelActionButton] {
        var buttons = project.threads.compactMap { rows[$0.id]?.openButton }
        for chat in project.threads where chat.canMarkSeen {
            if let button = rows[chat.id]?.seenButton { buttons.append(button) }
        }
        buttons.append(reloadButton)
        return buttons
    }
    private func rebuildKeyChain() {
        // Tab follows visual row order, then plugin reload and the on/off switch.
        var buttons: [NSView] = []
        for chat in project.threads {
            if let row = rows[chat.id] {
                buttons.append(row.openButton)
                if chat.canMarkSeen { buttons.append(row.seenButton) }
            }
        }
        if showingAlerts { buttons.append(contentsOf:settingsDocument?.keyViews ?? []) }
        else {
            for project in projectControls {
                if let toggle=controlRows[project.id]?.toggle { buttons.append(toggle) }
                for chat in project.threads {
                    if let row=groupedRows[chat.id] { buttons.append(row.openButton);if chat.canMarkSeen { buttons.append(row.seenButton) } }
                }
            }
        }
        if project.isStatusControl { buttons.append(settingsButton) }
        buttons.append(reloadButton)
        buttons.append(monitorSwitch)
        for (i, button) in buttons.enumerated() { button.nextKeyView = buttons[(i + 1) % buttons.count] }
    }
    func focusFirstRow() { if showingAlerts { window?.makeFirstResponder(settingsDocument?.compactRow.toggle);return };window?.makeFirstResponder(project.isStatusControl ? controlOrder.first.flatMap { controlRows[$0]?.toggle } ?? reloadButton : orderedButtons.first) }
    func navigate(_ direction: Int) {
        let buttons = orderedButtons
        let current = buttons.firstIndex { $0.isKeyboardFocused }
        let next = current.map { ($0 + direction + buttons.count) % buttons.count } ?? (direction > 0 ? 0 : buttons.count - 1)
        window?.makeFirstResponder(buttons[next])
        buttons[next].scrollToVisible(buttons[next].bounds)
    }
    override func keyDown(with event: NSEvent) {
        switch event.keyCode {
        case 53: onDismiss?()
        case 125: navigate(1)
        case 126: navigate(-1)
        case 36, 76, 49: orderedButtons.first?.performClick(nil)
        default: super.keyDown(with: event)
        }
    }
}

@MainActor
private final class StatusPanel: NSPanel {
    var onDismiss: (() -> Void)?
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
    override func cancelOperation(_ sender: Any?) { onDismiss?() }
}

@MainActor
final class ProjectPopover: NSObject, NSWindowDelegate {
    private var panel: StatusPanel?
    private var content: ProjectPanelView?
    private weak var anchor: CapsuleView?
    private let motion = PopoverSpringMotion()
    private var localMonitor: Any?
    private var globalMonitor: Any?
    private var elapsedTimer: Timer?
    private var progress: CGFloat = 0
    private var closingAnchor: CGRect?
    private var closingScreen: CGRect?
    private var intent = PopoverIntent()
    var isShown: Bool { intent.isOpen }
    var motionSnapshot: [String: Any] { ["open": isShown, "visible": panel?.isVisible ?? false, "progress": progress, "velocity": motion.velocity, "animating": motion.isRunning] }
    var onMotionSample: (([String: Any]) -> Void)?
    private var captured = false
    var projectID: String? { isShown ? anchor?.project.id : nil }
    let onEvent: (String, String?) -> Void

    init(onEvent: @escaping (String, String?) -> Void) { self.onEvent = onEvent }

    func toggle(from view: CapsuleView, keyboard: Bool) {
        if isShown && anchor === view { dismiss(animated: !keyboard); return }
        if anchor !== view { dismiss(animated: false) }
        anchor = view
        closingAnchor = nil
        closingScreen = nil
        if panel == nil {
            let panel = StatusPanel(contentRect: .zero, styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
            panel.isReleasedWhenClosed = false
            panel.isOpaque = false
            panel.backgroundColor = .clear
            panel.hasShadow = true
            panel.hidesOnDeactivate = false
            panel.becomesKeyOnlyIfNeeded = false
            panel.level = .popUpMenu
            panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
            panel.appearance = NSAppearance(named: .darkAqua)
            panel.delegate = self
            panel.onDismiss = { [weak self] in self?.dismiss(animated: false) }
            self.panel = panel
        }
        if content?.project.id != view.project.id {
            let content = ProjectPanelView(project: view.project, detail: view.connectionDetail, enabled: view.monitorEnabled, language: view.language, onEvent: { [weak self] event, id in
                guard let self else { return }
                if event == "open" { self.dismiss(animated: NSApp.currentEvent?.type != .keyDown) }
                self.onEvent(event, id)
            })
            content.onHeightChange = { [weak self] in self?.reposition() }
            content.onDismiss = { [weak self] in self?.dismiss(animated: false) }
            self.content = content
            panel?.contentView = content
        }
        update(from: view, animated: false)
        intent.set(true)
        panel?.ignoresMouseEvents = false
        reposition()
        panel?.alphaValue = min(1, max(0, progress))
        panel?.makeKeyAndOrderFront(nil)
        if keyboard { content?.focusFirstRow() } else { panel?.makeFirstResponder(content) }
        installMonitors()
        animate(to: 1, animated: !keyboard)
        captureAfterOpening()
    }

    func update(from view: CapsuleView, animated: Bool = true) {
        guard anchor === view, let content else { return }
        let screen = view.window?.screen ?? NSScreen.main
        if let screen, let window = view.window {
            let rect = window.convertToScreen(view.convert(view.bounds, to: nil))
            content.maximumHeight = min(Layout.value("panel-max-h"), rect.minY - screen.visibleFrame.minY - Layout.value("safe-gap"))
            content.availableWidth = screen.visibleFrame.width - Layout.value("safe-gap") * 2
        }
        content.notificationStates=view.notificationStates;content.compactMenuBar=view.compactMenuBar;content.statusEmoji=view.statusEmoji
        content.setProjectControls(view.projectControls)
        content.setMonitorEnabled(view.monitorEnabled)
        content.update(view.project, detail: view.connectionDetail, animated: animated, language: view.language)
        reposition()
    }

    func reposition() {
        guard let panel, let content else { return }
        let rect: CGRect, screen: CGRect
        if let closingAnchor, let closingScreen { rect = closingAnchor; screen = closingScreen }
        else {
            guard let anchor, let window = anchor.window, let currentScreen = window.screen else { return }
            rect = window.convertToScreen(anchor.convert(anchor.bounds, to: nil)); screen = currentScreen.frame
        }
        let placement = PopupLayout.placement(anchor: rect, screen: screen, height: content.frame.height, width: content.frame.width)
        content.arrowX = placement.arrowX
        var frame = placement.frame
        if !Motion.reduced { frame.origin.y += Layout.specification.popoverMotion.offset * (1 - progress) }
        panel.setFrame(frame, display: true)
        panel.invalidateShadow()
    }

    func dismiss(animated: Bool = true) {
        guard panel != nil else { return }
        if closingAnchor == nil, let anchor, let window = anchor.window {
            closingAnchor = window.convertToScreen(anchor.convert(anchor.bounds, to: nil))
            closingScreen = window.screen?.frame
        }
        content?.settingsDocument?.emojiButton.endChoosing()
        intent.set(false)
        panel?.ignoresMouseEvents = true
        removeMonitors()
        animate(to: 0, animated: animated)
    }

    func whenSettled(_ action: @escaping () -> Void) { motion.whenSettled(action) }
    func resignKeyForInspection() { panel?.resignKey() }

    private func animate(to target: CGFloat, animated: Bool) {
        motion.start(to: target, animated: animated, frame: { [weak self] value in
            guard let self else { return }
            self.progress = value
            self.panel?.alphaValue = min(1, max(0, value))
            self.reposition()
            self.onMotionSample?(self.motionSnapshot)
        }, completion: { [weak self] in
            if target == 0 { self?.panel?.orderOut(nil) }
        })
    }

    private func isOverAnchor(_ point: CGPoint) -> Bool {
        guard let anchor, let window = anchor.window else { return false }
        return window.convertToScreen(anchor.convert(anchor.bounds, to: nil)).contains(point)
    }
    private var isAnchorGestureInProgress: Bool {
        NSEvent.pressedMouseButtons & 3 != 0 && isOverAnchor(NSEvent.mouseLocation)
    }
    func windowDidResignKey(_ notification: Notification) {
        guard isShown, !isAnchorGestureInProgress, content?.isChoosingEmoji != true else { return }
        let revision = intent.revision
        // Clicking the native status item can resign our panel before the child
        // receives mouseDown. Let that explicit toggle win this event turn.
        DispatchQueue.main.async { [weak self] in
            guard let self, self.intent.shouldDismissAfterFocusLoss(revision: revision,
                isKey: self.panel?.isKeyWindow ?? false, anchorGesture: self.isAnchorGestureInProgress) else { return }
            self.dismiss()
        }
    }

    private func installMonitors() {
        removeMonitors()
        let timer = Timer(timeInterval: 1, target: self, selector: #selector(refreshElapsed), userInfo: nil, repeats: true)
        elapsedTimer = timer
        RunLoop.main.add(timer, forMode: .common)
        // Mouse clicks only, while our panel is open. No global keyboard monitor,
        // Accessibility access, event interception or event-content persistence.
        globalMonitor = NSEvent.addGlobalMonitorForEvents(matching: [.leftMouseDown, .rightMouseDown]) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self, !self.isOverAnchor(NSEvent.mouseLocation), self.content?.isChoosingEmoji != true else { return }
                self.dismiss()
            }
        }
        localMonitor = NSEvent.addLocalMonitorForEvents(matching: [.leftMouseDown, .rightMouseDown]) { [weak self] event in
            MainActor.assumeIsolated {
                guard let self else { return }
                if event.window === self.panel { return }
                if self.content?.isChoosingEmoji == true { return }
                if self.isOverAnchor(NSEvent.mouseLocation) { return }
                self.dismiss()
            }
            return event
        }
    }
    private func removeMonitors() {
        elapsedTimer?.invalidate()
        elapsedTimer = nil
        if let localMonitor { NSEvent.removeMonitor(localMonitor) }
        if let globalMonitor { NSEvent.removeMonitor(globalMonitor) }
        localMonitor = nil
        globalMonitor = nil
    }

    @objc private func refreshElapsed() {
        for row in content?.rows.values ?? Dictionary<String, ChatRowView>().values { row.openButton.needsDisplay = true }
    }

    func inspect(from view: CapsuleView, directory: String, requestID: String,
                 completion: @escaping ([String: Any]) -> Void) {
        let openedForInspection = !isShown
        if openedForInspection { toggle(from: view, keyboard: false) }
        motion.whenSettled { [weak self] in
            guard let self, let panel = self.panel, let content = self.content else {
                completion(["visible": false]); return
            }
            var report = LayoutDiagnostics.panel(content)
            report["visible"] = panel.isVisible && self.isShown
            report["windowFrame"] = LayoutDiagnostics.rect(panel.frame)
            report["arrowX"] = content.arrowX
            if let window = view.window {
                report["anchorFrame"] = LayoutDiagnostics.rect(window.convertToScreen(view.convert(view.bounds, to: nil)))
                report["screenFrame"] = window.screen.map { LayoutDiagnostics.rect($0.frame) }
            }
            if let bitmap = content.bitmapImageRepForCachingDisplay(in: content.bounds) {
                content.cacheDisplay(in: content.bounds, to: bitmap)
                let image = URL(fileURLWithPath: directory).appendingPathComponent("inspection-" + requestID + ".png")
                try? bitmap.representation(using: .png, properties: [:])?.write(to: image)
            }
            if openedForInspection, self.anchor === view { self.dismiss(animated: false) }
            completion(report)
        }
    }

    func chooseEmoji(from view:CapsuleView,directory:String,requestID:String) {
        guard !isShown || anchor === view else { return }
        if !isShown { toggle(from:view,keyboard:false) }
        motion.whenSettled { [weak self] in
            guard let self,let content=self.content else { return }
            content.setShowingAlerts(true)
            content.whenRouteSettled {
                guard let field=content.settingsDocument?.emojiButton else { return }
                field.choose()
                let report:[String:Any]=["choosing":field.choosing,"ownInputTarget":self.panel?.firstResponder === field,
                    "keyWindowIsPanel":NSApp.keyWindow === self.panel,"emoji":field.emoji]
                if let data=try? JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]) {
                    try? data.write(to:URL(fileURLWithPath:directory).appendingPathComponent("emoji-picker-"+requestID+".json"))
                }
            }
        }
    }

    func inspectSettings(from view:CapsuleView,directory:String,requestID:String) {
        // Never replace a project panel the user is currently using.
        guard !isShown || anchor === view else { return }
        let opened = !isShown
        if opened { toggle(from:view,keyboard:false) }
        motion.whenSettled { [weak self] in
            guard let self, let content=self.content,content.project.isStatusControl else { return }
            let root=URL(fileURLWithPath:directory),began=CACurrentMediaTime()
            var samples:[[String:Any]]=[],steps:[[String:Any]]=[]
            @MainActor func capture(_ name:String) {
                content.layoutSubtreeIfNeeded()
                var value=LayoutDiagnostics.panel(content);value["step"]=name;value["time"]=CACurrentMediaTime()-began
                steps.append(value)
                if let rep=content.bitmapImageRepForCachingDisplay(in:content.bounds) {
                    content.cacheDisplay(in:content.bounds,to:rep)
                    try? rep.representation(using:.png,properties:[:])?.write(to:root.appendingPathComponent("settings-"+requestID+"-"+name+".png"))
                }
            }
            content.onRouteSample={ value in if samples.count<120 { samples.append(value.merging(["time":CACurrentMediaTime()-began]){_,new in new}) } }
            capture("projects")
            content.settingsButton.performClick(nil)
            content.whenRouteSettled {
                capture("preferences")
                content.settingsButton.performClick(nil)
                content.whenRouteSettled {
                    capture("returned");content.onRouteSample=nil
                    let report:[String:Any]=["requestId":requestID,"steps":steps,"samples":samples,"input":"plugin-owned-settings-button","elapsed":CACurrentMediaTime()-began]
                    if let data=try? JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]) { try? data.write(to:root.appendingPathComponent("settings-"+requestID+".json")) }
                    if opened { self.dismiss(animated:false) }
                }
            }
        }
    }

    private func captureAfterOpening() {
        guard !captured, let directory = ProcessInfo.processInfo.environment["CODEX_MENU_UI_CAPTURE_DIR"] else { return }
        motion.whenSettled { [weak self] in
            guard let self, !self.captured, self.isShown, let panel = self.panel, let content = self.content else { return }
            self.captured = true
            content.layoutSubtreeIfNeeded()
            let root = URL(fileURLWithPath: directory)
            if let bitmap = content.bitmapImageRepForCachingDisplay(in: content.bounds) {
                content.cacheDisplay(in: content.bounds, to: bitmap)
                try? bitmap.representation(using: .png, properties: [:])?.write(to: root.appendingPathComponent("live-popup.png"))
            }
            let value: [String: Any] = ["project": content.project.name, "visible": panel.isVisible,
                "frame": NSStringFromRect(panel.frame), "arrowX": content.arrowX,
                "chatCount": content.project.threads.count, "blackSurface": true,
                "anchorContentFrame": NSStringFromRect(self.anchor?.frame ?? .zero),
                "anchorHostBounds": NSStringFromRect(self.anchor?.superview?.bounds ?? .zero),
                "anchorHostClass": self.anchor?.superview.map { NSStringFromClass(type(of: $0)) } ?? "none"]
            if let data = try? JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys]) {
                try? data.write(to: root.appendingPathComponent("live-popup.json"))
            }
        }
    }
}
