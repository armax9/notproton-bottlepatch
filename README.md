# NotProton BottlePatch

Native Steam. Your existing CrossOver bottle.

NotProton normally uses a separate Wine prefix for each game. If you already have a CrossOver bottle with your dependencies, VR mods and custom graphics libraries, setting everything up again is a pain.

BottlePatch redirects game launches to that bottle. You still press Play in native Steam and choose D3DMetal, DXVK and other per-game options in NotProton. No need to open CrossOver or wait for Windows Steam to start.

## How it works

A small Swift/AppKit app installs a Python launch adapter through NotProton's existing external-launch hook. It uses your installed CrossOver libraries and NotProton's native Steam bridge. It does not replace NotProton or patch CrossOver's application files.

## Setup

1. Install [NotProton](https://github.com/NotProtonNot/NotProton) and configure your CrossOver runner there first.
2. Install Homebrew Python 3 (`brew install python`); this preview expects `/opt/homebrew/bin/python3`.
3. Download the app from Releases, unzip it and move it to Applications. It is ad-hoc signed, not notarized.
4. Close your games, open BottlePatch, select the detected CrossOver installation and click **Patch**.
5. Fully quit Steam and reopen it. Launch games normally from native Steam.

Defaults to your existing `Steam` bottle. For another bottle, edit `~/Library/Application Support/NotProton BottlePatch/config.json` and apply again. The app reports Success or Fail and has an Open Log button.

After updates, run Patch again. A matching NotProton runner is required; incompatible Wine builds are refused. Future NotProton changes may require an adapter update.

## Compatibility

Experimental Apple Silicon macOS app (macOS 14+). Regular CrossOver and CrossOver Preview are detected; compatibility depends on an installed matching NotProton native bridge. Developed against CrossOver Preview 27.0.0.41069 and NotProton commit `5568282bdcb85c2c23b73adc73a96f5543664102`.

D3DMetal and DXVK routing, native Steam authorization, Subnautica and a separate 32-bit Steam API probe have been checked. This is not a guarantee for every game or CrossOver version. Custom renderers and mods must already be installed by you.

## Current limits

- One game at a time per shared bottle. Do not change global bottle settings while another game is running.
- Some Steam install-script helpers can still use NotProton's original per-game prefix.
- Steam Cloud path mapping, overlay, Retina and controller behavior across all games are not fully validated.
- Forced termination can interrupt Steam registry restoration. Back up your bottle before experimenting.
- Uninstall.command disconnects the adapter and restores tool metadata; private runtime/link files remain for recovery.

## Source and build

`App.swift`: English native UI and CrossOver discovery. `repair.py`: compatibility checks and installer. `adapter/`: launch routing, native bridge preparation and tool metadata integration.

Run `bash build.command` with Xcode Command Line Tools installed. Run adapter checks with `cd adapter && python3 -m unittest test_bridge`.

No Valve game files, Steam binaries, CrossOver binaries, personal configuration or logs are included. Runtime components are taken locally from existing installations. Not affiliated with Valve, CodeWeavers or NotProton. Thanks to the NotProton project for the native Steam integration this add-on builds on.
