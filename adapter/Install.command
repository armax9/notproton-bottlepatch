#!/bin/bash
set -eu
base=$(cd -- "$(dirname -- "$0")" && pwd)
/opt/homebrew/bin/python3 - "$base" <<'PY'
import pathlib, plistlib, sys
base=pathlib.Path(sys.argv[1])
agent=pathlib.Path.home()/'Library/LaunchAgents/local.armax.notproton-crossover-bottle.plist'
agent.parent.mkdir(parents=True,exist_ok=True)
agent.write_bytes(plistlib.dumps(dict(Label='local.armax.notproton-crossover-bottle',RunAtLoad=True,ProgramArguments=['/bin/launchctl','setenv','STEAM_GAME_LAUNCH_SHELL',str(base/'launch-shell') ])))
uiagent=agent.with_name('local.armax.notproton-crossover-ui.plist')
uiagent.write_bytes(plistlib.dumps(dict(Label='local.armax.notproton-crossover-ui',RunAtLoad=True,WatchPaths=[str(pathlib.Path.home()/'Library/Application Support/notproton/tools')],ProgramArguments=['/opt/homebrew/bin/python3',str(base/'refresh-tools.py')])))
PY
/opt/homebrew/bin/python3 "$base/refresh-tools.py"
uid=$(/usr/bin/id -u)
agent="$HOME/Library/LaunchAgents/local.armax.notproton-crossover-bottle.plist"
/bin/launchctl bootout "gui/$uid/local.armax.notproton-crossover-bottle" 2>/dev/null || true
/bin/launchctl bootstrap "gui/$uid" "$agent"
/bin/launchctl bootout "gui/$uid/local.armax.notproton-crossover-ui" 2>/dev/null || true
/bin/launchctl bootstrap "gui/$uid" "$HOME/Library/LaunchAgents/local.armax.notproton-crossover-ui.plist"
/bin/launchctl setenv STEAM_GAME_LAUNCH_SHELL "$base/launch-shell"
echo 'Connected. Future Steam starts use your CrossOver bottle. Restart Steam if it is running.'
