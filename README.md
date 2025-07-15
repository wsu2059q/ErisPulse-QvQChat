# ErisPulse-AIChat 模块文档

## 简介
ErisPulse-AIChat 是一个基于OpenAI的智能聊天机器人模块，支持多种触发方式和上下文管理。

## 安装

```bash
ep install AIChat
```

## 配置
安装完毕后首次加载模块时，会自动创建一个名为 `AIChat` 的配置文件，配置文件内容如下：

```toml
[AIChat]
trigger_words = ["AI"]  # 触发词列表，可以是单个或多个
system_prompt = "你是一个AI助手，你叫AI，你是一个智能聊天机器人"
clear_command = "/clear"  # 清除历史记录指令
max_history_length = 10  # 最大历史消息长度
show_nickname = true  # 是否在消息前显示用户昵称
```

### 触发方式说明
1. **默认模式**:
   - 消息中包含任意触发词即可触发
   - 例如: "你好AI"、"AI你好"、"这个AI很聪明"

2. **通配符模式**:
   - 触发词列表中定义的触发词可以包含通配符 `*`/`?`
   - 例如: "AI*"、"AI?你好"

### 其他功能
- 使用 `/clear` 指令可以清除当前会话的历史记录
- 自动管理对话上下文，可配置最大历史消息长度
- 支持在消息前显示用户昵称，帮助AI区分不同用户

## 依赖
本模块依赖 ErisPulse 的 `OpenAI` 模块，以下是 `OpenAI` 模块的配置文件示例：

```toml
[OpenAI]
base_url = "https://api.openai.com/v1"
key = "您的API密钥"
model = "使用的模型"

[OpenAI.Args]
temperature = 0.7
max_tokens = 1024
```

## 参考链接
- https://github.com/ErisPulse/ErisPulse/