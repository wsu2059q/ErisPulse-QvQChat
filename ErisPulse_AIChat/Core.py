import asyncio
import fnmatch
from typing import Dict, List, Optional, Callable, Any
from ErisPulse import sdk

class Main:
    def __init__(self, sdk):
        self.sdk = sdk
        self.logger = sdk.logger
        self.openai_module = sdk.OpenAI
        self.ai_chat_config = self._getConfig()
        self.trigger_words = self._parse_trigger_words(self.ai_chat_config.get("trigger_words", ["AI"]))
        self.clear_command = self.ai_chat_config.get("clear_command", "/clear")
        self.max_history_length = self.ai_chat_config.get("max_history_length", 10)
        
        # 获取 OpenAI 模块实例
        if not hasattr(sdk, "OpenAI"):
            raise RuntimeError("AIChat 模块需要依赖 OpenAI 模块，请先安装 OpenAI 模块")
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
                "trigger_words": ["AI"],
                "system_prompt": "你是一个AI助手，你叫AI，你是一个智能聊天机器人",
                "clear_command": "/clear",
                "max_history_length": 10
            }
            sdk.env.setConfig("AIChat", default_config)
            self.logger.warning("AIChat 已生成默认配置")
            return default_config
        return config
    
    def _parse_trigger_words(self, trigger_words) -> List[str]:
        if isinstance(trigger_words, str):
            return [trigger_words.strip()]
        elif isinstance(trigger_words, list):
            return [word.strip() for word in trigger_words]
        return ["AI"]
    
    def _register_handlers(self):
        self.sdk.adapter.on("message")(self._handle_message)
        self.logger.info("已注册全平台消息处理器")

    async def _handle_message(self, data):
        if data.get("alt_message"):
            message = data.get("alt_message", "").strip()
            if not message:
                return
                
            chat_id = self._get_chat_id(data)
            if not chat_id:
                return
                
            user_nickname = data.get("user_nickname", data.get("user_id", "未知用户"))
            
            # 处理清除历史指令
            if message.startswith(self.clear_command):
                await self.clear_history(chat_id)
                reply = f"已清空当前聊天历史记录"
                await self.send_response(data, reply)
                return
            
            # 检查是否触发机器人
            if not self._is_triggered(message):
                return
                
            # 存储带昵称的消息
            message_with_nickname = f"{user_nickname}: {message}"
                
            response = await self.get_ai_response(chat_id, message_with_nickname)
            await self.send_response(data, response)

    def _is_triggered(self, message: str) -> bool:
        message_lower = message.lower()
        for pattern in self.trigger_words:
            if '*' in pattern or '?' in pattern:
                if fnmatch.fnmatch(message_lower, pattern.lower()):
                    return True
            else:
                if pattern.lower() in message_lower:
                    return True
        return False

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

        ai_response = await self.openai_module.chat(
            messages=messages,
            stream=False
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
                self.logger.info(f"发送AI响应到 {adapter_name} - {detail_type} - {chat_id}: {response.strip()}")
                if not response.strip():
                    response = "抱歉，我没有理解您的问题。"             
                msgInfo = await adapter.Send.To("user" if detail_type == "private" else "group", chat_id).Text(response.strip())
                self.logger.info(f"消息信息: {msgInfo}")
        except Exception as e:
            self.logger.error(f"发送AI响应失败: {e}")

    async def get_message_history(self, chatId) -> List[Dict]:
        history = self.message_store.get(chatId, [])
        if len(history) > self.max_history_length:
            history = history[-self.max_history_length:]
            self.message_store[chatId] = history
            self.sdk.env.set("aichat_message_store", self.message_store)
        return history

    async def add_message(self, chatId, role: str, content: str):
        if chatId not in self.message_store:
            self.message_store[chatId] = []
        self.message_store[chatId].append({"role": role, "content": content})

        if len(self.message_store[chatId]) > self.max_history_length * 2:
            self.message_store[chatId] = self.message_store[chatId][-self.max_history_length * 2:]
        self.sdk.env.set("aichat_message_store", self.message_store)

    async def clear_history(self, chatId):
        if chatId in self.message_store:
            del self.message_store[chatId]
            self.sdk.env.set("aichat_message_store", self.message_store)

    def AddStreamHandle(self, handler: Callable):
        self.custom_handlers.append(handler)
