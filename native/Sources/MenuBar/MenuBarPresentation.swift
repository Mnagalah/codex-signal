import Foundation

// NSStatusBar inserts each new host to the left. Create the retained global
// host first, then projects right-to-left; never recreate it for a project change.
enum MenuBarPresentation {
    static func creationOrder(global:Project,projects:[Project],compact:Bool) -> [Project] {
        compact ? [global] : [global] + projects.reversed()
    }
}
