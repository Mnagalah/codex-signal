import AppKit

// Diagnostics render only this plugin's own views. This is not a desktop or
// system-menu-bar screenshot; real host coordinates preserve relative placement.
@MainActor enum MenuStripCapture {
    private final class Canvas:NSView {
        var pieces:[(NSImage,CGRect)]=[]
        override var isFlipped:Bool { true }
        override func draw(_ dirtyRect:NSRect) {
            NSColor(srgbRed:0.12,green:0.13,blue:0.15,alpha:1).setFill();bounds.fill()
            for (image,frame) in pieces { image.draw(in:frame,from:.zero,operation:.sourceOver,fraction:1,respectFlipped:true,hints:nil) }
        }
    }
    static func write(views:[CapsuleView],directory:URL) {
        let live=views.compactMap { view -> (CapsuleView,CGRect)? in
            guard let window=view.window,window.isVisible,window.occlusionState.contains(.visible),view.frame.width>2 else { return nil }
            return (view,window.convertToScreen(view.convert(view.bounds,to:nil)))
        }
        guard let left=live.map({$0.1.minX}).min(),let right=live.map({$0.1.maxX}).max(),let top=live.map({$0.1.maxY}).max(),right-left<4096 else { return }
        let height=live.map({$0.1.height}).max() ?? 22
        let canvas=Canvas(frame:CGRect(x:0,y:0,width:right-left+16,height:height+16))
        for (view,frame) in live {
            guard let rep=view.bitmapImageRepForCachingDisplay(in:view.bounds) else { continue };view.cacheDisplay(in:view.bounds,to:rep)
            let image=NSImage(size:view.bounds.size);image.addRepresentation(rep)
            canvas.pieces.append((image,CGRect(x:frame.minX-left+8,y:top-frame.maxY+8,width:frame.width,height:frame.height)))
        }
        guard let bitmap=NSBitmapImageRep(bitmapDataPlanes:nil,pixelsWide:Int(canvas.bounds.width*2),pixelsHigh:Int(canvas.bounds.height*2),bitsPerSample:8,samplesPerPixel:4,hasAlpha:true,isPlanar:false,colorSpaceName:.deviceRGB,bytesPerRow:0,bitsPerPixel:0) else { return }
        bitmap.size=canvas.bounds.size;canvas.cacheDisplay(in:canvas.bounds,to:bitmap)
        if let data=bitmap.representation(using:.png,properties:[:]) { try? data.write(to:directory.appendingPathComponent("live-menu-strip.png"),options:.atomic) }
    }
}
