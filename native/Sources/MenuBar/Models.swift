import AppKit

struct AdapterHealth: Codable, Sendable {
    var status: String
    var detail: String
    var requiresAttention: Bool { status == "protocol-error" || status == "disconnected" }
}

struct MonitorState: Codable, Sendable {
    var connected: Bool
    var detail: String
    var projects: [Project]
    var enabled: Bool? = nil
    var uiLanguage: String? = nil
    var projectControls: [Project]? = nil
    var compactMenuBar: Bool? = nil
    var statusEmoji: String? = nil
    var notificationStates: [String]? = nil
    var health: AdapterHealth? = nil
    var summaryStatus: String? {
        guard enabled != false else { return nil }
        let states=Set((projectControls ?? projects).filter { $0.updatesEnabled != false }.flatMap { $0.threads.map { $0.status == "syncing" ? "syncing" : (connected ? $0.status : "unknown") } })
        let phase = Layout.specification.statusPriority.first { states.contains($0) }
        if health?.requiresAttention == true, !["failed", "approval", "input"].contains(phase ?? "") { return "unknown" }
        return phase ?? (states.contains("syncing") ? "syncing" : nil)
    }
    var language: InterfaceLanguage { InterfaceLanguage(code: uiLanguage ?? "zh-CN") }
    var presentationDetail: String {
        if enabled == false { return language.text("monitorDisabled") }
        if let health, health.requiresAttention { return health.detail }
        if (projectControls ?? projects).contains(where: { $0.syncing == true && $0.updatesEnabled != false }) { return language.text("syncing") }
        return connected && projects.isEmpty ? language.text("noChats") : detail
    }
}

struct Project: Codable, Sendable, Equatable {
    var id: String
    var name: String
    var markerType: String
    var marker: String
    var threads: [Chat]
    var hostId: String? = nil
    var hostLabel: String? = nil
    var kind: String? = nil
    var updatesEnabled: Bool? = nil
    var summaryStatus: String? = nil
    var summaryCount: Int? = nil
    var syncing: Bool? = nil
    var healthDetail: String? = nil
    var isStatusControl: Bool { id == "control" || kind == "status-control" || kind == "global-control" }
    func displayName(in language: InterfaceLanguage) -> String {
        if isStatusControl { return language.text("statusTitle") }
        if kind == "chat-bucket" { return language.text("chatBucket") }
        if kind == "pending" { return language.text("pendingProject") }
        return name
    }
    var locationLabel: String { locationLabel(in: .chinese) }
    func locationLabel(in language: InterfaceLanguage) -> String {
        if isStatusControl { return language.text("allProjects") }
        if hostId == nil || hostId == "local" { return language.text("local") }
        if let hostLabel { return language.text("remote", ["host": hostLabel]) }
        return language.text("remoteGeneric")
    }
}

struct Chat: Codable, Sendable, Equatable {
    var id: String
    var index: Int
    var title: String
    var since: Double
    var canMarkSeen: Bool
    var status: String
    var detail: String

    var elapsed: String { elapsed(in: .chinese) }
    func detailLine(in language:InterfaceLanguage) -> String { status == "syncing" ? detail : detail + " · " + elapsed(in:language) }
    func elapsed(in language: InterfaceLanguage) -> String {
        let seconds = max(0, Int(Date().timeIntervalSince1970 - since))
        if seconds < 60 { return language.text("seconds", ["n": String(seconds)]) }
        if seconds < 3600 { return language.text("minutes", ["n": String(seconds / 60)]) }
        return language.text("hoursMinutes", ["h": String(seconds / 3600), "m": String((seconds % 3600) / 60)])
    }
}

@MainActor
enum Palette {
    static func background(_ status: String) -> NSColor {
        let rgb: (CGFloat, CGFloat, CGFloat) = switch status {
        case "running": (0.16, 0.39, 0.91)
        case "approval": (1.0, 0.67, 0.17)
        case "input": (0.53, 0.29, 0.84)
        case "completed": (0.14, 0.64, 0.35)
        case "failed": (0.83, 0.20, 0.24)
        default: (0.62, 0.64, 0.68)
        }
        return NSColor(srgbRed: rgb.0, green: rgb.1, blue: rgb.2, alpha: 1)
    }

