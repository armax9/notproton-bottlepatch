import importlib.util, json, os, pathlib, shlex, subprocess, sys, tempfile, unittest
SPEC = importlib.util.spec_from_file_location('bridge', pathlib.Path(__file__).with_name('bridge.py'))
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)

class AdapterTests(unittest.TestCase):
    def test_steam_directory_quoting_and_env(self):
        command = "CX_GRAPHICS_BACKEND=dxvk '/Users/test/Library/Application Support/Steam/compatibilitytools.d/notproton-fex-rosetta-41069'/run waitforexitandrun '/Games/A B/game.exe' -vr"
        rewritten = b.rewrite(command)
        self.assertTrue(rewritten.startswith('CX_GRAPHICS_BACKEND=dxvk '))
        self.assertIn('--run waitforexitandrun', rewritten)
        self.assertTrue(rewritten.endswith("'/Games/A B/game.exe' -vr"))
        self.assertNotIn('/compatibilitytools.d/', rewritten)

    def test_whole_path_quoting(self):
        self.assertIn('--run run ', b.rewrite("'/x/compatibilitytools.d/notproton-1/run' run x.exe"))

    def test_fail_closed(self):
        for command in ('/other/run run x', "'/x/compatibilitytools.d/notproton'/unknown run x"):
            with self.assertRaises(ValueError): b.rewrite(command)

    def test_real_subprocess_receives_exact_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            bottle = root/'bottles'/'Steam'
            bottle.mkdir(parents=True)
            (bottle/'cxbottle.conf').write_text('unchanged')
            wine = root/'CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine'
            wine.parent.mkdir(parents=True)
            wine.write_text('#!'+sys.executable+'\nimport sys,json,os\nprint(json.dumps([sys.argv[1:], dict(os.environ)]))\n')
            wine.chmod(0o755)
            cfg = dict(crossover=str(root/'CrossOver.app'), bottles=str(bottle.parent), bottle='Steam')
            for backend in ('dxvk','d3dmetal'):
                env = dict(os.environ, CX_GRAPHICS_BACKEND=backend, D3DM_MTL4='1', STEAM_COMPAT_INSTALL_PATH=tmp,
                           STEAM_COMPAT_DATA_PATH='/must/not/be/created', WINEPREFIX='/wrong', WINEDLLPATH='/wrong',
                           DYLD_INSERT_LIBRARIES='/native/steam.dylib')
                command, child = b.plan(['waitforexitandrun', '/Games/A B/game.exe', '-arg', 'a; b'], env, cfg)
                args, actual = json.loads(subprocess.check_output(command, env=child, text=True))
                self.assertEqual(args[-3:], ['/Games/A B/game.exe','-arg','a; b'])
                values = dict(x.split('=',1) for x in shlex.split(args[args.index('--env')+1]))
                self.assertEqual(values['CX_GRAPHICS_BACKEND'], backend)
                self.assertEqual(values['D3DM_MTL4'],'1')
                self.assertEqual(actual['CX_BOTTLE_PATH'], str(bottle.parent))
                self.assertNotIn('WINEDLLPATH', actual)
                self.assertNotIn('DYLD_INSERT_LIBRARIES',actual)
                self.assertEqual((bottle/'cxbottle.conf').read_text(),'unchanged')

    def test_complete_launch_shell(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            shutil.copy(b.__file__, root/'bridge.py')
            (root/'native_bridge.py').write_text("from pathlib import Path\ndef prepare(cfg): return {'WINELOADER':'/isolated/native/wine'}, Path('/isolated/native/steam.exe')\n")
            bottle = root/'bottles/Steam'
            bottle.mkdir(parents=True)
            (bottle/'cxbottle.conf').write_text('original')
            steam = bottle/'drive_c/Program Files (x86)/Steam/steam.exe'
            steam.parent.mkdir(parents=True)
            steam.write_text('original executable')
            wine = root/'CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine'
            wine.parent.mkdir(parents=True)
            wine.write_text('#!'+sys.executable+'\nimport sys,json\nprint(json.dumps(sys.argv[1:]))\n')
            wine.chmod(0o755)
            (root/'config.json').write_text(json.dumps(dict(crossover=str(root/'CrossOver.app'),bottles=str(bottle.parent),bottle='Steam')))
            command = "CX_GRAPHICS_BACKEND=dxvk '/x/compatibilitytools.d/notproton-rosetta'/run waitforexitandrun '/Game With Spaces/game.exe' -vr"
            lines = subprocess.check_output([sys.executable,str(root/'bridge.py'),command],text=True).splitlines()
            self.assertEqual(lines,[])
            calls=[json.loads(line) for line in (root/'last-game.log').read_text().splitlines()]
            launch=next(args for args in calls if '/isolated/native/steam.exe' in args)
            self.assertEqual(launch[-2:],['/Game With Spaces/game.exe','-vr'])
            self.assertEqual(sum('export' in args for args in calls),3)
            self.assertEqual(sum('import' in args for args in calls),3)
            self.assertEqual((root/'last-run.json').read_text().count('exited'),1)
            self.assertEqual(steam.read_text(),'original executable')

    def test_missing_bottle_cannot_create_prefix(self):
        with self.assertRaises(ValueError):
            b.plan(['run','x.exe'], {}, dict(crossover='/missing',bottles='/missing',bottle='Steam'))

if __name__ == '__main__': unittest.main()
