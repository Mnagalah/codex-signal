import AppKit
import Testing
@testable import MenuBar

@Test func noticeLifetimeHoldsSixSecondsAndIgnoresStaleExpiry() {
    var lifetime=NoticeLifetime()
    let first = lifetime.present("a",now:100)
    #expect(first)
    #expect(!lifetime.shouldExpire("a",now:105.999))
    #expect(lifetime.shouldExpire("a",now:106))
    let duplicate = lifetime.present("a",now:102)
    #expect(!duplicate)
    #expect(lifetime.deadline == 106)
    let replacement = lifetime.present("b",now:103)
    #expect(replacement)
    #expect(!lifetime.shouldExpire("a",now:106))
    #expect(!lifetime.shouldExpire("b",now:108.999))
    #expect(lifetime.shouldExpire("b",now:109))
    lifetime.clear()
    #expect(!lifetime.shouldExpire("b",now:120))
    let replay = lifetime.present("b",now:120)
    #expect(!replay)
}

@Test func noticeUsesTheApprovedHTMLGridAndScreenSafeArea() {
    let grid=NoticeLayout(width:340)
    #expect(NoticeLayout.height == 113)
    #expect(grid.header == CGRect(x:15,y:15,width:310,height:24))
    #expect(grid.title == CGRect(x:47,y:68,width:278,height:18))
    #expect(grid.badge == CGRect(x:15,y:56.5,width:20,height:20))
    #expect(grid.meter == CGRect(x:15,y:98,width:310,height:2))
    #expect(grid.icon.midY == grid.project.midY && grid.close.midY == grid.project.midY)
    #expect(grid.badge.midY == grid.copy.midY)
    for screen in [CGRect(x:0,y:0,width:3840,height:2136),CGRect(x:-1920,y:36,width:1920,height:1020),CGRect(x:0,y:0,width:320,height:700)] {
        let placement=NoticeLayout.placement(in:screen)
        #expect(placement.maxX == screen.maxX - 12 && placement.maxY == screen.maxY - 12)
        #expect(placement.minX >= screen.minX + 12)
    }
}

@MainActor private func noticePayload(kind: String? = nil) -> NoticePayload {
    NoticePayload(id:"n",source:"automatic",createdAt:0,
        project:Project(id:"p",name:"未分组",markerType:"icon",marker:"folder",threads:[],kind:kind),
        chat:Chat(id:"thread-5",index:1,title:"原文 {n} · English",since:0,canMarkSeen:false,status:"approval",detail:"等待授权"))
}

@Test @MainActor func noticeLocalizesOnlyInterfaceTextAndHasAnAccessibleDismissAction() {
    let view=StatusNoticeView(payload:noticePayload(),language:.chinese,onDismiss:{})
    #expect(view.stateText == "等待授权")
    view.update(noticePayload(),language:.english)
    #expect(view.projectName == "未分组")
    #expect(view.stateText == "Needs approval")
    #expect(view.payload.chat.id == "thread-5")
    #expect(view.payload.chat.title == "原文 {n} · English")
    #expect(view.accessibilityLabel()?.contains("原文 {n}") == true)
    view.update(noticePayload(kind:"chat-bucket"),language:.english)
    #expect(view.projectName == "Chat")
    var completed = noticePayload(); completed.chat.status = "completed"
    view.update(completed,language:.english)
    #expect(view.stateText == "Completed")
    let children=view.accessibilityChildren() as? [NSAccessibilityElement]
    #expect(children?.first?.accessibilityLabel() == "Dismiss status notice")
    #expect(!view.acceptsFirstResponder && !view.needsPanelToBecomeKey)
}

@Test @MainActor func reducedNoticeKeepsTheDeadlineWithoutCountdownMotion() {
    Motion.reduceMotionOverride=true
    defer{Motion.reduceMotionOverride=nil}
    let view=StatusNoticeView(payload:noticePayload(),language:.english,onDismiss:{})
    view.countdown(remaining:6,animated:true)
    #expect(view.layer?.sublayers?.allSatisfy { $0.animation(forKey:"remaining") == nil } == true)
    var lifetime=NoticeLifetime();lifetime.present("n",now:0)
    #expect(lifetime.deadline == 6)
}

