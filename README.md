# ErisPulse-AIChat 模块文档

## 简介
ErisPulse-AIChat 是一个简单的基于OpenAI的聊天机器人模块。

## 使用

安装本模块

```bash
ep install AIChat
```
安装完毕后首次加载模块时，会自动创建一个名为 `AIChat` 的配置文件，配置文件内容如下：

```toml
[AIChat]
bot_name = "用来触发机器人的关键词"
system_prompt = "系统提示词"
```

配置完毕后，即可使用本模块。
本模块依赖 ErisPulae 的 `OpenAI` 模块，以下是 `OpenAI` 模块的配置文件：

```toml
[OpenAI]
base_url = "https://api.openai.com/v1"
key = "密钥"
model = "使用的模型"

[OpenAI.Args]
temperature = 0.7
max_tokens = 1024
```

## 参考链接
- [ErisPulse 主库](https://github.com/ErisPulse/ErisPulse/)
