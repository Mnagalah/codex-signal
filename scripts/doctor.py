#!/usr/bin/env python3
"""Read-only, redacted prerequisite report. Never print chats, IDs or credentials."""
import argparse,json,os,platform,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
from runtime_paths import desktop_config,desktop_socket,desktop_state

def run(args):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=5)
        return p.returncode,p.stdout.strip()
    except (OSError,subprocess.TimeoutExpired):return -1,''

def report():
    spec=json.loads((ROOT/'platform.json').read_text());linux=sys.platform.startswith('linux');mac=sys.platform=='darwin'
    checks={'python310':sys.version_info>=(3,10),'packageOS':spec['os']==('Linux' if linux else 'macOS' if mac else ''),
            'desktopConfigPresent':desktop_config().is_file(),'desktopMetadataPresent':desktop_state().is_file(),
            'desktopIPCPresent':desktop_socket().exists()}
    details={'os':platform.system(),'architecture':platform.machine(),'python':platform.python_version(),'packageVersion':json.loads((ROOT/'plugin.json').read_text())['version']}
    if mac:
        checks['architecture']=platform.machine()==spec['architecture'];checks['macOS14']=int(platform.mac_ver()[0].split('.')[0])>=14
        helper=ROOT/'bin/codex-menu-bar';checks['renderer']=helper.is_file() and os.access(helper,os.X_OK)
        checks['localSignature']=run(['codesign','--verify','--strict',str(helper)])[0]==0
    elif linux:
        details['sessionType']=os.environ.get('XDG_SESSION_TYPE','unknown');details['desktop']=os.environ.get('XDG_CURRENT_DESKTOP','unknown')
        code,version=run(['gnome-shell','--version']);checks['gnome42']=code==0 and ' 42.' in version
        details['gnomeShell']=version or 'not found';checks['extensionTools']=all(shutil.which(p) for p in ('gnome-extensions','glib-compile-schemas'))
        checks['xdgOpen']=bool(shutil.which('xdg-open'))
        _,handler=run(['xdg-mime','query','default','x-scheme-handler/codex']);checks['codexLinkHandler']=bool(handler)
        _,info=run(['gnome-extensions','info','codex-signal@local']);checks['extensionRegistered']='codex-signal@local' in info
    return {'environment':details,'checks':checks,'ready':all(checks.values()),'privacy':'No chat data, local paths, IDs or credentials included.'}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--json',action='store_true');args=parser.parse_args();r=report()
    print(json.dumps(r,ensure_ascii=False,indent=2) if args.json else '\n'.join([f"Codex Signal {r['environment']['packageVersion']}"]+[('OK   ' if v else 'CHECK')+' '+k for k,v in r['checks'].items()]))
    raise SystemExit(0 if r['ready'] else 1)
