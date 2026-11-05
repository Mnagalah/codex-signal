// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "CodexMenuStatus",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "codex-menu-bar", targets: ["MenuBar"])],
    targets: [
        .executableTarget(name: "MenuBar"),
        .testTarget(name: "MenuBarTests", dependencies: ["MenuBar"])
    ]
)