    static func foreground(_ color: NSColor) -> NSColor {
        guard let c = color.usingColorSpace(.sRGB) else { return .black }
        func linear(_ v: CGFloat) -> CGFloat {
            v <= 0.04045 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4)
        }
        let luminance = 0.2126 * linear(c.redComponent) + 0.7152 * linear(c.greenComponent) + 0.0722 * linear(c.blueComponent)
        return (luminance + 0.05) / 0.05 >= 1.05 / (luminance + 0.05) ? .black : .white
    }
}

struct CapsuleLayout: Sendable {
    let height: CGFloat
    let nameWidth: CGFloat
    let count: Int
    var globalEntry: Bool = false
    var controlLabel: Bool = false
    var selectionHeight: CGFloat = Layout.value("selection-h")
    private var hostInset: CGFloat { Layout.value("host-inset") }
    var capsuleHeight: CGFloat { min(Layout.value("pill-h"), max(0, height)) }
    // The selection region is the shared parent grid, not a separate label nudge.
    // Prefer the system selection center, then clamp the entire pill inside a
    // shorter native host. All children follow this one parent center.
    var centerY: CGFloat { min(max(height, selectionHeight) / 2, height - capsuleHeight / 2) }
    var badgeDiameter: CGFloat { min(Layout.value("badge-menu"), max(0, capsuleHeight - Layout.grid("capsule").padding[0] - Layout.grid("capsule").padding[2])) }
    var badgePitch: CGFloat { badgeDiameter + Layout.value("badge-gap") }
    private var projectWidth: CGFloat { Layout.grid("project").intrinsicSize(columns: [0, nameWidth]).width }
    private var badgesWidth: CGFloat { CGFloat(count) * badgeDiameter + CGFloat(max(0, count - 1)) * Layout.value("badge-gap") }
    var width: CGFloat { if globalEntry { return hostInset * 2 + Layout.grid("globalButton").intrinsicSize().width }; if controlLabel { return hostInset * 2 + Layout.grid("statusLabel").intrinsicSize(columns: [nameWidth]).width }; return hostInset * 2 + Layout.grid("capsule").intrinsicSize(columns: [projectWidth, badgesWidth]).width }
    var capsule: CGRect { CGRect(x: hostInset, y: centerY - capsuleHeight / 2, width: width - hostInset * 2, height: capsuleHeight) }
    private var cells: PlacedGrid { Layout.grid("capsule").place(in: capsule, columns: [projectWidth, badgesWidth]) }
    private var projectCells: PlacedGrid { Layout.grid("project").place(in: cells.cell(0), columns: [0, nameWidth]) }
    var icon: CGRect { if controlLabel { return .zero }; if globalEntry { return Layout.grid("globalButton").place(in:capsule).item(0,size:CGSize(width:14,height:14)) }; return projectCells.item(0, size: CGSize(width: Layout.value("icon-menu"), height: Layout.value("icon-menu"))) }
    var name: CGRect { if globalEntry { return .zero }; if controlLabel { return Layout.grid("statusLabel").place(in: capsule, columns: [nameWidth]).cell() }; return projectCells.item(1, size: CGSize(width: nameWidth, height: Layout.value("label-h"))) }
    var firstBadgeX: CGFloat { globalEntry || controlLabel ? width : cells.cell(1).minX }
    func badge(_ index: Int) -> CGRect {
        CGRect(x: firstBadgeX + CGFloat(index) * badgePitch, y: cells.cell(1).midY - badgeDiameter / 2,
               width: badgeDiameter, height: badgeDiameter)
    }
    func hit(_ point: CGPoint) -> Int? {
        (0..<count).first { badge($0).insetBy(dx: -2, dy: -3).contains(point) }
    }
}

@MainActor
enum ProjectIcon {
    // Marker identity follows Codex. Emoji is preserved verbatim; named markers
    // use the corresponding SF Symbol, not the project's decorative color.
    static func symbol(_ marker: String) -> String {
        CompiledProjectIcons.symbols[marker] ?? "folder"
    }
}
