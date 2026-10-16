#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
out="${TMPDIR:-/tmp}/notproton-bottlepatch-public/NotProton BottlePatch.app"
mkdir -p "$out/Contents/MacOS" "$out/Contents/Resources/adapter"
xcrun swiftc -module-cache-path "${TMPDIR:-/tmp}/bottlepatch-module-cache" -swift-version 5 -O -framework Cocoa App.swift -o "$out/Contents/MacOS/BottlePatch"
cp Info.plist "$out/Contents/Info.plist"
cp repair.py "$out/Contents/Resources/repair.py"
for f in bridge.py native_bridge.py refresh-tools.py launch-shell Install.command Uninstall.command Start-Steam.command; do
 cp "adapter/$f" "$out/Contents/Resources/adapter/$f"
done
chmod +x "$out/Contents/Resources/adapter/launch-shell" "$out/Contents/Resources/adapter/"*.command
codesign --force --sign - "$out"
codesign --verify --deep --strict "$out"
echo "Built: $out"
