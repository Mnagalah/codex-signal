import AppKit
import QuartzCore
import CoreText

// A finite, interruptible native drawing/layout clock. NSStatusItem.length has
// no animator proxy: changing the real slot width is necessary to close gaps
// between independent project items, without scaling text or reserving space.
// Only these tiny native views redraw, only while a transition is in flight.
@MainActor
enum Motion {
    static let layout = 0.220
    static let color = 0.160
    static let popup = 0.180
    static let exit = 0.150
    static var reduceMotionOverride: Bool?
    static var reduced: Bool { reduceMotionOverride ?? NSWorkspace.shared.accessibilityDisplayShouldReduceMotion }

    static func easeOut(_ fraction: Double) -> CGFloat {
        // cubic-bezier(0.23, 1, 0.32, 1), inverted on x, not a polynomial proxy.
        let x = min(1, max(0, fraction))
        if x == 0 || x == 1 { return CGFloat(x) }
        var lo = 0.0, hi = 1.0
        for _ in 0..<16 {
            let t = (lo + hi) / 2, u = 1 - t
            let curveX = 3 * u * u * t * 0.23 + 3 * u * t * t * 0.32 + t * t * t
            if curveX < x { lo = t } else { hi = t }
        }
        return CGFloat(1 - pow(1 - (lo + hi) / 2, 3))
    }

    static func mix(_ a: CGFloat, _ b: CGFloat, _ p: CGFloat) -> CGFloat { a + (b - a) * p }
    static func mix(_ a: CGRect, _ b: CGRect, _ p: CGFloat) -> CGRect {
        CGRect(x: mix(a.minX, b.minX, p), y: mix(a.minY, b.minY, p),
               width: mix(a.width, b.width, p), height: mix(a.height, b.height, p))
    }
    static func mix(_ a: NSColor, _ b: NSColor, _ p: CGFloat) -> NSColor {
        let a = a.usingColorSpace(.sRGB)!, b = b.usingColorSpace(.sRGB)!
        return NSColor(srgbRed: mix(a.redComponent, b.redComponent, p), green: mix(a.greenComponent, b.greenComponent, p),
                       blue: mix(a.blueComponent, b.blueComponent, p), alpha: mix(a.alphaComponent, b.alphaComponent, p))
    }
}

@MainActor
final class MotionDriver: NSObject {
    private var timer: Timer?
    private var started = 0.0
    private var duration = 0.0
    private var frame: ((CGFloat) -> Void)?
    private var completion: (() -> Void)?
    var isRunning: Bool { timer != nil }

    func start(duration: Double, frame: @escaping (CGFloat) -> Void, completion: (() -> Void)? = nil) {
        stop()
        self.frame = frame
        self.completion = completion
        self.duration = duration
        started = CACurrentMediaTime()
        guard duration > 0 else { finish(); return }
        frame(0)
        let timer = Timer(timeInterval: 1.0 / 60, target: self, selector: #selector(tick), userInfo: nil, repeats: true)
        self.timer = timer
        RunLoop.main.add(timer, forMode: .common)
    }

    func stop() {
        timer?.invalidate()
        timer = nil
        frame = nil
        completion = nil
    }

    func finish() {
        let frame = frame, completion = completion
        stop()
        frame?(1)
        completion?()
    }

    @objc private func tick() {
        let fraction = (CACurrentMediaTime() - started) / duration
        if fraction >= 1 { finish() } else { frame?(Motion.easeOut(fraction)) }
    }
}

@MainActor
enum Drawing {
    enum VerticalMetrics {
        case font, capitals
    }

    struct TextPlacement {
        let line: CTLine
        let glyphBounds: CGRect
        let baseline: CGPoint
        var visibleRect: CGRect {
            CGRect(x: baseline.x + glyphBounds.minX, y: baseline.y - glyphBounds.maxY,
                   width: glyphBounds.width, height: glyphBounds.height)
        }
    }

    static func placement(_ text: String, rect: CGRect, font: NSFont, color: NSColor = .white,
                          alignment: NSTextAlignment = .left, truncate: Bool = true,
                          verticalMetrics: VerticalMetrics = .font) -> TextPlacement? {
        guard !text.isEmpty, rect.width > 0 else { return nil }
        let attrs: [NSAttributedString.Key: Any] = [NSAttributedString.Key(kCTFontAttributeName as String): font,
            NSAttributedString.Key(kCTForegroundColorAttributeName as String): color.cgColor]
        var line = CTLineCreateWithAttributedString(NSAttributedString(string: text, attributes: attrs))
        if truncate && CTLineGetTypographicBounds(line, nil, nil, nil) > rect.width {
            let token = CTLineCreateWithAttributedString(NSAttributedString(string: "…", attributes: attrs))
            guard let shortened = CTLineCreateTruncatedLine(line, rect.width, .end, token) else { return nil }
            line = shortened
        }
        let ink = CTLineGetBoundsWithOptions(line, .useGlyphPathBounds)
        guard !ink.isNull, !ink.isEmpty else { return nil }
        let x: CGFloat = switch alignment {
        case .center: rect.midX - ink.midX
        case .right: rect.maxX - ink.maxX
        default: rect.minX
        }
        // Same role/font => same baseline, for Latin, CJK and mixed strings.
        // Core Text owns font cascading and the relative baseline of glyph runs.
        // Per-string ink centering moves the baseline whenever its letters change.
        // The flipped view needs a y-down baseline. Numbers use cap metrics;
        // labels retain the system font's ascender/descender, including descenders.
        let metricCenter: CGFloat = switch verticalMetrics {
        case .font: (font.ascender + font.descender) / 2
        case .capitals: font.capHeight / 2
        }
        return TextPlacement(line: line, glyphBounds: ink, baseline: CGPoint(x: x, y: rect.midY + metricCenter))
    }

