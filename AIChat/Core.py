import asyncio
from typing import Dict, List, Optional, Callable, Any
from ErisPulse import sdk

class Main:
    def __init__(self, sdk):
        self.sdk = sdk
        self.logger = sdk.logger
        self.ai_chat_config = sdk.env.get("AIChat", {})
        if self.ai_chat_config is None:
            self.logger.warning("""AIChat配置缺失，请在env.py中添加配置
""")
        self.bot_name = self.ai_chat_config.get("bot_name", "AI")

        # 获取 OpenAI 模块实例
        if not hasattr(sdk, "OpenAI"):
            raise RuntimeError("AIChat 模块需要依赖 OpenAI 模块，请先加载 OpenAI 模块")
        self.openai = sdk.OpenAI

        self.system_prompt = self.ai_chat_config.get("system_prompt", "")
        self.message_store = sdk.env.get("aichat_message_store", {})
        self.custom_handlers = []

        # 注册适配器消息处理器
        self._register_all_adapters()

        self.logger.info("AIChat 模块已初始化")

    def _register_all_adapters(self):
        adapters = ["Yunhu", "OneBot", "Telegram"]

        for adapter_name in adapters:
            adapter = getattr(self.sdk.adapter, adapter_name, None)
            if adapter:
                @adapter.on("message")
                async def handler(data, name=adapter_name):
                    await self.handle_message(name, data)

                self.logger.info(f"已注册 {adapter_name} 的消息处理器")

    def _extract_message(self, adapter_name: str, data: dict) -> Optional[str]:
        try:
            if adapter_name == "Yunhu":
                return data["event"]["message"]["content"]["text"]
            elif adapter_name == "OneBot":
                return data.get("raw_message", "")
            elif adapter_name == "Telegram":
                return data["message"].get("text", "")
        except KeyError:
            self.logger.warning(f"[{adapter_name}] 消息格式错误或为空")
            return None

    def _extract_chat_id(self, adapter_name: str, data: dict) -> Optional[Any]:
        try:
            if adapter_name == "Yunhu":
                return data["event"]["sender"]["senderId"]
            elif adapter_name == "OneBot":
                return data.get("user_id") or data.get("group_id")
            elif adapter_name == "Telegram":
                return data["message"]["chat"]["id"]
        except KeyError:
            self.logger.warning(f"[{adapter_name}] 聊天ID提取失败")
            return None

    async def handle_message(self, adapter_name: str, data: dict):
        message = self._extract_message(adapter_name, data)
        chat_id = self._extract_chat_id(adapter_name, data)

        if not message or not chat_id:
            return

        if self.bot_name.lower() in message.lower():
            response = await self.get_ai_response(chat_id, message)
            await self.send_response(adapter_name, chat_id, response)

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

    async def send_response(self, adapter_name: str, chat_id: Any, response: str):
        try:
            if adapter_name == "Yunhu":
                await self.sdk.adapter.Yunhu.Send.To("user", chat_id).Text(response)
            elif adapter_name == "OneBot":
                await self.sdk.adapter.OneBot.Send.To("user", chat_id).Text(response)
            elif adapter_name == "Telegram":
                await self.sdk.adapter.Telegram.Send.To("user", chat_id).Text(response)
            else:
                self.logger.warning(f"不支持的适配器: {adapter_name}")
        except Exception as e:
            self.logger.error(f"[{adapter_name}] 发送消息失败: {e}")

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