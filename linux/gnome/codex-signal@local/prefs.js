const {Gtk,GLib} = imports.gi;
const ExtensionUtils=imports.misc.extensionUtils;
function init() {}
function buildPrefsWidget() {
    const settings=ExtensionUtils.getSettings(),zh=settings.get_string('current-language')==='zh-CN';
    const box=new Gtk.Box({orientation:Gtk.Orientation.VERTICAL,spacing:16,margin_top:24,margin_bottom:24,margin_start:24,margin_end:24});
    const button=new Gtk.Button({label:settings.get_string('current-icon'),halign:Gtk.Align.CENTER});
    button.set_tooltip_text(zh?'选择入口图标':'Choose status emoji');
    box.append(new Gtk.Label({label:zh?'Codex Signal · 入口图标':'Codex Signal · Status icon'}));box.append(button);
    const chooser=new Gtk.EmojiChooser();chooser.set_parent(button);
    chooser.connect('emoji-picked',(_,emoji)=>{settings.set_string('icon-request',emoji);button.set_label(emoji);});
    button.connect('clicked',()=>chooser.popup());
    let source=0;
    box.connect('map',()=>{source=GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE,()=>{source=0;chooser.popup();return GLib.SOURCE_REMOVE;});});
    box.connect('unmap',()=>{if(source)GLib.Source.remove(source);source=0;chooser.popdown();});
    return box;
}
