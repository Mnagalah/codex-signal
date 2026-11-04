import Testing
import AppKit
import CoreText
@testable import MenuBar

@Test func hitTargetsKeepTheirOwnNumberedCircle() {
    let layout = CapsuleLayout(height: 28, nameWidth: 80, count: 3)
    for i in 0..<3 {
        #expect(layout.hit(CGPoint(x: layout.badge(i).midX, y: 14)) == i)
    }
    #expect(layout.hit(CGPoint(x: 30, y: 14)) == nil)
    #expect(layout.badge(2).maxX < layout.width)
}

@Test func compactCapsuleFillsMoreOfRealMenuBarHeight() {
    let layout = CapsuleLayout(height: 22, nameWidth: 24, count: 2)
    #expect(layout.capsule.height == 22)
    #expect(layout.badgeDiameter == 18)
    #expect(layout.width < 103) // Previous two-chat geometry at this name width.
    #expect(layout.hit(CGPoint(x: layout.badge(1).midX, y: 11)) == 1)
}

@Test func outerAndInnerArcsAreConcentricWithUniformInset() {
    for h: CGFloat in [22, 24, 28, 32] {
        for count in [1, 2, 4] {
            let layout = CapsuleLayout(height: h, nameWidth: 60, count: count)
            let circle = layout.badge(count - 1), capsule = layout.capsule
            #expect(circle.midX == capsule.maxX - capsule.height / 2)
            #expect(circle.midY == capsule.midY)
            let inset = (capsule.height - circle.height) / 2
            #expect(capsule.maxX - circle.maxX == inset)
            #expect(circle.minY - capsule.minY == inset)
            #expect(capsule.maxY - circle.maxY == inset)
        }
    }
}

@Test func popupStaysBelowItsCapsuleAndInsideEitherScreenEdge() {
    let screen = CGRect(x: -1920, y: 0, width: 1920, height: 1080)
    for x: CGFloat in [-1918, -980, -82] {
        let anchor = CGRect(x: x, y: 1058, width: 80, height: 22)
        let placement = PopupLayout.placement(anchor: anchor, screen: screen, height: 178)
        #expect(placement.frame.maxY == anchor.minY - Layout.value("panel-anchor-gap"))
        #expect(placement.frame.minX >= screen.minX + Layout.value("safe-gap"))
        #expect(placement.frame.maxX <= screen.maxX - Layout.value("safe-gap"))
        #expect(placement.arrowX >= Layout.value("arrow-inset") && placement.arrowX <= PopupLayout.width - Layout.value("arrow-inset"))
        #expect(placement.frame.minX + placement.arrowX == anchor.midX)
    }
}

@Test func popupScrollsInsteadOfExtendingPastAvailableHeight() {
    let small = PopupLayout(count: 2, maximumHeight: 450)
    #expect(small.documentHeight == 112)
    #expect(small.height == 185)
    let crowded = PopupLayout(count: 20, maximumHeight: 350)
    #expect(crowded.documentHeight > crowded.viewportHeight)
    #expect(crowded.height == 350)
}

@MainActor private func sampleProject(_ count: Int = 3) -> Project {
    Project(id: "project", name: "同一项目", markerType: "icon", marker: "folder", threads: (1...count).map { i in
        Chat(id: "chat-\(i)", index: i, title: "聊天 \(i)", since: 0, canMarkSeen: false, status: "running", detail: "进行中")
    })
}

@MainActor private func mouse(_ type: NSEvent.EventType, point: CGPoint) throws -> NSEvent {
    try #require(NSEvent.mouseEvent(with: type, location: point, modifierFlags: [], timestamp: 0,
        windowNumber: 0, context: nil, eventNumber: 1, clickCount: 1, pressure: type == .leftMouseDown ? 1 : 0))
}

@Test @MainActor func disappearingChatCannotDispatchTheNeighbourAfterMouseDown() throws {
    var events: [String?] = []
    var project = sampleProject()
    let view = CapsuleView(project: project, height: 22, detail: "已连接", onEvent: { _, id in events.append(id) })
    let circle = view.layout.badge(0), point = CGPoint(x: circle.midX, y: circle.midY)
    view.mouseDown(with: try mouse(.leftMouseDown, point: point))
    project.threads.removeFirst()
    view.update(project, detail: "已连接")
    view.finishAnimation()
    view.mouseUp(with: try mouse(.leftMouseUp, point: point))
    #expect(events.isEmpty)
    #expect(view.chatID(at: point) == "chat-2")
    #expect(view.project.threads.map(\.index) == [2, 3])
}

