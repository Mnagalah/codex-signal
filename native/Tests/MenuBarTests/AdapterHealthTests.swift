import AppKit
import Testing
@testable import MenuBar

@Test func protocolFailureCannotBecomeAnEmptyHealthySummary() {
    var state = MonitorState(connected: true, detail: "Connected", projects: [], uiLanguage: "en")
    state.health = AdapterHealth(status: "protocol-error", detail: "Protocol changed; update the plugin")
    #expect(state.summaryStatus == "unknown")
    #expect(state.presentationDetail == state.health?.detail)
    state.health = AdapterHealth(status: "ready", detail: "Connected")
    #expect(state.summaryStatus == nil)
    #expect(state.presentationDetail == "No active chats")
}

@Test @MainActor func protocolFailureRemainsVisibleInGlobalTooltipAndHeader() {
    let message = "Protocol changed; update the plugin"
    var project = Project(id: "global-control", name: "Chat Status", markerType: "emoji", marker: "🔦", threads: [], kind: "global-control")
    project.summaryStatus = "unknown"; project.healthDetail = message
    let capsule = CapsuleView(project: project, height: 24, detail: message, language: .english) { _, _ in }
    let panel = ProjectPanelView(project: project, detail: message, language: .english) { _, _ in }
    #expect(capsule.aggregateDetail == message)
    #expect(panel.headerSubtitle == "Status unavailable")
}

@Test func healthDoesNotHideAKnownApprovalAndMasterPauseStillWins() {
    let chat = Chat(id: "sample", index: 1, title: "Sample chat", since: 0, canMarkSeen: false, status: "approval", detail: "Needs approval")
    let project = Project(id: "sample-project", name: "Sample project", markerType: "icon", marker: "folder", threads: [chat])
    var state = MonitorState(connected: true, detail: "Connected", projects: [project], uiLanguage: "en")
    state.health = AdapterHealth(status: "protocol-error", detail: "Protocol changed")
    #expect(state.summaryStatus == "approval")
    #expect(state.presentationDetail == "Protocol changed")
    state.enabled = false
    #expect(state.summaryStatus == nil)
    #expect(state.presentationDetail == "Updates paused")
}
