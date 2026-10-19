from __future__ import annotations

PROVIDER_PRESETS: list[dict] = [
    {"id": "openai", "name": "OpenAI", "base_url": "https://api.openai.com/v1"},
    {"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com/v1"},
    {"id": "siliconflow", "name": "SiliconFlow", "base_url": "https://api.siliconflow.cn/v1"},
    {"id": "moonshot", "name": "Moonshot (Kimi)", "base_url": "https://api.moonshot.cn/v1"},
    {"id": "zhipu", "name": "Zhipu (GLM)", "base_url": "https://open.bigmodel.cn/api/paas/v4"},
    {"id": "dashscope", "name": "Alibaba (Qwen)", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    {"id": "doubao", "name": "Volcengine (Doubao)", "base_url": "https://ark.cn-beijing.volces.com/api/v3"},
    {"id": "minimax", "name": "MiniMax", "base_url": "https://api.minimax.chat/v1"},
    {"id": "openrouter", "name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1"},
    {"id": "groq", "name": "Groq", "base_url": "https://api.groq.com/openai/v1"},
    {"id": "together", "name": "Together", "base_url": "https://api.together.xyz/v1"},
    {"id": "xai", "name": "xAI (Grok)", "base_url": "https://api.x.ai/v1"},
    {"id": "ollama", "name": "Ollama (local)", "base_url": "http://127.0.0.1:11434/v1"},
    {"id": "lmstudio", "name": "LM Studio (local)", "base_url": "http://127.0.0.1:1234/v1"},
    {"id": "custom", "name": "Custom", "base_url": ""},
]


def get_preset(preset_id: str) -> dict | None:
    for preset in PROVIDER_PRESETS:
        if preset["id"] == preset_id:
            return dict(preset)
    return None
