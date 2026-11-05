"""Platform paths; the established Mac data location and test override stay intact."""
from __future__ import annotations
import os,pathlib,sys

def data_directory():
    if os.environ.get('CODEX_MENU_STATUS_DATA'):return pathlib.Path(os.environ['CODEX_MENU_STATUS_DATA'])
    if sys.platform.startswith('linux'):
        return pathlib.Path(os.environ.get('XDG_STATE_HOME',str(pathlib.Path.home()/'.local/state')))/'codex-signal'
    return pathlib.Path.home()/'Library/Application Support/CodexMenuStatus'

def settings_path(data):
    if sys.platform.startswith('linux') and not os.environ.get('CODEX_MENU_STATUS_DATA'):
        return pathlib.Path(os.environ.get('XDG_CONFIG_HOME',str(pathlib.Path.home()/'.config')))/'codex-signal/settings.json'
    return data/'settings.json'

def codex_home():return pathlib.Path(os.environ.get('CODEX_HOME',str(pathlib.Path.home()/'.codex')))
def desktop_state():return pathlib.Path(os.environ.get('CODEX_SIGNAL_DESKTOP_STATE',str(codex_home()/'.codex-global-state.json')))
def desktop_config():return pathlib.Path(os.environ.get('CODEX_SIGNAL_CONFIG',str(codex_home()/'config.toml')))
def desktop_state_db():return pathlib.Path(os.environ.get('CODEX_SIGNAL_STATE_DB',str(desktop_state().parent/'state_5.sqlite')))
def desktop_socket():return pathlib.Path(os.environ.get('CODEX_SIGNAL_IPC',str(codex_home()/'ipc/ipc.sock')))

def ui_socket():
    root=pathlib.Path(os.environ.get('XDG_RUNTIME_DIR','/run/user/'+str(os.getuid())))
    return root/'codex-signal/ui.sock'
