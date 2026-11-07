"""Read only Codex's explicit UI language and share the HTML's interface copy."""
import json
import pathlib
import re
try:
    import tomllib
except ModuleNotFoundError:
    if __package__:
        from .vendor import tomli as tomllib
    else:
        from vendor import tomli as tomllib

COPY = json.loads((pathlib.Path(__file__).parent / 'interface-copy.generated.json').read_text())


def ui_language(setting):
    return 'zh-CN' if setting in ('zh-CN', 'zh-Hans') else 'en'


def text(key, language, **values):
    template = COPY[key][0 if language == 'zh-CN' else 1]
    return re.sub(r'\{(\w+)\}', lambda m: str(values.get(m[1], m[0])), template)


class DesktopLanguage:
    SOURCE = 'codex-config.desktop.localeOverride'

    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.signature = None
        self.setting = None
        self.error = None
        self.poll()

    @property
    def language(self):
        return ui_language(self.setting)

    def poll(self):
        try:
            stat = self.path.stat()
            signature = (stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
            # A same-length edit or atomic replacement can share a filesystem
            # timestamp. Read the selected value instead of trusting mtime.
            # Only the explicit language value survives this read. No config
            # contents or other settings are exposed, logged, or written.
            raw = tomllib.loads(self.path.read_text())
            value = raw.get('desktop', {}).get('localeOverride')
            if value is not None and not isinstance(value, str):
                raise ValueError('Invalid Codex locale setting')
        except FileNotFoundError:
            signature, value = None, None  # Automatic/absent => English.
        except (OSError, ValueError, TypeError, AttributeError):
            self.error = 'Could not read Codex language setting; retaining last valid value'
            return False
        changed = value != self.setting or self.error is not None
        self.setting, self.signature, self.error = value, signature, None
        return changed

    def metadata(self):
        result = {'source': self.SOURCE, 'value': self.setting}
        if self.error:
            result['error'] = self.error
        return result

CONNECTION_KEYS = {'正在连接 Codex': 'connection0', '监控已关闭': 'connection1', '菜单栏组件尚未编译': 'connection2', '本机通信权限不足': 'connection3', '等待 Codex 桌面启动': 'connection4', '正在同步当前聊天': 'connection5', '已连接当前 Codex 桌面': 'connection6', 'Codex 状态协议已变化，请更新插件': 'connection7', '菜单栏组件连接中断；状态服务仍在运行': 'connection8', '菜单栏组件未能保持运行；请从 Codex 桌面插件环境加载': 'connection9', '与 Codex 连接中断': 'connection10', '状态接口暂不可用，正在重连': 'connection11', '新版加载失败，已恢复先前插件版本': 'connection12'}

def connection_text(value, language):
    key = CONNECTION_KEYS.get(value)
    return text(key, language) if key else value

CONNECTION_KEYS.update({'找不到聊天链接处理器；请配置 codex:// 桌面入口':'linkHandlerMissing'})
