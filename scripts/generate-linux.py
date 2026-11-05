#!/usr/bin/env python3
"""Generate the GNOME renderer's actual shared contract, copy and icon resources."""
import argparse,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
TARGET=ROOT/'linux/gnome/codex-signal@local'
parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
outputs={}
def output(path,content):outputs[path]=content
s=(ROOT/'codex-status-layout.html').read_text()
for identifier,name in [('layout-contract','contract.json'),('interface-copy','copy.json')]:
    value=json.loads(re.search('<script id="'+identifier+'" type="application/json">\\s*(.*?)</script>',s,re.S)[1])
    output(TARGET/name,json.dumps(value,ensure_ascii=False,indent=2)+'\n')
icons=json.loads((ROOT/'project-icons.json').read_text())
output(TARGET/'project-icons.json',json.dumps({k:'lucide-'+v['linux'] for k,v in icons.items()},indent=2,sort_keys=True)+'\n')
m=json.loads(outputs[TARGET/'contract.json'])
v=m['metrics'];g=m['grids'];px=lambda n:str(n)+'px'
def padding(grid):return ' '.join(px(n) for n in g[grid]['padding'])
css=f'''/* Generated from the HTML contract. Do not edit these metric overrides. */
.signal-group,.signal-lane {{ spacing:{v['group-gap']}px; }}
.signal-capsule,.signal-global {{ height:{v['pill-h']}px; border-radius:{v['pill-h']/2}px; }}
.signal-global {{ min-width:{g['globalButton']['columns'][0]+sum(g['globalButton']['padding'][1::2])}px; }}
.signal-menu-name {{ max-width:{v['name-max']}px; font-size:{v['menu-font']}px; }}
.signal-emoji {{ font-size:{g['globalButton']['columns'][0]}px; }}
.signal-badges {{ spacing:{v['badge-gap']}px; }}
.signal-badge {{ width:{v['badge-menu']}px; height:{v['badge-menu']}px; border-radius:{v['badge-menu']/2}px; }}
.signal-row-badge {{ width:{v['badge-row']}px; height:{v['badge-row']}px; border-radius:{v['badge-row']/2}px; }}
.signal-popup-content {{ padding:{v['panel-pad']}px; border-radius:{v['radius']}px; }}
.signal-header {{ min-height:{v['header-h']}px; padding:{padding('globalHeader')}; spacing:{g['globalHeader']['columnGap']}px; }}
.signal-header-title,.signal-project-title {{ font-size:{v['header-font']}px; }}
.signal-source {{ font-size:{v['source-font']}px; }}
.signal-scroll {{ min-width:0; }}
.signal-project-row {{ height:{v['project-control-h']}px; padding:{padding('projectControl')}; spacing:{g['projectControl']['columnGap']}px; }}
.signal-chat-row {{ height:{v['row-h']}px; padding:0; }}
.signal-row-open {{ padding:{padding('rowOpen')}; spacing:{g['rowOpen']['columnGap']}px; }}
.signal-grouped .signal-row-open {{ padding:{padding('groupRowOpen')}; }}
.signal-row-copy {{ spacing:{g['rowCopy']['rowGap']}px; }}
.signal-chat-title {{ font-size:{v['title-font']}px; }}
.signal-detail {{ font-size:{v['detail-font']}px; }}
.signal-control {{ min-width:{v['control']}px; height:{v['control']}px; }}
.signal-section {{ font-size:{v['section-font']}px; }}
.signal-setting-row {{ height:{v['alert-row-h']}px; padding:{padding('alertRow')}; spacing:{g['alertRow']['columnGap']}px; }}
.signal-switch-track {{ width:{v['switch-w']}px; height:{v['switch-h']}px; border-radius:{v['switch-h']/2}px; }}
.signal-switch-knob {{ width:{v['switch-h']-4}px; height:{v['switch-h']-4}px; border-radius:{(v['switch-h']-4)/2}px; }}
.signal-notice {{ border-radius:{m['notice']['radius']}px; }}
'''
output(TARGET/'stylesheet.css',(TARGET/'stylesheet.base.css').read_text()+'\n'+css)
if args.check:
    stale=[str(p.relative_to(ROOT)) for p,value in outputs.items() if not p.is_file() or p.read_text()!=value]
    if stale:raise SystemExit('Stale GNOME resources: '+', '.join(stale))
    print('GNOME resources match the shared HTML contract')
else:
    for p,value in outputs.items():
        p.parent.mkdir(exist_ok=True,parents=True);p.write_text(value)
    print('Generated GNOME contract, copy, metrics and SVG resources from HTML')
