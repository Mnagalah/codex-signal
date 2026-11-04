import AppKit

struct SettingsMotionConfiguration: Decodable, Sendable {
    let out: Double
    let `in`: Double
    let icon: Double
    let resize: Double
    let offset: CGFloat
}

@MainActor
final class AlertSettingRow: NSView {
    var statusEmoji=EmojiPickerButton.defaultEmoji
    let phase: String?
    let toggle = NSSwitch()
    private var language: InterfaceLanguage
    let onEvent: (String, String?) -> Void
    var grid: ProjectControlLayout { ProjectControlLayout(width: bounds.width, height: bounds.height) }
    var titleText: String { language.text(phase == nil ? "statusButtonOnly" : phase == "completed" ? "noticeCompleted" : phase!) }

    init(phase: String?, language: InterfaceLanguage, onEvent: @escaping (String, String?) -> Void) {
        self.phase = phase; self.language = language; self.onEvent = onEvent
        super.init(frame: .zero)
        setAccessibilityElement(false)
        toggle.controlSize = .small; toggle.target = self; toggle.action = #selector(setValue(_:)); addSubview(toggle)
    }
    required init?(coder: NSCoder) { nil }
    override var isFlipped: Bool { true }
    func update(selected: Bool, language: InterfaceLanguage) {
        self.language = language; toggle.state = selected ? .on : .off
        toggle.setAccessibilityLabel(phase == nil ? titleText : language.text("alertSwitch", ["state":titleText]))
        toggle.toolTip = toggle.accessibilityLabel(); needsDisplay = true; needsLayout = true
    }
    @objc func setValue(_ sender: NSSwitch) {
        onEvent(phase == nil ? (sender.state == .on ? "compact_enable" : "compact_disable") : (sender.state == .on ? "notification_enable" : "notification_disable"), phase)
    }
    override func layout() {
        super.layout()
        let cell = grid.toggle
        let alignment = toggle.alignmentRect(forFrame: CGRect(origin: .zero, size: cell.size))
        toggle.frame = toggle.frame(forAlignmentRect: Layout.centered(alignment.size, in: cell))
    }
    override func draw(_ dirtyRect: NSRect) {
        let cells = Layout.grid("alertRow").place(in: bounds)
        if let phase {
            Palette.background(phase).setFill()
            NSBezierPath(ovalIn:Layout.square(Layout.value("alert-dot"),in:cells.cell(0))).fill()
        } else {
            Drawing.icon(Project(id:"glyph",name:"",markerType:"emoji",marker:statusEmoji,threads:[]),rect:Layout.square(Layout.value("header-icon"),in:cells.cell(0)))
        }
        Drawing.label(titleText,rect:cells.cell(1),role:"title")
    }
}

@MainActor
final class AlertSettingsView: NSView {
    let compactRow: AlertSettingRow
    let emojiButton = EmojiPickerButton()
    private(set) var stateRows: [String: AlertSettingRow] = [:]
    private var language: InterfaceLanguage
    static var sectionHeight: CGFloat { Layout.grid("settingsSection").intrinsicSize().height }
    static var height: CGFloat { sectionHeight * 2 + Layout.value("alert-row-h") * CGFloat(Layout.specification.alertTypes.count + 2) + Layout.value("settings-gap") }
    var alertSectionY: CGFloat { Self.sectionHeight + Layout.value("alert-row-h") * 2 + Layout.value("settings-gap") }

    init(language: InterfaceLanguage, onEvent: @escaping (String, String?) -> Void) {
        self.language = language; compactRow = AlertSettingRow(phase:nil,language:language,onEvent:onEvent)
        super.init(frame:.zero); setAccessibilityElement(false); addSubview(compactRow);addSubview(emojiButton)
        emojiButton.onSelect={ value in onEvent("set_status_emoji",value) }
        for phase in Layout.specification.alertTypes {
            let row = AlertSettingRow(phase:phase,language:language,onEvent:onEvent)
            stateRows[phase] = row; addSubview(row)
        }
    }
    required init?(coder: NSCoder) { nil }
    override var isFlipped: Bool { true }
    func update(compact: Bool, states: Set<String>, emoji:String = EmojiPickerButton.defaultEmoji, language: InterfaceLanguage) {
        self.language = language;emojiButton.update(emoji,language:language);compactRow.statusEmoji=emoji; compactRow.update(selected:compact,language:language)
        for (phase,row) in stateRows { row.update(selected:states.contains(phase),language:language) }
        needsDisplay = true; needsLayout = true
    }
    func setBodyEnabled(_ enabled: Bool) {
        compactRow.toggle.isEnabled = enabled
        emojiButton.isEnabled=enabled
        for row in stateRows.values { row.toggle.isEnabled = enabled }
    }
    var keyViews: [NSView] { [emojiButton,compactRow.toggle] + Layout.specification.alertTypes.compactMap { stateRows[$0]?.toggle } }
    override func layout() {
        super.layout()
        let h = Layout.value("alert-row-h")
        let emojiCells=Layout.grid("alertRow").place(in:CGRect(x:0,y:Self.sectionHeight,width:bounds.width,height:h))
        emojiButton.frame=Layout.centered(CGSize(width:Layout.value("switch-w"),height:Layout.value("control")),in:emojiCells.cell(2))
        compactRow.frame = CGRect(x:0,y:Self.sectionHeight+h,width:bounds.width,height:h)
        for (i,phase) in Layout.specification.alertTypes.enumerated() {
            stateRows[phase]?.frame = CGRect(x:0,y:alertSectionY + Self.sectionHeight + CGFloat(i)*h,width:bounds.width,height:h)
        }
    }
    override func draw(_ dirtyRect: NSRect) {
        let emojiCells=Layout.grid("alertRow").place(in:CGRect(x:0,y:Self.sectionHeight,width:bounds.width,height:Layout.value("alert-row-h")))
        Drawing.label(language.text("statusIcon"),rect:emojiCells.cell(1),role:"title")
        for (key,y) in [("menuBarSection",CGFloat.zero),("alertSettings",alertSectionY)] {
            let rect=Layout.grid("settingsSection").place(in:CGRect(x:0,y:y,width:bounds.width,height:Self.sectionHeight)).cell()
            Drawing.label(language.text(key),rect:rect,role:"section",color:.white.withAlphaComponent(0.5))
        }
    }
}
