# Codex Signal 对话状态

**看一眼菜单栏，就知道哪个聊天需要你。** 只呈现当前 Codex 桌面正在使用的聊天，按项目分组。不是独立应用，不需要额外 API Key。

[English](README.md) · [安装与更新](docs/INSTALL.md) · [交给 Codex 安装](docs/INSTALL-WITH-CODEX.md) · [Ubuntu 测试版](docs/UBUNTU-BETA.md)

## 颜色告诉你下一步

项目使用黑底白字胶囊，保留原图标和名称；右侧每个彩色编号对应一个聊天。总入口在本插件一组最右侧，项目向左展开、向右收起。

| 颜色 | 状态 |
| --- | --- |
| 蓝 | 进行中 |
| 橙 | 等待授权 |
| 紫 | 等待你回答 |
| 绿 | 本轮完成、尚未查看 |
| 红 | 运行失败 |
| 灰 | 已停止 |
| 灰色虚线 | 状态未知或连接中断 |

- 单击项目打开面板，再次单击收回；点击编号或聊天行返回原聊天，授权仍在 Codex 处理。
- 完全展开项目胶囊，或**仅保留总入口**。收纳后总入口仍有汇总状态色，面板按项目显示详细聊天；完全展开时总面板只列项目。
- 总开关暂停全部状态更新，项目开关只暂停该项目，不停止任务。恢复时先同步真实状态，避免短暂错色。
- 在设置里选择哪些状态触发 **6 秒可点击提示**；正文打开聊天，× 只关闭提示。
- 总入口图标通过系统表情选择器自定义，默认 🔦。
- Codex 选简体中文时显示中文，其余语言显示英文；项目名、聊天名不翻译。
- 每个项目当前可见聊天从 1 连号，聊天 ID、历史 slot 与本地已看记录独立保存。

## 下载对应平台的插件包

- **Mac：**`codex-signal-v0.2.4-macos-arm64.zip`，Apple Silicon、macOS 14+、Python 3.10+、Codex 桌面 App。已带编译好的菜单栏组件，使用者不需要 Xcode。
- **Ubuntu 测试版：**`codex-signal-v0.2.4-ubuntu22.04-beta-noarch.zip`，GNOME Shell 42、Python 3.10+，以及你自己已经能运行的兼容 Codex 桌面构建。包含完整 Python/GJS 源码与伴生扩展，不含 Mac 可执行文件。

解压到长期保留的目录后运行：

```sh
./scripts/install.sh                       # Mac
./scripts/install.sh --with-gnome          # Ubuntu，明确同意安装顶栏伴生扩展
```

**不捆绑 Python。** 安装前检查环境，缺失时告诉你需要什么，不静默安装 Python、系统包或其他版本的 Codex，也不添加常驻服务。你可以把[安装提示词](docs/INSTALL-WITH-CODEX.md)交给 Codex，由它按你的权限补齐环境。

安装通过 Codex 的本地 marketplace 完成，不请求重启 Codex；继续新一轮聊天后检查实际加载状态。已有版本可用插件刷新按钮热加载已安装更新。首次插件发现是否即时生效取决于桌面宿主版本，不把安装成功等同于已经热加载。

**Mac 下载信任：**当前组件只有 ad-hoc 签名，未做 Developer ID 公证；从网络下载后仍可能被系统阻止。不要关闭 Gatekeeper 或移除隔离属性绕过。0.2.4 以预发布版提供，见[打包说明](docs/PACKAGING.md)。

**Ubuntu 验收：**代码已实现，尚未在 Ubuntu 桌面实机验收。官方当前 Linux 桌面支持列表不含 22.04；本测试版不代装或升级桌面 App。真实状态接口、自动已看、跳转、4K/多屏、Xorg/Wayland 由测试机按[清单](docs/UBUNTU-BETA.md)确认。

## 数据留在本机

覆盖本桌面运行时及其连接的远程聊天，不扫描全部历史或独立 CLI/IDE。状态流可能包含正文；适配器立即投影为元数据和生命周期，正文不落盘。插件不批准命令、不发消息、不写 Codex 已读回执。打开聊天后 Codex 可按自己的规则清除未读；插件“已看”只改变自己的提醒记录。

Mac 沿用 `~/Library/Application Support/CodexMenuStatus/`；Linux 使用 XDG 配置和状态目录。数据不随安装包分发。更多见[隐私说明](docs/PRIVACY.md)。

## 源码与发布

网格、动画参数、双语文案统一维护在 `codex-status-layout.html`，生成正式 Swift 和 GNOME 资源。构建/测试命令见[英文 README](README.md#build-and-test)。

名称 **Codex Signal**，许可 **MIT**，第三方 Tomli 的许可随包保留。仓库名 `codex-signal`；Mac 候选包与文件名明确带 `beta` 的 Ubuntu 包放在同一个预发布 Release，供审查和测试。社区项目，与 OpenAI 官方无隶属关系。
