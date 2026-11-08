"""Synthetic desktop read events; never operate a real chat or approval."""
import argparse,copy,json,os,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from main import Plugin
from state import ThreadState,WatchRegistry,thread_key

TID='11111111-1111-4111-8111-111111111111'
class IPC:
    client_id='signal'
    def __init__(self):self.following=set();self.calls=[]
    def acknowledge_protocol(self,_):return False
    def follow(self,tid,enabled=True,*,host_id='local'):self.calls.append((host_id,tid,enabled))

def snapshot(turn='turn-a',phase='completed',unread=True,revision=1):
    return {'type':'snapshot','revision':revision,'conversationState':{'id':TID,'title':'Sample chat','workspaceKind':'project','hasUnreadTurn':unread,'threadRuntimeStatus':{'type':'active' if phase=='inProgress' else 'idle','activeFlags':[]},'turns':[{'id':turn,'status':phase,'turnStartedAtMs':100 if turn=='turn-a' else 200}]}}

class ReadSyncFixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'CODEX_HOME':self.tmp.name+'/codex','CODEX_MENU_STATUS_DATA':self.tmp.name,'CODEX_SIGNAL_CONFIG':self.tmp.name+'/no-config.toml','CODEX_SIGNAL_DESKTOP_STATE':self.tmp.name+'/no-desktop.json'});self.env.start()
        self.p=Plugin(argparse.Namespace(no_ui=True,seconds=0));self.p.ipc=IPC();self.p.connected=True
        self.p.metadata=types.SimpleNamespace(identities=lambda states:{k:{'id':thread_key(s.host_id,'project'),'name':'Sample project','markerType':'icon','marker':'folder'} for k,s in states.items()})
        self.add_state();self.p.publish()
    def tearDown(self):self.p.lock.close();self.env.stop();self.tmp.cleanup()
    def add_state(self,host='local',phase='completed'):
        s=ThreadState(TID,host_id=host);s.consume(snapshot(phase=phase),'owner');self.p.states[s.key]=s;return s
    def read(self,host='local',unread=False,version=3):
        self.p.consume_ipc(self.p.ipc,{'type':'broadcast','sourceClientId':'desktop','method':'thread-read-state-changed','version':version,'params':{'hostId':host,'conversationId':TID,'hasUnreadTurn':unread}})
    def chats(self):return [c for g in self.p.last_status['projects'] for c in g['threads']]

class ReadSyncTests(ReadSyncFixture):
    def test_opened_completion_clears_without_waiting_for_another_snapshot(self):
        self.assertEqual(len(self.chats()),1);self.read();self.p.publish()
        self.assertEqual(self.chats(),[])
        self.assertEqual(self.p.registry.acknowledged[TID],'turn-a')
        self.assertEqual(self.p.ipc.calls,[])  # No read receipt or task operation.
    def test_stale_unread_snapshot_cannot_resurrect_viewed_turn_but_new_turn_can(self):
        self.read();s=self.p.states[TID];s.consume(snapshot(revision=2),'owner');self.p.publish()
        self.assertEqual(self.chats(),[])
        s.consume(snapshot('turn-b','inProgress',revision=3),'owner');self.p.publish();self.assertEqual(self.chats()[0]['status'],'running')
        s.consume(snapshot('turn-b',revision=4),'owner');self.p.publish();self.assertEqual(self.chats()[0]['status'],'completed')
        self.assertEqual(self.p.registry.acknowledged[TID],'turn-a')
    def test_read_while_running_does_not_acknowledge_a_future_completion(self):
        self.p.states[TID].consume(snapshot(phase='inProgress',revision=2),'owner');self.p.publish();self.read()
        self.assertNotIn(TID,self.p.registry.acknowledged)
        self.p.states[TID].consume(snapshot(revision=3),'owner');self.p.publish();self.assertEqual(self.chats()[0]['status'],'completed')
    def test_local_read_does_not_clear_same_id_on_remote_host(self):
        self.add_state('remote-example');self.p.publish();self.read();self.p.publish()
        self.assertEqual([c['id'] for c in self.chats()],[thread_key('remote-example',TID)])
        self.read('remote-example');self.p.publish();self.assertEqual(self.chats(),[])
    def test_invalid_state_or_protocol_only_requests_reconciliation(self):
        before=copy.deepcopy(self.p.registry.saved());self.read(version=999);self.p.publish()
        self.assertEqual(self.p.registry.saved(),before)
        self.p.states[TID].valid=False;self.read();self.p.publish()
        self.assertNotIn(TID,self.p.registry.acknowledged);self.assertEqual(self.chats()[0]['status'],'unknown')
    def test_seen_turn_survives_payload_reload_without_resetting_other_records(self):
        self.p.registry.acknowledged['synthetic-history']='earlier-turn';self.read();self.p.publish()
        saved=json.loads((Path(self.tmp.name)/'slots.json').read_text());registry=WatchRegistry(saved)
        self.assertEqual(registry.acknowledged,{'synthetic-history':'earlier-turn',TID:'turn-a'})
        self.p.states[TID].consume(snapshot(revision=2),'owner')
        self.assertEqual(registry.update(self.p.states,self.p.metadata.identities(self.p.states),True),[])