    private static func draw(_ value: TextPlacement, clippedTo rect: CGRect) {
        guard let context = NSGraphicsContext.current?.cgContext else { return }
        context.saveGState()
        context.clip(to: rect)
        context.textMatrix = .identity
        context.translateBy(x: value.baseline.x, y: value.baseline.y)
        context.scaleBy(x: 1, y: -1)
        context.textPosition = .zero
        CTLineDraw(value.line, context)
        context.restoreGState()
    }

    static func text(_ text: String, rect: CGRect, size: CGFloat, weight: NSFont.Weight = .regular,
                     color: NSColor = .white, alignment: NSTextAlignment = .left) {
        if let value = placement(text, rect: rect, font: .systemFont(ofSize: size, weight: weight), color: color, alignment: alignment) {
            draw(value, clippedTo: rect)
        }
    }

    static func label(_ text: String, rect: CGRect, role: String, color: NSColor = .white,
                      alignment: NSTextAlignment = .left) {
        if let value = placement(text, rect: rect, font: Layout.font(role), color: color, alignment: alignment) {
            draw(value, clippedTo: rect)
        }
    }

    private static let emojiImages:NSCache<NSString,NSImage> = {
        let cache=NSCache<NSString,NSImage>();cache.countLimit=64;return cache
    }()
    private static func emojiImage(_ emoji:String,color:NSColor) -> NSImage? {
        let key=(emoji + (color.usingColorSpace(.sRGB)?.description ?? "white")) as NSString
        if let image=emojiImages.object(forKey:key) { return image }
        // Color emoji can contain transparent padding inside their nominal
        // Core Text glyph bounds. Fit the rendered alpha silhouette, not that
        // font box. This is cached icon preparation; text baselines are untouched.
        let side=192,fontSize:CGFloat=64
        guard let context=CGContext(data:nil,width:side,height:side,bitsPerComponent:8,bytesPerRow:side*4,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue | CGBitmapInfo.byteOrder32Big.rawValue) else { return nil }
        let line=CTLineCreateWithAttributedString(NSAttributedString(string:emoji,attributes:[NSAttributedString.Key(kCTFontAttributeName as String):NSFont.systemFont(ofSize:fontSize),NSAttributedString.Key(kCTForegroundColorAttributeName as String):color.cgColor]))
        context.textMatrix = .identity;context.textPosition=CGPoint(x:64,y:64);CTLineDraw(line,context)
        guard let data=context.data,let original=context.makeImage() else { return nil }
        let bytes=data.assumingMemoryBound(to:UInt8.self)
        var minX=side,minY=side,maxX = -1,maxY = -1
        for y in 0..<side { for x in 0..<side where bytes[y*side*4+x*4+3]>2 {
            minX=min(minX,x);maxX=max(maxX,x);minY=min(minY,y);maxY=max(maxY,y)
        } }
        guard maxX>=minX,maxY>=minY,let cropped=original.cropping(to:CGRect(x:minX,y:minY,width:maxX-minX+1,height:maxY-minY+1)) else { return nil }
        let image=NSImage(cgImage:cropped,size:CGSize(width:cropped.width,height:cropped.height))
        emojiImages.setObject(image,forKey:key);return image
    }

    static func icon(_ project: Project, rect: CGRect, color:NSColor = .white) {
        if project.markerType == "emoji",let image=emojiImage(project.marker,color:color) {
            let scale=min(rect.width/image.size.width,rect.height/image.size.height)
            let target=Layout.centered(CGSize(width:image.size.width*scale,height:image.size.height*scale),in:rect)
            image.draw(in:target,from:.zero,operation:.sourceOver,fraction:1,respectFlipped:true,hints:nil)
        } else if let image = NSImage(systemSymbolName: ProjectIcon.symbol(project.marker), accessibilityDescription: nil) {
            let config = NSImage.SymbolConfiguration(pointSize: rect.height - 1, weight: .medium).applying(.init(paletteColors: [color]))
            (image.withSymbolConfiguration(config) ?? image).draw(in: rect)
        }
    }

    static func badge(_ chat: Chat, rect: CGRect, color: NSColor, alpha: CGFloat = 1, pressed: Bool = false) {
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current?.cgContext.setAlpha(alpha)
        color.setFill()
        NSBezierPath(ovalIn: rect).fill()
        if pressed {
            NSColor.black.withAlphaComponent(0.15).setFill()
            NSBezierPath(ovalIn: rect).fill()
        }
        if chat.status == "unknown" {
            let edge = NSBezierPath(ovalIn: rect.insetBy(dx: 1.5, dy: 1.5))
            edge.lineWidth = 1
            edge.setLineDash([2, 2], count: 2, phase: 0)
            NSColor.black.setStroke()
            edge.stroke()
        }
        let small = rect.width <= Layout.value("badge-menu")
        let numberSize = Layout.value(chat.index > 9 ? (small ? "number-multi-font" : "number-row-multi-font")
                                     : (small ? "number-font" : "number-row-font"))
        if let value = placement(String(chat.index), rect: rect, font: .monospacedDigitSystemFont(ofSize: numberSize, weight: .semibold),
                                 color: Palette.foreground(color), alignment: .center, truncate: false,
                                 verticalMetrics: .capitals) { draw(value, clippedTo: rect) }
        NSGraphicsContext.restoreGraphicsState()
    }
}
