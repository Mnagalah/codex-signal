import AppKit
import Testing
@testable import MenuBar

private func global() -> Project { Project(id:"global-control",name:"对话状态",markerType:"emoji",marker:"😎",threads:[],kind:"global-control") }
private func liveProject() -> Project { Project(id:"p",name:"原始项目",markerType:"icon",marker:"folder",threads:[Chat(id:"stable",index:1,title:"原始聊天",since:0,canMarkSeen:false,status:"approval",detail:"等待授权")],updatesEnabled:true) }

@Test @MainActor func masterResumeUsesNeutralPillUntilRealAttentionArrivesAndReversesFromPresentation() {
    var p=global();p.summaryStatus="approval";p.summaryCount=1
    let view=CapsuleView(project:p,height:22,detail:"",onEvent:{_,_ in})
    p.summaryStatus=nil;view.globalEnabled=false;view.update(p,detail:"")
    RunLoop.main.run(until:Date().addingTimeInterval(0.04))
    let mid=view.pillColor
    p.summaryStatus="syncing";view.globalEnabled=true;view.update(p,detail:"")
    #expect(view.pillColor == mid)
    view.finishAnimation();#expect(view.pillColor.usingColorSpace(.sRGB) == NSColor.black.usingColorSpace(.sRGB))
    #expect(view.aggregateDetail == "正在同步 · 1 个聊天")
    p.summaryStatus="approval";view.update(p,detail:"");view.finishAnimation()
    #expect(view.pillColor == Palette.background("approval"))
    p.summaryStatus="unknown";view.update(p,detail:"");view.finishAnimation()
    #expect(view.pillColor == Palette.background("unknown"))
}
@Test @MainActor func compactRowsReverseWithoutStaleRemovalOrChatIdentityChange() throws {
    let p=liveProject();let panel=ProjectPanelView(project:global(),detail:"",onEvent:{_,_ in})
    panel.setProjectControls([p]);panel.compactMenuBar=true;panel.update(global(),detail:"",animated:false)
    let row=try #require(panel.groupedRows["stable"])
    panel.compactMenuBar=false;panel.update(global(),detail:"")
    #expect(!row.openButton.isEnabled && !row.isHidden)
    panel.compactMenuBar=true;panel.update(global(),detail:"");panel.finishAnimation()
    #expect(panel.groupedRows["stable"] === row && row.openButton.isEnabled && !row.isHidden)
    #expect(row.chat.id == "stable" && row.chat.index == 1)
}
@Test @MainActor func globalMasterPauseAndResumeReconcileCompactBodyAndSubtitle() throws {
    var p=liveProject();var g=global();let panel=ProjectPanelView(project:g,detail:"",onEvent:{_,_ in})
    panel.compactMenuBar=true;panel.setProjectControls([p]);panel.update(g,detail:"",animated:false)
    let original=try #require(panel.groupedRows["stable"])
    panel.setMonitorEnabled(false);p.threads=[];panel.setProjectControls([p]);panel.update(g,detail:"")
    #expect(panel.headerSubtitle == "状态更新已暂停" && !original.openButton.isEnabled)
    panel.finishAnimation();#expect(panel.groupedRows.isEmpty)
    panel.setMonitorEnabled(true);p=liveProject();p.threads[0].status="syncing";p.threads[0].detail="正在同步";p.syncing=true;g.syncing=true
    panel.setProjectControls([p]);panel.update(g,detail:"");panel.finishAnimation()
    #expect(panel.headerSubtitle == "正在同步")
    #expect(panel.groupedRows["stable"]?.chat.status == "syncing")
    p=liveProject();g.syncing=false;panel.setProjectControls([p]);panel.update(g,detail:"");panel.finishAnimation()
    #expect(panel.headerSubtitle == "全部项目" && panel.groupedRows["stable"]?.chat.status == "approval")
}
