import AppKit

// MARK: - Custom Smiley Face View

class SmileyFaceView: NSView {

    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)

        // Background
        NSColor.windowBackgroundColor.setFill()
        bounds.fill()

        // Center and size
        let size = min(bounds.width, bounds.height) * 0.8
        let center = NSPoint(x: bounds.midX, y: bounds.midY)
        let faceRect = NSRect(
            x: center.x - size / 2,
            y: center.y - size / 2,
            width: size,
            height: size
        )

        // Face circle (yellow fill + black stroke)
        let facePath = NSBezierPath(ovalIn: faceRect)
        NSColor.systemYellow.setFill()
        facePath.fill()
        NSColor.black.setStroke()
        facePath.lineWidth = size * 0.03
        facePath.stroke()

        let eyeRadius = size * 0.08
        let eyeOffsetX = size * 0.22
        let eyeOffsetY = size * 0.22

        // Left eye
        let leftEyeCenter = NSPoint(
            x: center.x - eyeOffsetX,
            y: center.y + eyeOffsetY
        )
        drawEye(center: leftEyeCenter, radius: eyeRadius)

        // Right eye
        let rightEyeCenter = NSPoint(
            x: center.x + eyeOffsetX,
            y: center.y + eyeOffsetY
        )
        drawEye(center: rightEyeCenter, radius: eyeRadius)

        // Smile (arc)
        let smilePath = NSBezierPath()
        let smileCenter = NSPoint(x: center.x, y: center.y - size * 0.1)
        let smileRadius = size * 0.3
        let startAngle: CGFloat = 220  // degrees
        let endAngle: CGFloat = 320    // degrees

        smilePath.appendArc(
            withCenter: smileCenter,
            radius: smileRadius,
            startAngle: startAngle,
            endAngle: endAngle
        )
        smilePath.lineWidth = size * 0.04
        NSColor.black.setStroke()
        smilePath.stroke()
    }

    private func drawEye(center: NSPoint, radius: CGFloat) {
        let eyeRect = NSRect(
            x: center.x - radius,
            y: center.y - radius,
            width: radius * 2,
            height: radius * 2
        )
        let eyePath = NSBezierPath(ovalIn: eyeRect)
        NSColor.black.setFill()
        eyePath.fill()
    }
}

// MARK: - Window & App Delegate

class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!

    func applicationDidFinishLaunching(_ notification: Notification) {
        let windowRect = NSRect(x: 0, y: 0, width: 400, height: 400)
        window = NSWindow(
            contentRect: windowRect,
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "😊 Smiley Face"
        window.center()

        let smileyView = SmileyFaceView(frame: windowRect)
        window.contentView = smileyView

        window.makeKeyAndOrderFront(nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
}

// MARK: - Main Entry

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
