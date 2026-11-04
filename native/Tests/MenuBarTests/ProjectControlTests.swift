import AppKit
import Testing
@testable import MenuBar

@MainActor private func controlProject(_ id: String = "p", enabled: Bool = true) -> Project {
    Project(id:id,name:"原始项目 {n}",markerType:"icon",marker:"folder",threads:[],updatesEnabled:enabled)
}
@MainActor private func globalControl() -> Project {
    Project(id:"global-control",name:"Codex",markerType:"emoji",marker:EmojiPickerButton.defaultEmoji,threads:[],kind:"global-control")
}

@Test @MainActor func globalControlIsALocalizedStatusPillWithoutRenamingRealProjects() {
    let p=globalControl()
    let view=CapsuleView(project:p,height:22,detail:"",onEvent:{_,_ in})
    #expect(view.layout.globalEntry)
    #expect(view.layout.width == 42 && view.layout.capsule.width == 40 && view.layout.capsule.height == 22)
    #expect(view.layout.icon.midY == view.layout.capsule.midY && view.layout.icon.midX == view.layout.capsule.midX)
    #expect(view.layout.name.isEmpty)
    #expect(view.displayName == "对话状态")
    view.update(p,detail:"Updates paused",language:.english);view.finishAnimation()
    #expect(view.displayName == "Chat Status" && view.frame.width == view.layout.width)
    let label = CapsuleView(project:Project(id:"control",name:"Codex",markerType:"icon",marker:"status-beacon",threads:[],kind:"status-control"),height:22,detail:"",onEvent:{_,_ in})
    #expect(label.layout.controlLabel && label.layout.icon.isEmpty)
    #expect(label.layout.name.midY == label.layout.capsule.midY)
    #expect(controlProject().displayName(in:.english) == "原始项目 {n}")
    #expect(EmojiPickerButton.defaultEmoji == "🔦")
}

@Test @MainActor func globalMasterAndProjectRowSwitchesHaveSeparateTargets() throws {
    var events:[(String,String?)]=[]
    let panel=ProjectPanelView(project:globalControl(),detail:"",onEvent:{events.append(($0,$1))})
    var remote=controlProject("host::p",enabled:false);remote.hostId="host";remote.hostLabel="My Mac"
    panel.setProjectControls([controlProject(),remote])
    panel.update(globalControl(),detail:"",animated:false)
    #expect(panel.controlRows.count == 2 && panel.frame.height == PopupLayout.rowsTop + Layout.grid("panel").padding[2] + 2*Layout.value("project-control-h") + Layout.value("group-gap"))
    let row=try #require(panel.controlRows["host::p"])
    #expect(row.toggle.state == .off)
    row.toggle.state = .on;row.setUpdates(row.toggle)
    panel.monitorSwitch.state = .off;panel.setMonitoring(panel.monitorSwitch)
    #expect(events.map(\.0) == ["project_enable","disable"])
    #expect(events.map(\.1) == ["host::p",nil])
    #expect(panel.monitorSwitch.accessibilityLabel() == "全部项目状态更新")
}

@Test @MainActor func projectChoicesRemainEditableWhileAllUpdatesArePausedAndLanguageChanges() throws {
    let p=globalControl()
    let panel=ProjectPanelView(project:p,detail:"",enabled:false,onEvent:{_,_ in})
    panel.setProjectControls([controlProject(enabled:false),controlProject("q")])
    panel.update(p,detail:"Updates paused",animated:false)
    let old=try #require(panel.controlRows["p"])
    panel.update(p,detail:"Updates paused",animated:false,language:.english)
    #expect(panel.controlRows["p"] === old)
    #expect(old.project.name == "原始项目 {n}")
    #expect(old.toggle.isEnabled && old.toggle.state == .off)
    #expect(old.detail == "Local · Paused")
    #expect(panel.controlRows["q"]?.detail == "Local · Ready to resume")
    #expect(panel.monitorSwitch.accessibilityLabel() == "All chat updates")
    #expect(!panel.monitorSwitch.accessibilityLabel()!.lowercased().contains("monitor"))
}

@Test @MainActor func projectControlRowUsesOneSharedCenterForTextIconAndNativeSwitch() {
    for width:CGFloat in [288,280,240] {
        let row=ProjectControlRowView(project:controlProject(),language:.english,globalEnabled:true,onEvent:{_,_ in})
        row.frame.size.width=width;row.layoutSubtreeIfNeeded()
        let g=row.grid
        let alignment=row.toggle.alignmentRect(forFrame:row.toggle.frame)
        #expect(g.copy.midY == g.icon.midY && abs(g.copy.midY-alignment.midY)<0.01)
        #expect(g.copy.maxX < g.toggle.minX && g.toggle.maxX <= width - 8)
        #expect(g.title.maxX == g.detail.maxX)
    }
}

