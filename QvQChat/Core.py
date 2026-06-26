"""
QvQChat 主模块

消息处理编排器，整合 AI 引擎、行为系统、记忆、知识库和工具。
支持预测模式（低token模式）：每N条消息做一次预测词判断，匹配才进入对话。
"""

import asyncio
from typing import Any, Dict, List, Optional

from ErisPulse import sdk
from ErisPulse.Core.Bases import BaseModule
from ErisPulse.Core.Event import message

from .agent.knowledge import KnowledgeBase
from .agent.multi import MultiAgentManager
from .agent.tools import MCPManager
from .ai import AIEngine, BehaviorManager, ModelPool
from .chat.memory import QvQMemory
from .chat.session import SessionManager
from .config import QvQConfig
from .dashboard import DashboardManager
from .utils import MessageSender, get_session_description, truncate_message


class Main(BaseModule):
    """
    QvQChat 主模块

    子系统：
    - AI 引擎：模型池 + 行为管理 + 执行引擎（故障转移）
    - 对话处理：记忆系统 + 会话管理（速率限制/活跃模式/回复判断）
    - 智能体管理：多智能体人格 + 知识库 + MCP工具
    - Dashboard：Web 管理面板
    """

    def __init__(self):
        self.sdk = sdk
        self.logger = sdk.logger.get_child("QvQChat")

        # 基础配置
        self.config = QvQConfig()

        # AI 引擎子系统
        self.model_pool = ModelPool(self.config, self.logger)
        self.behavior_manager = BehaviorManager(
            self.config, self.model_pool, self.logger
        )
        self.ai_engine = AIEngine(self.model_pool, self.behavior_manager, self.logger)

        # 首次运行自动分配模型
        self.behavior_manager.auto_assign_models()

        # 对话处理子系统
        self.memory = QvQMemory(self.config, self.ai_engine)
        self.session = SessionManager(self.config, self.logger)

        # 智能体管理子系统
        self.multi_agent = MultiAgentManager(self.config, self.logger)
        self.knowledge_base = KnowledgeBase(self.config, self.logger)
        self.mcp_manager = MCPManager(self.config, self.logger)

        # Dashboard
        self.dashboard = DashboardManager(self)

        # 消息发送器
        self.message_sender = MessageSender(
            self.sdk.adapter, self.config.config, self.logger
        )

        # AI 启用状态
        self._ai_disabled: Dict[str, bool] = {}

        self.logger.info("QvQChat 模块初始化完成")

    @staticmethod
    def get_load_strategy():
        from ErisPulse.loaders import ModuleLoadStrategy

        return ModuleLoadStrategy(lazy_load=False, priority=50)

    async def on_load(self, event: Dict[str, Any]) -> bool:
        try:
            self._register_event_handlers()
            self.dashboard.register()
            self.logger.info("QvQChat 模块已加载")
            return True
        except Exception as e:
            self.logger.error(f"QvQChat 模块加载失败: {e}")
            return False

    async def on_unload(self, event: Dict[str, Any]) -> bool:
        try:
            self.dashboard.unregister()
            self.logger.info("QvQChat 模块已卸载")
            return True
        except Exception as e:
            self.logger.error(f"QvQChat 模块卸载失败: {e}")
            return False

    def _register_event_handlers(self) -> None:
        message.on_message(priority=999)(self._handle_message)

    # ==================== AI 控制 ====================

    def is_ai_enabled(self, user_id: str, group_id: Optional[str] = None) -> bool:
        if group_id:
            return self.config.get_group_config(group_id).get("enable_ai", True)
        return self.session.get_session_key(user_id, group_id) not in self._ai_disabled

    def enable_ai(self, user_id: str, group_id: Optional[str] = None) -> str:
        if group_id:
            cfg = self.config.get_group_config(group_id)
            cfg["enable_ai"] = True
            self.config.set_group_config(group_id, cfg)
        else:
            self._ai_disabled.pop(self.session.get_session_key(user_id, group_id), None)
        return "AI已启用"

    def disable_ai(self, user_id: str, group_id: Optional[str] = None) -> str:
        if group_id:
            cfg = self.config.get_group_config(group_id)
            cfg["enable_ai"] = False
            self.config.set_group_config(group_id, cfg)
        else:
            self._ai_disabled[self.session.get_session_key(user_id, group_id)] = True
        return "AI已禁用"

    # ==================== 消息处理 ====================

    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """消息处理主入口"""
        try:
            alt_message = data.get("alt_message", "").strip()
            image_urls = self._extract_images(data)

            detail_type = data.get("detail_type", "private")
            user_id = str(data.get("user_id", ""))
            group_id = str(data.get("group_id", "")) if detail_type == "group" else None
            user_nickname = data.get("user_nickname", user_id)
            group_name = data.get("group_name", "")
            platform = data.get("self", {}).get("platform", "")

            # 跳过指令消息
            if self.config.get("ignore_command_messages", True):
                prefix = sdk.env.getConfig("ErisPulse.event.command.prefix", "/")
                if alt_message and alt_message.lstrip().startswith(prefix):
                    return

            if not user_id or not platform:
                return

            # 消息长度检查
            if not self.session.check_message_length(alt_message):
                return

            # AI 启用检查
            if not self.is_ai_enabled(user_id, group_id):
                return

            # 图片缓存
            if image_urls:
                self.session.cache_images(user_id, image_urls, group_id)

            if not alt_message and image_urls:
                alt_message = "[图片]"
            if not alt_message:
                return

            # 累积到短期记忆
            await self.memory.add_short_term_memory(
                user_id, "user", alt_message, group_id, user_nickname
            )

            # 更新群沉寂
            if group_id:
                self.session.update_group_silence(user_id, group_id)

            # 判断是否回复
            should_reply = await self._check_should_reply(
                data, alt_message, user_id, group_id
            )

            if not should_reply:
                return

            session_desc = get_session_description(
                user_id, user_nickname, group_id, group_name
            )
            self.logger.info(
                f"开始回复 - {session_desc} - {truncate_message(alt_message, 80)}"
            )

            # 速率限制
            est_tokens = SessionManager.estimate_tokens(alt_message) * 2
            if not self.session.check_rate_limit(est_tokens, user_id, group_id):
                return

            # 获取缓存图片
            cached = self.session.get_cached_images(user_id, group_id)
            all_images = list(set(image_urls + cached))

            # 生成回复
            response = await self._generate_response(
                user_id,
                group_id,
                alt_message,
                all_images,
                user_nickname,
                group_name,
                platform,
                data,
            )

            if not response:
                return

            # 发送回复
            await self._send_response(data, response, platform)
            self.logger.info(
                f"回复已发送 - {session_desc} - {truncate_message(response, 60)}"
            )

            # 更新回复时间
            self.session.update_last_reply_time(user_id, group_id)
            self.session.clear_cached_images(user_id, group_id)

            # 保存AI回复到记忆
            bot_names = self.config.get("bot_nicknames", [])
            bot_name = bot_names[0] if bot_names else ""
            await self.memory.add_short_term_memory(
                user_id, "assistant", response, group_id, bot_name
            )

            # 群聊后续监听
            if group_id:
                asyncio.create_task(
                    self._continue_conversation(user_id, group_id, platform)
                )

            # 回复后异步提取记忆（避免与对话 AI 并发）
            asyncio.create_task(self._extract_memory_async(user_id, group_id))

        except Exception as e:
            self.logger.error(f"处理消息出错: {e}")

    async def _check_should_reply(
        self,
        data: Dict[str, Any],
        alt_message: str,
        user_id: str,
        group_id: Optional[str],
    ) -> bool:
        """检查是否应该回复"""
        bot_ids = self.config.get("bot_ids", [])
        bot_nicknames = self.config.get("bot_nicknames", [])

        # 检查 @机器人
        is_mentioned = self._is_mentioned(data, bot_ids, bot_nicknames, alt_message)

        # 私聊：始终回复（跳过 AI 判断，省 token + 省时间）
        if not group_id:
            return True

        # 群聊被@：直接回复
        if is_mentioned:
            self.logger.info("群聊被@或叫名字，直接回复")
            return True

        # 群聊活跃模式：直接回复
        if self.session.is_active_mode(user_id, group_id):
            self.logger.info("活跃模式生效中，直接回复")
            return True

        # 窥屏模式未启用：直接回复
        if not self.config.get("stalker_mode.enabled", True):
            return True

        # 获取对话行为的触发模式
        trigger_mode = self.behavior_manager.get_trigger_mode("dialogue")
        session_key = self.session.get_session_key(user_id, group_id)

        if trigger_mode == "prediction":
            # 预测模式（低token模式）
            behavior = self.behavior_manager.get_behavior("dialogue")
            interval = behavior.get("prediction_interval", 5) if behavior else 5
            trigger_words = (
                behavior.get("trigger_words", ["回复"]) if behavior else ["回复"]
            )

            buffer = self.session.add_prediction_message(session_key, alt_message)
            if len(buffer) < interval:
                self.logger.debug(f"预测模式缓冲中 ({len(buffer)}/{interval})")
                return False

            self.session.clear_prediction_buffer(session_key)
            self.logger.info(f"预测模式触发 (累积{len(buffer)}条)")
            prediction = await self._run_prediction(
                buffer, bot_nicknames[0] if bot_nicknames else ""
            )

            if any(tw in prediction for tw in trigger_words):
                self.logger.info("预测命中触发词，进入对话")
                return True
            self.logger.info("预测未命中，跳过回复")
            return False

        # 标准模式：窥屏概率 + AI 判断
        return await self.session.should_reply(
            self.ai_engine,
            data,
            alt_message,
            user_id,
            group_id,
            bot_ids,
            bot_nicknames,
            True,
        )

    async def _run_prediction(self, messages_batch: List[str], bot_name: str) -> str:
        """执行预测（低token模式的核心）：批量消息 -> 预测词"""
        try:
            batch_text = "\n".join(f"- {m}" for m in messages_batch[-10:])
            prompt = (
                f"以下是群聊最近的{len(messages_batch)}条消息。\n"
                f"判断是否有值得回复的内容（被提问、被@、有趣话题等）。\n\n"
                f"消息列表:\n{batch_text}\n\n"
                + (f"你的名字是「{bot_name}」。\n" if bot_name else "")
                + "只回答一个词：「回复」表示应该回复，「跳过」表示不需要。"
            )
            result = await self.ai_engine.execute_behavior(
                "reply_judge", [{"role": "user", "content": prompt}]
            )
            prediction = result if isinstance(result, str) else ""
            self.logger.debug(f"预测结果: {prediction.strip()[:30]}")
            return prediction
        except Exception as e:
            self.logger.warning(f"预测失败: {e}")
            return "跳过"

    def _is_mentioned(
        self,
        data: Dict[str, Any],
        bot_ids: List[str],
        bot_nicknames: List[str],
        message: str,
    ) -> bool:
        """检查是否被@或叫名字"""
        for seg in data.get("message", []):
            if seg.get("type") == "mention":
                if str(seg.get("data", {}).get("user_id", "")) in [
                    str(b) for b in bot_ids
                ]:
                    return True
        for nick in bot_nicknames:
            if nick and nick in message:
                return True
        return False

    async def _generate_response(
        self,
        user_id: str,
        group_id: Optional[str],
        user_input: str,
        image_urls: List[str],
        user_nickname: str,
        group_name: str,
        platform: str,
        data: Dict[str, Any],
    ) -> Optional[str]:
        """生成AI回复"""
        try:
            session_key = self.session.get_session_key(user_id, group_id)
            history = await self.memory.get_session_history(user_id, group_id)

            # 构建系统提示词
            system_prompt = self._build_system_prompt(
                user_id, group_id, user_input, user_nickname, group_name
            )

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # 记忆上下文
            memory_ctx = await self._build_memory_context(user_id, history, group_id)
            if memory_ctx:
                messages.append({"role": "system", "content": memory_ctx})

            # 场景提示
            scene = self._build_scene_prompt(user_nickname, group_id is not None)
            if scene:
                messages.append({"role": "system", "content": scene})

            # 添加历史
            messages.extend(history[-15:])

            # 图片处理
            if image_urls:
                await self._inject_images(messages, image_urls, user_input)

            # MCP 工具
            tools = None
            if self.config.get("mcp.enabled", True) and self.config.get(
                "mcp.auto_inject", True
            ):
                tools = self.mcp_manager.get_openai_tools_schema()

            # 调用对话行为
            self.logger.info(f"调用对话行为 - 消息数: {len(messages)}")
            response = await self.ai_engine.dialogue(messages, tools=tools)

            if response and isinstance(response, str):
                self.logger.info(
                    f"对话行为完成 - 回复: {truncate_message(response, 80)}"
                )

            return response if isinstance(response, str) else None

        except Exception as e:
            self.logger.error(f"生成回复失败: {e}")
            return "抱歉，我现在无法回复。请稍后再试。"

    def _build_system_prompt(
        self,
        user_id: str,
        group_id: Optional[str],
        user_input: str,
        user_nickname: str,
        group_name: str,
    ) -> str:
        """构建系统提示词（多智能体 + 知识库 + 行为提示词）"""
        # 行为基础提示词
        prompt = self.behavior_manager.get_behavior_prompt("dialogue")
        source = "行为[dialogue]"

        # 多智能体覆盖
        if self.config.get("multi_agent.enabled", True):
            session_key = self.session.get_session_key(user_id, group_id)
            agent_prompt = self.multi_agent.get_effective_prompt(session_key)
            if agent_prompt:
                prompt = agent_prompt
                source = "多智能体"

        # 群配置覆盖
        if group_id:
            group_prompt = self.config.get_group_config(group_id).get(
                "system_prompt", ""
            )
            if group_prompt:
                prompt = group_prompt
                source = f"群配置[{group_id}]"

        # 知识库注入
        kb_note = ""
        if self.config.get("knowledge_base.enabled", True):
            max_tokens = self.config.get("knowledge_base.max_context_tokens", 2000)
            keyword = (
                user_input
                if self.config.get("knowledge_base.auto_search", True)
                else None
            )
            kb_ctx = self.knowledge_base.build_context(
                max_tokens=max_tokens, keyword=keyword
            )
            if kb_ctx:
                prompt = (prompt + "\n\n" + kb_ctx) if prompt else kb_ctx
                kb_note = " +知识库"

        self.logger.debug(f"提示词来源: {source}{kb_note}")
        return prompt

    async def _build_memory_context(
        self, user_id: str, history: List[Dict[str, str]], group_id: Optional[str]
    ) -> str:
        """构建记忆上下文"""
        try:
            user_memory = await self.memory.get_user_memory(user_id)
            long_term = user_memory.get("long_term", [])
            if not long_term:
                return ""

            memories = [m["content"] for m in long_term[-10:]]
            ctx = "用户记忆:\n" + "\n".join(f"- {m}" for m in memories)

            if group_id:
                group_memory = await self.memory.get_group_memory(group_id)
                group_context = group_memory.get("context", [])
                if group_context:
                    ctx += "\n\n群组记忆:\n" + "\n".join(
                        f"- {m['content']}" for m in group_context[-5:]
                    )

            return ctx
        except Exception:
            return ""

    def _build_scene_prompt(self, user_nickname: str, is_group: bool) -> str:
        """构建场景提示"""
        if is_group:
            prompt = "当前是群聊场景，你是一个普通群友，自然参与对话。"
        else:
            prompt = "当前是私聊场景，可以更自由地表达。"
        if user_nickname:
            prompt += f" 对方的名字是「{user_nickname}」。"
        prompt += "\n回复时直接说内容，不要加名字前缀。"
        return prompt

    async def _inject_images(
        self, messages: List[Dict[str, Any]], image_urls: List[str], user_input: str
    ) -> None:
        """将图片注入消息（视觉分析或多模态）"""
        try:
            descriptions = []
            for url in image_urls[:3]:
                desc = await self.ai_engine.analyze_image(
                    url, user_input if len(image_urls) == 1 else ""
                )
                if desc:
                    descriptions.append(desc)

            if descriptions:
                # 将图片描述注入最后一条用户消息
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i].get("role") == "user":
                        content = messages[i].get("content", "")
                        if isinstance(content, str):
                            messages[i]["content"] = (
                                content + "\n\n图片内容:\n" + "\n".join(descriptions)
                            )
                        break
            else:
                # 多模态模式
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i].get("role") == "user":
                        content = messages[i].get("content", "")
                        if isinstance(content, str):
                            messages[i]["content"] = [
                                {"type": "text", "text": content},
                                *[
                                    {"type": "image_url", "image_url": {"url": u}}
                                    for u in image_urls[:3]
                                ],
                            ]
                        break
        except Exception as e:
            self.logger.warning(f"图片处理失败: {e}")

    # 记忆提取并发控制
    _memory_locks: Dict[str, bool] = {}

    async def _extract_memory_async(
        self, user_id: str, group_id: Optional[str]
    ) -> None:
        """异步提取记忆（带并发控制 + 超时）"""
        session_key = self.session.get_session_key(user_id, group_id)

        # 防止同一会话并发提取
        if Main._memory_locks.get(session_key):
            self.logger.debug(f"记忆提取跳过（上次仍在执行）: {session_key}")
            return
        Main._memory_locks[session_key] = True

        try:
            history = await self.memory.get_session_history(user_id, group_id)
            if len(history) < 4:
                return

            recent = history[-15:]
            dialogue_text = "\n".join(f"{m['role']}: {m['content']}" for m in recent)

            # 调用记忆提取行为（带超时）
            prompt = f"从以下对话中提取值得长期记忆的关键信息（如果没有值得记忆的就回复'无'）:\n\n{dialogue_text}"

            result = await asyncio.wait_for(
                self.ai_engine.memory_process(prompt),
                timeout=30.0,
            )

            if result and result.strip() and result.strip() != "无":
                lines = [
                    line.strip().lstrip("-").strip()
                    for line in result.split("\n")
                    if line.strip() and line.strip() != "无"
                ]
                for line in lines:
                    await self.memory.add_long_term_memory(user_id, line)
                    if group_id:
                        group_cfg = self.config.get_group_config(group_id)
                        if group_cfg.get("memory_mode", "mixed") in (
                            "mixed",
                            "sender_only",
                        ):
                            await self.memory.add_group_memory(group_id, user_id, line)

                self.logger.info(f"行为[memory]完成 - 提取{len(lines)}条记忆")
            else:
                self.logger.debug("行为[memory]完成 - 无值得记忆的内容")

        except asyncio.TimeoutError:
            self.logger.warning("行为[memory]超时(30s)，跳过")
        except Exception as e:
            self.logger.debug(f"记忆提取跳过: {e}")
        finally:
            Main._memory_locks[session_key] = False

    async def _continue_conversation(
        self, user_id: str, group_id: str, platform: str
    ) -> None:
        """AI回复后的持续监听"""
        try:
            cfg = self.config.get("continue_conversation", {})
            if not cfg.get("enabled", True):
                return

            max_msgs = cfg.get("max_messages", 3)
            max_duration = cfg.get("max_duration", 120)
            bot_names = self.config.get("bot_nicknames", [])
            bot_name = bot_names[0] if bot_names else ""

            history = await self.memory.get_session_history(user_id, group_id)
            initial_len = len(history)
            start_time = asyncio.get_event_loop().time()
            consecutive = 0
            max_consecutive = 2

            for _ in range(max_msgs):
                if asyncio.get_event_loop().time() - start_time > max_duration:
                    break
                await asyncio.sleep(2)

                current = await self.memory.get_session_history(user_id, group_id)
                if len(current) <= initial_len:
                    continue

                should = await self.ai_engine.should_continue(current[-8:], bot_name)
                if not should or consecutive >= max_consecutive:
                    break

                consecutive += 1
                messages = current[-15:]

                response = await self.ai_engine.dialogue(messages)
                if not isinstance(response, str):
                    break

                await self.message_sender.send(platform, "group", group_id, response)
                await self.memory.add_short_term_memory(
                    user_id, "assistant", response, group_id, bot_name
                )
                initial_len = len(
                    await self.memory.get_session_history(user_id, group_id)
                )

        except Exception as e:
            self.logger.debug(f"持续监听结束: {e}")

    async def _send_response(
        self, data: Dict[str, Any], response: str, platform: str
    ) -> None:
        """发送回复"""
        try:
            if not platform:
                return
            detail_type = data.get("detail_type", "private")
            if detail_type == "private":
                target_type, target_id = "user", data.get("user_id")
            else:
                target_type, target_id = "group", data.get("group_id")
            if not target_id:
                return
            await self.message_sender.send(platform, target_type, target_id, response)
        except Exception as e:
            self.logger.error(f"发送回复失败: {e}")

    def _extract_images(self, data: Dict[str, Any]) -> List[str]:
        """提取消息中的图片URL"""
        urls = []
        for seg in data.get("message", []):
            if seg.get("type") == "image":
                url = seg.get("data", {}).get("url") or seg.get("data", {}).get("file")
                if url:
                    urls.append(url)
        return urls