@Test @MainActor func projectReappearingCancelsItsPendingRemoval() {
    var removed = false
    let view = CapsuleView(project: sampleProject(), height: 22, detail: "已连接", onEvent: { _, _ in })
    let originalWidth = view.frame.width
    view.setVisible(false) { removed = true }
    view.update(sampleProject(), detail: "已连接")
    view.finishAnimation()
    #expect(!removed)
    #expect(view.frame.width == originalWidth)
    #expect(!view.isAnimating)
}

@Test @MainActor func capsuleProjectRegionAndKeyboardOpenThePopoverOnly() throws {
    var opened: [Bool] = []
    var events = 0
    let view = CapsuleView(project: sampleProject(), height: 22, detail: "已连接", onEvent: { _, _ in events += 1 })
    view.onShowPopover = { _, keyboard in opened.append(keyboard) }
    view.mouseDown(with: try mouse(.leftMouseDown, point: CGPoint(x: 26, y: 11)))
    let key = try #require(NSEvent.keyEvent(with: .keyDown, location: .zero, modifierFlags: [], timestamp: 0,
        windowNumber: 0, context: nil, characters: " ", charactersIgnoringModifiers: " ", isARepeat: false, keyCode: 49))
    view.keyDown(with: key)
    #expect(opened == [false, true])
    #expect(events == 0)
}

@Test @MainActor func popupRowsRouteOpenSeenAndReconnectWithoutExtraActions() throws {
    var events: [(String, String?)] = []
    var project = sampleProject(2)
    project.threads[1].status = "completed"
    project.threads[1].detail = "完成未看"
    project.threads[1].canMarkSeen = true
    let panel = ProjectPanelView(project: project, detail: "已连接", onEvent: { events.append(($0, $1)) })
    let row = try #require(panel.rows["chat-2"])
    #expect(!row.seenButton.isHidden)
    #expect(panel.rows["chat-1"]?.seenButton.isHidden == true)
    row.openButton.performClick(nil)
    row.seenButton.performClick(nil)
    panel.reloadButton.performClick(nil)
    #expect(events.map(\.0) == ["open", "seen", "reload"])
    #expect(events.map(\.1) == ["chat-2", "chat-2", nil])
    #expect(row.chat.detail == "完成未看")
}

@Test @MainActor func removedPopupRowIsDisabledImmediatelyThenReleased() throws {
    var project = sampleProject(2)
    let panel = ProjectPanelView(project: project, detail: "已连接", onEvent: { _, _ in })
    let removed = try #require(panel.rows["chat-1"])
    project.threads.removeFirst()
    panel.update(project, detail: "已连接")
    #expect(!removed.openButton.isEnabled)
    #expect(!removed.seenButton.isEnabled)
    panel.finishAnimation()
    #expect(panel.rows["chat-1"] == nil)
    #expect(panel.rows["chat-2"]?.chat.index == 2)
    #expect(panel.frame.height == 129)
}

@Test @MainActor func reducedMotionUsesFinalGeometryAndRetainsGentleFade() {
    Motion.reduceMotionOverride = true
    defer { Motion.reduceMotionOverride = nil }
    var project = sampleProject(2)
    let view = CapsuleView(project: project, height: 22, detail: "已连接", onEvent: { _, _ in })
    project.threads.removeFirst()
    view.update(project, detail: "已连接")
    #expect(view.frame.width == view.layout.width)
    #expect(view.isAnimating)
    view.finishAnimation()
    #expect(!view.isAnimating)
}

@Test @MainActor func transitionClockIsFiniteAndRetargetDropsStaleCompletion() {
    let motion = MotionDriver()
    var values: [CGFloat] = []
    var stale = false
    motion.start(duration: 0.2, frame: { values.append($0) }, completion: { stale = true })
    motion.start(duration: 0.1, frame: { values.append($0) })
    motion.finish()
    #expect(!stale)
    #expect(values.last == 1)
    #expect(!motion.isRunning)
    #expect(Motion.easeOut(0) == 0)
    #expect(Motion.easeOut(1) == 1)
    #expect(Motion.easeOut(0.3) > 0.7)
}

