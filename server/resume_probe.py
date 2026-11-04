"""Explicit, bounded exercise of one plugin project switch; never a chat action."""
from __future__ import annotations
import copy


class ProjectResumeProbe:
    def __init__(self, ticket, project_id, now):
        self.ticket, self.project_id, self.started = ticket, project_id, now
        self.stage, self.at = 'initial', now
        self.samples = []
        self.transitions = []

    def observe(self, plugin, status, now):
        pid = self.project_id
        control = next((p for p in status.get('projectControls', []) if p['id'] == pid), {})
        group = next((p for p in status.get('projects', []) if p['id'] == pid), {})
        value = {'stage':self.stage,'connected':status.get('connected'),
                 'enabled':control.get('updatesEnabled'),'syncing':control.get('syncing',False),
                 'menu':[{k:c[k] for k in ('id','index','status')} for c in group.get('threads', [])],
                 'list':[{k:c[k] for k in ('id','index','status')} for c in control.get('threads', [])],
                 'sources':[{'id':key,'hostId':s.host_id,'valid':s.valid,'phase':s.phase(),'revision':s.revision}
                    for key,s in plugin.states.items() if (plugin.project_by_thread.get(key) or
                        plugin.registry.entries.get(key,{}).get('project',{}).get('id')) == pid]}
        if (not self.samples or {k:v for k,v in self.samples[-1].items() if k!='time'} != value) and len(self.samples)<128:
            self.samples.append(copy.deepcopy(value)|{'time':now-self.started})

    def ready(self, plugin):
        control=next((p for p in plugin.last_status.get('projectControls',[]) if p['id']==self.project_id),{})
        group=next((p for p in plugin.last_status.get('projects',[]) if p['id']==self.project_id),{})
        return control.get('updatesEnabled') is True and not control.get('syncing') and bool(group.get('threads')) and all(c['status']!='unknown' for c in group['threads'])

    def drive(self,plugin,on,stage,now):
        self.stage,self.at=stage,now
        self.transitions.append({'stage':stage,'time':now-self.started,'updatesEnabled':on})
        plugin.consume_ui({'event':'project_enable' if on else 'project_disable','projectId':self.project_id},_probe=True)

    def tick(self,plugin,now):
        if not plugin.enabled or not plugin.connected:return False,'connection-or-global-preference-changed'
        if self.project_id not in plugin.project_catalog:return False,'project-no-longer-tracked'
        if now-self.started>13:return False,'fresh-state-timeout'
        if self.stage=='initial':self.drive(plugin,False,'off',now)
        elif self.stage=='off' and now-self.at>=0.3:self.drive(plugin,True,'resume',now)
        elif self.stage=='resume' and self.ready(plugin):self.stage,self.at='first-ready',now
        elif self.stage=='first-ready' and now-self.at>=0.25:self.drive(plugin,False,'rapid-off',now)
        elif self.stage=='rapid-off' and now-self.at>=0.06:self.drive(plugin,True,'rapid-resume',now)
        elif self.stage=='rapid-resume' and self.ready(plugin):self.stage,self.at='second-ready',now
        elif self.stage=='second-ready' and now-self.at>=0.25:return True,'completed'
        return None
