from __future__ import annotations

PROVIDER_PRESETS: list[dict] = [
    {"id": "openai", "name": "OpenAI", "base_url": "https://api.openai.com/v1", "domain": "openai.com"},
    {"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "domain": "deepseek.com"},
    {"id": "siliconflow", "name": "SiliconFlow", "base_url": "https://api.siliconflow.cn/v1", "domain": "siliconflow.cn"},
    {"id": "moonshot", "name": "Moonshot (Kimi)", "base_url": "https://api.moonshot.cn/v1", "domain": "moonshot.cn"},
    {"id": "zhipu", "name": "Zhipu (GLM)", "base_url": "https://open.bigmodel.cn/api/paas/v4", "domain": "bigmodel.cn"},
    {"id": "dashscope", "name": "Alibaba (Qwen)", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "domain": "aliyun.com"},
    {"id": "doubao", "name": "Volcengine (Doubao)", "base_url": "https://ark.cn-beijing.volces.com/api/v3", "domain": "volcengine.com"},
    {"id": "minimax", "name": "MiniMax", "base_url": "https://api.minimax.chat/v1", "domain": "minimaxi.com"},
    {"id": "hunyuan", "name": "Tencent (Hunyuan)", "base_url": "https://api.hunyuan.cloud.tencent.com/v1", "domain": "tencent.com"},
    {"id": "qianfan", "name": "Baidu (Qianfan)", "base_url": "https://qianfan.baidubce.com/v2", "domain": "baidu.com"},
    {"id": "spark", "name": "iFlytek (Spark)", "base_url": "https://spark-api-open.xf-yun.com/v1", "domain": "xfyun.cn"},
    {"id": "stepfun", "name": "StepFun", "base_url": "https://api.stepfun.com/v1", "domain": "stepfun.com"},
    {"id": "yi", "name": "01.AI (Yi)", "base_url": "https://api.lingyiwanwu.com/v1", "domain": "lingyiwanwu.com"},
    {"id": "baichuan", "name": "Baichuan", "base_url": "https://api.baichuan-ai.com/v1", "domain": "baichuan-ai.com"},
    {"id": "sensenova", "name": "SenseNova", "base_url": "https://api.sensenova.cn/compatible-mode/v1", "domain": "sensetime.com"},
    {"id": "modelscope", "name": "ModelScope", "base_url": "https://api-inference.modelscope.cn/v1", "domain": "modelscope.cn"},
    {"id": "openrouter", "name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "domain": "openrouter.ai"},
    {"id": "groq", "name": "Groq", "base_url": "https://api.groq.com/openai/v1", "domain": "groq.com"},
    {"id": "together", "name": "Together", "base_url": "https://api.together.xyz/v1", "domain": "together.ai"},
    {"id": "fireworks", "name": "Fireworks", "base_url": "https://api.fireworks.ai/inference/v1", "domain": "fireworks.ai"},
    {"id": "deepinfra", "name": "DeepInfra", "base_url": "https://api.deepinfra.com/v1/openai", "domain": "deepinfra.com"},
    {"id": "cerebras", "name": "Cerebras", "base_url": "https://api.cerebras.ai/v1", "domain": "cerebras.ai"},
    {"id": "nebius", "name": "Nebius", "base_url": "https://api.studio.nebius.com/v1", "domain": "nebius.com"},
    {"id": "novita", "name": "Novita", "base_url": "https://api.novita.ai/v3/openai", "domain": "novita.ai"},
    {"id": "hyperbolic", "name": "Hyperbolic", "base_url": "https://api.hyperbolic.xyz/v1", "domain": "hyperbolic.xyz"},
    {"id": "nvidia", "name": "NVIDIA NIM", "base_url": "https://integrate.api.nvidia.com/v1", "domain": "nvidia.com"},
    {"id": "mistral", "name": "Mistral", "base_url": "https://api.mistral.ai/v1", "domain": "mistral.ai"},
    {"id": "gemini", "name": "Google (Gemini)", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "domain": "gemini.google.com"},
    {"id": "azure", "name": "Azure OpenAI", "base_url": "https://{resource}.openai.azure.com/openai/v1", "domain": "azure.microsoft.com"},
    {"id": "github", "name": "GitHub Models", "base_url": "https://models.github.ai/inference", "domain": "github.com"},
    {"id": "xai", "name": "xAI (Grok)", "base_url": "https://api.x.ai/v1", "domain": "x.ai"},
    {"id": "ppio", "name": "PPIO", "base_url": "https://api.ppio.com/openai/v1", "domain": "ppio.com"},
    {"id": "302ai", "name": "302.AI", "base_url": "https://api.302.ai/v1", "domain": "302.ai"},
    {"id": "aihubmix", "name": "AiHubMix", "base_url": "https://aihubmix.com/v1", "domain": "aihubmix.com"},
    {"id": "ollama", "name": "Ollama (local)", "base_url": "http://127.0.0.1:11434/v1", "domain": "ollama.com"},
    {"id": "lmstudio", "name": "LM Studio (local)", "base_url": "http://127.0.0.1:1234/v1", "domain": "lmstudio.ai"},
    {"id": "vllm", "name": "vLLM (local)", "base_url": "http://127.0.0.1:8000/v1", "domain": "vllm.ai"},
    {"id": "custom", "name": "Custom", "base_url": "", "domain": ""},
]


def get_preset(preset_id: str) -> dict | None:
    for preset in PROVIDER_PRESETS:
        if preset["id"] == preset_id:
            return dict(preset)
    return None
