import Testing
import AppKit
@testable import MenuBar

@Test func compiledProductionGridIsExactlyTheHTMLContract() throws {
    let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().appendingPathComponent("../../..").standardizedFileURL
    let html = try String(contentsOf: root.appendingPathComponent("codex-status-layout.html"), encoding: .utf8)
    let start = try #require(html.range(of: "<script id=\"layout-contract\" type=\"application/json\">"))
    let end = try #require(html.range(of: "</script>", range: start.upperBound..<html.endIndex))
    let source = try JSONSerialization.jsonObject(with: Data(html[start.upperBound..<end.lowerBound].utf8)) as? NSDictionary
    let compiled = try JSONSerialization.jsonObject(with: Data(CompiledLayoutContract.json.utf8)) as? NSDictionary
    #expect(try #require(source) == #require(compiled))
    #expect(Layout.specification.source == "codex-status-layout.html#layout-contract")
    #expect(Layout.specification.grids.count == 20)
}

@Test func panelCellsMatchTheHTMLGridRatherThanOldNativeOffsets() {
    let grid = PopupLayout(count: 1, maximumHeight: 450)
    #expect(grid.height == 129) // Includes the 8pt arrow; HTML body itself is 121pt.
    #expect(grid.icon == CGRect(x: 17, y: 31, width: 14, height: 14))
    #expect(grid.headerCopy == CGRect(x: 40, y: 22, width: 168, height: 32))
    #expect(grid.title == CGRect(x: 40, y: 22, width: 168, height: 18))
    #expect(grid.source == CGRect(x: 40, y: 42, width: 168, height: 12))
    #expect(grid.reload == CGRect(x: 216, y: 24, width: 28, height: 28))
    #expect(grid.toggle == CGRect(x: 252, y: 24, width: 36, height: 28))
    #expect(grid.divider == CGRect(x: 16, y: 60, width: 272, height: 1))
    #expect(grid.viewport == CGRect(x: 8, y: 65, width: 288, height: 56))
}

@Test func rowCellsUseSharedNestedColumnsAndCenterTheTwoLineCopyAsAGroup() {
    let grid = RowLayout(width: 288)
    #expect(grid.open == CGRect(x: 0, y: 0, width: 258, height: 56))
    #expect(grid.seen == CGRect(x: 260, y: 14, width: 28, height: 28))
    #expect(grid.badge == CGRect(x: 8, y: 18, width: 20, height: 20))
    #expect(grid.copy == CGRect(x: 40, y: 10, width: 210, height: 36))
    #expect(grid.title == CGRect(x: 40, y: 10, width: 210, height: 18))
    #expect(grid.detail == CGRect(x: 40, y: 30, width: 210, height: 16))
    #expect(grid.badge.midY == grid.copy.midY)
    #expect(grid.seen.midY == grid.copy.midY)
}

@Test func nativeAndHTMLUseTheSameResponsiveNameLimits() {
    #expect(Layout.value("name-max", forWidth: 3840) == 116)
    #expect(Layout.value("name-max", forWidth: 520) == 76)
    #expect(Layout.value("name-max", forWidth: 375) == 42)
    #expect(Layout.value("name-max", forWidth: 320) == 42)
}

@Test func narrowedPanelKeepsControlsAndRowsInsideTheSurface() {
    for width: CGFloat in [200, 248, 280, 304] {
        let grid = PopupLayout(count: 4, maximumHeight: 280, availableWidth: width)
        #expect(grid.height == 280)
        #expect(grid.icon.midY == grid.headerCopy.midY)
        #expect(grid.reload.midY == grid.headerCopy.midY)
        #expect(grid.toggle.midY == grid.headerCopy.midY)
        #expect(grid.title.maxX < grid.reload.minX)
        #expect(grid.toggle.maxX <= width - 16)
        let row = RowLayout(width: grid.viewport.width)
        #expect(row.title.maxX <= row.open.maxX - 8)
        #expect(row.open.maxX < row.seen.minX)
        #expect(row.seen.maxX == grid.viewport.width)
    }
}

@Test func popupBackgroundTracksItsAnimatedHeightDuringRemoval() {
    let grid = PopupLayout(count: 1, maximumHeight: 241, surfaceHeight: 241)
    #expect(grid.height == 241)
    #expect(grid.body.maxY == 241)
    #expect(grid.viewport.height == 168)
}

@Test @MainActor func actualRowDoesNotReflowWhenTheSeenActionAppears() {
    var chat = Chat(id: "grid-chat", index: 4, title: "设计 macOS 中英文混排", since: 0,
                    canMarkSeen: false, status: "running", detail: "进行中")
    let row = ChatRowView(chat: chat, onEvent: { _, _ in })
    row.layoutSubtreeIfNeeded()
    let openFrame = row.openButton.frame, seenFrame = row.seenButton.frame
    chat.canMarkSeen = true; chat.status = "completed"
    row.update(chat, animated: false)
    row.layoutSubtreeIfNeeded()
    #expect(!row.seenButton.isHidden)
    #expect(row.openButton.frame == openFrame)
    #expect(row.seenButton.frame == seenFrame)
    #expect(openFrame == RowLayout(width: row.bounds.width).open)
}

@Test @MainActor func actualPanelResizesFromTheGridWithoutChangingChatIdentity() {
    let chat = Chat(id: "remote::same-id", index: 7, title: "很长的项目中的 macOS 对话", since: 0,
                    canMarkSeen: false, status: "running", detail: "进行中")
    let project = Project(id: "remote::project", name: "Remote Lab", markerType: "icon", marker: "heart",
                          threads: [chat], hostId: "remote", hostLabel: "远程")
    let view = ProjectPanelView(project: project, detail: "已连接", onEvent: { _, _ in })
    view.availableWidth = 248
    view.update(project, detail: "已连接", animated: false)
    view.layoutSubtreeIfNeeded()
    #expect(view.frame.width == 248)
    #expect(view.reloadButton.frame == view.currentGrid.reload)
    let alignment = view.monitorSwitch.alignmentRect(forFrame: view.monitorSwitch.frame)
    #expect(alignment.midY == view.currentGrid.headerCopy.midY)
    #expect(alignment.midX == view.currentGrid.toggle.midX)
    #expect(view.currentGrid.toggle.contains(alignment))
    #expect(view.rows[chat.id]?.chat.index == 7)
    #expect(view.rows[chat.id]?.frame.width == view.currentGrid.viewport.width)
}

@Test @MainActor func hostGeometryRefreshUsesTheSameGridAndNeverRoutesAChatAction() {
    let chat = Chat(id: "same", index: 8, title: "进行中的聊天", since: 0, canMarkSeen: false,
                    status: "running", detail: "进行中")
    let project = Project(id: "project", name: "Aurora 中英文", markerType: "icon", marker: "folder", threads: [chat])
    var widths: [CGFloat] = [], actions = 0
    let view = CapsuleView(project: project, height: 22, detail: "已连接", onEvent: { _, _ in actions += 1 })
    view.onWidthChange = { widths.append($0) }
    view.refreshHostLayout()
    view.viewDidChangeBackingProperties()
    #expect(widths == [view.layout.width, view.layout.width])
    #expect(view.frame.width == view.layout.width)
    #expect(view.chatID(at: CGPoint(x: view.layout.badge(0).midX, y: view.layout.badge(0).midY)) == "same")
    #expect(view.project.threads.first?.index == 8)
    #expect(actions == 0)
}