@Test @MainActor func nativeHostHasNoExtraBezelOrPreallocatedWidth() throws {
    for count in [1, 2, 4] {
        let view = CapsuleView(project: sampleProject(count), height: 22, detail: "已连接", onEvent: { _, _ in })
        let width = view.layout.width
        let host = NSButton(frame: CGRect(x: 0, y: 0, width: width, height: 22))
        StatusItemHost.configure(host, content: view)
        host.highlight(true)
        let cell = try #require(host.cell as? NSButtonCell)
        #expect(cell.highlightsBy.isEmpty)
        #expect(cell.showsStateBy.isEmpty)
        #expect(cell.isTransparent)
        #expect(!host.isBordered)
        #expect(view.frame.width == width)
        #expect(host.bounds.width == width)
        #expect(view.frame.minX == 0)
        #expect(view.superview === host)
        #expect(view.layout.capsule.minX == 1)
        #expect(host.bounds.maxX - view.layout.capsule.maxX == 1)
    }
}

@Test @MainActor func capsuleWidthFollowsNameAndEveryAddedCircle() {
    var project = sampleProject(1)
    project.name = "短名"
    let view = CapsuleView(project: project, height: 22, detail: "已连接", onEvent: { _, _ in })
    view.animationsEnabled = false
    let shortWidth = view.frame.width
    project.name = "较长的项目名称"
    view.update(project, detail: "已连接")
    #expect(view.frame.width > shortWidth)
    let longWidth = view.frame.width
    project.threads.append(Chat(id: "new", index: 2, title: "新增聊天", since: 0, canMarkSeen: false, status: "running", detail: "进行中"))
    view.update(project, detail: "已连接")
    #expect(view.frame.width - longWidth == view.layout.badgePitch)
    project.threads.removeLast()
    view.update(project, detail: "已连接")
    #expect(view.frame.width == longWidth)
    project.name = "短名"
    view.update(project, detail: "已连接")
    #expect(view.frame.width == shortWidth)
}

@Test @MainActor func displayHeightChangesRelayoutStoredCircleGeometry() {
    let view = CapsuleView(project: sampleProject(2), height: 18, detail: "已连接", onEvent: { _, _ in })
    view.setFrameSize(NSSize(width: view.frame.width, height: 32))
    let circle = view.layout.badge(1)
    #expect(circle.height == 18)
    #expect(circle.midY == view.layout.centerY)
    #expect(view.chatID(at: CGPoint(x: circle.midX, y: circle.maxY - 0.5)) == "chat-2")
    view.setFrameSize(NSSize(width: view.frame.width, height: 18))
    #expect(view.layout.badgeDiameter == 14)
    #expect(view.layout.badge(0).midY == view.layout.centerY)
    #expect(view.frame.width == view.layout.width)
}

@Test @MainActor func projectSwitchRoutesOnlyExplicitProjectOnAndOffActions() {
    var events: [String] = []
    let panel = ProjectPanelView(project: sampleProject(1), detail: "已连接", onEvent: { event, _ in events.append(event) })
    #expect(panel.monitorSwitch.state == .on)
    panel.monitorSwitch.state = .off
    panel.setMonitoring(panel.monitorSwitch)
    panel.monitorSwitch.state = .on
    panel.setMonitoring(panel.monitorSwitch)
    #expect(events == ["project_disable", "project_enable"])
    panel.setMonitorEnabled(false)
    #expect(panel.monitorSwitch.state == .off)
    #expect(panel.monitorSwitch.toolTip == "开启此项目更新")
}

