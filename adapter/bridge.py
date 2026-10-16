#!/opt/homebrew/bin/python3
"""NotProton's external launch-shell adapter. No upstream or bottle DLL changes."""
import fcntl, json, os, pathlib, re, shlex, subprocess, sys, time
ROOT = pathlib.Path(__file__).resolve().parent
CONFIG = ROOT / 'config.json'
PREFIXES = ('CX_GRAPHICS', 'D3DM_', 'DXMT_', 'DXVK_', 'MTL_', 'ROSETTA_')
# Matches the directory quoting produced by Steam and recognized by hook_launch.c.
ROUTE = re.compile(r"'(?P<dir>[^'\n]*/compatibilitytools\.d/notproton[A-Za-z0-9_.-]*)(?:/\.)?'/run(?=\s)")
WHOLE = re.compile(r"'(?P<dir>[^'\n]*/compatibilitytools\.d/notproton[A-Za-z0-9_.-]*)/run'(?=\s)")

def rewrite(command):
    matches = list(ROUTE.finditer(command)) + list(WHOLE.finditer(command))
    if len(matches) != 1:
        raise ValueError('Unsupported NotProton launch format; refusing the original prefix launcher.')
    match = matches[0]
    replacement = shlex.join([sys.executable, str(ROOT / 'bridge.py'), '--run'])
    return command[:match.start()] + replacement + command[match.end():]

def plan(argv, env, cfg):
    if not argv:
        raise ValueError('Missing compatibility verb')
    verb, *args = argv
    if verb == 'getcompatpath':
        return None
    if verb not in ('run', 'waitforexitandrun', 'runinprefix') or not args:
        raise ValueError('Unsupported compatibility request: ' + verb)
    bottle = pathlib.Path(cfg['bottles']).expanduser() / cfg['bottle']
    wine = pathlib.Path(cfg['crossover']).expanduser() / 'Contents/SharedSupport/CrossOver/bin/wine'
    if not (bottle / 'cxbottle.conf').is_file() or not wine.is_file():
        raise ValueError('Configured CrossOver or existing bottle is missing; nothing was created.')
    overrides = {k: v for k, v in env.items() if k.startswith(PREFIXES) or k == 'WINEMSYNC'}
    # Missing UI switches mean Off, not the bottle's previous game's choice.
    for key in ('D3DM_ENABLE_METALFX', 'MTL_HUD_ENABLED', 'DXMT_ENABLE_NVEXT', 'DXMT_METALFX_SPATIAL_SWAPCHAIN'):
        overrides.setdefault(key, '0')
    if overrides.get('CX_GRAPHICS_BACKEND') not in (None, '', 'd3dmetal', 'dxvk', 'dxmt', 'wined3d'):
        raise ValueError('Unknown graphics backend')
    overrides = {k: v for k, v in overrides.items() if v != ''}
    # CrossOver reads bottle settings first, then applies --env. Keep its own DLL paths.
    child = dict(env)
    for key in list(child):
        if key.startswith('DYLD_') or key == 'STEAM_GAME_LAUNCH_SHELL' or key in ('WINEPREFIX', 'WINEDLLPATH', 'WINELOADER', 'WINESERVER', 'WINEDLLOVERRIDES', 'CX_ROOT', 'CX_INITIALIZED', 'LD_PRELOAD', 'SteamAppPath', 'SteamClientDll', 'SteamClientDll64'):
            child.pop(key, None)
    child['CX_BOTTLE_PATH'] = str(bottle.parent)
    command = [str(wine), '--bottle', cfg['bottle'], '--no-update', '--wait', '--env', shlex.join([k+'='+v for k, v in sorted(overrides.items())])]
    workdir = env.get('STEAM_COMPAT_INSTALL_PATH')
    if workdir and pathlib.Path(workdir).is_dir():
        command += ['--workdir', workdir]
    return command + args, child

def acquire_bottle_lock(lock, timeout=60):
    deadline=time.monotonic()+timeout
    while True:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic()>=deadline:
                raise ValueError('Bottle is still busy after waiting 60 seconds; close the previous game and retry.')
            time.sleep(0.1)

def request_directory():
    app=os.environ.get('STEAM_COMPAT_APP_ID') or os.environ.get('SteamAppId') or 'unknown'
    if not app.isdigit(): app='unknown'
    path=ROOT/'runs'/app
    path.mkdir(parents=True,exist_ok=True)
    return path

