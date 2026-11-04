import argparse,importlib,json,os,socket,stat,sys,tempfile,unittest,types
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import runtime_paths as paths
from linux_renderer import Bridge,validated_event,MAX_FRAME
from main import Plugin

class PlatformPathsTests(unittest.TestCase):
    def test_mac_original_data_location_and_override(self):
        with patch('runtime_paths.sys.platform','darwin'),patch.dict(os.environ,{},clear=True):
            self.assertEqual(paths.data_directory(),Path.home()/'Library/Application Support/CodexMenuStatus')
            self.assertEqual(paths.settings_path(paths.data_directory()).name,'settings.json')
        with patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':'/tmp/signal-fixture'},clear=True):
            self.assertEqual(paths.data_directory(),Path('/tmp/signal-fixture'))
    def test_linux_xdg_paths_and_legacy_override(self):
        with patch('runtime_paths.sys.platform','linux'),patch.dict(os.environ,{'XDG_STATE_HOME':'/tmp/state','XDG_CONFIG_HOME':'/tmp/config','XDG_RUNTIME_DIR':'/tmp/runtime','CODEX_HOME':'/tmp/codex'},clear=True):
            self.assertEqual(paths.data_directory(),Path('/tmp/state/codex-signal'))
            self.assertEqual(paths.settings_path(paths.data_directory()),Path('/tmp/config/codex-signal/settings.json'))
            self.assertEqual(paths.ui_socket(),Path('/tmp/runtime/codex-signal/ui.sock'))
            self.assertEqual(paths.desktop_socket(),Path('/tmp/codex/ipc/ipc.sock'))
            with patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':'/tmp/legacy'}):
                self.assertEqual(paths.settings_path(paths.data_directory()),Path('/tmp/legacy/settings.json'))
    def test_python310_toml_fallback_import_and_parse(self):
        from vendor import tomli
        value='[desktop]\nlocaleOverride="zh-CN"\n'
        self.assertEqual(tomli.loads(value)['desktop']['localeOverride'],'zh-CN')
        with self.assertRaises(ValueError):tomli.loads('[desktop\n')
        with patch.dict(sys.modules,{'tomllib':None}):
            spec=importlib.util.spec_from_file_location('fallback_locale',Path(__file__).resolve().parents[1]/'server/localization.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            self.assertEqual(module.tomllib.loads(value),tomli.loads(value))

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='signal-',dir='/tmp');self.path=Path(self.tmp.name)/'ui.sock';self.events=[]
        self.bridge=Bridge(self.path,self.events.append,credentials=lambda _:os.getuid());self.bridge.start();self.clients=[]
    def tearDown(self):
        for c in self.clients:c.close()
        self.bridge.close();self.tmp.cleanup()
    def connect(self,hello=True):
        c=socket.socket(socket.AF_UNIX);c.settimeout(.3);c.connect(str(self.path));self.clients.append(c);self.bridge.poll(0)
        if hello:c.sendall(b'{"event":"hello","protocol":1}\n');self.bridge.poll(0);self.bridge.poll(0)
        return c
    def frame(self,c):return json.loads(c.recv(MAX_FRAME).splitlines()[0])
    def test_private_socket_handshake_and_event_allowlist(self):
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode),0o600)
        c=self.connect();self.assertEqual(self.events[-1]['event'],'ready')
        c.sendall(b'{"event":"project_enable","projectId":"p","command":"not allowed"}\n{"event":"approve"}\n')
        self.bridge.poll(0);self.assertEqual(self.events[-1],{'event':'project_enable','projectId':'p'})
        self.assertIsNone(validated_event({'event':'open','threadId':'a\nb'}))
        self.assertIsNone(validated_event({'event':'notification_enable','status':'invented'}))
    def test_state_coalesces_and_reconnect_never_replays_notices(self):
        for n in range(100):self.bridge.enqueue({'kind':'state','n':n})
        self.bridge.poll(0);c=self.connect();self.assertEqual(self.frame(c)['n'],99)
        self.bridge.enqueue({'kind':'status_notice','notice':{'id':'ephemeral'}});self.bridge.poll(0);self.bridge.poll(0)
        self.assertEqual(self.frame(c)['kind'],'status_notice');c.close();self.bridge.poll(0)
        d=self.connect();self.assertEqual(self.frame(d)['kind'],'state')
        with self.assertRaises(socket.timeout):d.recv(1)
    def test_partial_handshake_wrong_protocol_and_frame_limit(self):
        c=self.connect(False);c.sendall(b'{"event":"he');self.bridge.poll(0);self.assertFalse(self.bridge.hello)
        c.sendall(b'llo","protocol":9}\n');self.bridge.poll(0);self.assertIsNone(self.bridge.client)
        c=self.connect(False);self.bridge.buffer=bytearray(b'x'*MAX_FRAME);c.sendall(b'x');self.bridge.poll(0)
        self.assertIsNone(self.bridge.client)
    def test_eof_cannot_be_lost_when_queue_full(self):
        for _ in range(64):self.bridge.enqueue({'kind':'status_notice'})
        self.bridge.enqueue(None);self.bridge.poll(0);self.assertFalse(self.bridge.running)
    def test_different_uid_rejected(self):
        self.bridge.credentials=lambda _:os.getuid()+1;c=self.connect(False)
        self.assertIsNone(self.bridge.client);self.assertEqual(c.recv(1),b'')
    def test_live_duplicate_refused_and_cleanup_only_owns_socket(self):
        duplicate=Bridge(self.path,lambda _:None,credentials=lambda _:os.getuid())
        try:
            with self.assertRaises(OSError):duplicate.start()
        finally:duplicate.close()
        self.assertTrue(self.path.exists());self.bridge.close();self.assertFalse(self.path.exists())
    def test_refuses_symlink_or_public_directory(self):
        self.bridge.close();self.path.symlink_to('unrelated');other=Bridge(self.path,lambda _:None)
        try:
            with self.assertRaises(PermissionError):other.start()
        finally:other.close()
        self.assertTrue(self.path.is_symlink());self.path.unlink();os.chmod(self.path.parent,0o755);other=Bridge(self.path,lambda _:None)
        try:
            with self.assertRaises(PermissionError):other.start()
        finally:other.close()