@Test func olderStateWithoutSwitchStillDecodesAsEnabled() throws {
    let state = try JSONDecoder().decode(MonitorState.self, from: Data(#"{"connected":true,"detail":"已连接","projects":[]}"#.utf8))
    #expect(state.enabled == nil)
    #expect((state.enabled ?? true) == true)
}

@Test func capsuleMatchesMeasuredSystemSelectionCenterWithoutOverflow() {
    let layout = CapsuleLayout(height: 22, nameWidth: 60, count: 2)
    let systemSelection = CGRect(x: -12, y: 0, width: layout.width + 24, height: 24)
    #expect(layout.capsule.midY == min(systemSelection.midY,22-layout.capsule.height/2))
    #expect(layout.capsule.minY == 0)
    #expect(systemSelection.maxY - layout.capsule.maxY == 2)
    #expect(layout.capsule.maxY <= layout.height)
    #expect(layout.badge(1).midY == layout.capsule.midY)
}

@Test @MainActor func systemBaselineIsStableAcrossChineseLatinMixedAndTruncatedLabels() throws {
    let rect = CGRect(x: 25, y: 4, width: 140, height: 16)
    let font = NSFont.systemFont(ofSize: 12)
    let expectedBaseline = rect.midY + (font.ascender + font.descender) / 2
    for text in ["Aurora", "未分组", "Atlas", "设计 macOS 工程", "gjpq", "Aurora · 英语作文批改助手与工程化项目"] {
        let value = try #require(Drawing.placement(text, rect: rect, font: font, alignment: .center))
        #expect(abs(value.baseline.y - expectedBaseline) < 0.001)
        #expect(abs(value.visibleRect.midX - rect.midX) < 0.001)
        #expect(value.visibleRect.minY >= rect.minY)
        #expect(value.visibleRect.maxY <= rect.maxY)
    }
    let narrow = CGRect(x: 0, y: 0, width: 70, height: 19)
    let title = try #require(Drawing.placement("Build a writing assistant", rect: narrow, font: .systemFont(ofSize: 13)))
    #expect(CTLineGetTypographicBounds(title.line, nil, nil, nil) <= narrow.width)
    #expect(title.visibleRect.minY >= narrow.minY)
    #expect(title.visibleRect.maxY <= narrow.maxY)
}

@Test @MainActor func numberedCirclesUseOneCapitalBaselineForEveryDigit() throws {
    let rect = CGRect(x: 0, y: 0, width: 16, height: 16)
    let font = NSFont.monospacedDigitSystemFont(ofSize: 10, weight: .semibold)
    for text in ["1", "2", "3", "8", "9", "12"] {
        let value = try #require(Drawing.placement(text, rect: rect, font: font, alignment: .center,
                                                 truncate: false, verticalMetrics: .capitals))
        #expect(value.baseline.y == rect.midY + font.capHeight / 2)
        #expect(abs(value.visibleRect.midY - rect.midY) < 0.35)
        #expect(abs(value.visibleRect.midX - rect.midX) < 0.001)
    }
}

@Test func popupHeaderControlsShareOneVerticalCenter() {
    let width = PopupLayout.width
    for rect in [PopupLayout.headerIcon(), PopupLayout.headerGroup(width: width),
                 PopupLayout.reloadControl(width: width), PopupLayout.switchControl(width: width)] {
        #expect(rect.midY == PopupLayout.headerCenterY)
    }
}

@Test @MainActor func nativeHostKeyboardActionDoesNotOpenAChat() throws {
    var showCount = 0, events = 0
    let view = CapsuleView(project: sampleProject(1), height: 22, detail: "已连接", onEvent: { _, _ in events += 1 })
    view.onShowPopover = { _, _ in showCount += 1 }
    let host = NSButton(frame: view.bounds)
    StatusItemHost.configure(host, content: view)
    host.performClick(nil)
    #expect(showCount == 1)
    #expect(events == 0)
}

@Test @MainActor func numberContrastMeetsSmallTextMinimum() {
    for state in ["running", "approval", "input", "completed", "failed", "stopped", "unknown"] {
        let color = Palette.background(state).usingColorSpace(.sRGB)!
        func linear(_ x: CGFloat) -> CGFloat { x <= 0.04045 ? x / 12.92 : pow((x + 0.055) / 1.055, 2.4) }
        let l = 0.2126 * linear(color.redComponent) + 0.7152 * linear(color.greenComponent) + 0.0722 * linear(color.blueComponent)
        #expect(max((l + 0.05) / 0.05, 1.05 / (l + 0.05)) >= 4.5)
    }
}

@Test @MainActor func circleClickDispatchesOnlyItsChat() throws {
    var received: [(String, String?)] = []
    let chats = (1...3).map { i in Chat(id: "chat-\(i)", index: i, title: "聊天 \(i)", since: 0,
        canMarkSeen: false, status: "running", detail: "进行中") }
    let view = CapsuleView(project: Project(id: "project", name: "同一项目", markerType: "icon", marker: "folder", threads: chats), height: 28, detail: "已连接", onEvent: { received.append(($0, $1)) })
    let rect = view.layout.badge(1)
    let point = CGPoint(x: rect.midX, y: rect.midY)
    let down = try #require(NSEvent.mouseEvent(with: .leftMouseDown, location: point, modifierFlags: [], timestamp: 0, windowNumber: 0, context: nil, eventNumber: 1, clickCount: 1, pressure: 1))
    let up = try #require(NSEvent.mouseEvent(with: .leftMouseUp, location: point, modifierFlags: [], timestamp: 0, windowNumber: 0, context: nil, eventNumber: 2, clickCount: 1, pressure: 0))
    view.mouseDown(with: down)
    view.mouseUp(with: up)
    #expect(received.count == 1)
    #expect(received.first?.0 == "open")
    #expect(received.first?.1 == "chat-2")
}
