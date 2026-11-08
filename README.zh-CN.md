# Codex Signal

Codex Signal 是面向 Codex 桌面端的 macOS 菜单栏插件，按项目汇总当前对话，显示运行、待授权、待回复和完成状态。

[English](README.md) · [下载](https://github.com/Mnagalah/codex-signal/releases) · [安装说明](docs/INSTALL.md)

## 核心功能

- 集中查看本地对话及 Codex 桌面端已连接的远程对话状态。
- 从菜单栏打开对应对话，并选择需要提醒的状态变化。
- 根据阅读、归档及已确认的本地删除同步完成提醒和对话列表。
- 支持全局或按项目暂停状态更新，提供简体中文和英文界面。

## 安装

预编译安装包适用于 Apple Silicon Mac，要求 macOS 14 及以上、Codex 桌面端和 Python 3.10 及以上。

可以将仓库链接交给 Codex：

> 帮我安装 Codex Signal：https://github.com/Mnagalah/codex-signal

Codex 可按[安装指引](docs/INSTALL-WITH-CODEX.md)完成下载、环境准备与插件校验。安装程序会复用可用的 Python 解释器；缺少运行环境时，经你确认后协助配置。

当前预发布版本为 [v0.2.9](https://github.com/Mnagalah/codex-signal/releases/tag/v0.2.9)，原生组件采用 ad-hoc 签名。平台与签名情况见[兼容性说明](docs/COMPATIBILITY.md)。

## 技术实现

Python 后端通过标准输入输出提供 MCP 服务，并通过 Codex 桌面端的本地 IPC 连接读取对话状态。远程对话状态由桌面端连接提供。

Swift/AppKit 原生组件负责菜单栏展示与交互，通过标准输入输出与后端交换逐行 JSON 格式的状态和操作数据。

启动程序使用安装时校验并记录的 Python 路径。首次通过 ZIP 安装时，插件包会复制到按版本管理的专用目录。设置、对话标识及提醒记录保存在本机，对话正文不写入这些记录。详见[隐私说明](docs/PRIVACY.md)。

## 开发

源码构建需要 macOS、Swift 6.2 及以上、Python 3.10 及以上和 Apple 命令行开发工具。项目结构、测试与构建命令见[贡献指南](CONTRIBUTING.md)，发行流程见[打包说明](docs/PACKAGING.md)。

## 许可证

本项目由社区独立维护，采用 [MIT 许可证](LICENSE)。第三方组件说明见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。