@Test @MainActor func settingsAndBackPreserveTheProjectHierarchyAndExposeIndependentPreferences() throws {
    var events:[(String,String?)]=[]
    let panel=ProjectPanelView(project:globalControl(),detail:"",onEvent:{events.append(($0,$1))})
    var parent=controlProject();parent.threads=[Chat(id:"chat",index:1,title:"原始聊天",since:0,canMarkSeen:false,status:"running",detail:"进行中")]
    panel.compactMenuBar=true
    panel.setProjectControls([parent]);panel.update(globalControl(),detail:"",animated:false)
    let original=try #require(panel.groupedRows["chat"])
    panel.settingsButton.performClick(nil);panel.finishRouteAnimation()
    #expect(panel.showingAlerts && panel.settingsButton.accessibilityLabel() == "返回项目列表")
    let preferences=try #require(panel.settingsDocument)
    #expect(preferences.stateRows.count == 6)
    #expect(preferences.stateRows["running"]?.toggle.state == .on)
    preferences.compactRow.toggle.state = .on;preferences.compactRow.setValue(preferences.compactRow.toggle)
    let approval=try #require(preferences.stateRows["approval"])
    approval.toggle.state = .off;approval.setValue(approval.toggle)
    #expect(events.map(\.0) == ["compact_enable","notification_disable"])
    #expect(events.map(\.1) == [nil,"approval"])
    #expect(panel.currentGrid.settings.maxX < panel.currentGrid.reload.minX)
    #expect(panel.currentGrid.reload.maxX < panel.currentGrid.toggle.minX)
    panel.settingsButton.performClick(nil);panel.finishRouteAnimation()
    #expect(!panel.showingAlerts && panel.settingsButton.accessibilityLabel() == "设置")
    #expect(panel.groupedRows["chat"] === original && !original.isHidden)
    #expect(original.grouped)
    original.openButton.performClick(nil)
    #expect(events.last?.0 == "open" && events.last?.1 == "chat")
}

@Test @MainActor func interruptedSettingsRouteNeverRunsTheStaleSwapOrLosesChoices() {
    let panel=ProjectPanelView(project:globalControl(),detail:"",onEvent:{_,_ in})
    panel.setProjectControls([controlProject()]);panel.update(globalControl(),detail:"",animated:false)
    panel.notificationStates=["approval","completed"];panel.compactMenuBar=true
    panel.setShowingAlerts(true);panel.setShowingAlerts(false);panel.finishRouteAnimation()
    #expect(!panel.showingAlerts)
    panel.setShowingAlerts(true);panel.finishRouteAnimation()
    panel.setShowingAlerts(false);panel.setShowingAlerts(true);panel.finishRouteAnimation()
    #expect(panel.showingAlerts)
    #expect(panel.settingsDocument?.compactRow.toggle.state == .on)
    #expect(panel.settingsDocument?.stateRows["running"]?.toggle.state == .off)
    #expect(panel.settingsDocument?.stateRows["approval"]?.toggle.state == .on)
}

@Test @MainActor func settingsUseSectionHierarchyAndTheSameNativeSwitchCenterAtNarrowWidths() throws {
    let settings=AlertSettingsView(language:.english,onEvent:{_,_ in})
    settings.update(compact:true,states:["completed"],language:.english)
    settings.frame=CGRect(x:0,y:0,width:280,height:AlertSettingsView.height)
    settings.layoutSubtreeIfNeeded()
    #expect(settings.compactRow.titleText == "Status button only")
    #expect(AlertSettingsView.height == 376)
    #expect(settings.compactRow.frame.minY == 64)
    #expect(settings.stateRows["running"]?.frame.minY == 136)
    for row in [settings.compactRow] + Array(settings.stateRows.values) {
        row.layoutSubtreeIfNeeded()
        let alignment=row.toggle.alignmentRect(forFrame:row.toggle.frame)
        #expect(abs(alignment.midY-row.bounds.midY) < 0.01)
        #expect(alignment.maxX <= row.bounds.maxX-8)
    }
    #expect(settings.stateRows["completed"]?.titleText == "Completed")
    #expect(settings.stateRows["completed"]?.toggle.state == .on)
    #expect(settings.stateRows["failed"]?.toggle.state == .off)
}

@Test @MainActor func settingsReducedMotionAndImmediateKeyboardRouteKeepOneBody() {
    Motion.reduceMotionOverride=true
    defer { Motion.reduceMotionOverride=nil }
    let panel=ProjectPanelView(project:globalControl(),detail:"",onEvent:{_,_ in})
    panel.setShowingAlerts(true,animated:false)
    #expect(panel.showingAlerts && panel.settingsDocument?.isHidden == false)
    panel.setShowingAlerts(false,animated:false)
    #expect(!panel.showingAlerts && panel.settingsDocument?.isHidden == true)
}

