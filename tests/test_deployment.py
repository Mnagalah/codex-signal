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
            cli.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CLI_LOG"\nprintf "{}\\n"\n'); cli.chmod(0o755)
            env = dict(os.environ, HOME=str(home), CODEX_HOME=str(codex), CODEX_CLI=str(cli), CLI_LOG=str(log))
            target = base / 'deployment'
            deployment.stage(target, 'codex-menu-status-local')
            if sys.platform.startswith('linux'):
                p = target / 'platform.json'; value = json.loads(p.read_text()); value['os'] = 'Linux'; p.write_text(json.dumps(value))
            result = subprocess.run([str(target / 'scripts/install.sh')], env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('plugin add codex-menu-status@codex-menu-status-local --json', log.read_text())
            market = target / '.agents/plugins/marketplace.json'; value = json.loads(market.read_text()); value['name'] = 'codex-signal'; market.write_text(json.dumps(value))
            log_before = log.read_text()
            result = subprocess.run([str(target / 'scripts/install.sh')], env=env, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('development edition is enabled', result.stderr)
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
