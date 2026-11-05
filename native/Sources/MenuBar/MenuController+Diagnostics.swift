import AppKit

// Development-only inspection and exercises. The controller remains the sole
// owner of status-item identity, state and presentation; no OS events are posted.
@MainActor
extension MenuController {
    func captureOwnViews(in directory: String) {
        let root = URL(fileURLWithPath: directory, isDirectory: true)
        try? FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        var evidence: [[String: Any]] = []
        for (id, view) in views {
            let safe = id.replacingOccurrences(of: "[^A-Za-z0-9_-]", with: "-", options: .regularExpression)
            if let bitmap = view.bitmapImageRepForCachingDisplay(in: view.bounds) {
                view.cacheDisplay(in: view.bounds, to: bitmap)
                try? bitmap.representation(using: .png, properties: [:])?.write(to: root.appendingPathComponent(safe + ".png"))
            }
            evidence.append(["project": view.project.name, "windowAttached": view.window != nil,
                             "windowVisible": view.window?.isVisible ?? false,
                             "occlusionVisible": view.window?.occlusionState.contains(.visible) ?? false,
                             "width": view.frame.width, "height": view.frame.height,
                             "screenFrame": view.window.map { LayoutDiagnostics.rect($0.convertToScreen(view.convert(view.bounds, to: nil))) } ?? [:],
                             "kind": view.project.kind ?? "project",
                             "numberedChats": view.project.threads.count,
                             "contentTargetWidth": view.layout.width,
                             "itemLength": items[id]?.length ?? 0,
                             "buttonFrame": NSStringFromRect(items[id]?.button?.frame ?? .zero),
                             "viewFrameInButton": NSStringFromRect(view.frame),
                             "hosting": "transparent-native-button", "grid": LayoutDiagnostics.capsule(view)])
        }
        MenuStripCapture.write(views:Array(views.values),directory:root)
        if let data = try? JSONSerialization.data(withJSONObject: evidence, options: [.prettyPrinted, .sortedKeys]) {
            try? data.write(to: root.appendingPathComponent("live-views.json"), options: .atomic)
        }
    }

