#!/usr/bin/env python3
"""Build platform ZIPs from an explicit public allowlist. Never publish or install."""
from pathlib import Path
import argparse,json,re,stat,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
FIXED=['plugin.json','mcp.json','platform.json','codex-status-layout.html','project-icons.json','README.md','README.zh-CN.md','CHANGELOG.md','CONTRIBUTING.md','SECURITY.md','LICENSE','THIRD-PARTY-NOTICES.md','.gitignore','.agents/plugins/marketplace.json','.github/workflows/validate.yml','native/Package.swift']
PATTERNS=['server/*.py','server/*.json','server/vendor/**/*.py','server/vendor/**/LICENSE','server/vendor/**/UPSTREAM.json','server/vendor/**/py.typed','tests/*.py','tests/*.cjs','native/Sources/MenuBar/*.swift','native/Tests/MenuBarTests/*.swift','scripts/*.py','scripts/*.sh','docs/*.md','linux/gnome/**/*.js','linux/gnome/**/*.json','linux/gnome/**/*.css','linux/gnome/**/*.svg','linux/gnome/**/*.xml','linux/gnome/**/LICENSE']
FORBIDDEN={'slots.json','settings.json','status.json','auth.json','.env','monitor.lock'}
PRIVATE=[re.compile(rb'/' + rb'Users/'),re.compile(rb'01[0-9a-f]{6}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',re.I)]
def inventory(target):
    selected={ROOT/p for p in FIXED}
    for pattern in PATTERNS:selected.update(ROOT.glob(pattern))
    if target=='macos':selected.add(ROOT/'bin/codex-menu-bar')
    files=sorted(selected,key=lambda p:str(p.relative_to(ROOT)))
    for p in files:
        if not p.is_file() or p.is_symlink():raise ValueError('Missing file or symlink: '+str(p.relative_to(ROOT)))
        if any(part in ('.git','.build','__pycache__','work','evidence') for part in p.relative_to(ROOT).parts) or p.name in FORBIDDEN:raise ValueError('Private/runtime file selected')
        if any(pattern.search(p.read_bytes()) for pattern in PRIVATE):raise ValueError('Private path or live-style ID detected in '+str(p.relative_to(ROOT)))
    return files

def archive(path,items):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data,executable in items:
            info=zipfile.ZipInfo(name);info.create_system=3;info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(stat.S_IFREG|(0o755 if executable else 0o644))<<16;z.writestr(info,data)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target',choices=['macos','ubuntu22.04-beta'],default='macos');args=parser.parse_args()
    version=json.loads((ROOT/'plugin.json').read_text())['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+',version) or ('VERSION = "'+version+'"') not in (ROOT/'server/main.py').read_text():raise ValueError('Backend/manifest numeric versions disagree')
    mcp=json.loads((ROOT/'mcp.json').read_text())
    if mcp['mcpServers']['menu_status'].get('env',{}).get('CODEX_MENU_STATUS_CAPTURE')=='1':raise ValueError('Public diagnostic capture must be off')
    marketplace=json.loads((ROOT/'.agents/plugins/marketplace.json').read_text())
    if marketplace['name']!='codex-signal' or marketplace['plugins'][0]['source']['path']!='./':raise ValueError('Unexpected marketplace root')
    mac=args.target=='macos';spec=json.loads((ROOT/'platform.json').read_text())
    if mac:
        arch=spec['architecture']
        if arch not in ('arm64','x86_64'):raise ValueError('Unsupported build architecture')
        subprocess.run(['lipo','-verify_arch',arch,str(ROOT/'bin/codex-menu-bar')],check=True)
        subprocess.run(['codesign','--verify','--strict',str(ROOT/'bin/codex-menu-bar')],check=True)
    else:
        arch='noarch';spec={'os':'Linux','architecture':'any','distribution':'ubuntu22.04-gnome42-beta','pythonMinimum':'3.10','runtimeBundled':False,'gnomeShell':['42'],'desktopIPC':'stream-v11-read-v3','realDeviceTested':False}
    files=inventory('macos' if mac else 'linux');out=ROOT/'dist';out.mkdir(exist_ok=True)
    target=out/f'codex-signal-v{version}-{args.target}-{arch}.zip'
    archive(target,[(str(p.relative_to(ROOT)),json.dumps(spec,indent=2).encode()+b'\n' if p.name=='platform.json' and p.parent==ROOT else p.read_bytes(),p.suffix=='.sh' or p.name=='codex-menu-bar') for p in files])
    companion=None
    if not mac:
        companion=out/f'codex-signal-v{version}-gnome42-companion-beta.zip';base=ROOT/'linux/gnome/codex-signal@local'
        assets=[p for p in files if p.is_relative_to(base)];assets.append(ROOT/'LICENSE')
        archive(companion,[(str(p.relative_to(base)) if p!=ROOT/'LICENSE' else 'LICENSE',p.read_bytes(),False) for p in assets])
    report={'name':target.name,'version':version,'platform':args.target,'architecture':arch,'bytes':target.stat().st_size,'files':[str(p.relative_to(ROOT)) for p in files],
            'privacyScan':'passed','signature':'ad-hoc' if mac else 'not applicable','notarized':False,'published':False,'pythonMinimum':'3.10','runtimeBundled':False,'license':'MIT','companion':companion.name if companion else None}
    (out/(target.stem+'-inventory.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2))
if __name__=='__main__':main()
