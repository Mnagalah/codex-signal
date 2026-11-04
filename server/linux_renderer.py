#!/usr/bin/env python3
"""Plugin-owned stdio ↔ private Unix socket bridge for the GNOME 42 UI.

No model/task APIs, network listener, service installation, or body persistence.
"""
from __future__ import annotations
import collections,errno,fcntl,json,os,pathlib,queue,selectors,socket,stat,struct,sys,threading
if __package__:
    from .runtime_paths import ui_socket
else:
    from runtime_paths import ui_socket

MAX_FRAME=1024*1024
PROTOCOL=1
SIMPLE={'enable','disable','reload','reconnect','compact_enable','compact_disable'}
FIELDS={'open':'threadId','seen':'threadId','project_enable':'projectId','project_disable':'projectId',
        'notification_enable':'status','notification_disable':'status','set_status_emoji':'emoji'}
PHASES={'running','approval','input','completed','failed','stopped'}

def validated_event(value):
    if not isinstance(value,dict):return None
    event=value.get('event')
    if event in SIMPLE:return {'event':event}
    if event in FIELDS:
        key=FIELDS[event];v=value.get(key)
        if not isinstance(v,str) or not v or len(v.encode('utf-8'))>4096 or any(ord(c)<32 for c in v):return None
        if key=='status' and v not in PHASES:return None
        if key=='emoji' and (len(v.encode('utf-8'))>128 or any(c.isspace() for c in v)):return None
        return {'event':event,key:v}
    if event=='notice_open':
        if all(isinstance(value.get(k),str) and 0<len(value[k])<=4096 for k in ('noticeId','threadId')):
            return {k:value[k] for k in ('event','noticeId','threadId')}
    if event in ('notice_shown','notice_closed'):
        if not isinstance(value.get('noticeId'),str) or len(value['noticeId'])>256:return None
        allowed=('event','noticeId','source','reason','dwellMs','uiLanguage','becameKey','activatedApplication')
        result={k:value[k] for k in allowed if k in value and isinstance(value[k],(str,int,float,bool))}
        if any(isinstance(v,str) and len(v)>256 for v in result.values()):return None
        return result
    return None

def peer_uid(client):
    if not sys.platform.startswith('linux'):raise OSError('Linux SO_PEERCRED required')
    return struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]

