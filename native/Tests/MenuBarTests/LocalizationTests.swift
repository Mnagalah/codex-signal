import AppKit
import Testing
@testable import MenuBar

@Test func elapsedAndRawTemplateValuesUseOnlyTheInterfaceLanguage() {
    let chat = Chat(id: "id", index: 1, title: "Atlas {n}", since: Date().timeIntervalSince1970 - 125, canMarkSeen: false, status: "running", detail: "Running")
    #expect(chat.elapsed(in: .english) == "2m")
    #expect(chat.elapsed(in: .chinese) == "2 分钟")
    #expect(InterfaceLanguage.english.text("openRow", ["n":"1", "title":chat.title]) == "Open chat 1, Atlas {n}")
    #expect(chat.id == "id" && chat.title == "Atlas {n}")
    var project = Project(id: "remote::p", name: "远程项目", markerType: "icon", marker: "folder", threads: [], hostId: "remote")
    #expect(project.locationLabel(in: .english) == "Remote")
    project.hostLabel = "Remote Lab Mac mini"
    #expect(project.locationLabel(in: .english) == "Remote · Remote Lab Mac mini")
}

@Test @MainActor func liveViewLanguageUpdatePreservesRowsAndRoutesTheSameChatID() {
    let chat = Chat(id: "chat-5", index: 1, title: "中文项目的真实标题", since: 0, canMarkSeen: true, status: "completed", detail: "Completed · Unseen")
    let project = Project(id: "real", name: "未分组", markerType: "icon", marker: "folder", threads: [chat])
    var events: [String?] = []
    let view = ProjectPanelView(project: project, detail: "已连接", onEvent: { _, id in events.append(id) })
    let row = view.rows[chat.id]
    view.update(project, detail: "Connected", animated: false, language: .english)
    #expect(view.rows[chat.id] === row)
    #expect(view.project.name == "未分组")
    #expect(view.reloadButton.accessibilityLabel() == "Reload plugin")
    #expect(view.monitorSwitch.accessibilityLabel() == "Updates for 未分组")
    #expect(row?.seenButton.toolTip == "Mark seen")
    #expect(row?.openButton.accessibilityLabel() == "Open chat 1, 中文项目的真实标题")
    row?.openButton.performClick(nil)
    #expect(events == ["chat-5"])
}

@Test @MainActor func displayRenumberingCannotChangeTheIdentityOfAPressedCircle() throws {
    let first = Chat(id:"id-4",index:1,title:"甲",since:0,canMarkSeen:false,status:"running",detail:"Running")
    var second = Chat(id:"id-5",index:2,title:"乙",since:0,canMarkSeen:false,status:"running",detail:"Running")
    var project = Project(id:"p",name:"项目",markerType:"icon",marker:"folder",threads:[first,second])
    var events:[String?]=[]
    let view = CapsuleView(project:project,height:22,detail:"Connected",language:.english,onEvent:{ _, id in events.append(id) })
    let rect=view.layout.badge(0), point=CGPoint(x:rect.midX,y:rect.midY)
    func event(_ type:NSEvent.EventType) throws -> NSEvent {
        try #require(NSEvent.mouseEvent(with:type,location:point,modifierFlags:[],timestamp:0,windowNumber:0,context:nil,eventNumber:1,clickCount:1,pressure:0))
    }
    view.mouseDown(with:try event(.leftMouseDown))
    second.index=1;project.threads=[second];view.update(project,detail:"Connected");view.finishAnimation()
    view.mouseUp(with:try event(.leftMouseUp));#expect(events.isEmpty)
    view.mouseDown(with:try event(.leftMouseDown));view.mouseUp(with:try event(.leftMouseUp))
    #expect(events == ["id-5"])
}