class InactiveReadSyncTests(ReadSyncFixture):
    """Replay remote read-file edges without a read broadcast, as on desktop."""

    def test_read_file_change_requeries_inactive_remote_without_manual_refresh(self):
        from desktop import DesktopMetadata
        host='remote-control:example-host'
        state=self.add_state(host)
        state.metadata['hasUnreadTurn']=False
        self.p.publish()
        self.assertNotIn(state.key,self.p.registry.entries)
        path=Path(self.tmp.name)/'desktop.json'
        def write_reads(ids):
            path.write_text(json.dumps({'electron-thread-read-state-v1':{
                'version':1,'unreadByIdentity':{'opaque-account':{'opaque-host-key':ids}}}}))
        write_reads([])
        self.p.metadata=DesktopMetadata(path);self.p.metadata.poll()
        # The remote chat remains followed, but no longer has a visible entry.
        self.p.ipc.following.add((host,TID))
        write_reads([TID,'22222222-2222-4222-8222-222222222222'])
        ipc=self.p.ipc
        def reply(tid,enabled=True,*,host_id='local'):
            ipc.calls.append((host_id,tid,enabled))
            if host_id==host:
                self.p.consume_ipc(ipc,{'type':'broadcast','sourceClientId':'owner',
                    'method':'thread-stream-state-changed','version':11,'params':{
                        'hostId':host,'conversationId':tid,'change':snapshot(revision=2)}})
        ipc.follow=reply;ipc.close=lambda:None
        self.p.primary=True
        self.p.events.put(('shutdown',None))
        with patch('main.signal.signal'):
            self.p.run(start_mcp_reader=False)  # Real metadata-poll/refresh/publish loop.
        self.assertIn((host,TID,True),ipc.calls)
        self.assertTrue(all(call[1]==TID for call in ipc.calls))
        self.assertIn(state.key,[c['id'] for c in self.chats()])
        self.assertNotIn(state.key,self.p.registry.acknowledged)

    def test_refresh_is_bounded_to_observed_chats_and_respects_project_pause(self):
        remote=self.add_state('remote-control:example-host')
        remote.metadata['hasUnreadTurn']=False
        self.p.publish()
        pid=self.p.project_by_thread[TID]
        self.p.paused_projects[pid]={'id':pid}
        self.p.refresh_tracked()
        self.assertEqual(self.p.ipc.calls,[(remote.host_id,TID,True)])
        # Only existing states are requested. No unread-file IDs, account
        # buckets or history inventories become discovery candidates.
        self.assertEqual(set(self.p.states),{TID,remote.key})
