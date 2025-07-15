import asyncio
from typing import Dict, List, Optional, Callable, Any
from ErisPulse import sdk

class Main:
    def __init__(self, sdk):
        self.sdk = sdk
        self.logger = sdk.logger
        self.ai_chat_config = self._getConfig()
        self.bot_name = self.ai_chat_config.get("bot_name", "AI")
        
        # 获取 OpenAI 模块实例
        if not hasattr(sdk, "OpenAI"):
            raise RuntimeError("AIChat 模块需要依赖 OpenAI 模块，请先安装 OpenAI 模块")
        self.openai = sdk.OpenAI

        self.system_prompt = self.ai_chat_config.get("system_prompt", "")
        self.message_store = sdk.env.get("aichat_message_store", {})
        self.custom_handlers = []

        # 注册统一的消息处理器
        self._register_handlers()
        self.logger.info("AIChat 模块已初始化")
    
    @staticmethod
    def should_eager_load() -> bool:
        return True
    
    def _getConfig(self):
        config = sdk.env.getConfig("AIChat")
        if not config:
            default_config = {
                "bot_name": "AI",
                "system_prompt": "你是一个AI助手，你叫AI，你是一个智能聊天机器人",
            }
            sdk.env.setConfig("AIChat", default_config)
            self.logger.warning("AIChat 已生成默认配置")
            return default_config
        return config
    
    def _register_handlers(self):
        self.sdk.adapter.on("message")(self._handle_message)
        self.logger.info("已注册全平台消息处理器")

    async def _handle_message(self, data):
        if data.get("alt_message"):
            message = data.get("alt_message", "").strip()
            if not message:
                return
                
            if self.bot_name.lower() not in message.lower():
                return
                
            chat_id = self._get_chat_id(data)
            if not chat_id:
                return
                
            response = await self.get_ai_response(chat_id, message)
            await self.send_response(data, response)

    def _get_chat_id(self, data) -> Optional[Any]:
        detail_type = data.get("detail_type", "private")
        return data.get("user_id") if detail_type == "private" else data.get("group_id")

    async def get_ai_response(self, chat_id: Any, message: str) -> str:
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        history = await self.get_message_history(chat_id)
        messages.extend(history)

        messages.append({"role": "user", "content": message})

        ai_response = ""

        async def stream_handler(content: str):
            nonlocal ai_response
            ai_response += content
            for handler in self.custom_handlers:
                await handler(content)

        ai_response = await self.openai.chat(
            messages=messages,
            stream=True,
            stream_handler=stream_handler
        )

        await self.add_message(chat_id, "user", message)
        await self.add_message(chat_id, "assistant", ai_response)

        return ai_response

    async def send_response(self, data: dict, response: str):
        try:
            detail_type = data.get("detail_type", "private")
            chat_id = self._get_chat_id(data)
            adapter_name = data.get("self", {}).get("platform", None)
            
            if adapter_name:
                adapter = getattr(self.sdk.adapter, adapter_name)
                await adapter.Send.To("user" if detail_type == "private" else "group", chat_id).Text(response)
        except Exception as e:
            self.logger.error(f"发送AI响应失败: {e}")

    async def get_message_history(self, chatId) -> List[Dict]:
        return self.message_store.get(chatId, [])

    async def add_message(self, chatId, role: str, content: str):
        if chatId not in self.message_store:
            self.message_store[chatId] = []
        self.message_store[chatId].append({"role": role, "content": content})
        self.sdk.env.set("aichat_message_store", self.message_store)

    async def clear_history(self, chatId):
        if chatId in self.message_store:
            del self.message_store[chatId]
            self.sdk.env.set("aichat_message_store", self.message_store)

    def AddStreamHandle(self, handler: Callable):
        self.custom_handlers.append(handler)
