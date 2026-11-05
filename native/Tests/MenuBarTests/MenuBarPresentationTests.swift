import AppKit
import Testing
@testable import MenuBar

private func project(_ id:String,kind:String?=nil) -> Project {
    Project(id:id,name:id,markerType:"emoji",marker:"🔦",threads:[],kind:kind)
}
@Test func rightAnchorIsAlwaysCreatedBeforeAnyProject() {
    let global=project("global-control",kind:"global-control"),a=project("local"),b=project("remote::project")
    #expect(MenuBarPresentation.creationOrder(global:global,projects:[a,b],compact:false).map(\.id) == [global.id,b.id,a.id])
    #expect(MenuBarPresentation.creationOrder(global:global,projects:[a,b],compact:true) == [global])
    #expect(MenuBarPresentation.creationOrder(global:global,projects:[],compact:false) == [global])
    #expect(MenuBarPresentation.creationOrder(global:global,projects:[b],compact:false).first == global)
    #expect(MenuBarPresentation.creationOrder(global:global,projects:[a,b,project("new")],compact:false).first == global)
}
@Test @MainActor func projectVisibilityRetargetsFromPresentationAndCancelsOldRemoval() throws {
    // Test normal-motion interpolation independently of the machine's setting.
    let prior=Motion.reduceMotionOverride;Motion.reduceMotionOverride=false;defer { Motion.reduceMotionOverride=prior }
    var p=project("p");p.threads=[Chat(id:"stable-id",index:1,title:"原始聊天",since:0,canMarkSeen:false,status:"running",detail:"进行中")]
    let view=CapsuleView(project:p,height:22,detail:"",onEvent:{_,_ in})
    var staleRemoval=false
    let width=view.frame.width
    view.setVisible(false) { staleRemoval=true }
    RunLoop.main.run(until:Date().addingTimeInterval(0.06))
    let midWidth=view.frame.width,midAlpha=try #require(view.visibilitySnapshot["alpha"] as? CGFloat)
    #expect(midWidth>1 && midWidth<width && midAlpha>0 && midAlpha<1)
    #expect(view.chatID(at:CGPoint(x:view.layout.badge(0).midX,y:view.layout.centerY)) == nil)
    #expect(view.accessibilityChildren()?.isEmpty != false)
    view.update(p,detail:"")
    #expect(abs(view.frame.width-midWidth)<0.01)
    #expect(abs((view.visibilitySnapshot["alpha"] as? CGFloat ?? -1)-midAlpha)<0.01)
    view.finishAnimation();#expect(!staleRemoval && view.frame.width == width && !view.isAnimating)
    #expect(view.project.threads[0].id == "stable-id")
    #expect(Layout.specification.menuMotion.transition == 0.2)
}
@Test @MainActor func reducedProjectRetractionKeepsFadeButDoesNotSlide() throws {
    Motion.reduceMotionOverride=true;defer { Motion.reduceMotionOverride=nil }
    let view=CapsuleView(project:project("p"),height:22,detail:"",onEvent:{_,_ in})
    view.setVisible(false)
    #expect(view.frame.width == 1 && view.isAnimating)
    view.finishAnimation();#expect(view.visibilitySnapshot["alpha"] as? CGFloat == 0)
}

@Test @MainActor func unchangedBackingNotificationsDoNotSnapOrFinishProjectMotion() {
    let prior=Motion.reduceMotionOverride;Motion.reduceMotionOverride=false;defer { Motion.reduceMotionOverride=prior }
    let view=CapsuleView(project:project("p"),height:22,detail:"",onEvent:{_,_ in})
    view.setVisible(false,animated:false);view.setVisible(true)
    RunLoop.main.run(until:Date().addingTimeInterval(0.06))
    let width=view.frame.width
    #expect(width>1 && width<view.layout.width && view.isAnimating)
    view.refreshHostLayout()
    #expect(view.isAnimating && view.frame.width == width)
    view.finishAnimation()
    var removed=false;view.setVisible(false) { removed=true }
    RunLoop.main.run(until:Date().addingTimeInterval(0.06))
    let retractingWidth=view.frame.width;view.refreshHostLayout()
    #expect(view.isAnimating && view.frame.width == retractingWidth && !removed)
    view.finishAnimation();#expect(removed)
}
