"""Isolated native Steam bridge using matching, installed NotProton components."""
import hashlib, json, os, pathlib, shutil
ROOT=pathlib.Path(__file__).resolve().parent
SUPPORT=pathlib.Path.home()/'Library/Application Support/notproton'

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def link(src,dst):
    if dst.is_symlink() and os.readlink(dst)==str(src): return
    if dst.exists() or dst.is_symlink():
        raise ValueError('Refusing to replace existing runtime entry: '+str(dst))
    dst.symlink_to(src, target_is_directory=src.is_dir())

def redirect_shim(data):
    # Preserve PE layout. Redirect complete NUL-terminated literals, including
    # wide strings, so suffixes such as config/libraryfolders.vdf remain intact.
    hits=0
    for encoding,zero in [('utf-16-le',b'\0\0'),('ascii',b'\0')]:
        old='C:\\Program Files (x86)\\Steam'.encode(encoding)
        new='C:\\notproton-native'.encode(encoding)
        pos=0
        while True:
            pos=data.find(old,pos)
            if pos<0: break
            end=pos+len(old)
            step=2 if encoding=='utf-16-le' else 1
            while data[end:end+step]!=zero:
                end+=step
                if end>=len(data): raise ValueError('Unterminated shim path')
            old_string=data[pos:end]
            replacement=new+old_string[len(old):]
            data=data[:pos]+replacement+bytes(len(old_string)-len(replacement))+data[end:]
            pos=end+step
            hits+=1
    if hits<4: raise ValueError('Unknown Steam shim layout; bridge not prepared')
    return data,hits

def prepare(cfg):
    live=pathlib.Path(cfg['crossover'])/'Contents/SharedSupport/CrossOver'
    bridge=SUPPORT/'bridge'
    candidates=[]
    for candidate in (SUPPORT/'runners').glob('crossover-*/CrossOver'):
        clean=candidate/'lib/wine/x86_64-windows/ntdll.dll.notproton-orig'
        unix=candidate/'lib/wine/x86_64-unix/ntdll.so'
        if clean.is_file() and unix.is_file() and digest(clean)==digest(live/'lib/wine/x86_64-windows/ntdll.dll') and digest(unix)==digest(live/'lib/wine/x86_64-unix/ntdll.so'):
            candidates.append(candidate)
    if not candidates: raise ValueError('No installed native Steam bridge matches this CrossOver build')
    runner=sorted(candidates)[-1]
    runtime=ROOT/'native-runtime/CrossOver'
    runtime.mkdir(parents=True,exist_ok=True)
    for p in live.iterdir():
        if p.name!='lib': link(p,runtime/p.name)
    (runtime/'lib/wine').mkdir(parents=True,exist_ok=True)
    for p in (live/'lib').iterdir():
        if p.name!='wine': link(p,runtime/'lib'/p.name)
    for arch in (live/'lib/wine').iterdir():
        if not arch.is_dir() or arch.is_symlink():
            link(arch,runtime/'lib/wine'/arch.name)
            continue
        dest=runtime/'lib/wine'/arch.name
        dest.mkdir(exist_ok=True)
        for item in arch.iterdir():
            if item.name=='ntdll.so':
                # Wine derives its builtin directory from this Mach-O's location.
                # A symlink resolves back to stock Wine and bypasses patched ntdll.
                target=dest/item.name
                if target.is_symlink(): target.unlink()
                if not target.exists() or digest(target)!=digest(item): shutil.copy2(item,target)
            elif item.name=='ntdll.dll':
                patched=runner/'lib/wine'/arch.name/item.name
                if not patched.is_file(): raise ValueError('Missing patched ntdll for '+arch.name)
                link(patched,dest/item.name)
            elif item.name=='wine' and arch.name.endswith('-unix'):
                # A copy is necessary: dyld must use this overlay's directory.
                source=runner/'lib/wine'/arch.name/'wine'
                if not source.is_file(): source=item
                if not (dest/item.name).exists(): shutil.copy2(source,dest/item.name)
            else: link(item,dest/item.name)
        name='lsteamclient.so' if arch.name.endswith('-unix') else 'lsteamclient.dll'
        payload=bridge/arch.name/name
        if payload.is_file(): link(payload,dest/name)
    payload=ROOT/'native-payload'
    payload.mkdir(exist_ok=True)
    for name in ('steamclient64.dll','steamclient.dll','tier0_s64.dll','vstdlib_s64.dll','lsteamclient.dll'):
        link(bridge/name,payload/name)
    link(bridge/'x86_64-unix/lsteamclient.so',payload/'lsteamclient.so')
    # The 32-bit loader needs a physical trigger in its redirected system folder,
    # just as upstream install_lsteamclient_trigger does for WoW64.
    bottle=pathlib.Path(cfg['bottles'])/cfg['bottle']
    trigger=bottle/'drive_c/windows/syswow64/lsteamclient.dll'
    link(bridge/'i386-windows/lsteamclient.dll',trigger)
    # Keep dependency resolution inside the sidecar, without replacing Steam files.
    for name in ('tier0_s.dll','vstdlib_s.dll'):
        source=bottle/'drive_c/Program Files (x86)/Steam'/name
        if source.is_file(): link(source,payload/name)
    patched,hits=redirect_shim((bridge/'steam.exe').read_bytes())
    shim=payload/'steam.exe'
    if not shim.exists() or shim.read_bytes()!=patched: shim.write_bytes(patched)
    # A separate, unmistakable directory; never replace the real Steam directory.
    alias=pathlib.Path(cfg['bottles'])/cfg['bottle']/'drive_c/notproton-native'
    link(payload,alias)
    paths=[payload,runtime/'lib/wine/x86_64-windows',runtime/'lib/wine/i386-windows',runtime/'lib/wine/x86_64-unix']
    client=pathlib.Path.home()/'Library/Application Support/Steam/Steam.AppBundle/Steam/Contents/MacOS'
    if not (client/'steamclient.dylib').is_file(): raise ValueError('Native Steam client library missing')
    (ROOT/'native-bridge-state.json').write_text(json.dumps({'matchedRunner':str(runner),'redirectedShimPaths':hits,'liveCrossOver':str(live)},indent=2))
    return {'WINEPATH':r'C:\notproton-native',
            'WINELOADER':str(runtime/'lib/wine/x86_64-unix/wine'),
            'CX_WINELOADER':str(runtime/'lib/wine/x86_64-unix/wine'),
            'WINEDLLPATH':':'.join(map(str,paths)),
            'WINEDLLOVERRIDES':'steamclient=n;steamclient64=n;lsteamclient=b',
            'STEAM_COMPAT_CLIENT_INSTALL_PATH':str(client)},shim
