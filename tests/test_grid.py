import argparse
import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
from control import enqueue
from main import Plugin

spec = importlib.util.spec_from_file_location('layout_generator', ROOT / 'scripts/generate-layout.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class GridTests(unittest.TestCase):
    def test_production_generated_grid_is_current_and_comes_from_html(self):
        contract = generator.read_contract()
        self.assertEqual(generator.TARGET.read_text(), generator.generated(contract))
        self.assertEqual(contract['source'], 'codex-status-layout.html#layout-contract')
        self.assertEqual(contract['grids']['header']['columns'], [16, 'minmax(0,1fr)', 28, 36])
        self.assertEqual(contract['grids']['row']['columns'], ['minmax(0,1fr)', 28])

    def test_generator_rejects_missing_contract_and_unknown_tracks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp); path = root / 'codex-status-layout.html'
            path.write_text('<html></html>')
            with self.assertRaises(ValueError): generator.read_contract(root)
            contract = generator.read_contract()
            contract['grids']['header']['columns'][0] = 'arbitrary-css'
            path.write_text('<script id="layout-contract" type="application/json">'+json.dumps(contract)+'</script>')
            with self.assertRaises(ValueError): generator.read_contract(root)

    def test_inspection_uses_only_own_renderer_and_keeps_registry_and_settings(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'CODEX_MENU_STATUS_DATA':tmp,'CODEX_MENU_STATUS_CAPTURE':'1'}):
            plugin = Plugin(argparse.Namespace(no_ui=True, seconds=0))
            try:
                plugin.ui_ready = True
                plugin.renderer = types.SimpleNamespace(stdin=io.StringIO(),poll=lambda:None)
                plugin.registry.acknowledged['same-local-id'] = 'turn-7'
                plugin.registry.next_number['project'] = 8
                before = plugin.registry.saved()
                ticket = enqueue(plugin.data, 'inspect')
                plugin.consume_commands()
                command = json.loads(plugin.renderer.stdin.getvalue())
                self.assertEqual(command, {'kind':'inspect_layout','requestId':ticket})
                self.assertTrue(json.loads((plugin.data/'command-results'/f'{ticket}.json').read_text())['accepted'])
                self.assertEqual(plugin.registry.saved(),before)
                self.assertFalse((plugin.data/'settings.json').exists())
                self.assertTrue(plugin.enabled)
            finally: plugin.lock.close()

    def test_toggle_exercise_only_routes_to_own_native_renderer(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'CODEX_MENU_STATUS_DATA':tmp,'CODEX_MENU_STATUS_CAPTURE':'1'}):
            plugin = Plugin(argparse.Namespace(no_ui=True, seconds=0))
            try:
                plugin.ui_ready = True
                plugin.renderer = types.SimpleNamespace(stdin=io.StringIO(), poll=lambda:None)
                plugin.registry.acknowledged['same-local-id'] = 'turn-7'
                plugin.registry.next_number['project'] = 8
                before = plugin.registry.saved()
                ticket = enqueue(plugin.data, 'exercise')
                plugin.consume_commands()
                self.assertEqual(json.loads(plugin.renderer.stdin.getvalue()), {'kind':'exercise_toggle','requestId':ticket})
                self.assertTrue(json.loads((plugin.data/'command-results'/f'{ticket}.json').read_text())['accepted'])
                self.assertEqual(plugin.registry.saved(), before)
                self.assertFalse((plugin.data/'settings.json').exists())
            finally: plugin.lock.close()

    def test_menu_exercise_routes_only_presentation_and_keeps_persisted_preferences(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'CODEX_MENU_STATUS_DATA':tmp,'CODEX_MENU_STATUS_CAPTURE':'1'}):
            plugin=Plugin(argparse.Namespace(no_ui=True,seconds=0))
            try:
                plugin.ui_ready=True;plugin.renderer=types.SimpleNamespace(stdin=io.StringIO(),poll=lambda:None)
                before=plugin.registry.saved()
                ticket=enqueue(plugin.data,'exercise-menu');plugin.consume_commands()
                self.assertEqual(json.loads(plugin.renderer.stdin.getvalue()),{'kind':'exercise_menu_layout','requestId':ticket})
                self.assertEqual(plugin.registry.saved(),before)
                self.assertFalse((plugin.data/'settings.json').exists())
            finally:plugin.lock.close()

    def test_inspection_pipe_failure_is_local_and_does_not_end_mcp(self):
        class Broken:
            def write(self,*args):raise BrokenPipeError()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'CODEX_MENU_STATUS_DATA':tmp,'CODEX_MENU_STATUS_CAPTURE':'1'}):
            plugin = Plugin(argparse.Namespace(no_ui=True, seconds=0))
            try:
                plugin.ui_ready=True;plugin.renderer=types.SimpleNamespace(stdin=Broken(),poll=lambda:None)
                ticket=enqueue(plugin.data,'inspect');plugin.consume_commands()
                self.assertFalse(json.loads((plugin.data/'command-results'/f'{ticket}.json').read_text())['accepted'])
                self.assertTrue(plugin.running)
                self.assertFalse(plugin.ui_ready)
            finally:plugin.lock.close()

    def test_runtime_reports_layout_from_the_actual_renderer_ready_event(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'CODEX_MENU_STATUS_DATA':tmp}):
            plugin=Plugin(argparse.Namespace(no_ui=True,seconds=0))
            try:
                plugin.consume_ui({'event':'ready','layoutSource':'codex-status-layout.html#layout-contract','layoutVersion':'1','layoutEngine':'shared-native-grid'})
                plugin.publish()
                self.assertEqual(plugin.last_status['uiLayout']['source'],'codex-status-layout.html#layout-contract')
                self.assertEqual(plugin.last_status['uiLayout']['engine'],'shared-native-grid')
            finally:plugin.lock.close()


if __name__=='__main__':unittest.main()
