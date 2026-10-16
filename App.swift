import Cocoa
import UniformTypeIdentifiers

final class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    let picker = NSPopUpButton(frame: .zero, pullsDown: false)
    let patch = NSButton(title: "Patch", target: nil, action: nil)
    let browse = NSButton(title: "Browse…", target: nil, action: nil)
    let selectedPath = NSTextField(labelWithString: "")
    let status = NSTextField(wrappingLabelWithString: "Select a CrossOver installation, then click Patch.")
    let spinner = NSProgressIndicator()
    var targets: [String] = []
    var logURL = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/NotProton BottlePatch/patch.log")

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.applicationIconImage = NSImage(systemSymbolName: "shippingbox.fill", accessibilityDescription: "BottlePatch")
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 560, height: 365), styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "NotProton BottlePatch"
        window.center()
        let title = NSTextField(labelWithString: "NotProton BottlePatch")
        title.font = .boldSystemFont(ofSize: 24)
        let subtitle = NSTextField(wrappingLabelWithString: "Native Steam. Your CrossOver bottle.")
        subtitle.textColor = .secondaryLabelColor
        let label = NSTextField(labelWithString: "CrossOver")
        picker.widthAnchor.constraint(equalToConstant: 360).isActive = true
        browse.target = self; browse.action = #selector(chooseApp)
        let row = NSStackView(views: [picker, browse]); row.orientation = .horizontal; row.spacing = 10
        selectedPath.font = .systemFont(ofSize: 11)
        selectedPath.textColor = .secondaryLabelColor
        selectedPath.cell?.lineBreakMode = .byTruncatingMiddle
        let note = NSTextField(wrappingLabelWithString: "Checks compatibility and restores the Steam connection after updates. Does not launch Steam or games.")
        note.textColor = .secondaryLabelColor
        status.font = .systemFont(ofSize: 13)
        status.heightAnchor.constraint(greaterThanOrEqualToConstant: 36).isActive = true
        patch.target = self; patch.action = #selector(applyPatch); patch.bezelStyle = .rounded; patch.keyEquivalent = "\r"
        let log = NSButton(title: "Open Log", target: self, action: #selector(openLog)); log.bezelStyle = .rounded
        spinner.style = .spinning; spinner.controlSize = .small; spinner.isDisplayedWhenStopped = false
        let actions = NSStackView(views: [patch, log, spinner]); actions.orientation = .horizontal; actions.spacing = 12
        let stack = NSStackView(views: [title, subtitle, label, row, selectedPath, note, status, actions])
        stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false
        window.contentView!.addSubview(stack)
        NSLayoutConstraint.activate([stack.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor, constant: 24), stack.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor, constant: -24), stack.topAnchor.constraint(equalTo: window.contentView!.topAnchor, constant: 22)])
        patch.isEnabled = false
        picker.isEnabled = false
        status.stringValue = "Finding CrossOver installations…"
        picker.target = self; picker.action = #selector(selectionChanged)
        discoverInstallations()
        window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
    }

    func discoverInstallations() {
        DispatchQueue.global(qos: .userInitiated).async {
            let fm = FileManager.default
            var paths = Set<String>()
            let roots = ["/Applications", NSHomeDirectory()+"/Applications"]
            for root in roots {
                let url = URL(fileURLWithPath: root)
                if let scan = fm.enumerator(at: url, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles, .skipsPackageDescendants]) {
                    for case let candidate as URL in scan {
                        if candidate.pathExtension.lowercased() == "app" { paths.insert(candidate.path) }
                        if candidate.pathComponents.count - url.pathComponents.count > 3 { scan.skipDescendants() }
                    }
                }
            }
            let query = Process(); let output = Pipe()
            query.executableURL = URL(fileURLWithPath: "/usr/bin/mdfind")
            query.arguments = ["-0", "kMDItemContentTypeTree == 'com.apple.application-bundle' && (kMDItemCFBundleIdentifier == 'com.codeweavers.CrossOver*' || kMDItemFSName == '*CrossOver*.app'cd)"]
            query.standardOutput = output; query.standardError = FileHandle.nullDevice
            if (try? query.run()) != nil {
                let data = output.fileHandleForReading.readDataToEndOfFile(); query.waitUntilExit()
                for value in (String(data: data, encoding: .utf8) ?? "").split(separator: "\0") { paths.insert(String(value)) }
            }
            let valid = Set(paths.compactMap { value -> String? in
                let url = URL(fileURLWithPath: value).resolvingSymlinksInPath()
                return fm.fileExists(atPath: url.appendingPathComponent("Contents/SharedSupport/CrossOver/bin/wine").path) ? url.path : nil
            }).sorted { $0.localizedCaseInsensitiveCompare($1) == .orderedAscending }
            DispatchQueue.main.async {
                for path in valid { self.addTarget(path) }
                let config = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/NotProton BottlePatch/config.json")
                var preferred: String? = nil
                if let data = try? Data(contentsOf: config), let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let path = object["crossover"] as? String { preferred = URL(fileURLWithPath: path).resolvingSymlinksInPath().path }
                let index = preferred.flatMap { self.targets.firstIndex(of: $0) } ?? 0
                if !self.targets.isEmpty { self.picker.selectItem(at: index); self.selectionChanged() }
                self.picker.isEnabled = true
                self.patch.isEnabled = !self.targets.isEmpty
                self.status.stringValue = self.targets.isEmpty ? "No CrossOver installation found. Use Browse to locate a copy." : "Select a CrossOver installation, then click Patch."
            }
        }
    }

    func addTarget(_ value: String) {
        let path = URL(fileURLWithPath: value).resolvingSymlinksInPath().path
        if let index = targets.firstIndex(of: path) { picker.selectItem(at: index); return }
        targets.append(path)
        let url = URL(fileURLWithPath: path)
        let info = NSDictionary(contentsOf: url.appendingPathComponent("Contents/Info.plist"))
        let version = info?["CFBundleShortVersionString"] as? String ?? ""
        picker.addItem(withTitle: url.deletingPathExtension().lastPathComponent + (version.isEmpty ? "" : " — \(version)"))
        picker.selectItem(at: targets.count-1)
        picker.toolTip = path
        selectedPath.stringValue = (path as NSString).abbreviatingWithTildeInPath
        picker.lastItem?.toolTip = path
        patch.isEnabled = true
    }

    @objc func selectionChanged() {
        if picker.indexOfSelectedItem >= 0 { let path = targets[picker.indexOfSelectedItem]; picker.toolTip = path; selectedPath.stringValue = (path as NSString).abbreviatingWithTildeInPath }
    }

    @objc func chooseApp() {
        let panel = NSOpenPanel(); panel.canChooseFiles = true; panel.canChooseDirectories = false
        panel.allowedContentTypes = [.applicationBundle]; panel.directoryURL = URL(fileURLWithPath: "/Applications")
        panel.message = "Choose CrossOver, CrossOver Preview, or another installed copy."
        panel.beginSheetModal(for: window) { response in
            if response == .OK, let url = panel.url { self.addTarget(url.path) }
        }
    }

    @objc func openLog() {
        if FileManager.default.fileExists(atPath: logURL.path) { NSWorkspace.shared.open(logURL) }
        else { status.stringValue = "A log will be available after the first patch attempt." }
    }

    @objc func applyPatch() {
        guard picker.indexOfSelectedItem >= 0, let resources = Bundle.main.resourceURL else { return }
        let selected = targets[picker.indexOfSelectedItem]
        status.stringValue = "Checking compatibility and applying patch…"
        patch.isEnabled = false; picker.isEnabled = false; browse.isEnabled = false; spinner.startAnimation(nil)
        DispatchQueue.global(qos: .userInitiated).async {
            let process = Process(); let pipe = Pipe()
            process.executableURL = URL(fileURLWithPath: "/opt/homebrew/bin/python3")
            process.arguments = [resources.appendingPathComponent("repair.py").path, "--crossover", selected]
            process.standardOutput = pipe; process.standardError = pipe
            var succeeded = false; var message = "Could not start the patcher."
            do {
                try process.run()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                process.waitUntilExit()
                let text = String(data: data, encoding: .utf8) ?? ""
                if let line = text.split(separator: "\n").last, let jsonData = String(line).data(using: .utf8), let result = try JSONSerialization.jsonObject(with: jsonData) as? [String: Any] {
                    succeeded = result["success"] as? Bool == true && process.terminationStatus == 0
                    message = result["message"] as? String ?? text
                } else { message = text.isEmpty ? "The patcher returned no result. Open the log for details." : text }
            } catch { message = error.localizedDescription }
            DispatchQueue.main.async {
                self.patch.isEnabled = true; self.picker.isEnabled = true; self.browse.isEnabled = true; self.spinner.stopAnimation(nil)
                self.status.stringValue = (succeeded ? "Success — " : "Fail — ")+message
                let alert = NSAlert(); alert.messageText = succeeded ? "Success" : "Fail"
                alert.informativeText = message; alert.alertStyle = succeeded ? .informational : .warning
                alert.addButton(withTitle: "OK"); alert.addButton(withTitle: "Open Log")
                alert.beginSheetModal(for: self.window) { result in if result == .alertSecondButtonReturn { self.openLog() } }
            }
        }
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}
let delegate = AppDelegate()
NSApplication.shared.delegate = delegate
NSApplication.shared.run()
