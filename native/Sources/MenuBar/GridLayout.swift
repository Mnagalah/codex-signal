import AppKit

// The same tracks, padding and gaps drive CSS Grid and the production native UI.
// AppKit remains the status-item/window/accessibility host. It does not maintain
// another collection of per-label x/y offsets or an independent set of constants.
enum GridTrack: Decodable, Sendable, Equatable {
    case fixed(CGFloat), content, fraction
    init(from decoder: any Decoder) throws {
        let value = try decoder.singleValueContainer()
        if let number = try? value.decode(Double.self) { self = .fixed(CGFloat(number)); return }
        switch try value.decode(String.self) {
        case "max-content": self = .content
        case "minmax(0,1fr)": self = .fraction
        default: throw DecodingError.dataCorruptedError(in: value, debugDescription: "Unknown grid track")
        }
    }
}

struct GridDefinition: Decodable, Sendable, Equatable {
    let columns: [GridTrack]
    let rows: [GridTrack]
    let columnGap: CGFloat
    let rowGap: CGFloat
    let padding: [CGFloat] // CSS top/right/bottom/left order.
    let alignContent: String
    let alignItems: String

    private func natural(_ tracks: [GridTrack], content: [CGFloat]) -> [CGFloat] {
        tracks.enumerated().map { i, track in
            if case let .fixed(value) = track { return value }
            return content.indices.contains(i) ? content[i] : 0
        }
    }

    func intrinsicSize(columns: [CGFloat] = [], rows: [CGFloat] = []) -> CGSize {
        CGSize(width: natural(self.columns, content: columns).reduce(0, +) + CGFloat(max(0, self.columns.count - 1)) * columnGap + padding[1] + padding[3],
               height: natural(self.rows, content: rows).reduce(0, +) + CGFloat(max(0, self.rows.count - 1)) * rowGap + padding[0] + padding[2])
    }

    func place(in frame: CGRect, columns: [CGFloat] = [], rows: [CGFloat] = []) -> PlacedGrid {
        func solve(_ tracks: [GridTrack], content: [CGFloat], available: CGFloat, gap: CGFloat) -> [CGFloat] {
            var sizes = natural(tracks, content: content)
            let fractions = tracks.filter { $0 == .fraction }.count
            let fixed = zip(tracks, sizes).filter { $0.0 != .fraction }.map(\.1).reduce(0, +)
            let remaining = max(0, available - fixed - CGFloat(max(0, tracks.count - 1)) * gap)
            for i in tracks.indices where tracks[i] == .fraction { sizes[i] = remaining / CGFloat(fractions) }
            return sizes
        }
        let inner = CGRect(x: frame.minX + padding[3], y: frame.minY + padding[0],
                           width: max(0, frame.width - padding[1] - padding[3]), height: max(0, frame.height - padding[0] - padding[2]))
        let widths = solve(self.columns, content: columns, available: inner.width, gap: columnGap)
        let heights = solve(self.rows, content: rows, available: inner.height, gap: rowGap)
        let usedHeight = heights.reduce(0, +) + CGFloat(max(0, heights.count - 1)) * rowGap
        return PlacedGrid(origin: CGPoint(x: inner.minX, y: inner.minY + (alignContent == "center" ? max(0, inner.height - usedHeight) / 2 : 0)),
                          widths: widths, heights: heights, columnGap: columnGap, rowGap: rowGap, alignItems: alignItems)
    }
}

struct PlacedGrid: Sendable {
    let origin: CGPoint
    let widths: [CGFloat]
    let heights: [CGFloat]
    let columnGap: CGFloat
    let rowGap: CGFloat
    let alignItems: String
    func cell(_ column: Int = 0, _ row: Int = 0) -> CGRect {
        CGRect(x: origin.x + widths.prefix(column).reduce(0, +) + CGFloat(column) * columnGap,
               y: origin.y + heights.prefix(row).reduce(0, +) + CGFloat(row) * rowGap,
               width: widths[column], height: heights[row])
    }
    func item(_ column: Int = 0, _ row: Int = 0, size: CGSize) -> CGRect {
        let frame = cell(column, row), width = min(size.width, frame.width)
        let height = alignItems == "stretch" ? frame.height : min(size.height, frame.height)
        return CGRect(x: frame.midX - width / 2, y: frame.midY - height / 2, width: width, height: height)
    }
}

