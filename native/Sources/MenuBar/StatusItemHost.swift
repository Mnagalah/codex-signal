import AppKit

@MainActor
enum StatusItemHost {
    // The native button tracks the content width, with no preset extra width.
    // Its cell bezel is transparent; macOS may still draw its own selection
    // outside these bounds. That system layer is deliberately left intact.
    static func configure(_ button: NSButton, content: CapsuleView) {
        button.title = ""
        button.image = nil
        button.isBordered = false
        button.focusRingType = .none
        if let cell = button.cell as? NSButtonCell {
            cell.highlightsBy = []
            cell.showsStateBy = []
            cell.isTransparent = true
        }
        button.setAccessibilityElement(false)
        content.focusRingType = .none
        content.frame.origin = .zero
        content.autoresizingMask = [.height]
        button.addSubview(content)
        // Native menu-bar keyboard navigation still has an action. Pointer
        // events land on the child, preserving per-circle chat routing.
        button.target = content
        button.action = #selector(CapsuleView.openFromStatusButton(_:))
    }
}
