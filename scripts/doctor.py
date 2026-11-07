#!/usr/bin/env python3
"""Read-only macOS prerequisite report; no chat data or private paths."""
import argparse,json,os,platform,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
from runtime_paths import desktop_socket,desktop_state
def report():
    spec=json.loads((ROOT/'platform.json').read_text());helper=ROOT/'bin/codex-menu-bar'
    checks={'macOS':sys.platform=='darwin','python310':sys.version_info>=(3,10),
        'architecture':platform.machine()==spec['architecture'],'renderer':helper.is_file() and os.access(helper,os.X_OK),
        'desktopMetadataPresent':desktop_state().is_file(),'desktopIPCPresent':desktop_socket().exists()}
    if sys.platform=='darwin':
        checks['macOS14']=int(platform.mac_ver()[0].split('.')[0])>=14
        checks['localSignature']=subprocess.run(['/usr/bin/codesign','--verify','--strict',str(helper)],capture_output=True).returncode==0
    return {'environment':{'os':platform.system(),'architecture':platform.machine(),'python':platform.python_version(),'packageVersion':json.loads((ROOT/'plugin.json').read_text())['version']},'checks':checks,'ready':all(checks.values())}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--json',action='store_true');a=p.parse_args();r=report()
    print(json.dumps(r,indent=2) if a.json else '\n'.join(('OK   ' if v else 'CHECK')+' '+k for k,v in r['checks'].items()))
    raise SystemExit(0 if r['ready'] else 1)
