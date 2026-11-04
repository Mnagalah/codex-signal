import AppKit
import QuartzCore
import SwiftUI

struct PopoverMotionConfiguration: Decodable, Sendable {
    var response: Double
    var dampingRatio: Double
    let offset: CGFloat
    let epsilon: Double
    let reducedResponse: Double
    func reduced(_ enabled: Bool) -> Self {
        var value = self
        if enabled { value.response = reducedResponse; value.dampingRatio = 1 }
        return value
    }
}

// Intent is independent of window focus and the in-flight presentation. A click
// changes it exactly once; an older focus-loss event may not undo that click.
struct PopoverIntent: Sendable {
    private(set) var isOpen = false
    private(set) var revision = 0
    mutating func set(_ open: Bool) { isOpen = open; revision += 1 }
    func shouldDismissAfterFocusLoss(revision: Int, isKey: Bool, anchorGesture: Bool) -> Bool {
        isOpen && self.revision == revision && !isKey && !anchorGesture
    }
}

struct SpringTrajectory: Sendable {
    private(set) var value = 0.0
    private(set) var velocity = 0.0
    private(set) var target = 0.0
    private(set) var duration = 0.0
    private var origin = 0.0
    private var initialVelocity = 0.0
    private var started = 0.0
    private var curve = SwiftUI.Spring(response: Layout.specification.popoverMotion.response,
                                       dampingRatio: Layout.specification.popoverMotion.dampingRatio)

    mutating func retarget(_ target: Double, at now: Double, configuration: PopoverMotionConfiguration) {
        // The stored value/velocity are the last frame actually presented, not
        // the previous target or a newly simulated value that was never drawn.
        origin = value; initialVelocity = velocity; started = now; self.target = target
        curve = SwiftUI.Spring(response: configuration.response, dampingRatio: configuration.dampingRatio)
        duration = abs(target - origin) < configuration.epsilon && abs(velocity) < configuration.epsilon
            ? 0 : curve.settlingDuration(target: target - origin, initialVelocity: initialVelocity, epsilon: configuration.epsilon)
    }
    mutating func sample(at now: Double) {
        let elapsed = max(0, now - started)
        if elapsed >= duration { finish(); return }
        value = origin + curve.value(target: target - origin, initialVelocity: initialVelocity, time: elapsed)
        velocity = curve.velocity(target: target - origin, initialVelocity: initialVelocity, time: elapsed)
    }
    mutating func finish() { value = target; velocity = 0 }
}

@MainActor
final class PopoverSpringMotion: NSObject {
    private var timer: Timer?
    private(set) var trajectory = SpringTrajectory()
    private var frame: ((CGFloat) -> Void)?
    private var completion: (() -> Void)?
    private var observers: [() -> Void] = []
    var isRunning: Bool { timer != nil }
    var value: CGFloat { CGFloat(trajectory.value) }
    var velocity: Double { trajectory.velocity }

    func start(to target: CGFloat, animated: Bool = true, frame: @escaping (CGFloat) -> Void, completion: (() -> Void)? = nil) {
        timer?.invalidate(); timer = nil
        self.frame = frame; self.completion = completion
        trajectory.retarget(Double(target), at: CACurrentMediaTime(), configuration: Layout.specification.popoverMotion.reduced(Motion.reduced))
        guard animated, trajectory.duration > 0 else { finish(); return }
        frame(value)
        let timer = Timer(timeInterval: 1.0 / 60, target: self, selector: #selector(tick), userInfo: nil, repeats: true)
        self.timer = timer
        RunLoop.main.add(timer, forMode: .common)
    }
    func whenSettled(_ action: @escaping () -> Void) {
        if isRunning { observers.append(action) } else { action() }
    }
    func finish() {
        timer?.invalidate(); timer = nil
        trajectory.finish()
        let frame = frame, completion = completion, observers = observers
        self.frame = nil; self.completion = nil; self.observers = []
        frame?(value); completion?()
        for observer in observers { observer() }
    }
    @objc private func tick() {
        trajectory.sample(at: CACurrentMediaTime())
        if trajectory.velocity == 0 && trajectory.value == trajectory.target { finish() }
        else { frame?(value) }
    }
}
