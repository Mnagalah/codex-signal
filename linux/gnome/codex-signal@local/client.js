const {Gio,GLib} = imports.gi;
const ByteArray = imports.byteArray;
var Client = class {
    constructor(onMessage,onConnection) {
        this._message=onMessage;this._connection=onConnection;this._cancel=null;this._stream=null;this._input=null;
        this._retry=0;this._generation=0;this._running=false;this._writing=false;this._queue=[];this._buffer=new Uint8Array(0);
    }
    start() {this._running=true;this._connect();}
    _connect() {
        if (!this._running) return;
        const generation=++this._generation;this._cancel=new Gio.Cancellable();
        const runtime=GLib.get_user_runtime_dir();
        const address=Gio.UnixSocketAddress.new(GLib.build_filenamev([runtime,'codex-signal','ui.sock']));
        const client=new Gio.SocketClient({timeout:2,enable_proxy:false});
        client.connect_async(address,this._cancel,(source,result)=>{
            if (generation!==this._generation) return;
            try {this._stream=source.connect_finish(result);}
            catch (_) {this._lost();return;}
            this._input=this._stream.get_input_stream();this._queue=[];this._buffer=new Uint8Array(0);
            this.send({event:'hello',protocol:1});this._connection(true);this._read(generation);
        });
    }
    _read(generation) {
        if (!this._input || !this._running) return;
        this._input.read_bytes_async(65536,GLib.PRIORITY_DEFAULT,this._cancel,(source,result)=>{
            if (generation!==this._generation) return;
            try {
                const bytes=source.read_bytes_finish(result).get_data();
                if (!bytes.length) {this._lost();return;}
                if (this._buffer.length+bytes.length>1048576) {this._lost();return;}
                const all=new Uint8Array(this._buffer.length+bytes.length);all.set(this._buffer);all.set(bytes,this._buffer.length);
                let start=0;
                for (let i=0;i<all.length;i++) if (all[i]===10) {
                    const value=JSON.parse(ByteArray.toString(all.slice(start,i)));start=i+1;
                    this._message(value);
                }
                this._buffer=all.slice(start);this._read(generation);
            } catch (_) {this._lost();}
        });
    }
    send(value) {
        if (!this._stream) return false;
        if (this._queue.length>=32) {this._lost();return false;}
        this._queue.push(ByteArray.fromString(JSON.stringify(value)+'\n'));this._write();return true;
    }
    _write() {
        if (this._writing || !this._stream || !this._queue.length) return;
        this._writing=true;const generation=this._generation,bytes=this._queue[0];
        this._stream.get_output_stream().write_all_async(bytes,GLib.PRIORITY_DEFAULT,this._cancel,(source,result)=>{
            if (generation!==this._generation) return;
            try {source.write_all_finish(result);this._queue.shift();this._writing=false;this._write();}
            catch (_) {this._lost();}
        });
    }
    _lost() {
        ++this._generation;this._cancel?.cancel();this._cancel=null;
        try {this._stream?.close(null);} catch (_) {}
        this._stream=null;this._input=null;this._queue=[];this._writing=false;this._buffer=new Uint8Array(0);
        this._connection(false);
        if (this._running && !this._retry) this._retry=GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT,2,()=>{this._retry=0;this._connect();return GLib.SOURCE_REMOVE;});
    }
    stop() {this._running=false;if(this._retry)GLib.Source.remove(this._retry);this._retry=0;this._lost();}
};