@MainActor private func noticeMouse(_ type: NSEvent.EventType, _ point: CGPoint, in view: StatusNoticeView) throws -> NSEvent {
    try #require(NSEvent.mouseEvent(with: type, location: view.convert(point, to: nil), modifierFlags: [], timestamp: 0,
        windowNumber: 0, context: nil, eventNumber: 1, clickCount: 1, pressure: type == .leftMouseDown ? 1 : 0))
}

@Test @MainActor func noticeBodyOpensItsChatWhileTheCloseButtonOnlyDismisses() throws {
    var opens: [String] = [], closes = 0
    let view=StatusNoticeView(payload:noticePayload(),language:.chinese,onDismiss:{closes += 1},onOpen:{opens.append($0.chat.id)})
    for cell in [view.grid.project, view.grid.badge, view.grid.title, view.grid.meter] {
        let point=CGPoint(x:cell.midX,y:cell.midY)
        view.mouseDown(with:try noticeMouse(.leftMouseDown,point,in:view));view.mouseUp(with:try noticeMouse(.leftMouseUp,point,in:view))
    }
    #expect(opens == Array(repeating:"thread-5",count:4));#expect(closes == 0)
    let point=CGPoint(x:view.grid.close.midX,y:view.grid.close.midY)
    view.mouseDown(with:try noticeMouse(.leftMouseDown,point,in:view));view.mouseUp(with:try noticeMouse(.leftMouseUp,point,in:view))
    #expect(opens.count == 4 && closes == 1)
}

@Test @MainActor func changingNoticeBetweenPressAndReleaseCannotOpenTheReplacement() throws {
    var opens=0,closes=0
    let view=StatusNoticeView(payload:noticePayload(),language:.english,onDismiss:{closes += 1},onOpen:{_ in opens += 1})
    let body=CGPoint(x:view.grid.title.midX,y:view.grid.title.midY)
    let close=CGPoint(x:view.grid.close.midX,y:view.grid.close.midY)
    view.mouseDown(with:try noticeMouse(.leftMouseDown,body,in:view))
    var replacement=noticePayload();replacement.chat.id="different-chat"
    replacement=NoticePayload(id:"new",source:"automatic",createdAt:0,project:replacement.project,chat:replacement.chat)
    view.update(replacement,language:.english)
    view.mouseUp(with:try noticeMouse(.leftMouseUp,body,in:view))
    view.mouseDown(with:try noticeMouse(.leftMouseDown,close,in:view));view.mouseUp(with:try noticeMouse(.leftMouseUp,body,in:view))
    view.mouseDown(with:try noticeMouse(.leftMouseDown,body,in:view));view.mouseUp(with:try noticeMouse(.leftMouseUp,close,in:view))
    view.mouseDown(with:try noticeMouse(.leftMouseDown,body,in:view));view.mouseUp(with:try noticeMouse(.leftMouseUp,CGPoint(x:-1,y:0),in:view))
    #expect(opens == 0 && closes == 0)
}

@Test @MainActor func noticeAccessibilitySeparatesOpenAndCloseAndSampleCannotOpenAChat() async throws {
    var opens:[String]=[],closes=0
    let view=StatusNoticeView(payload:noticePayload(),language:.english,onDismiss:{closes += 1},onOpen:{opens.append($0.chat.id)})
    let actions=try #require(view.accessibilityChildren() as? [NSAccessibilityElement])
    #expect(actions.count == 2)
    #expect(actions[0].accessibilityLabel() == "Open this chat in Codex")
    #expect(actions[1].accessibilityLabel() == "Dismiss status notice")
    let accepted=actions[0].accessibilityPerformPress();#expect(accepted)
    await Task.yield()
    #expect(opens == ["thread-5"] && closes == 0)
    let closed=actions[1].accessibilityPerformPress();#expect(closed)
    await Task.yield()
    #expect(closes == 1 && opens.count == 1)
    var sample=noticePayload()
    sample=NoticePayload(id:"sample",source:"diagnostic",createdAt:0,project:sample.project,chat:sample.chat)
    view.update(sample,language:.chinese)
    #expect(!view.canOpen && view.accessibilityChildren()?.count == 1)
    let point=CGPoint(x:view.grid.title.midX,y:view.grid.title.midY)
    view.mouseDown(with:try noticeMouse(.leftMouseDown,point,in:view));view.mouseUp(with:try noticeMouse(.leftMouseUp,point,in:view))
    #expect(opens.count == 1)
    #expect(!view.acceptsFirstResponder && !view.needsPanelToBecomeKey)
}
