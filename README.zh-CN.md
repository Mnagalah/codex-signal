# Codex Signal 对话状态

**看一眼 Mac 菜单栏，就知道哪个聊天需要你。** Codex 桌面插件，按项目呈现近期正在使用的聊天；不是独立应用，不需要额外 API Key。

[English](README.md) · [安装](docs/INSTALL.md) · [隐私](docs/PRIVACY.md)

## 交给 Codex 安装

把仓库链接发给 Codex，说：**帮我安装这个插件：https://github.com/Mnagalah/codex-signal**

首次安装使用 [0.2.9 预编译 macOS 安装包](https://github.com/Mnagalah/codex-signal/releases/download/v0.2.9/codex-signal-v0.2.9-macos-arm64.zip)，适用于 Apple Silicon Mac、macOS 14+ 和 Codex 桌面。缺少 Python 3.10+ 时经授权准备；用户无需 Git、Xcode 或 pip 依赖。

**执行安装的 Codex 请遵循[安装指引](docs/INSTALL-WITH-CODEX.md)。** 下载并解压 Release ZIP，运行 `/bin/sh scripts/install.sh`，激活已安装的状态工具，再执行 `/bin/sh scripts/install.sh --verify`。只有 `stage: ready` 才算完成，注册成功不等于已能使用。安装和环境准备由一次性脚本完成，不安装或常驻首次设置技能。

**0.2.9 是用于全新 Mac 安装测试的 macOS 预发布版。** [版本说明](https://github.com/Mnagalah/codex-signal/releases/tag/v0.2.9)。

## 颜色告诉你下一步

| 颜色 | 状态 |
| --- | --- |
| 蓝 | 进行中 |
| 橙 | 等待授权 |
| 紫 | 等待你回答 |
| 绿 | 本轮完成、尚未查看 |
| 红 | 运行失败 |
| 灰 | 已停止 |
| 灰色虚线 | 状态未知或连接中断 |

- 黑色胶囊保留项目图标和名称，每个彩色编号对应一个聊天。总入口位于本插件一组最右侧，项目向左展开、向右收起。
- 单击项目展开面板，再次单击收回；编号、聊天行、提示正文都能打开原聊天，授权仍在 Codex 中处理。
- 选择完全展开或仅保留总入口；收纳后的入口继续用颜色表示汇总状态，面板按项目呈现详细聊天。
- 总开关和项目开关只暂停状态更新，不停止任务。恢复、启动和重连都重新核实本地及桌面连接的远程状态，不拿旧颜色当事实。
- 选择哪些状态触发六秒提示；× 只关闭提示。恢复后的第一份快照作为基线，不重放旧通知。
- 总入口图标使用系统 emoji 选择器自定义，默认 🔦。
- Codex 简体中文使用中文，其余语言使用英文；项目名与聊天名保持原文。
- 每个项目当前可见聊天从 1 连号；聊天 ID、历史 slot 和本地已看记录独立保存。
- 归档后退出显示，取消归档后重新获取状态；只读核对已确认的本地删除。远程离线不当成删除。

## 数据与使用条件

记录沿用 `~/Library/Application Support/CodexMenuStatus/`。状态流可能带正文，适配器立即投影为必要元数据并丢弃正文，不落盘。插件不批准命令、不发消息、不启停任务，也不写 Codex 已读回执。私人记录和截图不进入安装包。

Python 不内置，Tomli 已随包提供；用户无需 pip 依赖或 Xcode。Mac 组件当前为 ad-hoc 签名，尚未 Developer ID 公证；下载信任与完整退出重开需要独立实机验收，不关闭系统安全机制。[兼容性](docs/COMPATIBILITY.md)。

## 源码与发布

网格、动画和双语文案统一维护在 `codex-status-layout.html`，生成原生资源。源码构建需要 Swift 6.2+，测试和打包命令见英文 README。保持单一业务源码，开发部署通过脚本导出，不维护安装缓存分叉。

项目名 Codex Signal，仓库 `codex-signal`，许可 MIT。社区项目，与 OpenAI 无隶属关系。
