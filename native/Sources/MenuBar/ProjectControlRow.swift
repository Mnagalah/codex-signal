import AppKit

struct ProjectControlLayout: Sendable {
    let width: CGFloat
    let height: CGFloat
    var singleLine = false
    private var cells: PlacedGrid { Layout.grid("projectControl").place(in: CGRect(x: 0, y: 0, width: width, height: height)) }
    var icon: CGRect { Layout.square(Layout.value("header-icon"), in: cells.cell(0)) }
    var copy: CGRect { Layout.centered(CGSize(width: cells.cell(1).width, height: Layout.grid(singleLine ? "projectHeadingCopy" : "rowCopy").intrinsicSize().height), in: cells.cell(1)) }
    var title: CGRect { Layout.grid(singleLine ? "projectHeadingCopy" : "rowCopy").place(in: copy).cell(0, 0) }
    var detail: CGRect { Layout.grid("rowCopy").place(in: copy).cell(0, 1) }
    var toggle: CGRect { Layout.centered(CGSize(width: Layout.value("switch-w"), height: Layout.value("control")), in: cells.cell(2)) }
}

@MainActor
final class ProjectControlRowView: NSView {
    private(set) var project: Project
    private(set) var language: InterfaceLanguage
    private var globalEnabled: Bool
    let toggle = NSSwitch()
    let onEvent: (String, String?) -> Void
    var paintOpacity: CGFloat = 1 { didSet { alphaValue = paintOpacity } }
    var singleLine = false
    var grid: ProjectControlLayout { ProjectControlLayout(width: bounds.width, height: bounds.height, singleLine:singleLine) }

    init(project: Project, language: InterfaceLanguage, globalEnabled: Bool, onEvent: @escaping (String, String?) -> Void) {
        self.project = project; self.language = language; self.globalEnabled = globalEnabled; self.onEvent = onEvent
        super.init(frame: CGRect(x: 0, y: 0, width: PopupLayout(count: 1, maximumHeight: Layout.value("panel-max-h")).viewport.width, height: PopupLayout.rowHeight))
        setAccessibilityElement(false)
        toggle.controlSize = .small; toggle.target = self; toggle.action = #selector(setUpdates(_:))
        addSubview(toggle); update(project, language: language, globalEnabled: globalEnabled)
    }
    required init?(coder: NSCoder) { nil }
    override var isFlipped: Bool { true }
    var detail: String {
        let key = project.updatesEnabled == false ? "projectPaused" : !globalEnabled ? "readyToResume" : project.syncing == true ? "syncing" : "updatesOn"
        return project.locationLabel(in: language) + " · " + language.text(key)
    }
    func update(_ value: Project, language: InterfaceLanguage, globalEnabled: Bool) {
        project = value; self.language = language; self.globalEnabled = globalEnabled
        toggle.state = value.updatesEnabled == false ? .off : .on
        toggle.isEnabled = true
        toggle.setAccessibilityLabel(language.text("projectSwitch", ["project": value.displayName(in: language) + " · " + value.locationLabel(in: language)]))
        toggle.setAccessibilityHelp(detail)
        toolTip = value.displayName(in: language) + "\n" + detail
        toggle.toolTip = language.text(value.updatesEnabled == false ? "projectOn" : "projectOff")
        needsLayout = true; needsDisplay = true
    }
    @objc func setUpdates(_ sender: NSSwitch) { onEvent(sender.state == .on ? "project_enable" : "project_disable", project.id) }
    override func layout() {
        super.layout()
        let target = grid.toggle
        let alignment = toggle.alignmentRect(forFrame: CGRect(origin: .zero, size: target.size))
        toggle.frame = toggle.frame(forAlignmentRect: Layout.centered(alignment.size, in: target))
    }
    override func draw(_ dirtyRect: NSRect) {
        Drawing.icon(project, rect: grid.icon)
        Drawing.label(project.displayName(in: language), rect: grid.title, role: "header")
        if !singleLine { Drawing.label(detail, rect: grid.detail, role: "detail", color: .white.withAlphaComponent(0.62)) }
    }
}