class Bridge:
    def __init__(self,path,emit,credentials=peer_uid):
        self.path=pathlib.Path(path);self.emit=emit;self.credentials=credentials
        self.selector=selectors.DefaultSelector();self.messages=queue.Queue(maxsize=64);self.state_lock=threading.Lock()
        self.client=None;self.buffer=bytearray();self.output=bytearray();self.hello=False
        self.last_state=None;self.coalesced_state=None;self.running=True;self.owned_inode=None;self.lock=None;self.listener=None
    def start(self):
        parent=self.path.parent
        if len(os.fsencode(self.path))>=104:raise OSError('UI socket path is too long')
        parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        info=parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
            raise PermissionError('UI socket directory must be private and owned by this user')
        self.lock=open(parent/'bridge.lock','a+');os.chmod(parent/'bridge.lock',0o600)
        fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if self.path.exists() or self.path.is_symlink():
            old=self.path.lstat()
            if not stat.S_ISSOCK(old.st_mode) or old.st_uid!=os.getuid():raise PermissionError('Refusing to replace an unrelated UI path')
            check=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            try:
                check.settimeout(.2);check.connect(str(self.path))
            except OSError as e:
                if e.errno not in (errno.ECONNREFUSED,errno.ENOENT):raise
                self.path.unlink()
            else:raise OSError(errno.EADDRINUSE,'UI socket is already active')
            finally:check.close()
        self.listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.listener.bind(str(self.path));os.chmod(self.path,0o600)
        self.owned_inode=self.path.stat().st_ino;self.listener.listen(1);self.listener.setblocking(False)
        self.selector.register(self.listener,selectors.EVENT_READ,'listener')
        self.emit({'event':'offline'})
    def enqueue(self,value):
        if value is None:
            self.running=False  # EOF cannot be dropped behind a full poll queue.
            return
        if value.get('kind')=='state':
            with self.state_lock:self.coalesced_state=value
            return
        try:self.messages.put(value,timeout=.2)
        except queue.Full:
            pass  # A bounded transient notice queue; no body/event history.
    def _queue(self,value):
        wire=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()+b'\n'
        if len(wire)>MAX_FRAME or len(self.output)+len(wire)>MAX_FRAME*2:
            self.drop();return
        self.output.extend(wire);self._interest()
    def _interest(self):
        if self.client:self.selector.modify(self.client,selectors.EVENT_READ|(selectors.EVENT_WRITE if self.output else 0),'client')
    def drop(self):
        client,self.client=self.client,None;was_ready=self.hello
        self.hello=False;self.buffer.clear();self.output.clear()
        if client:
            try:self.selector.unregister(client)
            except (KeyError,ValueError):pass
            client.close()
        if was_ready:self.emit({'event':'offline'})
    def _accept(self):
        client,_=self.listener.accept()
        try:
            if self.credentials(client)!=os.getuid():raise PermissionError('Different user')
            if self.client is not None:raise PermissionError('UI client already connected')
            client.setblocking(False);self.client=client;self.selector.register(client,selectors.EVENT_READ,'client')
        except (OSError,PermissionError):client.close()
    def _read(self):
        data=self.client.recv(65536)
        if not data:self.drop();return
        self.buffer.extend(data)
        if len(self.buffer)>MAX_FRAME:self.drop();return
        while self.client and b'\n' in self.buffer:
            line,_,rest=self.buffer.partition(b'\n');self.buffer=bytearray(rest)
            try:value=json.loads(line)
            except (ValueError,UnicodeError):self.drop();return
            if not self.hello:
                if not isinstance(value,dict) or value.get('event')!='hello' or value.get('protocol')!=PROTOCOL:
                    self.drop();return
                self.hello=True
                self.emit({'event':'ready','layoutSource':'codex-status-layout.html#layout-contract','layoutVersion':'1','layoutEngine':'gnome42-shared-grid'})
                if self.last_state:self._queue(self.last_state)
            elif (event:=validated_event(value)) is not None:self.emit(event)
    def poll(self,timeout=.15):
        if not self.running:return
        with self.state_lock:value,self.coalesced_state=self.coalesced_state,None
        if value is not None:
            self.last_state=value
            if self.hello:self._queue(value)
        for _ in range(64):
            try:value=self.messages.get_nowait()
            except queue.Empty:break
            if value is None:self.running=False;return
            if value.get('kind')=='state':self.last_state=value
            if self.hello and value.get('kind') in ('state','status_notice'):self._queue(value)
        for key,mask in self.selector.select(timeout):
            try:
                if key.data=='listener':self._accept();continue
                if self.client is None or key.fileobj is not self.client:continue
                if mask&selectors.EVENT_READ:self._read()
                if mask&selectors.EVENT_WRITE and self.client:
                    count=self.client.send(self.output);del self.output[:count];self._interest()
            except (OSError,ConnectionError):self.drop()
    def close(self):
        self.running=False;self.drop()
        if self.listener:self.listener.close()
        self.selector.close()
        try:
            if self.owned_inode and self.path.lstat().st_ino==self.owned_inode:self.path.unlink()
        except FileNotFoundError:pass
        if self.lock:self.lock.close()

def main():
    def emit(value):
        sys.stdout.write(json.dumps(value,ensure_ascii=False)+'\n');sys.stdout.flush()
    bridge=Bridge(ui_socket(),emit)
    try:
        bridge.start()
        def read_backend():
            try:
                while line:=sys.stdin.buffer.readline(MAX_FRAME+1):
                    if len(line)>MAX_FRAME:break
                    try:value=json.loads(line)
                    except (ValueError,UnicodeError):continue
                    if isinstance(value,dict):bridge.enqueue(value)
            finally:bridge.enqueue(None)
        threading.Thread(target=read_backend,daemon=True,name='gnome-bridge-input').start()
        while bridge.running:bridge.poll()
    except (OSError,ValueError) as e:
        print('Codex Signal GNOME bridge: '+str(e),file=sys.stderr)
        raise SystemExit(1)
    finally:bridge.close()
if __name__=='__main__':main()
