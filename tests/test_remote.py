import argparse
import json
import os
import pathlib
import sys
import socket
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
from desktop import DesktopIPC, DesktopMetadata
from state import ThreadState, WatchRegistry, thread_key
from main import Plugin, chat_url

TID = '11111111-1111-4111-8111-111111111111'
HOST = 'remote-control:example-host'


def snapshot(kind='active', unread=False, terminal='inProgress'):
    return {'type':'snapshot','revision':1,'conversationState':{
        'id':TID,'title':'远程聊天','workspaceKind':'project','cwd':'/workspace/project',
        'threadRuntimeStatus':{'type':kind,'activeFlags':[]},'hasUnreadTurn':unread,
        'turns':[{'id':'turn-1','status':terminal,'items':[{'content':'must not persist'}]}]}}


class FakeIPC:
    client_id='own'
    def __init__(self):self.following=set();self.calls=[]
    def acknowledge_protocol(self,message):return False
    def follow(self,tid,enabled=True,*,host_id='local'):
        self.calls.append((host_id,tid,enabled))
        if enabled:self.following.add((host_id,tid))
        else:self.following.discard((host_id,tid))
    def close(self):pass


class RemoteTests(unittest.TestCase):
    def test_subscriptions_and_cleanup_keep_host_identity(self):
        ipc=DesktopIPC(pathlib.Path('unused'));sock,peer=socket.socketpair()
        self.addCleanup(sock.close);self.addCleanup(peer.close)
        sock.setblocking(False);peer.setblocking(False);ipc.socket=sock;ipc.client_id='own'
        ipc.follow(TID);ipc.follow(TID,host_id=HOST)
        self.assertEqual(ipc.following,{('local',TID),(HOST,TID)})
        ipc.close()
        received=DesktopIPC(pathlib.Path('unused'));received.socket=peer
        messages=list(received.messages())
        released={m['params']['hostId'] for m in messages if m['params']['following'] is False}
        self.assertEqual(released,{'local',HOST})
        self.assertTrue(all(m['method']=='thread-stream-following-changed' for m in messages))

    def test_remote_identity_uses_registered_host_root_and_actual_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/'state.json'
            path.write_text(json.dumps({'local-projects':{'p':{'name':'本地'}},
                'thread-project-assignments':{TID:{'projectKind':'local','projectId':'p'}},
                'remote-projects':[
                    {'id':'p','hostId':HOST,'label':'真正的远程项目','remotePath':'/workspace/project'},
                    {'id':'nested','hostId':HOST,'label':'嵌套项目','remotePath':'/workspace/project/sub'},
                    {'id':'other','hostId':'remote-control:another','label':'另一主机','remotePath':'/workspace/project'}],
                'project-appearances':{'p':{'marker':{'kind':'emoji','emoji':'📚'}}}}))
            metadata=DesktopMetadata(path);metadata.poll()
            local=ThreadState(TID);local.consume(snapshot(),'owner')
            remote=ThreadState(TID,host_id=HOST);remote.consume(snapshot(),'owner')
            states={local.key:local,remote.key:remote}
            ids=metadata.identities(states)
            self.assertEqual(ids[TID]['id'],'p')
            self.assertEqual(ids[remote.key]['id'],thread_key(HOST,'p'))
            self.assertEqual(ids[remote.key]['name'],'真正的远程项目')
            self.assertEqual(ids[remote.key]['marker'],'📚')
            remote.metadata['cwd']='/workspace/project/sub/work'
            self.assertEqual(metadata.identities(states)[remote.key]['name'],'嵌套项目')
            remote.metadata['cwd']='/workspace/project-not-the-same'
            self.assertNotIn(remote.key,metadata.identities(states))

    def test_same_thread_id_on_two_hosts_does_not_merge_or_share_seen(self):
        local=ThreadState(TID);local.consume(snapshot(),'owner')
        remote=ThreadState(TID,host_id=HOST);remote.consume(snapshot(unread=True,kind='idle',terminal='completed'),'owner')
        registry=WatchRegistry();states={local.key:local,remote.key:remote}
        projects={local.key:{'id':'p','name':'同名项目','markerType':'icon','marker':'folder'},
                  remote.key:{'id':thread_key(HOST,'p'),'name':'同名项目','hostId':HOST,'markerType':'icon','marker':'folder'}}
        groups=registry.update(states,projects,True)
        self.assertEqual(len(groups),2)
        self.assertEqual(registry.entries[TID]['index'],1)
        self.assertEqual(registry.entries[remote.key]['index'],1)
        registry.mark_seen(remote)
        self.assertIn(TID,registry.entries)
        self.assertNotIn(remote.key,registry.entries)
        self.assertIn(remote.key,registry.acknowledged)
        self.assertNotIn(TID,registry.acknowledged)
        restored=WatchRegistry(registry.saved())
        self.assertEqual(restored.entries[TID]['index'],1)

    def test_viewed_idle_remote_history_does_not_become_a_capsule(self):
        remote=ThreadState(TID,host_id=HOST)
        remote.consume(snapshot(kind='idle',terminal='completed',unread=False),'owner')
        self.assertEqual(WatchRegistry().update({remote.key:remote},{},True),[])

    def test_plugin_discovers_projects_reads_and_routes_remote_without_execution(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=Plugin(argparse.Namespace(no_ui=True,seconds=0));ipc=FakeIPC();p.ipc=ipc;p.connected=True
            p.metadata.remote_projects=[{'id':'p','hostId':HOST,'label':'远程项目','remotePath':'/workspace/project'}]
            def message(method,params,version):
                p.consume_ipc(ipc,{'type':'broadcast','sourceClientId':'desktop','method':method,'version':version,'params':{'hostId':HOST,'conversationId':TID,**params}})
            message('thread-stream-following-changed',{'following':True},1)
            self.assertEqual(ipc.calls,[(HOST,TID,True)])
            message('thread-stream-state-changed',{'change':snapshot()},11)
            p.publish()
            group=p.last_status['projects'][0];chat=group['threads'][0]
            self.assertEqual(group['name'],'远程项目');self.assertEqual(group['hostId'],HOST)
            self.assertEqual(chat['id'],thread_key(HOST,TID));self.assertEqual(chat['threadId'],TID)
            self.assertEqual(chat['status'],'running')
            self.assertNotIn('must not persist',json.dumps(p.states[chat['id']].metadata))
            message('thread-read-state-changed',{'hasUnreadTurn':False},3)
            self.assertTrue(p.refresh_pending)
            p.refresh_tracked();self.assertEqual(ipc.calls[-1],(HOST,TID,True))
            with patch('main.sys.platform','darwin'), patch('main.subprocess.Popen') as opened:
                p.consume_ui({'event':'open','threadId':chat['id']})
                url=opened.call_args.args[0][1]
                self.assertEqual(parse_qs(urlparse(url).query)['hostId'],[HOST])
                self.assertTrue(url.startswith('codex://threads/'+TID))
            p.lock.close()

    def test_local_deep_link_contract_is_unchanged_and_remote_is_encoded(self):
        self.assertEqual(chat_url(TID),'codex://threads/'+TID)
        host='ssh:host with spaces/?'
        url=chat_url(thread_key(host,TID))
        self.assertEqual(parse_qs(urlparse(url).query),{'hostId':[host]})
        self.assertIsNone(chat_url('not-a-thread'))


if __name__=='__main__':unittest.main()
