import importlib.util
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stage_deployment', ROOT / 'scripts/stage-deployment.py')
deployment = importlib.util.module_from_spec(spec); spec.loader.exec_module(deployment)


class DeploymentTests(unittest.TestCase):
    def test_generated_local_installer_keeps_its_identity_and_public_migration_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); home = base / 'home'; home.mkdir()
            codex = base / 'codex'; codex.mkdir()
            (codex / 'config.toml').write_text('[plugins."codex-menu-status@codex-menu-status-local"]\nenabled=true\n')
            cli = base / 'fake-codex'; log = base / 'calls.txt'
            target = base / 'deployment'
            cli.write_text('#!'+sys.executable+'\n'+'''import os,sys,json
from pathlib import Path
r=Path(os.environ['TEST_PACKAGE']);a=sys.argv[1:]
with open(os.environ['CLI_LOG'],'a') as f:f.write(' '.join(a)+'\\n')
m=json.loads((r/'.agents/plugins/marketplace.json').read_text())['name'];v=json.loads((r/'plugin.json').read_text())['version'];p='codex-menu-status@'+m
if a[:3]==['plugin','marketplace','add']:x={'marketplaceName':m,'installedRoot':str(r)}
elif a[:2]==['plugin','add']:x={'pluginId':p,'version':v,'installedPath':str(r)}
else:x={'installed':[{'pluginId':p,'version':v,'installed':True,'enabled':True}]}
print(json.dumps(x))
'''); cli.chmod(0o755)
            env = dict(os.environ, HOME=str(home), CODEX_HOME=str(codex), CODEX_CLI=str(cli), CLI_LOG=str(log), TEST_PACKAGE=str(target), CODEX_SIGNAL_PYTHON=sys.executable)
            deployment.stage(target, 'codex-menu-status-local')
            result = subprocess.run(['/bin/sh',str(target / 'scripts/install.sh'),'--no-open'], env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['stage'],'installed-needs-activation')
            self.assertIn('plugin add codex-menu-status@codex-menu-status-local --json', log.read_text())
            market = target / '.agents/plugins/marketplace.json'; value = json.loads(market.read_text()); value['name'] = 'codex-signal'; market.write_text(json.dumps(value))
            log_before = log.read_text()
            result = subprocess.run(['/bin/sh',str(target / 'scripts/install.sh'),'--no-open'], env=env, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)['stage'],'identity')
            self.assertEqual(log.read_text(), log_before)

    def test_local_identity_is_an_export_not_a_business_source_fork(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            sentinel = target / 'unrelated-note.txt'; sentinel.write_text('Keep this file')
            record = deployment.stage(target, 'sample-local-source')
            self.assertTrue(record['generated'])
            self.assertFalse(record['diagnosticCapture'])
            self.assertEqual(json.loads((target / '.agents/plugins/marketplace.json').read_text())['name'], 'sample-local-source')
            for path in ['server/main.py','server/state.py','server/control.py','server/localization.py','server/lifecycle.py']:
                self.assertEqual((target / path).read_bytes(), (ROOT / path).read_bytes())
            self.assertEqual(json.loads((target / 'plugin.json').read_text())['version'], record['version'])
            self.assertEqual(sentinel.read_text(), 'Keep this file')
            self.assertFalse((target / 'slots.json').exists())

    def test_staging_refuses_canonical_tree_and_unrelated_plugin(self):
        with self.assertRaises(ValueError): deployment.stage(ROOT, 'sample')
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'plugin.json'; p.write_text('{"name":"other-plugin"}')
            with self.assertRaises(ValueError): deployment.stage(tmp, 'sample')
            self.assertEqual(json.loads(p.read_text())['name'], 'other-plugin')
