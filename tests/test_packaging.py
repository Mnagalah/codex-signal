import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import call, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('signal_packaging', ROOT / 'scripts/package.py')
packaging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging)


class PackagingTests(unittest.TestCase):
    def test_macos_verification_places_input_before_architecture_list(self):
        binary = Path('/tmp/sample-menu-bar')
        with patch.object(packaging.subprocess, 'run') as run:
            packaging.verify_macos_binary(binary, 'arm64')
        self.assertEqual(run.call_args_list, [
            call(['lipo', str(binary), '-verify_arch', 'arm64'], check=True),
            call(['codesign', '--verify', '--strict', str(binary)], check=True),
        ])

    def test_unsupported_architecture_is_rejected_before_running_tools(self):
        with patch.object(packaging.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                packaging.verify_macos_binary(Path('/tmp/sample-menu-bar'), 'riscv64')
        run.assert_not_called()

    def test_inventory_is_mac_only_and_contains_the_native_helper(self):
        with self.assertRaises(ValueError):packaging.inventory('unsupported')
        self.assertIn(ROOT/'bin/codex-menu-bar',packaging.inventory('macos'))

    def test_one_time_installation_does_not_install_a_resident_skill(self):
        manifest=json.loads((ROOT/'plugin.json').read_text())
        self.assertNotIn('onboardingSkill',manifest['extensions']['com.openai'])
        self.assertFalse((ROOT/'skills').exists())
        self.assertFalse(any(p.relative_to(ROOT).parts[0]=='skills' for p in packaging.inventory('macos')))
