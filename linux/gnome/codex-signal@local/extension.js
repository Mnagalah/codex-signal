const {St,Clutter,Gio,GLib,GObject,Pango} = imports.gi;
const Main=imports.ui.main, PanelMenu=imports.ui.panelMenu, PopupMenu=imports.ui.popupMenu, BoxPointer=imports.ui.boxpointer;
const ExtensionUtils=imports.misc.extensionUtils, ByteArray=imports.byteArray;
const Me=ExtensionUtils.getCurrentExtension(), Core=Me.imports.core.API, Client=Me.imports.client.Client;
function jsonResource(name) {return JSON.parse(ByteArray.toString(GLib.file_get_contents(GLib.build_filenamev([Me.path,name]))[1]));}
const Contract=jsonResource('contract.json'), Copy=jsonResource('copy.json'), ProjectIcons=jsonResource('project-icons.json'), Metrics=Contract.metrics;

class Motion {
    constructor(reduced) {this.reduced=reduced;this.timers=new Map();}
    stop(key) {const id=this.timers.get(key);if(id)GLib.Source.remove(id);this.timers.delete(key);}
    tween(key,seconds,frame,done) {
        this.stop(key);if(this.reduced() || seconds===0) {frame(1);done?.();return;}
        const began=GLib.get_monotonic_time()/1e6;frame(0);
        const id=GLib.timeout_add(GLib.PRIORITY_DEFAULT,16,()=>{
            const x=Math.min(1,(GLib.get_monotonic_time()/1e6-began)/seconds);frame(1-(1-x)**3);
            if(x===1) {this.timers.delete(key);done?.();return GLib.SOURCE_REMOVE;}return GLib.SOURCE_CONTINUE;
        });this.timers.set(key,id);
    }
    color(actor,phase,globalEntry=false) {
        if(actor._signalPhase===phase)return;actor._signalPhase=phase;
        const target=Core.rgb(Core.color(phase,globalEntry)),from=actor._signalRGB || target;
        this.tween(actor,.16,p=>{
            actor._signalRGB=target.map((v,i)=>Math.round(from[i]+(v-from[i])*p));
            const rgb=actor._signalRGB,hex='#'+rgb.map(v=>v.toString(16).padStart(2,'0')).join('');
            actor.set_style((actor._signalBase || '')+`background-color:rgb(${rgb.join(',')});color:${Core.foreground(hex)};border:1px ${phase==='unknown'?'dashed':'solid'} ${phase==='unknown'?'#222':'transparent'};`);
        });
    }
    size(actor,visible,vertical=false,done) {
        actor._leaving=!visible;const prop=vertical?'height':'width',start=actor[prop],alpha=actor.opacity;
        actor[prop]=-1;const natural=(vertical?actor.get_preferred_height(-1):actor.get_preferred_width(-1))[1];actor[prop]=start;
        const target=visible?natural:0,key=actor._signalSizeKey || (actor._signalSizeKey={});
        this.tween(key,Contract.menuMotion.transition,p=>{actor[prop]=Math.max(0,this.reduced()?target:start+(target-start)*p);actor.opacity=Math.round(alpha+((visible?255:0)-alpha)*p);},()=>{if(visible)actor[prop]=-1;done?.();});
    }
    forget(actor) {for(const child of actor.get_children())this.forget(child);this.stop(actor);if(actor._signalSizeKey)this.stop(actor._signalSizeKey);}
    destroy() {for(const id of this.timers.values())GLib.Source.remove(id);this.timers.clear();}
}
class Spring {
    constructor(actor,reduced) {this.actor=actor;this.reduced=reduced;this.value=0;this.velocity=0;this.target=0;this.source=0;this.revision=0;}
    set(target,keyboard,onSettled) {
        this.target=target;const revision=++this.revision;
        if(this.source)GLib.Source.remove(this.source);this.source=0;
        const paint=()=>{this.actor.opacity=Math.round(Math.max(0,Math.min(1,this.value))*255);this.actor.translation_y=-Contract.popoverMotion.offset*(1-this.value);};
        if(keyboard || this.reduced()) {this.value=target;this.velocity=0;paint();onSettled?.();return;}
        let last=GLib.get_monotonic_time()/1e6;const began=last;paint();
        this.source=GLib.timeout_add(GLib.PRIORITY_DEFAULT,16,()=>{
            const now=GLib.get_monotonic_time()/1e6,step=Core.spring(this.value,this.velocity,target,Math.min(.05,now-last),Contract.popoverMotion.response,Contract.popoverMotion.dampingRatio);last=now;
            this.value=step.value;this.velocity=step.velocity;paint();
            if((Math.abs(this.value-target)<Contract.popoverMotion.epsilon && Math.abs(this.velocity)<.01) || now-began>1) {
                this.value=target;this.velocity=0;paint();this.source=0;if(revision===this.revision)onSettled?.();return GLib.SOURCE_REMOVE;
            }return GLib.SOURCE_CONTINUE;
        });
    }
    destroy() {++this.revision;if(this.source)GLib.Source.remove(this.source);this.source=0;}
}
function label(value,style) {return new St.Label({text:String(value || ''),style_class:style || '',y_align:Clutter.ActorAlign.CENTER});}
function text(value,style) {const actor=label(value,style);actor.clutter_text.ellipsize=Pango.EllipsizeMode.END;return actor;}
function button(child,name,action) {
    const b=new St.Button({style_class:'signal-action',reactive:true,can_focus:true,track_hover:true,accessible_name:name,y_align:Clutter.ActorAlign.CENTER});b.set_child(child);b._signalAction=true;
    function run(keyboard) {let node=b;while(node){if(node._leaving)return;node=node.get_parent();}action(keyboard);}
    b.connect('clicked',()=>run(false));b.connect('key-press-event',(_,e)=>{if([Clutter.KEY_Return,Clutter.KEY_KP_Enter,Clutter.KEY_space].includes(e.get_key_symbol())){run(true);return Clutter.EVENT_STOP;}return Clutter.EVENT_PROPAGATE;});return b;
}
function interactive(actor,value) {for(const c of actor.get_children())interactive(c,value);if(actor._signalAction){actor.reactive=value;actor.can_focus=value;}}
function projectIcon(p,size) {
    if(p.markerType==='emoji')return label(p.marker,'signal-emoji');
    const name=ProjectIcons[p.marker] || ProjectIcons.folder;
    return new St.Icon({gicon:new Gio.FileIcon({file:Gio.File.new_for_path(GLib.build_filenamev([Me.path,'icons',name+'-symbolic.svg']))}),icon_size:size,y_align:Clutter.ActorAlign.CENTER});
}
function smallIcon(name) {return new St.Icon({icon_name:name,icon_size:Metrics['control-icon'],y_align:Clutter.ActorAlign.CENTER});}

