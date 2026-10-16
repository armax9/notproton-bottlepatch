#!/opt/homebrew/bin/python3
"""User-invoked installer. Never launches games, stops Steam, or edits CrossOver."""
import argparse, datetime, fcntl, importlib.util, json, os, pathlib, shutil, subprocess, sys, traceback
sys.dont_write_bytecode=True
HOME=pathlib.Path.home()
DATA=HOME/'Library/Application Support/NotProton BottlePatch'
# Standalone release: no developer installation paths.
OLD=DATA
FILES=('bridge.py','native_bridge.py','refresh-tools.py','launch-shell','Install.command','Uninstall.command','Start-Steam.command')

def run(args,log):
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    log.write(result.stdout);log.flush()
    if result.returncode: raise RuntimeError('Command failed: '+str(args[0])+' (exit '+str(result.returncode)+')')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--crossover',required=True);parser.add_argument('--check',action='store_true')
    args=parser.parse_args();DATA.mkdir(parents=True,exist_ok=True)
    logfile=DATA/'patch.log'
    with logfile.open('w') as log:
        locks=[]
        try:
            log.write('NotProton BottlePatch '+datetime.datetime.now().isoformat()+'\n')
            cx=pathlib.Path(args.crossover).resolve()
            log.write('Selected CrossOver: '+str(cx)+'\n')
            if not (cx/'Contents/SharedSupport/CrossOver/bin/wine').is_file():
                raise RuntimeError('This is not a CrossOver installation. Select CrossOver or CrossOver Preview.')
            if not pathlib.Path('/opt/homebrew/bin/python3').is_file(): raise RuntimeError('Python 3 was not found at /opt/homebrew/bin/python3.')
            steam=pathlib.Path('/Applications/Steam.app/Contents/MacOS/notproton.dylib')
            if not steam.is_file(): raise RuntimeError('Install NotProton in native Steam first.')
            strings=subprocess.check_output(['/usr/bin/strings',str(steam)],text=True,errors='replace')
            if 'STEAM_GAME_LAUNCH_SHELL' not in strings:
                raise RuntimeError('This NotProton version no longer exposes the expected integration hook. No patch was applied.')
            cfgpath=DATA/'config.json'
            sourcecfg=cfgpath if cfgpath.exists() else OLD/'config.json'
            cfg=json.loads(sourcecfg.read_text()) if sourcecfg.exists() else {'bottles':str(HOME/'Library/Application Support/CrossOver/Bottles'),'bottle':'Steam'}
            cfg['crossover']=str(cx)
            bottle=pathlib.Path(cfg['bottles'])/cfg['bottle']
            if not (bottle/'cxbottle.conf').is_file(): raise RuntimeError('The existing bottle was not found: '+str(bottle))
            for folder in dict.fromkeys((OLD,DATA)):
                if not folder.exists(): continue
                lock=(folder/'session.lock').open('a')
                try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:
                    lock.close();raise RuntimeError('A game is running or still shutting down. Close it, then click Patch again.')
                locks.append(lock)
            bundled=pathlib.Path(__file__).parent/'adapter'
            spec=importlib.util.spec_from_file_location('native_bridge_check',bundled/'native_bridge.py')
            mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
            live=cx/'Contents/SharedSupport/CrossOver'
            support=HOME/'Library/Application Support/notproton'
            candidates=[]
            for runner in (support/'runners').glob('crossover-*/CrossOver'):
                clean=runner/'lib/wine/x86_64-windows/ntdll.dll.notproton-orig'
                unix=runner/'lib/wine/x86_64-unix/ntdll.so'
                if clean.is_file() and unix.is_file() and mod.digest(clean)==mod.digest(live/'lib/wine/x86_64-windows/ntdll.dll') and mod.digest(unix)==mod.digest(live/'lib/wine/x86_64-unix/ntdll.so'):
                    candidates.append(runner)
            if not candidates:
                raise RuntimeError('No compatible native Steam bridge was found for this CrossOver. Set up this CrossOver version in NotProton, then click Patch again.')
            runner=sorted(candidates)[-1];log.write('Matched native bridge: '+str(runner)+'\n')
            for arch in (live/'lib/wine').iterdir():
                if not arch.is_dir(): continue
                if (arch/'ntdll.dll').exists():
                    if not (runner/'lib/wine'/arch.name/'ntdll.dll').is_file(): raise RuntimeError('The native bridge is missing ntdll for: '+arch.name)
                    clean=runner/'lib/wine'/arch.name/'ntdll.dll.notproton-orig'
                    if not clean.is_file() or mod.digest(clean)!=mod.digest(arch/'ntdll.dll'):
                        raise RuntimeError('Wine versions do not match for '+arch.name+'; set up a matching runner in NotProton.')
            for rel in ('steam.exe','steamclient64.dll','steamclient.dll','tier0_s64.dll','vstdlib_s64.dll','lsteamclient.dll','i386-windows/lsteamclient.dll','x86_64-unix/lsteamclient.so'):
                if not (support/'bridge'/rel).is_file(): raise RuntimeError('The NotProton bridge installation is incomplete: '+rel)
            mod.redirect_shim((support/'bridge/steam.exe').read_bytes())
            alias=bottle/'drive_c/notproton-native';alias_old=None
            if alias.is_symlink():
                alias_old=os.readlink(alias)
                if pathlib.Path(alias_old) not in (OLD/'native-payload',DATA/'native-payload'):
                    raise RuntimeError('The bridge folder belongs to another installation: '+str(alias))
            elif alias.exists(): raise RuntimeError('The bridge folder is already in use: '+str(alias))
            trigger=bottle/'drive_c/windows/syswow64/lsteamclient.dll'
            if (trigger.exists() or trigger.is_symlink()) and (not trigger.is_symlink() or os.readlink(trigger)!=str(support/'bridge/i386-windows/lsteamclient.dll')):
                raise RuntimeError('An existing 32-bit bridge component belongs to another installation. See the log.')
            if args.check:
                log.write('Preflight SUCCESS. No installation performed.\n')
                print(json.dumps({'success':True,'message':'Compatibility checks passed.','log':str(logfile)},ensure_ascii=False));return 0
            previous=DATA/'previous-install'
            if previous.exists(): shutil.rmtree(previous)
            previous.mkdir()
            old_runtime=DATA/'native-runtime'
            had_runtime=old_runtime.exists()
            old_cfg=cfgpath.read_bytes() if cfgpath.exists() else None
            alias_changed=False
            if (DATA/'native-payload').exists():
                shutil.copytree(DATA/'native-payload',previous/'native-payload',symlinks=True)
            agent_dir=HOME/'Library/LaunchAgents'
            labels=['local.armax.notproton-crossover-bottle','local.armax.notproton-crossover-ui']
            agents={label:(agent_dir/(label+'.plist')).read_bytes() if (agent_dir/(label+'.plist')).exists() else None for label in labels}
            saved_environment=subprocess.run(['/bin/launchctl','getenv','STEAM_GAME_LAUNCH_SHELL'],capture_output=True,text=True).stdout.strip()
            try:
                for name in FILES:
                    target=DATA/name
                    if target.exists(): shutil.copy2(target,previous/name)
                    shutil.copy2(bundled/name,target)
                if not (DATA/'tool-metadata-backup.json').exists() and (OLD/'tool-metadata-backup.json').exists():
                    shutil.copy2(OLD/'tool-metadata-backup.json',DATA/'tool-metadata-backup.json')
                cfgpath.write_text(json.dumps(cfg,indent=2))
                if had_runtime: old_runtime.rename(previous/'native-runtime')
                if alias.is_symlink() and os.readlink(alias)!=str(DATA/'native-payload'):
                    alias.unlink();alias_changed=True
                mod.ROOT=DATA
                mod.prepare(cfg)
                run(['/bin/bash',str(DATA/'Install.command')],log)
            except Exception:
                log.write('Restoring previous runtime/configuration after failed installation.\n')
                if had_runtime and (previous/'native-runtime').exists():
                    if old_runtime.exists(): shutil.rmtree(old_runtime)
                    (previous/'native-runtime').rename(old_runtime)
                for name in FILES:
                    if (previous/name).exists(): shutil.copy2(previous/name,DATA/name)
                if old_cfg is not None: cfgpath.write_bytes(old_cfg)
                else: cfgpath.unlink(missing_ok=True)
                if (previous/'native-payload').exists():
                    shutil.rmtree(DATA/'native-payload')
                    shutil.copytree(previous/'native-payload',DATA/'native-payload',symlinks=True)
                for label,data in agents.items():
                    target=agent_dir/(label+'.plist')
                    subprocess.run(['/bin/launchctl','bootout','gui/'+str(os.getuid())+'/'+label],stdout=log,stderr=subprocess.STDOUT)
                    if data is not None:
                        target.write_bytes(data)
                        subprocess.run(['/bin/launchctl','bootstrap','gui/'+str(os.getuid()),str(target)],stdout=log,stderr=subprocess.STDOUT)
                    else: target.unlink(missing_ok=True)
                if saved_environment:
                    subprocess.run(['/bin/launchctl','setenv','STEAM_GAME_LAUNCH_SHELL',saved_environment],stdout=log,stderr=subprocess.STDOUT)
                else:
                    subprocess.run(['/bin/launchctl','unsetenv','STEAM_GAME_LAUNCH_SHELL'],stdout=log,stderr=subprocess.STDOUT)
                if alias_changed and alias_old:
                    if alias.is_symlink(): alias.unlink()
                    alias.symlink_to(alias_old)
                raise
            if (previous/'native-runtime').exists(): shutil.rmtree(previous/'native-runtime')
            log.write('SUCCESS: existing bottle + native Steam bridge + UI connection installed.\n')
            print(json.dumps({'success':True,'message':'Patch installed. Quit Steam completely, then reopen it.','log':str(logfile)},ensure_ascii=False));return 0
        except Exception as error:
            log.write(traceback.format_exc());log.flush()
            print(json.dumps({'success':False,'message':str(error),'log':str(logfile)},ensure_ascii=False));return 1
        finally:
            for lock in locks: lock.close()

if __name__=='__main__':sys.exit(main())
