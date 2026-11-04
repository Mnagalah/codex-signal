import AppKit
import Testing
@testable import MenuBar

private func pendingProject() -> Project {
    Project(id:"p",name:"Aurora",markerType:"icon",marker:"graduation-cap",threads:[Chat(id:"same-chat",index:1,title:"原始聊天",since:0,canMarkSeen:false,status:"syncing",detail:"正在同步")],updatesEnabled:true,syncing:true)
}
@Test @MainActor func syncIsLoadingNotAFalseUnknownAndDoesNotOverrideKnownAttention() {
    let p=pendingProject()
    var state=MonitorState(connected:true,detail:"",projects:[],projectControls:[p])
    #expect(state.summaryStatus == "syncing")
    var other=p;other.id="other";other.threads[0].status="approval";other.syncing=false
    state.projectControls=[p,other];#expect(state.summaryStatus == "approval")
    state.enabled=false;#expect(state.summaryStatus == nil)
    state.enabled=true;other.updatesEnabled=false;state.projectControls=[other];#expect(state.summaryStatus == nil)
}
@Test @MainActor func syncingHeaderUsesTheExistingGridAndProjectSwitchStaysInterruptible() throws {
    var global=Project(id:"global-control",name:"对话状态",markerType:"emoji",marker:"😎",threads:[],kind:"global-control",syncing:true)
    let panel=ProjectPanelView(project:global,detail:"",onEvent:{_,_ in})
    panel.setProjectControls([pendingProject()]);panel.update(global,detail:"",animated:false)
    let frame=panel.currentGrid.headerCopy
    #expect(panel.headerSubtitle == "正在同步")
    let row=try #require(panel.controlRows["p"])
    #expect(row.toggle.isEnabled && row.toggle.state == .on && row.detail.contains("正在同步"))
    panel.update(global,detail:"",animated:false,language:.english)
    #expect(panel.headerSubtitle == "Syncing" && panel.currentGrid.headerCopy == frame)
    global.syncing=false;panel.update(global,detail:"",animated:false)
    #expect(panel.headerSubtitle == "All projects")
}
@Test @MainActor func pendingChatDoesNotShowStaleElapsedTimeOrExposeSeenAction() {
    let chat=pendingProject().threads[0]
    #expect(chat.detailLine(in:.chinese) == "正在同步")
    let row=ChatRowView(chat:chat,onEvent:{_,_ in})
    #expect(row.seenButton.isHidden)
    #expect(row.openButton.toolTip == "原始聊天\n正在同步")
    var fresh=chat;fresh.status="approval";fresh.detail="等待授权";row.update(fresh,animated:false)
    #expect(fresh.detailLine(in:.chinese).contains("等待授权 · "))
    #expect(row.chat.id == "same-chat" && row.chat.index == 1)
}
