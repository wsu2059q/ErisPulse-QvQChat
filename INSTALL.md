# QvQChat 安装指南

## Docker 安装（ghcr 镜像）

### 一行启动

```bash
docker run -d --name qvqchat -p 8000:8000 --restart unless-stopped ghcr.io/wsu2059q/erispulse-qvqchat:latest
```

容器基于 `erispulse/erispulse` 官方镜像构建，已内置 QvQChat 模块。

### 安装适配器

在 Dashboard 中安装所需的平台适配器（OneBot11 / 云湖 / Telegram 等），连接配置一并填写。

### 打开 Dashboard

浏览器访问 `http://<服务器IP>:8000` 进入 Dashboard：

- **QvQChat → 模型池** — 添加 OpenAI 兼容模型（名称 / Base URL / API Key / 模型名）
- **QvQChat → 对话** — 直接测试智能体，工具可用
- **QvQChat → 设置** — 触发方式、安全级别、完全信任开关、生态桥过滤等（按分类导航）

独立访问：`http://<服务器IP>:8000/QvQChat/view`。装有 Dashboard 时自动复用其登录令牌；未装 Dashboard 时使用 QvQChat 自己的访问令牌（首次启动自动生成并打印在日志，或配置 `QvQChat.view_token` 固定）。

---

## 手动安装

```bash
# 推荐：SDK CLI
epsdk install ErisPulse-QvQChat

# 或 pip
pip install ErisPulse-QvQChat
```

要求：

- Python 3.10+
- ErisPulse >= 2.8.0（生态服务桥与交互会话依赖 2.8 的 `module.services` / `interaction`）
- 至少一个平台适配器（如 `epsdk install ErisPulse-OneBotAdapter`）

### 首次配置

1. 启动后打开 Dashboard 的 QvQChat 视窗
2. 「模型池」页添加模型并测试连通
3. 私聊或 @ 机器人即可对话

可选增强：装 [ErisPulse-Cron](https://github.com/wsu2059q/ErisPulse-Cron) 后 cron 定时任务自动交给它托管。装任意声明了 `meta.services` 的生态模块，智能体无需重启即获得对应工具（生图、语音合成、知识库等推荐做成独立扩展模块）；实现 `qvq_prompts` / `qvq_personas` / `qvq_schemas` 可进一步注入提示词、注册人格、精确定义参数，详见 README「扩展 QvQChat」。

---

## 开发者本地运行

```bash
git clone https://github.com/wsu2059q/ErisPulse-QvQChat
cd ErisPulse-QvQChat
pip install -e .[test]
pytest
```
