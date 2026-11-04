import Testing
import SwiftUI
@testable import MenuBar

@Test func explicitToggleWinsOverAnEarlierResignKeyNotification() {
    var intent = PopoverIntent()
    intent.set(true)
    let lostKeyRevision = intent.revision
    intent.set(false) // second pointer-down, before the deferred focus handler
    #expect(!intent.shouldDismissAfterFocusLoss(revision: lostKeyRevision, isKey: false, anchorGesture: false))
    #expect(!intent.isOpen)
    intent.set(true) // a third click reverses the close
    #expect(!intent.shouldDismissAfterFocusLoss(revision: lostKeyRevision, isKey: false, anchorGesture: false))
    #expect(intent.isOpen)
}

@Test func outsideFocusLossStillDismissesButAnAnchorGestureDoesNot() {
    var intent = PopoverIntent(); intent.set(true)
    #expect(intent.shouldDismissAfterFocusLoss(revision: intent.revision, isKey: false, anchorGesture: false))
    #expect(!intent.shouldDismissAfterFocusLoss(revision: intent.revision, isKey: false, anchorGesture: true))
    #expect(!intent.shouldDismissAfterFocusLoss(revision: intent.revision, isKey: true, anchorGesture: false))
}

@Test func springReversalPreservesTheDisplayedValueAndVelocity() {
    let config = Layout.specification.popoverMotion
    var spring = SpringTrajectory()
    spring.retarget(1, at: 0, configuration: config)
    spring.sample(at: 0.06)
    let displayed = spring.value, velocity = spring.velocity
    #expect(displayed > 0 && displayed < 1)
    #expect(velocity > 0)
    spring.retarget(0, at: 0.065, configuration: config)
    #expect(spring.value == displayed)
    #expect(spring.velocity == velocity)
    spring.sample(at: 0.10)
    let turning = spring.value, reverseVelocity = spring.velocity
    spring.retarget(1, at: 0.105, configuration: config)
    #expect(spring.value == turning)
    #expect(spring.velocity == reverseVelocity)
    spring.sample(at: 2)
    #expect(spring.value == 1 && spring.velocity == 0)
}

@Test func bothSpringDirectionsSettleAndTheCloseIsNotAnInstantHide() {
    let config = Layout.specification.popoverMotion
    var spring = SpringTrajectory()
    spring.retarget(1, at: 0, configuration: config); spring.sample(at: 2)
    spring.retarget(0, at: 2, configuration: config)
    #expect(spring.value == 1)
    spring.sample(at: 2.05)
    #expect(spring.value > 0 && spring.value < 1)
    spring.sample(at: 4)
    #expect(spring.value == 0 && spring.velocity == 0)
}

@Test @MainActor func aRetargetCannotRunTheStaleCloseCompletion() {
    let motion = PopoverSpringMotion()
    var staleClosed = false, latestOpened = false, settled = false
    motion.start(to: 1, animated: false, frame: { _ in })
    motion.start(to: 0, frame: { _ in }, completion: { staleClosed = true })
    motion.whenSettled { settled = true }
    motion.start(to: 1, frame: { _ in }, completion: { latestOpened = true })
    motion.finish()
    #expect(!staleClosed && latestOpened && settled)
    #expect(motion.value == 1 && motion.velocity == 0)
}

@Test @MainActor func keyboardOpenAndCloseCompleteImmediately() {
    let motion = PopoverSpringMotion()
    motion.start(to: 1, animated: false, frame: { _ in })
    #expect(motion.value == 1 && !motion.isRunning)
    motion.start(to: 0, animated: false, frame: { _ in })
    #expect(motion.value == 0 && !motion.isRunning)
}

@Test func reducedPopupSpringKeepsTheFadeButRemovesBounce() {
    let base = Layout.specification.popoverMotion
    let reduced = base.reduced(true)
    #expect(reduced.response == base.reducedResponse && reduced.dampingRatio == 1)
    var spring = SpringTrajectory()
    spring.retarget(1, at: 0, configuration: reduced)
    for time in [0.01, 0.03, 0.08, 0.15] {
        spring.sample(at: time)
        #expect(spring.value >= 0 && spring.value <= 1)
    }
    spring.sample(at: 2)
    #expect(spring.value == 1 && spring.velocity == 0)
}