@Test @MainActor func compactHierarchyDisablesOutgoingChatRowsWithoutCollidingWithHostProjectKeys() throws {
    var p=controlProject("chat::project")
    p.threads=[Chat(id:"chat",index:1,title:"原始聊天",since:0,canMarkSeen:true,status:"completed",detail:"完成未看")]
    let panel=ProjectPanelView(project:globalControl(),detail:"",onEvent:{_,_ in})
    panel.compactMenuBar=true
    panel.setProjectControls([p]);panel.update(globalControl(),detail:"",animated:false)
    let row=try #require(panel.groupedRows["chat"])
    #expect(panel.controlRows["chat::project"]?.frame.height == Layout.value("project-control-h"))
    p.threads=[]
    panel.setProjectControls([p]);panel.update(globalControl(),detail:"")
    #expect(!row.openButton.isEnabled && !row.seenButton.isEnabled)
    panel.finishAnimation()
    #expect(panel.groupedRows["chat"] == nil)
    #expect(panel.controlRows["chat::project"] != nil)
}

@Test @MainActor func fullMenuUsesProjectNamesOnlyWhileCompactMenuShowsConversationDetails() {
    var parent=controlProject()
    parent.threads=[Chat(id:"chat",index:1,title:"原始聊天",since:0,canMarkSeen:false,status:"running",detail:"进行中")]
    let panel=ProjectPanelView(project:globalControl(),detail:"",onEvent:{_,_ in})
    panel.setProjectControls([parent]);panel.update(globalControl(),detail:"",animated:false)
    #expect(panel.groupedRows.isEmpty && panel.controlRows["p"]?.singleLine == true)
    #expect(panel.preferredLayout.documentHeight == Layout.value("project-control-h"))
    panel.compactMenuBar=true;panel.update(globalControl(),detail:"",animated:false)
    #expect(panel.groupedRows["chat"]?.grouped == true)
    #expect(panel.preferredLayout.documentHeight == Layout.value("project-control-h")+PopupLayout.rowHeight)
}

@Test @MainActor func emojiButtonRequiresItsOwnInputTargetAndPreservesAGraphemeChoice() {
    let field=EmojiPickerButton();var opened=0;var selected:[String]=[]
    field.openPalette={opened += 1};field.onSelect={selected.append($0)}
    field.choose();#expect(opened == 0 && !field.choosing)
    #expect(field.needsPanelToBecomeKey && field.acceptsFirstMouse(for:nil))
    field.insertText("🧭",replacementRange:NSRange(location:0,length:0));#expect(selected.isEmpty)
    #expect(field.commitSelectedEmoji("👩🏽‍💻"))
    #expect(field.accessibilityRole() == .button && field.emoji == "👩🏽‍💻")
    #expect(selected == ["👩🏽‍💻"] && !field.choosing)
    #expect(EmojiPickerButton.valid("⚕️") && EmojiPickerButton.valid("👨‍👩‍👧‍👦"))
    #expect(!EmojiPickerButton.valid("\n") && !EmojiPickerButton.valid("AB"))
}

@Test @MainActor func aggregateEntryPrioritizesAttentionAndExcludesPausedProjectsWithoutUsingAlertPreferences() throws {
    func project(_ phase:String,_ id:String="p",enabled:Bool=true) -> Project {
        Project(id:id,name:"原项目",markerType:"icon",marker:"folder",threads:[Chat(id:id+"chat",index:1,title:"原聊天",since:0,canMarkSeen:false,status:phase,detail:phase)],updatesEnabled:enabled)
    }
    var state=MonitorState(connected:true,detail:"",projects:[project("running"),project("approval","q"),project("input","r")])
    state.notificationStates=[]
    #expect(state.summaryStatus == "approval")
    state.projects.append(project("failed","f"));#expect(state.summaryStatus == "failed")
    state.projects[state.projects.count-1].updatesEnabled=false;#expect(state.summaryStatus == "approval")
    state.connected=false;#expect(state.summaryStatus == "unknown")
    state.enabled=false;#expect(state.summaryStatus == nil)
    state.enabled=true;state.connected=true;state.projects=[];#expect(state.summaryStatus == nil)
    for phase in Layout.specification.statusPriority { state.projects=[project(phase)];#expect(state.summaryStatus == phase) }
}

@Test @MainActor func aggregatePillColorsAreFiniteInterruptibleAndKeepTheWholeEntryAsItsClickTarget() {
    var project=globalControl();project.summaryStatus="approval";project.summaryCount=3
    var chatEvents=0
    let view=CapsuleView(project:project,height:22,detail:"",onEvent:{_,_ in chatEvents+=1})
    #expect(view.pillColor == Palette.background("approval"))
    #expect(view.aggregateDetail == "等待授权 · 3 个聊天")
    #expect(view.chatID(at:CGPoint(x:view.layout.icon.midX,y:view.layout.centerY)) == nil)
    project.summaryStatus="input";view.update(project,detail:"")
    #expect(view.pillColor == Palette.background("approval"))
    project.summaryStatus="failed";view.update(project,detail:"");view.finishAnimation()
    #expect(view.pillColor == Palette.background("failed"))
    view.globalEnabled=false;project.summaryStatus=nil;view.update(project,detail:"");view.finishAnimation()
    #expect(view.pillColor.usingColorSpace(.sRGB) == NSColor.black.usingColorSpace(.sRGB) && view.aggregateDetail == "状态更新已暂停")
    #expect(chatEvents == 0)
}

