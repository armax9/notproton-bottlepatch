#!/bin/bash
set -eu
base=$(cd -- "$(dirname -- "$0")" && pwd)
uid=$(/usr/bin/id -u)
/bin/launchctl bootout "gui/$uid/local.armax.notproton-crossover-bottle" 2>/dev/null || true
/bin/launchctl bootout "gui/$uid/local.armax.notproton-crossover-ui" 2>/dev/null || true
/opt/homebrew/bin/python3 "$base/refresh-tools.py" --restore
rm -f "$HOME/Library/LaunchAgents/local.armax.notproton-crossover-ui.plist"
/bin/launchctl unsetenv STEAM_GAME_LAUNCH_SHELL
rm -f "$HOME/Library/LaunchAgents/local.armax.notproton-crossover-bottle.plist"
echo 'Disconnected. Restart Steam to return to stock NotProton. Bottle and NotProton were not changed.'