    // An explicit diagnostic request to our renderer, not an OS event injection.
    // Uses the real status item/window and production popup; never opens a chat,
    // marks anything seen, changes the monitor switch or alters saved numbering.
    func inspectLayout(requestID: String) {
        guard requestID.range(of: "^[0-9a-f]{32}$", options: .regularExpression) != nil,
              let directory = ProcessInfo.processInfo.environment["CODEX_MENU_UI_CAPTURE_DIR"],
              let view = popover.projectID.flatMap({ views[$0] }) ?? views["global-control"] ?? order.compactMap({ views[$0] }).first else { return }
        captureOwnViews(in: directory)
        popover.inspect(from: view, directory: directory, requestID: requestID) { [weak self] popup in
            guard let self else { return }
            let report: [String: Any] = ["requestId": requestID, "contract": LayoutDiagnostics.contract,
                "capsules": self.order.compactMap { self.views[$0] }.map(LayoutDiagnostics.capsule), "popup": popup]
            let path = URL(fileURLWithPath: directory).appendingPathComponent("inspection-" + requestID + ".json")
            if let data = try? JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]) {
                try? data.write(to: path, options: .atomic)
            }
        }
    }

    func chooseEmoji(requestID:String) {
        guard requestID.range(of:"^[0-9a-f]{32}$",options:.regularExpression) != nil,
              let directory=ProcessInfo.processInfo.environment["CODEX_MENU_UI_CAPTURE_DIR"],let view=views["global-control"] else { return }
        popover.chooseEmoji(from:view,directory:directory,requestID:requestID)
    }

    func inspectSettings(requestID:String) {
        guard requestID.range(of:"^[0-9a-f]{32}$",options:.regularExpression) != nil,
              let directory=ProcessInfo.processInfo.environment["CODEX_MENU_UI_CAPTURE_DIR"],let view=views["global-control"] else { return }
        captureOwnViews(in:directory)
        popover.inspectSettings(from:view,directory:directory,requestID:requestID)
    }

    // Presentation-only round trip through the production apply path. No
    // settings, IPC subscription, chat identity or local seen state is changed.
    func exerciseMenuLayout(requestID:String) {
        guard requestID.range(of:"^[0-9a-f]{32}$",options:.regularExpression) != nil,
              let directory=ProcessInfo.processInfo.environment["CODEX_MENU_UI_CAPTURE_DIR"] else { return }
        let path=URL(fileURLWithPath:directory).appendingPathComponent("menu-layout-"+requestID+".json")
        guard !exercising,!popover.isShown,latestState?.projects.isEmpty == false,let original=items["global-control"] else {
            if let data=try? JSONSerialization.data(withJSONObject:["requestId":requestID,"completed":false,"reason":"popover-open-or-no-live-projects"]) { try? data.write(to:path) };return
        }
        exercising=true
        let began=CACurrentMediaTime()
        var steps:[[String:Any]]=[],samples:[[String:Any]]=[],finished=false
        let sampler=MotionDriver()
        @MainActor func snapshot(_ label:String) -> [String:Any] {
            var result:[String:Any]=["step":label,"time":CACurrentMediaTime()-began,"sameGlobalHost":items["global-control"] === original,
                "compactPresentation":compactPresentationOverride ?? latestState?.compactMenuBar ?? false]
            result["views"]=order.compactMap { id -> [String:Any]? in
                guard let view=views[id],let window=view.window else { return nil }
                return ["id":id,"kind":view.project.kind ?? "project","frame":LayoutDiagnostics.rect(window.convertToScreen(view.convert(view.bounds,to:nil))),
                    "occlusionVisible":window.occlusionState.contains(.visible),"motion":view.visibilitySnapshot,
                    "visual":LayoutDiagnostics.capsule(view)]
            }
            return result
        }
        @MainActor func setCompact(_ value:Bool?) {
            compactPresentationOverride=value
            if let latestState { apply(latestState) }
        }
        @MainActor func mark(_ label:String) {
            steps.append(snapshot(label))
            if ["expanded","collapsed","expanded-again","restored"].contains(label) {
                captureOwnViews(in:directory)
                let root=URL(fileURLWithPath:directory),source=root.appendingPathComponent("live-menu-strip.png")
                let target=root.appendingPathComponent("menu-layout-"+requestID+"-"+label+".png")
                if let data=try? Data(contentsOf:source) { try? data.write(to:target,options:.atomic) }
            }
        }
        @MainActor func finish(cancelled:Bool=false) {
            guard !finished else { return };finished=true;sampler.stop();cancelMenuExercise=nil
            setCompact(nil);mark("restored")
            exercising=false;captureOwnViews(in:directory)
            let report:[String:Any]=["requestId":requestID,"completed":!cancelled,"input":"plugin-owned-presentation-override","settingsChanged":false,
                "steps":steps,"samples":samples,"sameGlobalHost":items["global-control"] === original,"menuMotionSeconds":Layout.specification.menuMotion.transition]
            if let data=try? JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]) { try? data.write(to:path,options:.atomic) }
        }
        cancelMenuExercise={ finish(cancelled:true) }
        setCompact(false)
        sampler.start(duration:3,frame: { _ in
            if !finished && samples.count<180 { samples.append(snapshot("frame")) }
        })
        DispatchQueue.main.asyncAfter(deadline:.now()+0.35) {
            guard !finished else { return };mark("expanded");setCompact(true);mark("collapse-begin")
            DispatchQueue.main.asyncAfter(deadline:.now()+0.30) {
                guard !finished else { return };mark("collapsed");setCompact(false);mark("expand-begin")
                DispatchQueue.main.asyncAfter(deadline:.now()+0.06) {
                    guard !finished else { return };mark("before-interrupt-collapse");setCompact(true);mark("after-interrupt-collapse")
                    DispatchQueue.main.asyncAfter(deadline:.now()+0.06) {
                        guard !finished else { return };mark("before-interrupt-expand");setCompact(false);mark("after-interrupt-expand")
                        DispatchQueue.main.asyncAfter(deadline:.now()+0.30) {
                            guard !finished else { return };mark("expanded-again");setCompact(nil)
                            DispatchQueue.main.asyncAfter(deadline:.now()+0.30) { finish() }
                        }
                    }
                }
            }
        }
    }

    func exerciseToggle(requestID: String) {
        guard requestID.range(of: "^[0-9a-f]{32}$", options: .regularExpression) != nil,
              let directory = ProcessInfo.processInfo.environment["CODEX_MENU_UI_CAPTURE_DIR"],
              !exercising, !popover.isShown,
              let view = order.compactMap({ views[$0] }).first(where: { $0.project.id != "control" }),
              let window = view.window else { return }
        exercising = true
        var steps: [[String: Any]] = [], samples: [[String: Any]] = [], finished = false
        let began = CACurrentMediaTime()
        popover.onMotionSample = { sample in
            if samples.count < 240 { samples.append(sample.merging(["time": CACurrentMediaTime() - began]) { _, new in new }) }
        }
        func capture(_ label: String) { steps.append(popover.motionSnapshot.merging(["step": label]) { _, new in new }) }
        func click() {
            let point = view.convert(CGPoint(x: view.layout.name.isEmpty ? view.layout.icon.midX : view.layout.name.midX, y: view.layout.centerY), to: nil)
            guard let down = NSEvent.mouseEvent(with: .leftMouseDown, location: point, modifierFlags: [],
                timestamp: ProcessInfo.processInfo.systemUptime, windowNumber: window.windowNumber,
                context: nil, eventNumber: 1, clickCount: 1, pressure: 1),
                  let up = NSEvent.mouseEvent(with: .leftMouseUp, location: point, modifierFlags: [],
                timestamp: ProcessInfo.processInfo.systemUptime, windowNumber: window.windowNumber,
                context: nil, eventNumber: 2, clickCount: 1, pressure: 0) else { return }
            // Calls only our own native handlers, never posts an OS mouse event.
            view.mouseDown(with: down); view.mouseUp(with: up)
        }
        func finish(_ timedOut: Bool = false) {
            guard !finished else { return }; finished = true
            exercising = false; popover.onMotionSample = nil
            let report: [String: Any] = ["requestId": requestID, "project": view.project.name,
                "contract": LayoutDiagnostics.contract, "timedOut": timedOut,
                "steps": steps, "samples": samples, "final": popover.motionSnapshot,
                "input": "plugin-owned-native-handlers"]
            if let data = try? JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]) {
                try? data.write(to: URL(fileURLWithPath: directory).appendingPathComponent("toggle-" + requestID + ".json"), options: .atomic)
            }
        }
        click(); capture("first-click-target-open")
        popover.whenSettled { [self] in
            guard !finished else { return }; capture("first-click-settled-open")
            popover.resignKeyForInspection() // The problematic real-window event order.
            click(); capture("second-click-after-resign-target-closed")
            popover.whenSettled { [self] in
                guard !finished else { return }; capture("second-click-settled-closed")
                click()
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.06) { [self] in
                    guard !finished else { return }; capture("before-rapid-close")
                    click(); capture("after-rapid-close")
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.06) { [self] in
                        guard !finished else { return }; capture("before-rapid-reopen")
                        click(); capture("after-rapid-reopen")
                        popover.whenSettled { [self] in
                            guard !finished else { return }; capture("rapid-reopen-settled-open")
                            click()
                            popover.whenSettled { guard !finished else { return }; capture("final-settled-closed"); finish() }
                        }
                    }
                }
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 4) { finish(true) }
    }

}
