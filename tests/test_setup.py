"""Python bootstrap and strict first-setup criteria; all user data is temporary."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('signal_setup',ROOT/'scripts/install.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
from test_read_sync import ReadSyncFixture


class PythonBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='signal setup ')
        self.root = Path(self.tmp.name)
        self.env = {**os.environ,'HOME':str(self.root),'CODEX_HOME':str(self.root/'codex'),
            'CODEX_MENU_STATUS_DATA':str(self.root/'private data'),'PATH':'/usr/bin:/bin',
            'CODEX_SIGNAL_PYTHON':sys.executable,'PYTHONDONTWRITEBYTECODE':'1'}

    def tearDown(self):self.tmp.cleanup()

    def run_script(self,name,*args):
        return subprocess.run(['/bin/sh',str(ROOT/'scripts'/name),*args],env=self.env,
            capture_output=True,text=True,timeout=12)

    def test_minimal_path_pins_real_interpreter_in_private_file(self):
        p = self.run_script('python.sh')
        self.assertEqual(p.returncode,0,p.stderr)
        pin = self.root/'private data/python-path'
        self.assertEqual(pin.read_text().strip(),os.path.realpath(sys.executable))
        self.assertEqual(pin.stat().st_mode & 0o777,0o600)
        del self.env['CODEX_SIGNAL_PYTHON']
        q = self.run_script('python.sh')
        self.assertEqual(p.stdout,q.stdout)

    def test_explicit_incompatible_runtime_fails_without_a_success_message(self):
        self.env['CODEX_SIGNAL_PYTHON']='/usr/bin/python3'
        p = self.run_script('install.sh','--no-open')
        self.assertEqual(p.returncode,78)
        self.assertIn('SIGNAL_PYTHON_INVALID',p.stderr)
        self.assertEqual(p.stdout,'')
        self.assertFalse((self.root/'private data/python-path').exists())

    def test_broken_pin_repairs_using_an_existing_runtime_not_the_system_stub(self):
        self.run_script('python.sh')
        pin = self.root/'private data/python-path'
        pin.write_text('/missing/python3\n')
        del self.env['CODEX_SIGNAL_PYTHON']
        p = self.run_script('python.sh')
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertNotEqual(pin.read_text().strip(),'/usr/bin/python3')

    def test_launcher_performs_mcp_handshake_from_minimal_path_and_ends_with_parent(self):
        self.run_script('python.sh')
        del self.env['CODEX_SIGNAL_PYTHON']
        # Disabled temporary profile avoids IPC/UI and never reads real records.
        data = self.root/'private data'
        (data/'settings.json').write_text('{"enabled":false}')
        request = json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{}})+'\n'
        p = subprocess.run(['/bin/sh',str(ROOT/'scripts/launch.sh'),'--no-ui'],env=self.env,
            input=request,capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)
        response = json.loads(p.stdout.splitlines()[0])
        self.assertEqual(response['id'],1)
        self.assertEqual(response['result']['serverInfo']['version'],json.loads((ROOT/'plugin.json').read_text())['version'])

    def test_install_guidance_is_opt_in_and_does_not_install_when_runtime_exists(self):
        p = self.run_script('install-python.sh','--install')
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('no installation was needed',p.stdout)
        p = self.run_script('install-python.sh','--plan')
        if sys.platform == 'darwin':
            self.assertEqual(p.returncode,0)
            self.assertIn('https://www.python.org/',p.stdout)


class SetupVerificationTests(ReadSyncFixture):
    def test_fresh_live_nonce_proves_primary_and_does_not_modify_user_records(self):
        from main import VERSION
        self.p.ui_ready = True
        before = copy.deepcopy(self.p.registry.saved())
        def answer():
            import time
            for _ in range(40):
                if list((Path(self.tmp.name)/'commands').glob('*.json')):
                    self.p.consume_commands()
                    return
                time.sleep(.025)
        worker = threading.Thread(target=answer)
        worker.start()
        value = setup.live_check(Path(self.tmp.name),VERSION,2)
        worker.join(timeout=2)
        self.assertTrue(value['connected'])
        self.assertTrue(value['menuBarReady'])
        self.assertEqual(before,self.p.registry.saved())

    def test_stale_ready_file_is_not_success_when_no_live_server_answers(self):
        from main import VERSION
        (Path(self.tmp.name)/'status.json').write_text(json.dumps({'pluginVersion':VERSION,'connected':True,'menuBarReady':True}))
        with self.assertRaises(setup.SetupError) as result:
            setup.live_check(Path(self.tmp.name),VERSION,.05)
        self.assertEqual(result.exception.stage,'activation')

    def test_empty_exit_zero_cli_result_is_not_installation_success(self):
        config=Path(self.tmp.name)/'setup-config.toml'
        config.write_text('[marketplaces.codex-signal]\nsource_type=\"local\"\n')
        with patch.object(setup.runtime_paths,'desktop_config',return_value=config),patch.object(setup,'cli_json',return_value={}):
            with self.assertRaises(setup.SetupError) as result:
                setup.install(Path('/fake/codex'),'codex-menu-status@codex-signal','0.2.8')
        self.assertEqual(result.exception.stage,'registration')

    def test_missing_disabled_wrong_version_and_malformed_inventory_are_rejected(self):
        for entry in (None,{}, {'installed':True,'enabled':False}, {'installed':True,'enabled':True,'version':'old'}):
            inventory = [] if entry is None else [{'pluginId':'signal@market',**entry}]
            with self.subTest(entry=entry),patch.object(setup,'cli_json',return_value={'installed':inventory}):
                with self.assertRaises(setup.SetupError):setup.installed_entry(Path('/fake'),'signal@market','1.0.0')
        with patch.object(setup,'cli_json',return_value={'installed':None}):
            with self.assertRaises(setup.SetupError):setup.installed_entry(Path('/fake'),'signal@market','1.0.0')

    def test_cli_bad_json_and_nonzero_exit_are_reported_as_registration_failures(self):
        for code,output in ((0,'not json'),(0,'[]'),(1,'{}')):
            with patch.object(setup.subprocess,'run',return_value=subprocess.CompletedProcess([],code,output,'error')):
                with self.assertRaises(setup.SetupError):setup.cli_json(Path('/fake'),'plugin','list')

    def test_existing_git_registration_keeps_the_hosts_managed_source(self):
        root=Path(self.tmp.name)/'git-source'
        catalogue=root/'.agents/plugins/marketplace.json'
        catalogue.parent.mkdir(parents=True)
        catalogue.write_text('{}')
        entry={'pluginId':'codex-menu-status@codex-signal','version':'0.2.8',
               'installed':True,'enabled':True,'source':{'path':str(root)},
               'marketplaceSource':{'sourceType':'git'}}
        config=Path(self.tmp.name)/'setup-config.toml'
        config.write_text('[marketplaces.codex-signal]\nsource_type=\"git\"\n')
        with patch.object(setup.runtime_paths,'desktop_config',return_value=config),patch.object(setup,'cli_json',return_value={'installed':[entry]}) as cli:
            result=setup.install(Path('/fake'),'codex-menu-status@codex-signal','0.2.8')
        self.assertEqual(result,str(catalogue))
        cli.assert_called_once_with(Path('/fake'),'plugin','list','--marketplace','codex-signal')
