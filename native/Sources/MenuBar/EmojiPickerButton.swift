import AppKit

// A native icon button which is also the system palette's text input client.
// No editable field, caret, hidden editor or insertion into the front Codex chat.
@MainActor
final class EmojiPickerButton: NSButton, @MainActor NSTextInputClient {
    static let defaultEmoji = "🔦"
    private(set) var choosing = false
    private(set) var emoji = defaultEmoji
    private var activationObserver:NSObjectProtocol?
    private var palettePresented=false
    private var marked = NSAttributedString(string: "")
    var onSelect: ((String) -> Void)?
    var openPalette: () -> Void = { NSApp.orderFrontCharacterPalette(nil) }

    init() {
        super.init(frame:.zero)
        title="";isBordered=false;setButtonType(.momentaryChange)
        target=self;action=#selector(selectIcon(_:));focusRingType = .exterior
        setAccessibilityRole(.button)
    }
    required init?(coder:NSCoder) { nil }
    override var isFlipped:Bool { true }
    override var acceptsFirstResponder:Bool { true }
    override var needsPanelToBecomeKey:Bool { true }
    override func acceptsFirstMouse(for event:NSEvent?) -> Bool { true }
    static func valid(_ value:String) -> Bool {
        value.count == 1 && value.utf8.count <= 128 && !value.unicodeScalars.contains { CharacterSet.whitespacesAndNewlines.contains($0) || CharacterSet.controlCharacters.contains($0) && $0.value != 0x200D }
    }
    func update(_ value:String,language:InterfaceLanguage) {
        emoji=value;needsDisplay=true
        setAccessibilityLabel(language.text("chooseStatusEmoji"));toolTip=language.text("chooseStatusEmoji")
        setAccessibilityValue(value)
    }
    override func draw(_ dirtyRect:NSRect) {
        NSColor.white.withAlphaComponent(isHighlighted ? 0.16 : 0.08).setFill()
        NSBezierPath(roundedRect:bounds,xRadius:6,yRadius:6).fill()
        let project=Project(id:"status-icon",name:"",markerType:"emoji",marker:emoji,threads:[])
        Drawing.icon(project,rect:Layout.centered(CGSize(width:18,height:18),in:bounds))
    }
    override func drawFocusRingMask() { NSBezierPath(roundedRect:bounds,xRadius:6,yRadius:6).fill() }
    override var focusRingMaskBounds:NSRect { bounds }
    @objc private func selectIcon(_ sender:Any?) { choose() }
    func choose() {
        guard let owner=window else { return }
        removeActivationObserver();choosing=true;palettePresented=false
        if !NSApp.isActive {
            activationObserver=NotificationCenter.default.addObserver(forName:NSApplication.didBecomeActiveNotification,object:NSApp,queue:.main) { [weak self] _ in
                Task { @MainActor in self?.presentPaletteIfReady() }
            }
        }
        NSApp.activate();owner.makeKeyAndOrderFront(nil)
        // NSApplication.activate is asynchronous. The first click must wait
        // for our input context, not open against the previously active app.
        presentPaletteIfReady()
        DispatchQueue.main.async { [weak self] in self?.presentPaletteIfReady() }
    }
    private func removeActivationObserver() {
        if let activationObserver { NotificationCenter.default.removeObserver(activationObserver);self.activationObserver=nil }
    }
    private func presentPaletteIfReady() {
        guard choosing,!palettePresented,NSApp.isActive,let owner=window else { return }
        guard owner.makeFirstResponder(self),owner.firstResponder === self,let context=inputContext else { endChoosing();return }
        context.activate();context.invalidateCharacterCoordinates()
        palettePresented=true;removeActivationObserver();openPalette()
    }
    func endChoosing() { choosing=false;removeActivationObserver();marked=NSAttributedString(string:"");inputContext?.discardMarkedText() }
    override func keyDown(with event:NSEvent) {
        if [36,76,49].contains(event.keyCode) { choose() }
        else if event.keyCode == 53 { endChoosing() }
        else if choosing { interpretKeyEvents([event]) }
        else { super.keyDown(with:event) }
    }
    @discardableResult func commitSelectedEmoji(_ value:String) -> Bool {
        guard Self.valid(value) else { return false }
        emoji=value;choosing=false;removeActivationObserver();marked=NSAttributedString(string:"");needsDisplay=true
        setAccessibilityValue(value);onSelect?(value);return true
    }
    // Public NSTextInputClient insertion is used by macOS Emoji & Symbols.
    func insertText(_ string:Any,replacementRange:NSRange) {
        guard choosing else { return }
        let value=(string as? NSAttributedString)?.string ?? (string as? String) ?? ""
        _ = commitSelectedEmoji(value)
    }
    func setMarkedText(_ string:Any,selectedRange:NSRange,replacementRange:NSRange) {
        marked=(string as? NSAttributedString) ?? NSAttributedString(string:(string as? String) ?? "")
    }
    func unmarkText() { marked=NSAttributedString(string:"") }
    func hasMarkedText() -> Bool { marked.length > 0 }
    func markedRange() -> NSRange { hasMarkedText() ? NSRange(location:0,length:marked.length) : NSRange(location:NSNotFound,length:0) }
    func selectedRange() -> NSRange { NSRange(location:0,length:(emoji as NSString).length) }
    func attributedSubstring(forProposedRange range:NSRange,actualRange:NSRangePointer?) -> NSAttributedString? {
        let text=NSAttributedString(string:emoji),safe=NSIntersectionRange(range,NSRange(location:0,length:text.length))
        guard safe.length > 0 else { return nil };actualRange?.pointee=safe;return text.attributedSubstring(from:safe)
    }
    func validAttributesForMarkedText() -> [NSAttributedString.Key] { [] }
    func firstRect(forCharacterRange range:NSRange,actualRange:NSRangePointer?) -> NSRect {
        actualRange?.pointee=selectedRange()
        return window?.convertToScreen(convert(bounds,to:nil)) ?? .zero
    }
    func characterIndex(for point:NSPoint) -> Int { 0 }
    func windowLevel() -> Int { window?.level.rawValue ?? NSWindow.Level.popUpMenu.rawValue }
    override func doCommand(by selector:Selector) {
        if selector == #selector(NSResponder.cancelOperation(_:)) { endChoosing() }
        else if selector == #selector(NSResponder.insertNewline(_:)) { choose() }
    }
}