var SignalIndicator=GObject.registerClass(class SignalIndicator extends PanelMenu.Button {
    _init() {
        super._init(.5,'Codex Signal');
        this._settings=ExtensionUtils.getSettings();this._desktop=new Gio.Settings({schema_id:'org.gnome.desktop.interface'});
        this._motion=new Motion(()=>!this._desktop.get_boolean('enable-animations'));
        this._spring=new Spring(this.menu.actor,()=>!this._desktop.get_boolean('enable-animations'));
        this._state={kind:'state',connected:false,enabled:true,uiLanguage:'en',projects:[],projectControls:[],statusEmoji:'🔦'};
        this._online=false;this._selected='global-control';this._settingsMode=false;this._settingsTarget=false;this._routeRevision=0;this._routeBusy=false;this._slots=new Map();this._rows=new Map();this._focus=[];this._notice=null;this._outgoingNotices=new Set();this._noticeTimer=0;this._tooltipTimer=0;this._destroyed=false;
        this.add_style_class_name('signal-host');
        this._lane=new St.BoxLayout({style_class:'signal-lane',y_align:Clutter.ActorAlign.CENTER});
        this._globalIcon=label('🔦','signal-emoji');this._globalButton=button(this._globalIcon,'Chat Status',kb=>this._toggle('global-control',this._globalButton,kb));this._globalButton.add_style_class_name('signal-global');
        const root=new St.BoxLayout({style_class:'signal-group',y_align:Clutter.ActorAlign.CENTER});root.add_child(this._lane);root.add_child(this._globalButton);this.add_child(root);
        this.menu.box.add_style_class_name('signal-popup-content');this.menu.actor.add_style_class_name('signal-popup');
        this._originalSource=this.menu.sourceActor;
        this._originalSource.disconnectObject(this.menu); // Child triggers own keyboard behavior.
        const open=this.menu.open.bind(this.menu),close=this.menu.close.bind(this.menu);
        this.menu.open=animation=>{
            if(this.menu.isOpen)return;open(BoxPointer.PopupAnimation.NONE);this.menu.actor._leaving=false;this.menu.actor.reactive=true;interactive(this.menu.actor,true);
            this._spring.set(1,animation===BoxPointer.PopupAnimation.NONE,()=>{});
        };
        this.menu.close=animation=>{
            if(!this.menu.isOpen && this._spring.target===0)return;
            close(BoxPointer.PopupAnimation.NONE);this.menu.actor.show();this.menu.actor._leaving=true;this.menu.actor.reactive=false;interactive(this.menu.actor,false);
            this._spring.set(0,animation===BoxPointer.PopupAnimation.NONE,()=>{if(this._spring.target===0)this.menu.actor.hide();});
        };
        this._buildPanel();
        this._client=new Client(value=>this._receive(value),online=>this._setOnline(online));this._client.start();
        this._iconSignal=this._settings.connect('changed::icon-request',()=>this._requestIcon());
        this._sessionSignal=Main.sessionMode.connect('updated',()=>{if(Main.sessionMode.isLocked){this.hide();this.menu.close(BoxPointer.PopupAnimation.NONE);this._dismissNotice('locked',true);}else{this.show();this._render();}});
        this._clock=GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT,1,()=>{if(this.menu.isOpen && !this._settingsMode && !this._routeBusy)this._renderRows();return GLib.SOURCE_CONTINUE;});
        this._render();
    }
    vfunc_event(_event) {return Clutter.EVENT_PROPAGATE;}
    _t(key,values) {return Core.text(Copy,this._state,key,values);}
    _send(event,id) {
        if(!this._online)return false;
        const value={event};if(id!==undefined)value[event.startsWith('project_')?'projectId':event.startsWith('notification_')?'status':event==='set_status_emoji'?'emoji':'threadId']=id;
        return this._client.send(value);
    }
    _setOnline(value) {this._online=value;if(!value){this._dismissNotice('disconnected',true);this.menu.close(BoxPointer.PopupAnimation.NONE);}this._render();}
    _receive(value) {
        if(value.kind==='state' && Core.validState(value)) {
            this._state=value;this._settings.set_string('current-icon',value.statusEmoji || '🔦');this._settings.set_string('current-language',value.uiLanguage==='zh-CN'?'zh-CN':'en');this._requestIcon();this._render();
            if(this._notice && !Core.noticeAllowed(this._notice.value,value))this._dismissNotice('paused',true);
            else if(this._notice)this._renderNotice();
        } else if(value.kind==='status_notice' && Core.validNotice(value.notice) && Core.noticeAllowed(value.notice,this._state))this._showNotice(value.notice);
    }
    _requestIcon() {
        const choice=this._settings.get_string('icon-request');if(!choice || !Core.safeEmoji(choice))return;
        if(choice===this._state.statusEmoji)this._settings.set_string('icon-request','');
        else this._send('set_status_emoji',choice);
    }
    _badge(chat,row=false) {
        const number=label(chat.index,'');number.clutter_text.ellipsize=Pango.EllipsizeMode.NONE;number.set_style(`font-size:${Metrics[row?'number-row-font':'number-font']}px;font-weight:600;`);
        const b=new St.Bin({child:number,style_class:'signal-badge'+(row?' signal-row-badge':''),x_align:Clutter.ActorAlign.CENTER,y_align:Clutter.ActorAlign.CENTER});
        this._motion.color(b,chat.status);return b;
    }
    _updateBadge(b,c) {b.get_child().text=String(c.index);this._motion.color(b,c.status);}
    _render() {
        if(this._destroyed)return;
        const state=this._state,phase=this._online?Core.summary(state,Contract.statusPriority):'unknown';
        this._globalIcon.text=state.statusEmoji || '🔦';this._motion.color(this._globalButton,phase,true);
        const count=Core.active(state).reduce((n,p)=>n+p.threads.length,0),description=!this._online?this._t('extensionOffline'):state.enabled===false?this._t('monitorDisabled'):Core.healthDetail(state) || (phase?this._t('aggregateStatus',{status:this._t(phase),n:count}):this._t('noChats'));
        this._globalButton.accessible_name=this._t('statusTitle')+' · '+description;
        const projects=this._online?Core.menuProjects(state):[],live=new Set(projects.map(p=>p.id));
        for(const [id,slot] of this._slots) if(!live.has(id) && !slot.actor._leaving) {
            interactive(slot.actor,false);if(this._selected===id)this.menu.close(BoxPointer.PopupAnimation.FULL);
            this._motion.size(slot.actor,false,false,()=>{if(slot.actor._leaving){this._motion.forget(slot.actor);slot.actor.destroy();this._slots.delete(id);}});
        }
        projects.forEach((p,index)=>{
            let slot=this._slots.get(p.id),fresh=!slot;
            if(fresh) {
                const actor=new St.BoxLayout({style_class:'signal-capsule',y_align:Clutter.ActorAlign.CENTER,clip_to_allocation:true});
                const title=button(new St.BoxLayout(),Core.projectName(Copy,state,p),kb=>this._toggle(p.id,title,kb));title.add_style_class_name('signal-project-trigger');
                const badges=new St.BoxLayout({style_class:'signal-badges',y_align:Clutter.ActorAlign.CENTER});actor.add_child(title);actor.add_child(badges);this._lane.add_child(actor);slot={actor,title,badges,map:new Map()};this._slots.set(p.id,slot);
            }
            const signature=JSON.stringify([p.markerType,p.marker,Core.projectName(Copy,state,p)]);
            if(slot.signature!==signature){const content=slot.title.get_child();content.destroy_all_children();content.add_child(projectIcon(p,Metrics['icon-menu']));content.add_child(text(Core.projectName(Copy,state,p),'signal-menu-name'));slot.signature=signature;}
            slot.title.accessible_name=Core.projectName(Copy,state,p);const ids=new Set(p.threads.map(c=>c.id));
            for(const [id,b] of slot.map)if(!ids.has(id) && !b._leaving){interactive(b,false);this._motion.size(b,false,false,()=>{if(b._leaving){this._motion.forget(b);b.destroy();slot.map.delete(id);}});}
            p.threads.forEach(c=>{
                let b=slot.map.get(c.id);
                if(!b){const dot=this._badge(c);b=button(dot,'',()=>{this._send('open',c.id);this.menu.close(BoxPointer.PopupAnimation.FULL);});b.add_style_class_name('signal-badge-button');slot.badges.add_child(b);slot.map.set(c.id,b);if(!fresh){b.width=0;b.opacity=0;this._motion.size(b,true);}}
                if(b._leaving){interactive(b,true);this._motion.size(b,true);}
                this._updateBadge(b.get_child(),c);b.accessible_name=this._t('openBadge',{project:p.name,n:c.index,title:c.title,status:this._t(c.status)});
            });
            this._lane.set_child_at_index(slot.actor,index);interactive(slot.actor,true);
            if(fresh){slot.actor.width=0;slot.actor.opacity=0;this._motion.size(slot.actor,true);}
            else if(slot.actor._leaving)this._motion.size(slot.actor,true);
        });
        if(this.menu.isOpen){this._renderHeader();if(!this._routeBusy)this._settingsMode?this._renderSettings():this._renderRows();}
    }
    _toggle(id,source,keyboard) {
        if(!this._online && id!=='global-control')return;
        if(this.menu.isOpen && this._selected===id){this.menu.close(keyboard?BoxPointer.PopupAnimation.NONE:BoxPointer.PopupAnimation.FULL);return;}
        if(this.menu.isOpen)this.menu.close(BoxPointer.PopupAnimation.NONE);
        this._selected=id;this._settingsMode=false;this._settingsTarget=false;this._routeBusy=false;this._routeAnimating=false;++this._routeRevision;this._motion.stop('route');this._clearBody();
        this.menu.sourceActor=source;this._renderHeader();this._renderRows();
        this.menu.open(keyboard?BoxPointer.PopupAnimation.NONE:BoxPointer.PopupAnimation.FULL);
        if(keyboard)(this._focus[0] || this._globalButton).grab_key_focus();
    }
    _switch(value,name,action) {
        const track=new St.Bin({style_class:'signal-switch-track'}),knob=new St.Widget({style_class:'signal-switch-knob',x_align:Clutter.ActorAlign.START});track.set_child(knob);
        const b=button(track,name,()=>action(!b._value));b._switchKnob=knob;b._value=value;b._setValue=on=>{b._value=!!on;track.set_style('background-color:'+(on?'#176bcb':'#303030'));knob.translation_x=on?16:0;};b._setValue(value);return b;
    }
    _buildPanel() {
        this._header=new St.BoxLayout({style_class:'signal-header'});this._headerIcon=new St.Bin();
        const copy=new St.BoxLayout({vertical:true,style_class:'signal-header-copy',x_expand:true,y_align:Clutter.ActorAlign.CENTER});this._title=text('','signal-header-title');this._subtitle=text('','signal-source');copy.add_child(this._title);copy.add_child(this._subtitle);
        this._settingsButton=button(smallIcon('emblem-system-symbolic'),'Settings',kb=>this._route(!this._settingsTarget,kb));
        const reload=button(smallIcon('view-refresh-symbolic'),'Reload plugin',()=>this._send('reload'));this._reload=reload;
        this._master=this._switch(true,'All chat updates',on=>this._selected==='global-control'?this._send(on?'enable':'disable'):this._send(on?'project_enable':'project_disable',this._selected));
        [this._headerIcon,copy,this._settingsButton,reload,this._master].forEach(a=>this._header.add_child(a));
        const item=new PopupMenu.PopupBaseMenuItem({reactive:false,can_focus:false});item.add_child(this._header);this.menu.addMenuItem(item);
        const separator=new PopupMenu.PopupSeparatorMenuItem();this.menu.addMenuItem(separator);
        this._body=new St.BoxLayout({vertical:true,style_class:'signal-body'});this._scroll=new St.ScrollView({style_class:'signal-scroll',hscrollbar_policy:St.PolicyType.NEVER,vscrollbar_policy:St.PolicyType.AUTOMATIC,overlay_scrollbars:true});this._scroll.add_actor(this._body);
        const bodyItem=new PopupMenu.PopupBaseMenuItem({reactive:false,can_focus:false});bodyItem.add_child(this._scroll);this.menu.addMenuItem(bodyItem);
        this.menu.actor.connect('key-press-event',(_,event)=>{
            const key=event.get_key_symbol();if(key===Clutter.KEY_Escape){this.menu.close(BoxPointer.PopupAnimation.NONE);this._globalButton.grab_key_focus();return Clutter.EVENT_STOP;}
            if(key===Clutter.KEY_Up || key===Clutter.KEY_Down){const list=this._focus.filter(a=>a.mapped && a.can_focus && a.reactive);if(!list.length)return Clutter.EVENT_STOP;let index=list.indexOf(global.stage.get_key_focus());index=(index+(key===Clutter.KEY_Down?1:-1)+list.length)%list.length;list[index].grab_key_focus();return Clutter.EVENT_STOP;}return Clutter.EVENT_PROPAGATE;
        });
    }
    _renderHeader() {
        const p=Core.controls(this._state).find(p=>p.id===this._selected),isGlobal=this._selected==='global-control';
        this._title.text=isGlobal?this._t('statusTitle'):p?Core.projectName(Copy,this._state,p):this._t('pendingProject');
        const syncing=Core.active(this._state).some(p=>p.syncing),source=isGlobal?this._settingsMode?this._t('preferences'):!this._online?this._t('extensionOffline'):this._state.enabled===false?this._t('monitorDisabled'):Core.isSyncing(this._state)?this._t('syncing'):Core.healthDetail(this._state)?this._t('statusUnavailable'):syncing?this._t('syncing'):this._t('allProjects'):p?.hostId && p.hostId!=='local'?this._t('remote',{host:p.hostLabel || p.hostId}):this._t('local');
        this._subtitle.text=source;this._headerIcon.set_child(isGlobal?label(this._state.statusEmoji || '🔦','signal-emoji'):projectIcon(p || {},Metrics['header-icon']));
        this._master._setValue(isGlobal?this._state.enabled!==false:p?.updatesEnabled!==false);this._master.accessible_name=isGlobal?this._t('monitorLabel'):this._t('projectSwitch',{project:p?.name || ''});
        this._settingsButton.visible=isGlobal;this._settingsButton.accessible_name=this._t(this._settingsTarget?'backToProjects':'settings');this._settingsButton.set_child(smallIcon(this._settingsTarget?'go-previous-symbolic':'emblem-system-symbolic'));this._reload.accessible_name=this._t('productionReload');
        const monitor=Main.layoutManager.primaryMonitor,scale=St.ThemeContext.get_for_stage(global.stage).scale_factor;this.menu.box.set_style(`width:${Math.min(Metrics['panel-w'],monitor.width/scale-2*Metrics['safe-gap'])}px;`);
        this._scroll.set_style(`max-height:${Math.max(80,Math.min(Metrics['panel-max-h']-80,(monitor.height-Main.panel.height)/scale-120))}px;`);
    }
    _chatRow(unit) {
        const c=unit.chat,actor=new St.BoxLayout({style_class:'signal-chat-row',clip_to_allocation:true}),dot=this._badge(c,true),copy=new St.BoxLayout({vertical:true,x_expand:true,y_align:Clutter.ActorAlign.CENTER,style_class:'signal-row-copy'}),title=text(c.title,'signal-chat-title'),detail=text('','signal-detail');copy.add_child(title);copy.add_child(detail);
        const body=new St.BoxLayout({style_class:'signal-row-open',x_expand:true});body.add_child(dot);body.add_child(copy);
        const open=button(body,this._t('openRow',{n:c.index,title:c.title}),()=>{this._send('open',c.id);this.menu.close(BoxPointer.PopupAnimation.FULL);});open.x_expand=true;
        const seen=button(smallIcon('object-select-symbolic'),this._t('seen'),()=>this._send('seen',c.id));seen.add_style_class_name('signal-control');actor.add_child(open);actor.add_child(seen);return {actor,dot,title,detail,open,seen};
    }
    _renderRows() {
        if(this._settingsMode || this._routeBusy)return;
        if(!this._routeAnimating){this._body.opacity=255;this._body.translation_y=0;}
        let units=this._online?Core.rows(this._state,this._selected):[];
        if(this._state.uiError)units=[{kind:'message',key:'error',message:this._state.uiError},...units];
        if(!units.length)units=[{kind:'message',key:'empty',message:this._online?this._state.enabled===false?this._t('monitorDisabled'):Core.healthDetail(this._state) || (this._state.connected?this._t('noChats'):this._state.detail):this._t('extensionOffline')}];
        const live=new Set(units.map(u=>u.key));this._focus=[];
        for(const [key,row] of this._rows)if(!live.has(key) && !row.actor._leaving){interactive(row.actor,false);this._motion.size(row.actor,false,true,()=>{if(row.actor._leaving){this._motion.forget(row.actor);row.actor.destroy();this._rows.delete(key);}});}
        units.forEach((unit,index)=>{
            let row=this._rows.get(unit.key),fresh=!row;
            if(!row) {
                if(unit.kind==='chat')row=this._chatRow(unit);
                else if(unit.kind==='project') {
                    const actor=new St.BoxLayout({style_class:'signal-project-row',clip_to_allocation:true}),title=text('','signal-project-title');title.x_expand=true;const icon=new St.Bin({y_align:Clutter.ActorAlign.CENTER}),toggle=this._switch(true,'',on=>this._send(on?'project_enable':'project_disable',unit.project.id));[icon,title,toggle].forEach(a=>actor.add_child(a));row={actor,title,icon,toggle};
                } else row={actor:label(unit.message,'signal-empty')};
                this._rows.set(unit.key,row);this._body.add_child(row.actor);
            }
            if(unit.kind==='chat') {
                const c=unit.chat;this._selected==='global-control'?row.actor.add_style_class_name('signal-grouped'):row.actor.remove_style_class_name('signal-grouped');this._updateBadge(row.dot,c);row.title.text=c.title;row.detail.text=c.status==='syncing'?this._t('syncing'):this._t(c.status)+' · '+Core.elapsed(Copy,this._state,c.since,Date.now()/1000);row.open.accessible_name=this._t('openRow',{n:c.index,title:c.title});row.seen.visible=!!c.canMarkSeen;row.seen.accessible_name=this._t('seenLabel',{n:c.index});this._focus.push(row.open);if(c.canMarkSeen)this._focus.push(row.seen);
            } else if(unit.kind==='project') {const p=unit.project;row.title.text=Core.projectName(Copy,this._state,p);row.icon.set_child(projectIcon(p,Metrics['header-icon']));row.toggle._setValue(p.updatesEnabled!==false);row.toggle.accessible_name=this._t('projectSwitch',{project:p.name});this._focus.push(row.toggle);}
            else row.actor.text=unit.message;
            this._body.set_child_at_index(row.actor,index);interactive(row.actor,true);
            if(fresh){row.actor.height=0;row.actor.opacity=0;this._motion.size(row.actor,true,true);}else if(row.actor._leaving)this._motion.size(row.actor,true,true);
        });
    }
    _clearBody() {
        for(const actor of this._body.get_children()){this._motion.forget(actor);actor.destroy();}
        this._rows.clear();this._settingsBody=null;this._settingsRows=null;
    }
    _route(target,keyboard) {
        const revision=++this._routeRevision;this._settingsTarget=target;this._routeBusy=true;this._routeAnimating=true;interactive(this._body,false);this._renderHeader();
        const start=this._body.opacity,translation=this._body.translation_y;
        this._motion.tween('route',keyboard?0:Contract.settingsMotion.out,p=>{this._body.opacity=Math.round(start*(1-p));this._body.translation_y=translation+(-Contract.settingsMotion.offset-translation)*p;},()=>{
            if(revision!==this._routeRevision)return;this._settingsMode=target;this._clearBody();this._routeBusy=false;
            this._renderHeader();target?this._renderSettings():this._renderRows();interactive(this._body,false);this._routeBusy=true;
            this._body.opacity=0;this._motion.tween('route',keyboard?0:Contract.settingsMotion.in,p=>{this._body.opacity=Math.round(255*p);this._body.translation_y=Contract.settingsMotion.offset*(1-p);},()=>{
                if(revision===this._routeRevision){this._routeBusy=false;this._routeAnimating=false;interactive(this._body,true);target?this._renderSettings():this._renderRows();}
            });
        });
    }
    _renderSettings() {
        if(!this._settingsBody){this._settingsBody=new St.BoxLayout({vertical:true,style_class:'signal-settings'});this._settingsRows=new Map();this._body.add_child(this._settingsBody);}
        if(!this._settingsRows.size) {
            this._menuSection=label('','signal-section');this._settingsBody.add_child(this._menuSection);
            const iconRow=new St.BoxLayout({style_class:'signal-setting-row'}),iconLabel=text('','signal-setting-title');iconLabel.x_expand=true;const icon=button(label('🔦','signal-emoji'),'Choose status emoji',()=>ExtensionUtils.openPrefs());iconRow.add_child(iconLabel);iconRow.add_child(icon);this._settingsBody.add_child(iconRow);this._settingsRows.set('icon',{title:iconLabel,button:icon});
            const create=(key,action)=>{const row=new St.BoxLayout({style_class:'signal-setting-row'}),title=text('','signal-setting-title');title.x_expand=true;const toggle=this._switch(false,'',action);row.add_child(title);row.add_child(toggle);this._settingsBody.add_child(row);this._settingsRows.set(key,{title,toggle});};
            create('compact',on=>this._send(on?'compact_enable':'compact_disable'));
            this._alertSection=label('','signal-section');this._settingsBody.add_child(this._alertSection);
            for(const phase of Contract.alertTypes)create(phase,on=>this._send(on?'notification_enable':'notification_disable',phase));
        }
        this._menuSection.text=this._t('menuBarSection');this._alertSection.text=this._t('alertSettings');this._focus=[];
        for(const [key,row] of this._settingsRows) {
            const name=this._t(key==='icon'?'statusIcon':key==='compact'?'statusButtonOnly':key==='completed'?'noticeCompleted':key);row.title.text=name;
            if(key==='icon'){row.button.get_child().text=this._state.statusEmoji || '🔦';row.button.accessible_name=this._t('chooseStatusEmoji');this._focus.push(row.button);}
            else {row.toggle._setValue(key==='compact'?!!this._state.compactMenuBar:(this._state.notificationStates || Contract.alertTypes).includes(key));row.toggle.accessible_name=key==='compact'?name:this._t('alertSwitch',{state:name});this._focus.push(row.toggle);}
        }
    }
    _showNotice(value) {
        if(Main.sessionMode.isLocked)return;
        this._dismissNotice('replaced',true);for(const old of this._outgoingNotices){this._motion.forget(old);old.destroy();}this._outgoingNotices.clear();const actor=new St.BoxLayout({vertical:true,style_class:'signal-notice'}),dot=this._badge(value.chat,true),copy=new St.BoxLayout({vertical:true,x_expand:true}),project=text('','signal-source'),status=text('','signal-header-title'),title=text('','signal-chat-title');[project,status,title].forEach(a=>copy.add_child(a));
        const bodyBox=new St.BoxLayout({style_class:'signal-notice-body'});bodyBox.add_child(dot);bodyBox.add_child(copy);
        const body=button(bodyBox,this._t('openNotice'),()=>{if(!this._notice || this._notice.value.id!==value.id)return;this._client.send({event:'notice_open',noticeId:value.id,threadId:value.chat.id});this._dismissNotice('opened');});body.x_expand=true;
        const close=button(label('×','signal-close'),this._t('dismissNotice'),()=>this._dismissNotice('dismissed'));close.add_style_class_name('signal-control');const line=new St.BoxLayout({style_class:'signal-notice-line'}),progress=new St.Widget({style_class:'signal-notice-progress',x_expand:true});progress.set_pivot_point(0,0);line.add_child(body);line.add_child(close);actor.add_child(line);actor.add_child(progress);Main.uiGroup.add_child(actor);
        this._notice={value,actor,project,status,title,began:GLib.get_monotonic_time()/1000};this._renderNotice();actor.opacity=0;const monitor=Main.layoutManager.primaryMonitor,scale=St.ThemeContext.get_for_stage(global.stage).scale_factor,width=Math.min(Contract.notice.width,monitor.width/scale-24);actor.set_style(`width:${width}px;`);actor.set_position(monitor.x+monitor.width-width*scale-12*scale,monitor.y+Main.panel.height+12*scale);
        this._motion.tween(actor,Contract.notice.motionSeconds,p=>{actor.opacity=Math.round(p*255);actor.translation_y=-Contract.notice.offset*(1-p);},()=>{
            if(!this._notice || this._notice.value.id!==value.id)return;
            this._notice.began=GLib.get_monotonic_time()/1000;
            this._client.send({event:'notice_shown',noticeId:value.id,source:value.source,uiLanguage:this._state.uiLanguage,becameKey:false,activatedApplication:false});
            this._noticeTimer=GLib.timeout_add(GLib.PRIORITY_DEFAULT,50,()=>{
                const left=1-(GLib.get_monotonic_time()/1000-this._notice.began)/(Contract.notice.holdSeconds*1000);progress.scale_x=Math.max(0,left);
                if(left<=0){this._noticeTimer=0;this._dismissNotice('expired');return GLib.SOURCE_REMOVE;}return GLib.SOURCE_CONTINUE;
            });
        });
    }
    _renderNotice() {const n=this._notice;if(!n)return;n.project.text=this._t('noticeProject',{project:n.value.project.name,n:n.value.chat.index});n.status.text=this._t(n.value.chat.status==='completed'?'noticeCompleted':n.value.chat.status);n.title.text=n.value.chat.title;}
    _dismissNotice(reason,immediate=false) {
        if(this._noticeTimer)GLib.Source.remove(this._noticeTimer);this._noticeTimer=0;
        const n=this._notice;this._notice=null;if(!n)return;interactive(n.actor,false);
        this._client?.send({event:'notice_closed',noticeId:n.value.id,source:n.value.source,reason,dwellMs:Math.max(0,GLib.get_monotonic_time()/1000-n.began),uiLanguage:this._state.uiLanguage});
        this._outgoingNotices.add(n.actor);const alpha=n.actor.opacity;this._motion.tween(n.actor,immediate?0:Contract.notice.motionSeconds,p=>{n.actor.opacity=Math.round(alpha*(1-p));n.actor.translation_y=-4*p;},()=>{this._motion.forget(n.actor);n.actor.destroy();this._outgoingNotices.delete(n.actor);});
    }
    shutdown() {
        this._destroyed=true;++this._routeRevision;this._dismissNotice('extension-disabled',true);this._spring.destroy();this._motion.destroy();for(const actor of this._outgoingNotices)actor.destroy();this._outgoingNotices.clear();this._client.stop();
        if(this._clock)GLib.Source.remove(this._clock);this._clock=0;
        this._settings.disconnect(this._iconSignal);Main.sessionMode.disconnect(this._sessionSignal);this.menu.sourceActor=this._originalSource;this.destroy();
    }
});
let indicator=null;
function init() {}
function enable() {indicator=new SignalIndicator();Main.panel.addToStatusArea('codex-signal',indicator,0,'right');}
function disable() {indicator?.shutdown();indicator=null;}