struct TextRole: Decodable, Sendable {
    let size: String
    let weight: Int
}

struct LayoutSpecification: Decodable, Sendable {
    let version: Int
    let source: String
    let metrics: [String: CGFloat]
    let grids: [String: GridDefinition]
    let fonts: [String: TextRole]
    let responsive: [GridBreakpoint]
    let popoverMotion: PopoverMotionConfiguration
    let menuMotion: MenuMotionConfiguration
    let settingsMotion: SettingsMotionConfiguration
    let statusPriority: [String]
    let alertTypes: [String]
    let notice: NoticeConfiguration
}

struct GridBreakpoint: Decodable, Sendable {
    let maximumWidth: CGFloat
    let metrics: [String: CGFloat]
}

enum Layout {
    static let specification: LayoutSpecification = {
        do { return try JSONDecoder().decode(LayoutSpecification.self, from: Data(CompiledLayoutContract.json.utf8)) }
        catch { preconditionFailure("Invalid compiled layout contract: \(error)") }
    }()
    static func value(_ name: String) -> CGFloat {
        guard let value = specification.metrics[name] else { preconditionFailure("Missing layout metric: \(name)") }
        return value
    }
    static func value(_ name: String, forWidth width: CGFloat) -> CGFloat {
        var value = value(name)
        for rule in specification.responsive where width <= rule.maximumWidth {
            value = rule.metrics[name] ?? value
        }
        return value
    }
    static func grid(_ name: String) -> GridDefinition {
        guard let value = specification.grids[name] else { preconditionFailure("Missing layout grid: \(name)") }
        return value
    }
    @MainActor static func font(_ role: String) -> NSFont {
        guard let role = specification.fonts[role] else { preconditionFailure("Missing text role: \(role)") }
        let weight: NSFont.Weight = switch role.weight { case 600: .semibold; case 500: .medium; default: .regular }
        return .systemFont(ofSize: value(role.size), weight: weight)
    }
    static func centered(_ size: CGSize, in frame: CGRect) -> CGRect {
        let width = min(size.width, frame.width), height = min(size.height, frame.height)
        return CGRect(x: frame.midX - width / 2, y: frame.midY - height / 2, width: width, height: height)
    }
    static func square(_ side: CGFloat, in frame: CGRect) -> CGRect { centered(CGSize(width: side, height: side), in: frame) }
}

struct RowLayout: Sendable {
    let width: CGFloat
    var height: CGFloat = Layout.value("row-h")
    var grouped = false
    private var outer: PlacedGrid { Layout.grid("row").place(in: CGRect(x: 0, y: 0, width: width, height: height)) }
    var open: CGRect { outer.cell(0) }
    var seen: CGRect { outer.item(1, size: CGSize(width: Layout.value("control"), height: Layout.value("control"))) }
    private var inner: PlacedGrid { Layout.grid(grouped ? "groupRowOpen" : "rowOpen").place(in: CGRect(origin: .zero, size: open.size)) }
    var badge: CGRect { inner.item(0, size: CGSize(width: Layout.value("badge-row"), height: Layout.value("badge-row"))) }
    var copy: CGRect {
        let height = Layout.grid("rowCopy").intrinsicSize().height
        return inner.item(1, size: CGSize(width: inner.cell(1).width, height: height))
    }
    var title: CGRect { Layout.grid("rowCopy").place(in: copy).cell(0, 0) }
    var detail: CGRect { Layout.grid("rowCopy").place(in: copy).cell(0, 1) }
}

struct MenuMotionConfiguration: Decodable, Sendable {
    let transition:Double
}