class LinuxUITests(unittest.TestCase):
    def test_offline_invalidates_transient_notices_not_records(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=Plugin(argparse.Namespace(no_ui=True,seconds=0))
            try:
                before=p.registry.saved();p.ui_ready=True;p.pending_notice={'id':'n'};p.notice_target=('n','a');p.consume_ui({'event':'offline'})
                self.assertFalse(p.ui_ready);self.assertIsNone(p.pending_notice);self.assertIsNone(p.notice_target);self.assertEqual(before,p.registry.saved())
            finally:p.lock.close()
    def test_linux_missing_opener_and_failed_launch(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=Plugin(argparse.Namespace(no_ui=True,seconds=0))
            try:
                with patch('main.sys.platform','linux'),patch('main.shutil.which',return_value=None):self.assertFalse(p.open_chat_url('codex://threads/example'))
                with patch('main.sys.platform','linux'),patch('main.shutil.which',side_effect=lambda n:'/usr/bin/'+n),patch('main.subprocess.run',return_value=types.SimpleNamespace(returncode=0,stdout='codex.desktop')),patch('main.subprocess.Popen',side_effect=OSError) as opened:
                    self.assertFalse(p.open_chat_url('codex://threads/example'));opened.assert_called_once()
            finally:p.lock.close()

    def test_linux_requires_scheme_handler_and_uses_argv_for_original_link(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=Plugin(argparse.Namespace(no_ui=True,seconds=0))
            try:
                with patch('main.sys.platform','linux'),patch('main.shutil.which',side_effect=lambda n:'/usr/bin/'+n),patch('main.subprocess.run',return_value=types.SimpleNamespace(returncode=0,stdout='')) as query,patch('main.subprocess.Popen') as opened:
                    self.assertFalse(p.open_chat_url('codex://threads/example'));opened.assert_not_called()
                    query.assert_called_once()
                with patch('main.sys.platform','linux'),patch('main.shutil.which',side_effect=lambda n:'/usr/bin/'+n),patch('main.subprocess.run',return_value=types.SimpleNamespace(returncode=0,stdout='codex.desktop')),patch('main.subprocess.Popen') as opened:
                    url='codex://threads/example?hostId=remote+host'
                    self.assertTrue(p.open_chat_url(url));self.assertEqual(opened.call_args.args[0],['/usr/bin/xdg-open',url])
                    self.assertNotIn('shell',opened.call_args.kwargs)
            finally:p.lock.close()
