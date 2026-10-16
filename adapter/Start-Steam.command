#!/bin/bash
set -eu
base=$(cd -- "$(dirname -- "$0")" && pwd)
if /usr/bin/pgrep -x steam_osx >/dev/null; then
  echo 'Quit Steam through Steam > Quit, then run this launcher again. Its environment is set at startup.'
  exit 1
fi
python=/opt/homebrew/bin/python3
[ -x "$python" ] || { echo 'Python 3 is missing at /opt/homebrew/bin/python3'; exit 1; }
[ -f /Applications/Steam.app/Contents/MacOS/notproton.dylib ] || { echo 'NotProton is not installed in Steam.app'; exit 1; }
# Verify that the installed integration still offers the external-shell entry point.
/usr/bin/strings /Applications/Steam.app/Contents/MacOS/notproton.dylib | /usr/bin/grep -q STEAM_GAME_LAUNCH_SHELL || { echo 'This NotProton version needs a compatibility review.'; exit 1; }
"$python" "$base/refresh-tools.py"
exec /usr/bin/open /Applications/Steam.app --env "STEAM_GAME_LAUNCH_SHELL=$base/launch-shell"
