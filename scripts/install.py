"""Register one desktop plugin; independently verify live first-setup readiness."""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'server'))
from control import enqueue, write_json
from localization import tomllib
import runtime_paths


class SetupError(Exception):
    def __init__(self, stage, message, next_action):
        self.stage, self.message, self.next_action = stage, message, next_action
        super().__init__(message)


def fail(stage, message, next_action):
    raise SetupError(stage, message, next_action)


def desktop_cli():
    if os.environ.get('CODEX_CLI'):
        path = Path(os.environ['CODEX_CLI']).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return path.resolve()
        fail('desktop', 'CODEX_CLI is not executable.', 'Select the CLI bundled with the running desktop app.')
    candidates = []
    if sys.platform == 'darwin':
        pid = os.getppid()
        for _ in range(6):
            try:
                p = subprocess.run(['/bin/ps','-p',str(pid),'-o','ppid=','-o','comm='],capture_output=True,text=True,timeout=2)
                parent, command = p.stdout.strip().split(None, 1)
                if '.app/Contents/' in command:
                    app = Path(command.split('.app/Contents/',1)[0]+'.app')
                    for candidate in (app/'Contents/Resources/codex-cli/bin/codex',app/'Contents/Resources/codex'):
                        if candidate.is_file() and os.access(candidate, os.X_OK):
                            return candidate.resolve()
                pid = int(parent)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                break
        candidates = [Path('/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex'),
                      Path('/Applications/Codex.app/Contents/Resources/codex')]
    found = list(dict.fromkeys(p.resolve() for p in candidates if p.is_file() and os.access(p, os.X_OK)))
    if len(found) == 1:
        return found[0]
    fail('desktop', 'The desktop CLI is missing or ambiguous.', 'Set CODEX_CLI to the running desktop bundled CLI; retain its CODEX_HOME profile.')


def cli_json(cli, *args):
    try:
        p = subprocess.run([str(cli),*args,'--json'],capture_output=True,text=True,timeout=45)
    except (OSError, subprocess.TimeoutExpired) as error:
        fail('registration', str(error), 'Check the selected desktop CLI and retry.')
    if p.returncode:
        fail('registration', p.stderr.strip() or 'Codex rejected installation.', 'Resolve this CLI error; registration has not been confirmed.')
    try:
        value = json.loads(p.stdout)
        if isinstance(value, dict):
            return value
    except ValueError:
        pass
    fail('registration', 'Codex returned an invalid result.', 'Use a compatible desktop; an exit code alone is not installation proof.')


def installed_entry(cli, plugin_id, version):
    market = plugin_id.split('@',1)[1]
    result = cli_json(cli,'plugin','list','--marketplace',market)
    entries = result.get('installed')
    if not isinstance(entries,list) or not all(isinstance(x,dict) for x in entries):
        fail('registration','Codex returned an invalid installed-plugin inventory.','Use a compatible desktop and retry; installation is not confirmed.')
    entry = next((x for x in entries if x.get('pluginId') == plugin_id), None)
    if not entry or not entry.get('installed') or not entry.get('enabled') or entry.get('version') != version:
        fail('registration', 'This profile does not list the expected enabled plugin/version.', 'Check the current desktop plugin page, source/profile and enabled state.')
    return entry


def live_check(data, version, timeout):
    # A nonce round trip to the live primary, never an old status.json readback.
    ticket = enqueue(data,'check')
    receipt = data/'command-results'/(ticket+'.json')
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        if receipt.is_file():
            value = json.loads(receipt.read_text())
            receipt.unlink()
            if value.get('pluginVersion') != version:
                fail('activation', 'An older Signal payload is still running.', 'Call Signal control_monitor reload, then repeat --verify.')
            return value
        time.sleep(.1)
    fail('activation', 'Registration succeeded, but the host-owned MCP service has not answered.', 'Invoke the installed Signal get_status tool, then repeat --verify. If this turn has not discovered the tool, continue in the next Codex turn; no restart or detached process.')


