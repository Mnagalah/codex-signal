import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
from localization import DesktopLanguage, COPY, text, ui_language
from main import Plugin
from state import ThreadState, WatchRegistry
from test_state import snapshot


class LocalizationTests(unittest.TestCase):
    def test_explicit_simplified_only_and_no_system_language_fallback(self):
        for value in ('zh-CN', 'zh-Hans'):
            self.assertEqual(ui_language(value), 'zh-CN')
        for value in (None, '', 'auto', 'zh-TW', 'zh-HK', 'ja-JP', 'en-US', 'unknown'):
            self.assertEqual(ui_language(value), 'en')

    def test_real_setting_path_live_atomic_replace_and_invalid_read_retains_last_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.toml'
            path.write_text('[desktop]\nlocaleOverride="zh-CN"\n')
            source = DesktopLanguage(path)
            self.assertEqual(source.language, 'zh-CN')
            other = path.with_suffix('.new')
            other.write_text('[desktop]\nlocaleOverride="ja-JP"\n')
            other.replace(path)
            self.assertTrue(source.poll())
            self.assertEqual(source.language, 'en')
            path.write_text('[desktop\n')
            self.assertFalse(source.poll())
            self.assertEqual(source.setting, 'ja-JP')
            self.assertIsNotNone(source.error)
            path.write_text('[desktop]\nlocaleOverride="zh-CN"\n')
            source.poll()
            self.assertEqual(source.language, 'zh-CN')
            before = path.read_bytes()
            source.poll()
            self.assertEqual(path.read_bytes(), before)
            path.unlink(); source.poll()
            self.assertEqual(source.language, 'en')

    def test_registry_projects_ordinals_without_rewriting_historical_ids_or_slots(self):
        states = {}
        for key in ('a', 'b'):
            state = ThreadState(key); state.consume(snapshot(), 'owner'); states[key] = state
        project = {'id':'p','name':'未分组','markerType':'icon','marker':'folder'}
        identities = {key:project for key in states}
        registry = WatchRegistry(); registry.update(states, identities, True)
        registry.entries['a']['index'] = 4; registry.entries['b']['index'] = 5
        registry.next_number['p'] = 6; registry.acknowledged['history'] = 'turn-7'
        before = registry.saved()
        result = registry.update(states, identities, True, language='en')
        self.assertEqual(result[0]['name'], '未分组')
        self.assertEqual([c['index'] for c in result[0]['threads']], [1,2])
        self.assertEqual(result[0]['threads'][0]['title'], '测试聊天')
        self.assertEqual(result[0]['threads'][0]['detail'], 'Running')
        self.assertEqual(registry.saved(), before)
        states['a'].consume(snapshot('idle', False, 'completed'), 'owner')
        result = registry.update(states, identities, True, language='en')
        self.assertEqual([(c['id'], c['index']) for c in result[0]['threads']], [('b',1)])
        self.assertEqual(registry.entries['b']['index'], 5)
        c = ThreadState('c'); c.consume(snapshot(),'owner'); states['c']=c;identities['c']=project
        result = registry.update(states, identities, True, language='en')
        self.assertEqual([(c['id'], c['index']) for c in result[0]['threads']], [('b',1),('c',2)])
        self.assertEqual(registry.acknowledged['history'], 'turn-7')

    def test_system_bucket_is_localized_by_identity_on_local_and_remote(self):
        local = ThreadState('a'); remote = ThreadState('a', host_id='remote:host')
        for state in (local, remote):
            data=snapshot();data['conversationState']['workspaceKind']='standalone';state.consume(data,'owner')
        registry = WatchRegistry();states={s.key:s for s in (local, remote)}
        groups=registry.update(states,{},True,language='en')
        self.assertEqual([g['name'] for g in groups],['Chat','Chat'])
        self.assertEqual([g['threads'][0]['index'] for g in groups],[1,1])
        self.assertNotEqual(groups[0]['id'],groups[1]['id'])
        self.assertEqual([g['name'] for g in registry.update(states,{},True,language='zh-CN')],['聊天','聊天'])

    def test_template_values_are_not_reinterpreted_and_compiled_copy_matches_html(self):
        value=text('openBadge','en',project='项目 {n}',n='2',title='标题 {status}',status='Running')
        self.assertIn('项目 {n}',value);self.assertIn('标题 {status}',value)
        spec=importlib.util.spec_from_file_location('generator',ROOT/'scripts/generate-layout.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.read_copy(), COPY)
        self.assertEqual(module.COPY_TARGET.read_text(),module.generated_copy(COPY))

    def test_locale_change_is_published_without_changing_registry_or_monitor_settings(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'CODEX_MENU_STATUS_DATA':tmp}):
            p=Plugin(argparse.Namespace(no_ui=True,seconds=0))
            try:
                path=Path(tmp)/'codex.toml';path.write_text('[desktop]\nlocaleOverride="zh-CN"')
                p.language=DesktopLanguage(path);p.enabled=False;p.publish()
                self.assertEqual(p.last_status['uiLanguage'],'zh-CN')
                self.assertEqual(p.last_status['detail'],'正在连接 Codex')
                saved=p.registry.saved()
                path.write_text('[desktop]\nlocaleOverride="en-US"');p.language.poll();p.publish()
                self.assertEqual(p.last_status['uiLanguage'],'en')
                self.assertEqual(p.last_status['languageSetting']['value'],'en-US')
                self.assertEqual(p.last_status['detail'],'Connecting to Codex')
                self.assertEqual(p.registry.saved(),saved)
                self.assertFalse((Path(tmp)/'settings.json').exists())
            finally:p.lock.close()
