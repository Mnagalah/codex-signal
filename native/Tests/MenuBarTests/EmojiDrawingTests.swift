import AppKit
import Testing
@testable import MenuBar

@MainActor private final class IconBitmapView:NSView {
    var emoji="⚕️"
    override var isFlipped:Bool { true }
    override func draw(_ dirtyRect:NSRect) {
        NSGraphicsContext.current?.cgContext.clear(bounds)
        Drawing.icon(Project(id:"icon",name:"",markerType:"emoji",marker:emoji,threads:[]),rect:CGRect(x:9,y:9,width:14,height:14))
    }
}
@Test(arguments:["🔦","⚕️","🧭","👩🏽‍💻","👨‍👩‍👧‍👦"]) @MainActor func actualEmojiBitmapCentersInItsIconCell(emoji:String) throws {
    let view=IconBitmapView(frame:CGRect(x:0,y:0,width:32,height:32));view.emoji=emoji
    let image=try #require(NSBitmapImageRep(bitmapDataPlanes:nil,pixelsWide:64,pixelsHigh:64,bitsPerSample:8,samplesPerPixel:4,hasAlpha:true,isPlanar:false,colorSpaceName:.deviceRGB,bytesPerRow:0,bitsPerPixel:0))
    image.size=view.bounds.size;view.cacheDisplay(in:view.bounds,to:image)
    var xs:[Int]=[],ys:[Int]=[]
    for y in 0..<image.pixelsHigh { for x in 0..<image.pixelsWide {
        if let c=image.colorAt(x:x,y:y)?.usingColorSpace(.sRGB),c.alphaComponent>0.2 { xs.append(x);ys.append(y) }
    } }
    let minX=try #require(xs.min()),maxX=try #require(xs.max()),minY=try #require(ys.min()),maxY=try #require(ys.max())
    let centerX=CGFloat(minX+maxX+1)/4,centerY=CGFloat(minY+maxY+1)/4
    #expect(abs(centerX-16)<=0.5 && abs(centerY-16)<=0.5,"actual bitmap center: \(centerX),\(centerY); glyph pixels \(minX)...\(maxX),\(minY)...\(maxY)")
}
