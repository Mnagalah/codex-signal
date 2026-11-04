import AppKit

@MainActor
enum LayoutDiagnostics {
    static func rect(_ frame: CGRect) -> [String: CGFloat] {
        ["x": frame.minX, "y": frame.minY, "width": frame.width, "height": frame.height]
    }
    static var contract: [String: Any] {
        ["source": Layout.specification.source, "version": Layout.specification.version, "engine": "shared-native-grid"]
    }
    static func capsule(_ view: CapsuleView) -> [String: Any] {
        let grid = view.layout
        let pill=view.pillColor.usingColorSpace(.sRGB) ?? view.pillColor
        return ["pillRGB":[pill.redComponent,pill.greenComponent,pill.blueComponent],"contract": contract, "project": view.displayName, "kind": view.project.kind ?? "project", "summaryStatus":view.project.summaryStatus ?? "idle", "summaryCount":view.project.summaryCount ?? 0, "uiLanguage": view.language.code, "hostId": view.project.hostId ?? "local",
                "host": rect(view.bounds), "capsule": rect(grid.capsule), "icon": rect(grid.icon), "name": rect(grid.name),
                "badgePresentation":view.badgePresentation,
                "nameBaseline": Drawing.placement(view.project.name, rect: grid.name, font: Layout.font("menu"))?.baseline.y ?? 0,
                "badges": view.project.threads.enumerated().map { ["index": $1.index, "frame": rect(grid.badge($0))] }]
    }
    static func panel(_ view: ProjectPanelView) -> [String: Any] {
        view.layoutSubtreeIfNeeded()
        let grid = view.currentGrid
        return ["contract": contract, "project": view.project.displayName(in: view.language), "uiLanguage": view.language.code, "hostId": view.project.hostId ?? "local",
                "sourceText": view.project.locationLabel(in: view.language), "headerSubtitle":view.headerSubtitle, "reloadLabel": view.reloadButton.accessibilityLabel() ?? "", "monitorLabel": view.monitorSwitch.accessibilityLabel() ?? "",
                "bounds": rect(view.bounds), "body": rect(grid.body), "header": rect(grid.headerFrame),
                "icon": rect(grid.icon), "headerCopy": rect(grid.headerCopy), "title": rect(grid.title), "source": rect(grid.source),
                "settingsRoute":view.showingAlerts,
                "settingsLabel":view.settingsButton.accessibilityLabel() ?? "",
                "settings":rect(view.settingsButton.frame),
                "alertPreferences":view.settingsDocument.map { settings in Layout.specification.alertTypes.map { phase in ["status":phase,"enabled":settings.stateRows[phase]?.toggle.state == .on] as [String:Any] } } ?? [],
                "compactPreference":view.settingsDocument?.compactRow.toggle.state == .on,
                "groupedChats":view.groupedRows.values.map { row in ["id":row.chat.id,"index":row.chat.index,"title":row.chat.title,"grouped":row.grouped,"hidden":row.isHidden] as [String:Any] },
                "reload": rect(view.reloadButton.frame), "switch": rect(grid.toggle), "switchViewFrame": rect(view.monitorSwitch.frame),
                "switchAlignment": rect(view.monitorSwitch.alignmentRect(forFrame: view.monitorSwitch.frame)),
                "divider": rect(grid.divider), "viewport": rect(grid.viewport),
                "projectControls": view.projectControls.compactMap { value -> [String: Any]? in
                    guard let row = view.controlRows[value.id] else { return nil }
                    row.layoutSubtreeIfNeeded()
                    return ["id":value.id, "name":value.displayName(in:view.language), "enabled":row.toggle.state == .on,
                            "label":row.toggle.accessibilityLabel() ?? "", "frame":rect(row.frame), "copy":rect(row.grid.copy),
                            "switch":rect(row.grid.toggle), "switchAlignment":rect(row.toggle.alignmentRect(forFrame:row.toggle.frame))]
                },
                "rows": view.project.threads.compactMap { chat -> [String: Any]? in
                    guard let row = view.rows[chat.id] else { return nil }
                    row.layoutSubtreeIfNeeded()
                    let cells = RowLayout(width: row.bounds.width, height: row.bounds.height)
                    return ["index": chat.index, "id": chat.id, "titleText": chat.title, "detailText": chat.detail, "openLabel": row.openButton.accessibilityLabel() ?? "", "seenLabel": row.seenButton.accessibilityLabel() ?? "", "frame": rect(row.frame), "open": rect(row.openButton.frame),
                            "badge": rect(cells.badge), "copy": rect(cells.copy), "title": rect(cells.title),
                            "detail": rect(cells.detail), "seen": rect(row.seenButton.frame), "canMarkSeen": chat.canMarkSeen]
                }]
    }
}