def preflight():
    spec = json.loads((ROOT/'platform.json').read_text())
    if sys.platform == 'darwin':
        import platform
        if spec.get('os') != 'macOS' or spec.get('architecture') != platform.machine():
            fail('package','Wrong Mac package.','Use the matching platform release or repository build.')
        if int(platform.mac_ver()[0].split('.')[0]) < 14:
            fail('package','macOS 14+ is required.','Use a supported Mac.')
        helper = ROOT/'bin/codex-menu-bar'
        if not helper.is_file():
            fail('package','Prebuilt menu helper is missing.','Use a complete platform package.')
        if not os.access(helper, os.X_OK):
            helper.chmod(helper.stat().st_mode | 0o100)  # ZIP extractors can drop modes.
        p = subprocess.run(['/usr/bin/codesign','--verify','--strict',str(helper)],capture_output=True,text=True)
        if p.returncode:
            fail('package','Native signature verification failed.','Download the reviewed package again; retain OS trust/quarantine checks.')
    else:
        fail('package','Unsupported platform.','Use macOS.')


def install(cli, plugin_id, version):
    # Serialize source/catalogue/cache mutations for this profile. The monitor
    # lock is deliberately separate: installation must not stop live clients.
    directory = runtime_paths.codex_home()/'plugins'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory/'codex-signal-install.lock').open('a+') as lock:
        os.fchmod(lock.fileno(), 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        return install_locked(cli, plugin_id, version)


def install_locked(cli, plugin_id, version):
    name, market = plugin_id.split('@',1)
    config_path = runtime_paths.desktop_config()
    config = tomllib.loads(config_path.read_text()) if config_path.exists() else {}
    for key, value in config.get('plugins',{}).items():
        if key.startswith(name+'@') and key != plugin_id and value.get('enabled') is True:
            fail('identity','Another Signal edition is enabled.','Update that edition or approve plugin-only migration; retain local records.')
    # An existing exact-version registration already has a host-managed source
    # (including Git upgrade tracking). First setup must not replace that source.
    inventory = (cli_json(cli,'plugin','list','--marketplace',market)
                 if market in config.get('marketplaces',{}) else {'installed':[]})
    if not isinstance(inventory.get('installed'),list):
        fail('registration','Codex returned an invalid installed-plugin inventory.','Use a compatible desktop and retry.')
    existing = next((x for x in inventory['installed'] if isinstance(x,dict)
                     and x.get('pluginId') == plugin_id and x.get('version') == version
                     and x.get('installed') and x.get('enabled')),None)
    if existing:
        source = existing.get('source',{})
        path = source.get('path')
        if (existing.get('marketplaceSource',{}).get('sourceType') == 'git'
                and path and (Path(path)/'.agents/plugins/marketplace.json').is_file()):
            return str(Path(path)/'.agents/plugins/marketplace.json')
    registered = config.get('marketplaces',{}).get(market,{})
    managed = runtime_paths.codex_home()/'plugins/sources'/market
    source = Path(registered.get('source','')).expanduser().resolve()
    if registered.get('source_type') == 'git':
        fail('source','The Git-managed edition has a different installed version.',
             'Upgrade the original Git marketplace and rerun setup from its matching checkout.')
    if registered and source not in (ROOT.resolve(),managed.resolve()):
        fail('source','This marketplace is registered to another local source.',
             'Update from that existing source, or explicitly migrate this plugin source while preserving records.')
    if registered and source == ROOT.resolve():
        # Existing generated/local-source callers retain their original contract.
        source_root = ROOT
    else:
        # Stable marketplace catalogue, immutable versioned payloads. Removing a
        # download cannot break registration; upgrades retain the same root.
        import importlib.util
        spec = importlib.util.spec_from_file_location('signal_package',ROOT/'scripts/package.py')
        package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        durable = managed/name/version
        try:
            files = package.inventory('macos')
        except ValueError as error:
            fail('package',str(error),'Use a clean complete Signal package; keep private diagnostics outside the package.')
        if durable.exists():
            if not all((durable/p.relative_to(ROOT)).is_file()
                       and (durable/p.relative_to(ROOT)).read_bytes() == p.read_bytes() for p in files):
                fail('package','A different payload already uses this version.','Use a new version; installed source directories are immutable.')
        else:
            durable.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.signal-source-',dir=durable.parent) as staging:
                staged = Path(staging)/'package'
                for path in files:
                    target = staged/path.relative_to(ROOT)
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(path,target)
                staged.rename(durable)
        catalogue = json.loads((ROOT/'.agents/plugins/marketplace.json').read_text())
        catalogue['plugins'][0]['source']['path'] = './'+name+'/'+version
        target = managed/'.agents/plugins/marketplace.json'
        target.parent.mkdir(parents=True,exist_ok=True)
        write_json(target,catalogue)
        source_root = managed
    added = cli_json(cli,'plugin','marketplace','add',str(source_root))
    if added.get('marketplaceName') != market or not added.get('installedRoot'):
        fail('registration','Marketplace registration was not confirmed.','Inspect the CLI result before continuing.')
    cache = runtime_paths.codex_home()/'plugins/cache'/market/name
    with tempfile.TemporaryDirectory(prefix='signal-payloads-') as tmp:
        backups = Path(tmp)
        if cache.exists():
            for path in cache.iterdir():
                if path.is_dir() and not path.is_symlink() and re.fullmatch(r'\d+\.\d+\.\d+',path.name):
                    shutil.copytree(path,backups/path.name)
        try:
            result = cli_json(cli,'plugin','add',plugin_id)
        finally:
            # An older live host client may still refer to a prior immutable payload.
            for path in backups.iterdir():
                if not (cache/path.name).exists():
                    shutil.copytree(path,cache/path.name)
    if (result.get('pluginId') != plugin_id or result.get('version') != version
            or not Path(result.get('installedPath','/nonexistent')).is_dir()):
        fail('registration','The installed payload/version was not confirmed.','Resolve the marketplace or host-version mismatch.')
    installed_entry(cli,plugin_id,version)
    return str(Path(added['installedRoot'])/'.agents/plugins/marketplace.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true',help='Require the live host-owned service and UI; do not install.')
    parser.add_argument('--no-open',action='store_true',help='Skip opening the plugin page (isolated automation).')
    parser.add_argument('--timeout',type=float,default=15)
    args = parser.parse_args()
    try:
        preflight()
        manifest = json.loads((ROOT/'plugin.json').read_text())
        market = json.loads((ROOT/'.agents/plugins/marketplace.json').read_text())['name']
        plugin_id, version = manifest['name']+'@'+market, manifest['version']
        cli = desktop_cli()
        if args.verify:
            installed_entry(cli,plugin_id,version)
            value = live_check(runtime_paths.data_directory(),version,args.timeout)
            if not value.get('menuBarReady'):
                fail('interface','The backend answered but the menu renderer is not ready.','Resolve the UI/extension error, then repeat verification.')
            if value.get('enabled') is False:
                fail('paused','Saved preference has updates paused.','Resume updates from Signal if desired; then repeat verification.')
            if not value.get('connected') or value.get('health',{}).get('status') != 'ready':
                fail('connection','Signal is not synchronized with this desktop.','Check connection/protocol health and repeat verification.')
            value = {'stage':'ready','pluginId':plugin_id,'version':version,'installed':True,
                     'enabled':True,'connected':True,'menuBarReady':True,'python':sys.executable}
        else:
            path = install(cli,plugin_id,version)
            opened = False
            if not args.no_open and sys.platform == 'darwin':
                url = 'codex://plugins/'+manifest['name']+'?'+urlencode({'marketplacePath':path})
                opened = subprocess.run(['/usr/bin/open',url],capture_output=True).returncode == 0
            value = {'stage':'installed-needs-activation','pluginId':plugin_id,'version':version,
                     'installed':True,'enabled':True,'menuBarReady':False,'pluginPageRequested':opened,
                     'python':sys.executable,'nextAction':'Invoke the installed Signal get_status tool, then run this installer with --verify. No setup skill is installed.'}
        print(json.dumps(value,ensure_ascii=False,indent=2))
        return 0
    except SetupError as error:
        print(json.dumps({'stage':error.stage,'ready':False,'message':error.message,'nextAction':error.next_action},ensure_ascii=False,indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
