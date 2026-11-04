import Foundation

struct InterfaceLanguage: Sendable, Equatable {
    let code: String
    static let chinese = Self(code: "zh-CN")
    static let english = Self(code: "en")
    private static let copy = try! JSONDecoder().decode([String: [String]].self, from: Data(CompiledInterfaceCopy.json.utf8))

    func text(_ key: String, _ values: [String: String] = [:]) -> String {
        let template = Self.copy[key]![code == "zh-CN" ? 0 : 1]
        // Match the original template once: braces inside an extracted name
        // must never be interpreted as another localization placeholder.
        return template.replacing(/\{(\w+)\}/) { values[String($0.1)] ?? String($0.0) }
    }
}
