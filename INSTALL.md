# QvQChat 安装教程

## 目录

- [前置条件](#前置条件)
- [方式一：Docker 安装（推荐）](#方式一docker-安装推荐)
  - [步骤 0：克隆代码仓库](#步骤-0克隆代码仓库)
  - [步骤 1：准备配置文件](#步骤-1准备配置文件)
  - [步骤 2：启动容器](#步骤-2启动容器)
  - [步骤 3：配置适配器（重要）](#步骤-3配置适配器重要)
  - [步骤 4：查看日志](#步骤-4查看日志)
  - [详细配置](#详细配置)
  - [常用命令](#常用命令)
- [方式二：手动安装](#方式二手动安装)
  - [步骤 0：克隆代码仓库](#步骤-0克隆代码仓库-1)
  - [步骤 1：安装 ErisPulse 框架](#步骤-1安装-erispulse-框架)
  - [步骤 2：安装适配器](#步骤-2安装适配器)
  - [步骤 3：安装 QvQChat 模块](#步骤-3安装-qvqchat-模块)
  - [步骤 4：配置](#步骤-4配置)
  - [步骤 5：准备适配器服务](#步骤-5准备适配器服务)
  - [步骤 6：启动](#步骤-6启动)
- [适配器配置指南](#适配器配置指南)
  - [OneBotv11 适配器（推荐）](#onebotv11-适配器推荐)
  - [云湖适配器](#云湖适配器)
- [配置文件说明](#配置文件说明)
  - [基础配置](#基础配置)
  - [AI 配置](#ai-配置)
  - [安全防护](#安全防护)
- [常见问题](#常见问题)

---

## 前置条件

### 必需条件
- **Python 版本**：3.10 或更高
- **操作系统**：Linux、macOS 或 Windows
- **网络访问**：需要访问 AI API（OpenAI 或兼容服务）

### 可选条件
- **Docker**：20.10+（仅 Docker 安装需要）
- **Docker Compose**：2.0+（仅 Docker Compose 安装需要）

---

## 方式一：Docker 安装（推荐）

Docker 安装方式提供完整的环境隔离，易于部署和迁移。

### 步骤 0：克隆代码仓库

首先，克隆 QvQChat 代码仓库到本地：

```bash
# 使用 HTTPS 克隆
git clone https://github.com/wsu2059q/ErisPulse-QvQChat.git

# 或使用 SSH 克隆（如果配置了 SSH 密钥）
git clone git@github.com:wsu2059q/ErisPulse-QvQChat.git

# 进入项目目录
cd ErisPulse-QvQChat
```

**如果代码已下载**：直接进入项目目录即可，跳过此步骤。

### 步骤 1：准备配置文件

复制示例配置文件：

```bash
cp config.example.toml config.toml
```

编辑 `config.toml`，至少配置以下内容：

```toml
[QvQChat]
bot_nicknames = ["Amer"]  # 你的机器人昵称
bot_ids = ["123456789"]    # 你的机器人QQ号

[QvQChat.dialogue]
base_url = "https://api.openai.com/v1"  # 或使用中转服务
api_key = "sk-your-actual-api-key-here"  # 填入你的API密钥
model = "gpt-4o"  # 建议使用支持视觉的模型
```

### 步骤 2：启动容器

**使用 Docker Compose（推荐）**：

```bash
docker-compose up -d
```

**使用 Docker 命令**：

```bash
# 构建镜像
docker build -t erispulse-qvqchat .

# 运行容器
docker run -d \
  --name erispulse-qvqchat \
  -p 8000:8000 \
  -v $(pwd)/config.toml:/app/config.toml \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  erispulse-qvqchat
```

### 步骤 3：配置适配器（重要）

⚠️ **关键步骤**：QvQChat 需要通过适配器连接到消息平台（如 QQ、云湖等），必须正确配置适配器连接。

##### 3.1 选择适配器

根据你的使用场景选择合适的适配器：

| 适配器 | 适用平台 | 模式 | 推荐度 |
|--------|---------|------|--------|
| OneBotv11 | QQ (Lagrange、NapCat 等) | Client/Server | ⭐⭐⭐⭐⭐ |
| Yunhu | 云湖 | Server | ⭐⭐⭐⭐ |
| Telegram | Telegram | Server | ⭐⭐⭐ |

##### 3.2 配置 OneBotv11 适配器（QQ）

OneBotv11 有两种连接模式：

**Client 模式（推荐）**：QvQChat 作为客户端连接到 OneBotv11 服务

编辑 `config.toml`：

```toml
[OneBotv11_Adapter]
mode = "client"  # 客户端模式

[OneBotv11_Adapter.client]
url = "ws://your-onebot-server:port"  # OneBotv11 服务器地址
token = "your-access-token"  # 访问令牌
```

**示例配置**（使用 NapCat）：

```toml
[OneBotv11_Adapter]
mode = "client"

[OneBotv11_Adapter.client]
url = "ws://192.168.1.100:3001"
token = "8_abc123def456"
```

**Server 模式**：OneBotv11 服务作为客户端连接到 QvQChat

```toml
[OneBotv11_Adapter]
mode = "server"  # 服务端模式

[ErisPulse.server]
host = "0.0.0.0"
port = 8000

[OneBotv11_Adapter.server]
path = "/onebot"  # WebSocket 路径
```

##### 3.3 配置云湖适配器

编辑 `config.toml`：

```toml
[Yunhu_Adapter]
token = "your-yunhu-token"

[Yunhu_Adapter.server]
path = "/webhook"  # Webhook 路径
```

##### 3.4 配置适配器启用状态

确保在 `config.toml` 中启用对应的适配器：

```toml
[ErisPulse.adapters.status]
onebot11 = true   # 启用 OneBotv11
yunhu = true      # 启用云湖
```

##### 3.5 准备外部服务

根据选择的适配器，你需要准备对应的外部服务：

**OneBotv11 服务推荐**：
- [NapCat](https://github.com/NapNeko/NapCatQQ) - QQ NT 官方协议适配器（推荐）
- [Lagrange](https://github.com/LagrangeDev/Lagrange.Core) - 高性能 QQ 适配器

**云湖服务**：
- 登录 [云湖平台](https://www.yhchat.com/control) 获取 webhook token

##### 3.6 网络连接注意事项

Docker 容器内的网络访问配置：

```yaml
# docker-compose.yml
services:
  qvqchat:
    networks:
      - qvqchat-network
    # 使用 host 网络模式（可选，直接访问宿主机网络）
    # network_mode: "host"

networks:
  qvqchat-network:
    driver: bridge
```

**注意事项**：
- Client 模式下，容器需要访问外部 OneBotv11 服务，确保网络可达
- 使用 `host` 网络模式可以让容器直接访问宿主机网络
- 如果 OneBotv11 服务在同一宿主机，建议使用 `host` 模式或使用 `host.docker.internal`（Linux 需要额外配置）

### 步骤 4：查看日志

```bash
# Docker Compose
docker-compose logs -f qvqchat

# Docker 命令
docker logs -f erispulse-qvqchat
```

### 详细配置

#### 环境变量

在 `docker-compose.yml` 中可以配置环境变量：

```yaml
environment:
  - TZ=Asia/Shanghai  # 时区设置
  - PYTHONUNBUFFERED=1  # Python 输出无缓冲
```

#### 卷挂载说明

| 卷 | 说明 | 示例 |
|-----|------|--------|
| config.toml | 主配置文件 | `./config.toml:/app/config.toml` |
| config/ | 运行时配置 | `./config:/app/config` |
| data/ | 数据持久化 | `./data:/app/data` |
| logs/ | 日志文件 | `./logs:/app/logs` |

#### 端口映射

根据 ErisPulse 配置调整端口映射：

```yaml
ports:
  - "8000:8000"  # Web 服务器端口
```

### 常用命令

#### Docker Compose 命令

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose stop

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f

# 进入容器调试
docker-compose exec qvqchat /bin/bash

# 更新代码后重新构建
docker-compose up -d --build
```

#### Docker 命令

```bash
# 查看运行中的容器
docker ps

# 查看容器日志
docker logs -f erispulse-qvqchat

# 进入容器
docker exec -it erispulse-qvqchat /bin/bash

# 停止容器
docker stop erispulse-qvqchat

# 启动容器
docker start erispulse-qvqchat

# 重启容器
docker restart erispulse-qvqchat

# 删除容器
docker rm erispulse-qvqchat

# 删除镜像
docker rmi erispulse-qvqchat
```

---

## 方式二：手动安装

手动安装方式适合开发环境或需要自定义配置的场景。

### 步骤 0：克隆代码仓库

首先，克隆 QvQChat 代码仓库到本地：

```bash
# 使用 HTTPS 克隆
git clone https://github.com/wsu2059q/ErisPulse-AIChat.git

# 或使用 SSH 克隆（如果配置了 SSH 密钥）
git clone git@github.com:wsu2059q/ErisPulse-AIChat.git

# 进入项目目录
cd ErisPulse-AIChat
```

**如果代码已下载**：直接进入项目目录即可，跳过此步骤。

### 步骤 1：安装 ErisPulse 框架

```bash
pip install erispulse
```

或使用国内镜像加速：

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple erispulse
```

### 步骤 2：安装适配器

根据需要选择并安装适配器：

```bash
# QQ 适配器（推荐）
epsdk install OneBot11

# 其他适配器
epsdk install Telegram  # Telegram
epsdk install Yunhu     # 云湖
```

**说明**：`epsdk` 是 ErisPulse 提供的命令行工具，会自动处理依赖安装。

### 步骤 3：安装 QvQChat 模块

```bash
# 使用 ep sdk 安装
epsdk install QvQChat
```

### 步骤 4：配置

#### 4.1 创建配置文件

如果不存在配置文件，复制示例配置：

```bash
cp config.example.toml config.toml
```

#### 4.2 编辑配置文件

编辑 `config.toml`，至少配置以下内容：

```toml
[QvQChat]
bot_nicknames = ["Amer"]  # 你的机器人昵称（列表）
bot_ids = ["123456789"]    # 你的机器人QQ号（列表）

[QvQChat.dialogue]
base_url = "https://api.openai.com/v1"  # API 地址
api_key = "sk-your-actual-api-key-here"  # 填入你的API密钥
model = "gpt-4o"  # 模型名称
```

#### 4.3 配置适配器

详细配置请参考下方的[适配器配置指南](#适配器配置指南)。

**OneBotv11 适配器（QQ）**：

```toml
[OneBotv11_Adapter]
mode = "client"  # 客户端模式

[OneBotv11_Adapter.client]
url = "ws://your-onebot-server:port"
token = "your-access-token"
```

**云湖适配器**：

```toml
[Yunhu_Adapter]
token = "your-yunhu-token"

[Yunhu_Adapter.server]
path = "/webhook"
```

**适配器启用状态**：

```toml
[ErisPulse.adapters.status]
onebot11 = true   # 启用 OneBotv11
yunhu = true      # 启用云湖
```

**详细配置选项**：查看 [config.example.toml](config.example.toml) 获取所有配置项。

### 步骤 5：准备适配器服务

根据选择的适配器，启动对应的外部服务：

**OneBotv11 服务**：
- 下载并配置 NapCat、Lagrange 或 go-cqhttp
- 确保服务运行并可被 QvQChat 访问
- 记录服务的地址和 token

**云湖服务**：
- 登录云湖平台获取 webhook token
- 配置 webhook 推送地址

### 步骤 6：启动

#### 6.1 初始化 ErisPulse

```bash
ep-init
```

#### 6.2 启动 ErisPulse

```bash
ep run
```

#### 6.3 检查日志

启动后，查看日志确保 QvQChat 正常加载：

```
[INFO] QvQChat 模块已初始化
[INFO] 已配置的AI: dialogue, memory, intent
[INFO] OneBotv11 适配器已连接 (Client模式)
[INFO] QvQChat 模块已启动
```

---

## 配置文件说明

### 基础配置

```toml
[QvQChat]
# 机器人基本信息
bot_nicknames = ["Amer", "Ying"]  # 机器人昵称列表
bot_ids = ["123456789", "987654321"]  # 机器人QQ号列表

# 记忆配置
max_history_length = 20  # 最大会话历史长度
memory_cleanup_interval = 86400  # 记忆清理间隔（秒）
max_memory_tokens = 10000  # 最大记忆tokens数

# 安全防护
max_message_length = 1000  # 忽略长度超过此值的消息（防止刷屏）
rate_limit_tokens = 20000  # 短时间内允许的最大token数
rate_limit_window = 60  # 时间窗口（秒）
```

### AI 配置

#### 对话 AI（必需）

```toml
[QvQChat.dialogue]
base_url = "https://api.openai.com/v1"  # API 地址
api_key = "sk-your-api-key"  # API 密钥
model = "gpt-4o"  # 模型名称
temperature = 0.7  # 温度参数（0-1，越高越随机）
max_tokens = 500  # 最大输出tokens数
system_prompt = "你是..."  # 系统提示词
```

#### 记忆 AI（可选）

```toml
[QvQChat.memory]
model = "gpt-3.5-turbo"  # 使用不同模型
temperature = 0.3  # 更低温度，更确定性
max_tokens = 1000  # 允许更多输出
# api_key 和 base_url 可留空，自动复用 dialogue 配置
```

#### 意图识别 AI（可选）

```toml
[QvQChat.intent]
model = "gpt-3.5-turbo"
temperature = 0.1  # 很低温度，明确识别
max_tokens = 500
```

#### 视觉 AI（可选）

```toml
[QvQChat.vision]
base_url = "https://api.siliconflow.cn/v1"
api_key = "sk-xxx"  # 可以独立配置
model = "Qwen/Qwen3-VL-8B-Instruct"
temperature = 0.3
max_tokens = 300
```

#### 语音合成（可选）

```toml
[QvQChat.voice]
enabled = true  # 启用语音功能
api_key = "sk-xxx"  # 语音API密钥
api_url = "https://api.siliconflow.cn/v1/audio/speech"
model = "FunAudioLLM/CosyVoice2-0.5B"
voice = "speech:amer:nu5h6ye36m:ahldwvelhofwpcqcxoky"  # 音色ID
platforms = ["qq", "onebot11"]  # 支持的平台
```

### 安全防护

```toml
[QvQChat]
# 消息长度限制
max_message_length = 1000  # 忽略长度超过此值的消息

# 速率限制
rate_limit_tokens = 20000  # 60秒内允许的最大token数
rate_limit_window = 60  # 时间窗口（秒）

# 窥屏模式限制（群聊）
[QvQChat.stalker_mode]
enabled = true  # 启用窥屏模式
default_probability = 0.03  # 默认回复概率（3%）
max_replies_per_hour = 8  # 每小时最多回复次数
min_messages_between_replies = 15  # 两次回复间隔消息数
```

---

## 适配器配置指南

适配器是 QvQChat 与消息平台（如 QQ、云湖等）之间的桥梁，正确配置适配器是使用 QvQChat 的关键。

### 适配器连接模式

适配器有两种连接模式：

| 模式 | 说明 | 适用场景 | 推荐度 |
|------|------|----------|--------|
| Client | QvQChat 作为客户端，主动连接到适配器服务 | 适配器服务已运行，地址稳定 | ⭐⭐⭐⭐⭐ |
| Server | QvQChat 作为服务端，等待适配器连接 | QvQChat 作为中心服务，适配器主动推送 | ⭐⭐⭐ |

### OneBotv11 适配器（QQ）

OneBotv11 是 QQ 机器人最常用的适配器协议，支持多个实现。

#### 推荐的 OneBotv11 实现

| 名称 | 协议版本 | 特点 | 推荐度 |
|------|---------|------|--------|
| NapCat | OneBot v11 | QQ NT 官方协议，稳定、功能全 | ⭐⭐⭐⭐⭐ |
| Lagrange | OneBot v11 | 高性能、低延迟 | ⭐⭐⭐⭐ |

#### Client 模式配置（推荐）

适用场景：OneBotv11 服务已经运行在服务器上

```toml
[OneBotv11_Adapter]
mode = "client"  # 客户端模式

[OneBotv11_Adapter.client]
url = "ws://192.168.1.100:3001"  # OneBotv11 WebSocket 地址
token = "your-access-token"      # 访问令牌（如有）
```

**配置说明**：
- `url`：OneBotv11 的 WebSocket 服务器地址，格式：`ws://ip:port` 或 `ws://domain:port`
- `token`：访问令牌，防止未授权连接（在 OneBotv11 配置中设置）

#### Server 模式配置

适用场景：QvQChat 作为服务端，等待 OneBotv11 连接

```toml
[OneBotv11_Adapter]
mode = "server"  # 服务端模式

[ErisPulse.server]
host = "0.0.0.0"  # 监听所有网卡
port = 8000        # 端口号

[OneBotv11_Adapter.server]
path = "/onebot"  # WebSocket 路径
```

**配置说明**：
- QvQChat 会在 `0.0.0.0:8000/onebot` 上等待连接
- OneBotv11 需要配置反向 WebSocket 地址为 `ws://your-server-ip:8000/onebot`

#### NapCat 配置示例

NapCat 配置文件 `config/onebot_11.json`：

```json
{
  "http": {
    "enable": false
  },
  "ws": {
    "enable": true,
    "host": "0.0.0.0",
    "port": 3001
  },
  "token": "your-access-token"
}
```

### 云湖适配器

云湖是即时通讯平台，通过 webhook 接收消息。

#### 配置

```toml
[Yunhu_Adapter]
token = ""  # 云湖提供的 token

[Yunhu_Adapter.server]
path = "/webhook"  # Webhook 路径
```

#### 配置云湖平台

1. 登录 [云湖平台](https://www.yhchat.com/control)
2. 选择对应的机器人
3. 设置 webhook 地址为：`http://your-server-ip:8000/webhook`
4. 复制机器人 token 到 `config.toml`

### Telegram 适配器

通过 Telegram Bot API 接收消息。

#### 获取 Telegram Bot Token

1. 与 [@BotFather](https://t.me/BotFather) 对话
2. 发送 `/newbot` 创建新机器人
3. 按提示设置机器人名称和用户名
4. 复制生成的 API Token

### 适配器启用状态

无论使用哪种适配器，都需要在配置文件中启用对应适配器：

```toml
[ErisPulse.adapters.status]
onebot11 = true    # 启用 OneBotv11
yunhu = true       # 启用云湖
telegram = true    # 启用 Telegram
```

### 网络连接配置

#### Docker 部署

**Client 模式 - 访问外部 OneBotv11 服务**：

```yaml
# docker-compose.yml
services:
  qvqchat:
    networks:
      - qvqchat-network
    # 如果 OneBotv11 服务在同一宿主机，可以使用 host 网络模式
    network_mode: "host"

networks:
  qvqchat-network:
    driver: bridge
```

**Server 模式 - 等待适配器连接**：

```yaml
# docker-compose.yml
services:
  qvqchat:
    ports:
      - "8000:8000"  # 映射端口到宿主机
```

#### 手动部署

确保防火墙开放对应端口：

```bash
# Linux (ufw)
sudo ufw allow 8000/tcp

# Linux (firewalld)
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
```

### 适配器调试

#### 查看适配器连接状态

启动后查看日志：

```
[INFO] OneBotv11 适配器已连接 (Client模式) - ws://192.168.1.100:3001
[INFO] 云湖适配器 Webhook 已注册 - /webhook
```

#### 常见连接问题

**Q: 连接失败 "Connection refused"**

检查：
1. OneBotv11 服务是否启动
2. URL 地址是否正确
3. 防火墙是否开放端口
4. 网络是否可达（尝试 `telnet ip port`）

**Q: 认证失败 "Unauthorized"**

检查：
1. token 是否与 OneBotv11 配置一致
2. token 是否有特殊字符需要转义

**Q: 消息收不到**

检查：
1. 适配器是否已启用（`[ErisPulse.adapters.status]`）
2. bot_ids 是否正确配置
3. 是否在支持的群组/私聊中

### 多适配器配置

可以同时配置多个适配器，QvQChat 会自动管理所有连接：

```toml
# 同时使用 QQ 和云湖
[OneBotv11_Adapter]
mode = "client"
[OneBotv11_Adapter.client]
url = "ws://192.168.1.100:3001"

[Yunhu_Adapter]
token = "yunhu-token-xxx"
[Yunhu_Adapter.server]
path = "/webhook"

[ErisPulse.adapters.status]
onebot11 = true
yunhu = true
```

---

## 常见问题

### Q: Docker 安装后无法连接适配器？

**A**: 检查以下几点：
1. 端口映射是否正确（`docker-compose.yml` 的 `ports` 部分）
2. 适配器配置是否正确（`config.toml` 中对应的配置）
3. 网络连接是否正常（`docker network ls` 查看网络）
4. 查看容器日志：`docker logs -f erispulse-qvqchat`

### Q: 如何更新 QvQChat 到最新版本？

**A**:
- Docker 方式：`docker-compose pull` 然后 `docker-compose up -d`
- 手动方式：`epsdk update QvQChat`

### Q: 如何查看详细日志？

**A**:
- Docker：`docker-compose logs -f qvqchat`
- 手动：查看 `logs/` 目录下的日志文件

### Q: 配置文件修改后需要重启吗？

**A**: 需要。修改配置文件后，需要重启服务：
- Docker：`docker-compose restart qvqchat`
- 手动：停止后重新运行 `ep run`

### Q: 如何测试 AI 配置是否正确？

**A**:
1. 检查启动日志，查看是否有 "已配置的AI" 输出
2. 发送测试消息，观察是否正常回复
3. 查看日志，确认 API 调用成功

### Q: 支持哪些 AI 服务商？

**A**:
- OpenAI（官方 API）
- 兼容 OpenAI API 的第三方服务（如 SiliconFlow、DeepSeek 等）
- 只需要提供 `base_url` 和 `api_key` 即可

### Q: 如何降低 API 成本？

**A**:
1. 使用更便宜的模型（如 `gpt-3.5-turbo`）
2. 合理设置 `max_tokens` 限制输出长度
3. 启用速率限制和消息长度限制
4. 使用第三方中转服务（如 SiliconFlow）
5. 配置窥屏模式，减少不必要的回复

### Q: Docker 容器内如何调试？

**A**:
```bash
# 进入容器
docker exec -it erispulse-qvqchat /bin/bash

# 安装调试工具
pip install ipython

# 运行 Python 交互
ipython

# 或直接运行 ep 命令
ep status  # 查看 ErisPulse 状态
```

### Q: 如何备份数据？

**A**:
- Docker：挂载的卷会自动持久化到宿主机目录
- 手动：定期备份 `config/` 和 `data/` 目录
- 导出记忆：使用模块提供的导出命令（如有）

### Q: 如何卸载？

**A**:
- Docker：
  ```bash
  docker-compose down
  docker-compose rm -v  # 删除容器和卷
  ```
- 手动：
  ```bash
  epsdk uninstall QvQChat
  ```

---

## 下一步

安装完成后，建议阅读以下文档：

- [README.md](README.md) - 功能介绍和快速开始
- [config.example.toml](config.example.toml) - 完整配置选项
- [ARCHITECTURE.md](ARCHITECTURE.md) - 系统架构和技术细节

## 获取帮助

- GitHub Issues: https://github.com/wsu2059q/ErisPulse-QvQChat/issues
- 邮箱：wsu2059@qq.com
- QQ群：871684833

---

**最后更新**：2025-12-28