def main():
    if len(sys.argv) == 2 and sys.argv[1] != '--run':
        os.execv('/bin/sh', ['sh', '-c', rewrite(sys.argv[1])])
    if len(sys.argv) < 3 or sys.argv[1] != '--run':
        raise ValueError('Expected the NotProton launch-shell command')
    cfg = json.loads(CONFIG.read_text())
    if sys.argv[2] == 'getcompatpath':
        # Do not let native Steam AutoCloud write into the shared Windows profile.
        raise ValueError('Native Steam AutoCloud prefix mapping is unavailable in shared-bottle mode; use Windows Steam cloud.')
    command, env = plan(sys.argv[2:], os.environ, cfg)
    # Serialize our launches without terminating the user's Windows Steam or bottle.
    with (ROOT / 'session.lock').open('a') as lock:
        run_dir=request_directory()
        (run_dir/'status.json').write_text(json.dumps({'state':'waiting-for-bottle','target':sys.argv[3]}))
        acquire_bottle_lock(lock)
        status = {'verb': sys.argv[2], 'backend': os.environ.get('CX_GRAPHICS_BACKEND', 'bottle default'),
                  'bottle': cfg['bottle'], 'prefix': str(pathlib.Path(cfg['bottles']) / cfg['bottle']), 'target': sys.argv[3], 'state': 'preparing'}
        (ROOT / 'last-error.txt').unlink(missing_ok=True)
        (run_dir/'error.txt').unlink(missing_ok=True)
        (ROOT / 'last-run.json').write_text(json.dumps(status, indent=2))
        from native_bridge import prepare
        native, shim = prepare(cfg)
        args = sys.argv[3:]
        launch_base = command[:-len(args)]
        values = dict(x.split('=', 1) for x in shlex.split(launch_base[launch_base.index('--env') + 1]))
        values.update(native)
        values['WINEDEBUG'] = os.environ.get('NOTPROTON_BRIDGE_DEBUG', 'err+all,fixme-all')
        app_id = os.environ.get('STEAM_COMPAT_APP_ID') or os.environ.get('SteamAppId')
        if sys.argv[2] == 'waitforexitandrun' and app_id:
            values['SteamAppId'] = app_id
            values['SteamGameId'] = os.environ.get('SteamGameId', app_id)
        else:
            env.pop('SteamAppId', None)
            env.pop('SteamGameId', None)
        launch_base[launch_base.index('--env') + 1] = shlex.join([k+'='+v for k,v in values.items()])
        target = args if sys.argv[2] == 'runinprefix' else [str(shim)] + args
        # CrossOver supplies the bottle environment, but its winewrapper would
        # keep a non-system Wine process alive and deadlock Proton's system shim.
        launch_base += ['--ux-app', native['WINELOADER']]
        stock = command[:command.index('--env')]
        keys = [r'HKCU\Software\Valve\Steam', r'HKLM\Software\Valve\Steam', r'HKLM\Software\Wow6432Node\Valve\Steam']
        (run_dir/'status.json').write_text(json.dumps(status,indent=2))
        last_log=ROOT/'last-game.log'
        last_log.unlink(missing_ok=True)
        last_log.symlink_to(run_dir/'game.log')
        with (run_dir / 'game.log').open('w') as log:
            backups=[]
            for index,key in enumerate(keys):
                path=ROOT / ('steam-registry-before-%d.reg' % index)
                export=subprocess.run(stock + ['reg.exe','export',key,str(path),'/y'],env=env,stdout=log,stderr=subprocess.STDOUT)
                if export.returncode!=0:
                    raise ValueError('Cannot back up Steam registry; native bridge not started')
                backups.append((key,path))
            try:
                status['state']='running'
                (run_dir/'status.json').write_text(json.dumps(status,indent=2))
                (ROOT / 'last-run.json').write_text(json.dumps(status,indent=2))
                result=subprocess.call(launch_base+target,env=env,stdout=log,stderr=subprocess.STDOUT,cwd=os.environ.get('STEAM_COMPAT_INSTALL_PATH') or None)
            finally:
                for key,path in backups:
                    # Import alone merges values and leaves newly created paths behind.
                    subprocess.run(stock+['reg.exe','delete',key,'/f'],env=env,stdout=log,stderr=subprocess.STDOUT)
                    restore=subprocess.run(stock+['reg.exe','import',str(path)],env=env,stdout=log,stderr=subprocess.STDOUT)
                    if restore.returncode!=0:
                        raise ValueError('Steam registry restore failed; backup: '+str(path))
        status.update(state='exited', exitCode=result)
        (run_dir/'status.json').write_text(json.dumps(status,indent=2))
        (ROOT / 'last-run.json').write_text(json.dumps(status, indent=2))
        sys.exit(result)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        (ROOT / 'last-error.txt').write_text(str(error) + '\n')
        directory=request_directory()
        (directory/'error.txt').write_text(str(error)+'\n')
        (directory/'status.json').write_text(json.dumps({'state':'adapter-error','error':str(error),'arguments':sys.argv[2:]}))
        print('CrossOver bottle adapter: ' + str(error), file=sys.stderr)
        sys.exit(78)
