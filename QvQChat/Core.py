"""
QvQChat 主模块

消息处理编排器。核心创新：
- 行为链：行为可触发后续行为（如对话→表情→记忆）
- 拟人化回复：打字延迟、时间感知、情绪感知
- 预测模式：低token批量判断
"""

import asyncio
import json
import random
import re
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from ErisPulse import i18n, sdk
from ErisPulse.Core.Bases import BaseModule
from ErisPulse.Core.Event import message

from .config import QvQConfig, QvQConfigData
from .I18n import QvQI18n
from .pipeline import PromptContext, PromptPipeline, create_default_injectors
from .agent.knowledge import KnowledgeBase
from .agent.multi import MultiAgentManager
from .agent.tools import MCPManager
from .ai import AIEngine, BehaviorManager, ModelPool
from .chat.humanize import Humanizer
from .chat.memory import QvQMemory
from .chat.proactive import ProactiveManager
from .chat.session import SessionManager
from .chat.sticker import StickerManager
from .dashboard import DashboardManager
from .utils import MessageSender, get_session_description, truncate_message

# 单轮回复允许的最大 MCP 工具调用次数
MAX_TOOL_CALLS = 10
# 工具调用循环的最大轮数
MAX_TOOL_ROUNDS = 15
# 单个工具结果写入上下文的最大字符数
TOOL_RESULT_MAX_CHARS = 4000


class Main(BaseModule):
    """
    QvQChat 主模块

    子系统：
    - AI 引擎：模型池 + 行为管理 + 执行引擎（故障转移）
    - 对话处理：记忆 + 会话管理（速率限制/活跃模式/回复判断）+ 拟人化 + 主动发起
    - 智能体：多智能体人格 + 知识库 + MCP工具
    - Dashboard：Web 管理面板
    """

    ConfigClass = QvQConfigData
    I18nClass = QvQI18n

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
        self.behavior_manager.auto_assign_models()

        # 对话处理子系统
        self.memory = QvQMemory(self.config, self.ai_engine)
        self.session = SessionManager(self.config, self.logger)
        self.sticker_manager = StickerManager(self.config, self.logger)
        self.humanizer = Humanizer(self.config, self.logger)
        self.proactive = ProactiveManager(self)

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

        # 提示词注入管线
        self.pipeline = PromptPipeline(self)
        for inj in create_default_injectors(self):
            self.pipeline.register(inj)

        # AI 启用状态
        self._ai_disabled: Dict[str, bool] = {}

        # 消息聚合状态
        self._msg_buffers: Dict[str, Dict[str, Any]] = {}
        self._msg_timers: Dict[str, asyncio.Task] = {}

        # 运行统计
        self._stats = {
            "total_messages": 0,
            "total_replies": 0,
            "total_tokens_est": 0,
            "started_at": time.time(),
        }

        self.logger.info(i18n.t("QvQChat.module_init_done"))

        # 检查配置引导
        if not self.model_pool.list_models():
            self.logger.warning(i18n.t("QvQChat.no_models_configured"))
        else:
            unassigned = [
                b["name"]
                for b in self.behavior_manager.list_behaviors()
                if b.get("behavior_type") == "ai"
                and not b.get("models")
                and b.get("enabled", True)
            ]
            if unassigned:
                self.logger.warning(
                    i18n.t("QvQChat.behaviors_unassigned", behaviors=", ".join(unassigned))
                )

    @staticmethod
    def get_load_strategy():
        """声明模块加载策略（立即加载，priority=50）"""
        from ErisPulse.loaders import ModuleLoadStrategy

        return ModuleLoadStrategy(lazy_load=False, priority=50)

    async def on_load(self, event: Dict[str, Any]) -> bool:
        """
        模块加载回调：注册事件处理器、注册 Dashboard、异步连接 MCP、启动主动发起循环

        :param event: 框架加载事件数据
        :return: bool 加载成功返回 True
        """
        try:
            self._register_event_handlers()
            self.dashboard.register()
            # 异步连接 MCP 服务器（不阻塞模块加载）
            if self.config.get("mcp.enabled", True):
                asyncio.create_task(self._connect_mcp_servers())
            # 主动发起对话循环
            if self.config.get("human_state.proactive_message.enabled", False):
                asyncio.create_task(self.proactive.loop())
            self.logger.info(i18n.t("QvQChat.module_loaded"))
            return True
        except Exception as e:
            self.logger.error(i18n.t("QvQChat.module_load_failed", error=e))
            return False

    async def on_unload(self, event: Dict[str, Any]) -> bool:
        """
        模块卸载回调：断开 MCP 连接、注销 Dashboard

        :param event: 框架卸载事件数据
        :return: bool 卸载成功返回 True
        """
        try:
            await self.mcp_manager.disconnect_all_servers()
            self.dashboard.unregister()
            self.logger.info(i18n.t("QvQChat.module_unloaded"))
            return True
        except Exception as e:
            self.logger.error(i18n.t("QvQChat.module_unload_failed", error=e))
            return False

    def _register_event_handlers(self) -> None:
        """{!--< internal-use >!--} 注册消息事件处理器"""
        message.on_message(priority=999)(self._handle_message)

    async def _connect_mcp_servers(self) -> None:
        """{!--< internal-use >!--} 异步连接所有已配置的 MCP 服务器"""
        try:
            await self.mcp_manager.connect_all_servers()
        except Exception as e:
            self.logger.warning(f"连接 MCP 服务器失败: {e}")

    # ==================== AI 控制 ====================

    def is_ai_enabled(self, user_id: str, group_id: Optional[str] = None) -> bool:
        """
        查询指定会话的 AI 启用状态

        :param user_id: 用户 ID
        :param group_id: 群组 ID，群聊会话以群配置为准
        :return: bool AI 是否启用
        """
        if group_id:
            return self.config.get_group_config(group_id).get("enable_ai", True)
        return self.session.get_session_key(user_id, group_id) not in self._ai_disabled

    def enable_ai(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        启用指定会话的 AI

        :param user_id: 用户 ID
        :param group_id: 群组 ID，提供时修改群配置
        :return: str 操作结果描述
        """
        if group_id:
            cfg = self.config.get_group_config(group_id)
            cfg["enable_ai"] = True
            self.config.set_group_config(group_id, cfg)
        else:
            self._ai_disabled.pop(self.session.get_session_key(user_id, group_id), None)
        return "AI已启用"

    def disable_ai(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        禁用指定会话的 AI

        :param user_id: 用户 ID
        :param group_id: 群组 ID，提供时修改群配置
        :return: str 操作结果描述
        """
        if group_id:
            cfg = self.config.get_group_config(group_id)
            cfg["enable_ai"] = False
            self.config.set_group_config(group_id, cfg)
        else:
            self._ai_disabled[self.session.get_session_key(user_id, group_id)] = True
        return "AI已禁用"

    # ==================== 运行统计 ====================

    def get_stats(self) -> Dict[str, Any]:
        """
        获取运行统计数据

        :return: Dict 包含消息/回复计数、运行时长、回复率的统计字典
        """
        uptime = int(time.time() - self._stats["started_at"])
        hours, rem = divmod(uptime, 3600)
        mins, secs = divmod(rem, 60)
        return {
            **self._stats,
            "uptime": f"{hours}h{mins}m{secs}s",
            "reply_rate": (
                f"{self._stats['total_replies'] / max(self._stats['total_messages'], 1) * 100:.1f}%"
            ),
        }

    # ==================== 消息处理 ====================

    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """
        {!--< internal-use >!--} 消息处理主入口：提取字段、累积冲动值、按聚合配置分发处理

        :param data: 适配器标准化的消息事件数据
        """
        try:
            self._stats["total_messages"] += 1

            alt_message = data.get("alt_message", "").strip()
            image_urls = self._extract_images(data)

            detail_type = data.get("detail_type", "private")
            user_id = str(data.get("user_id", ""))
            group_id = str(data.get("group_id", "")) if detail_type == "group" else None
            user_nickname = data.get("user_nickname", user_id)
            group_name = data.get("group_name", "")
            platform = data.get("self", {}).get("platform", "")

            if not user_id or not platform:
                return

            # 跳过命令类消息（/#开头的各种bot命令）
            if alt_message and alt_message.lstrip().startswith(("#", "/")):
                return

            # 消息长度检查
            if not self.session.check_message_length(alt_message):
                self.logger.debug(f"消息过长，跳过: {len(alt_message)}")
                return

            # AI 启用检查
            if not self.is_ai_enabled(user_id, group_id):
                self.logger.debug(f"AI已禁用: {group_id or user_id}")
                return

            # 图片缓存
            if image_urls:
                self.session.cache_images(user_id, image_urls, group_id)

            if not alt_message and image_urls:
                alt_message = "[图片]"
            if not alt_message:
                return

            # 更新群沉寂 + 注册群组
            if group_id:
                self.session.update_group_silence(user_id, group_id)
                if group_id not in self.config.list_all_groups():
                    group_cfg = self.config.get_group_config(group_id)
                    if group_name:
                        group_cfg["group_name"] = group_name
                    self.config.set_group_config(group_id, group_cfg)
                    self.logger.info(f"发现新群组: {group_name or group_id}")

            # 更新会话元数据（用于主动发起对话）
            session_key = self.session.get_session_key(user_id, group_id)
            self.session.update_session_meta(
                session_key, platform,
                "group" if group_id else "user",
                group_id or user_id,
            )
            # 记录该会话收到一条他人消息的时间（活跃度判断用）
            self.session.update_last_incoming(session_key)

            # 累积会话冲动值（主动发起的内驱力：聊天越热闹越想说话）
            self.session.add_urge(session_key, alt_message)

            # 消息聚合判断
            agg_cfg = self.config.get("message_aggregation", {})
            if agg_cfg.get("enabled", True):
                window = float(
                    agg_cfg.get(
                        "private_window" if not group_id else "group_window", 0
                    )
                )
                max_buffer = int(agg_cfg.get("max_buffer", 8))
                if window > 0:
                    await self._buffer_message(
                        data, alt_message, image_urls, user_id, group_id,
                        user_nickname, group_name, platform, window, max_buffer,
                    )
                    return

            # 无聚合：直接处理
            await self._process_message(
                data, alt_message, image_urls, user_id, group_id,
                user_nickname, group_name, platform,
            )

        except Exception as e:
            self.logger.error(f"处理消息出错: {e}\n{traceback.format_exc()}")

    async def _buffer_message(
        self,
        data: Dict[str, Any],
        alt_message: str,
        image_urls: List[str],
        user_id: str,
        group_id: Optional[str],
        user_nickname: str,
        group_name: str,
        platform: str,
        window: float,
        max_buffer: int,
    ) -> None:
        """{!--< internal-use >!--} 缓冲消息用于聚合，达到最大缓冲数时立即刷新

        :param data: 消息事件数据
        :param alt_message: 消息文本
        :param image_urls: 消息携带的图片 URL 列表
        :param user_id: 用户 ID
        :param group_id: 群组 ID，私聊为 None
        :param user_nickname: 用户昵称
        :param group_name: 群名称
        :param platform: 平台标识
        :param window: 聚合窗口秒数
        :param max_buffer: 最大缓冲条数
        """
        session_key = self.session.get_session_key(user_id, group_id)

        buf = self._msg_buffers.get(session_key)
        if buf is None:
            buf = {
                "messages": [],
                "images": [],
                "data": data,
                "user_id": user_id,
                "group_id": group_id,
                "user_nickname": user_nickname,
                "group_name": group_name,
                "platform": platform,
            }
            self._msg_buffers[session_key] = buf

        buf["messages"].append(alt_message)
        buf["images"].extend(image_urls)
        buf["data"] = data  # 更新为最新消息的事件数据（用于回复）

        count = len(buf["messages"])
        self.logger.debug(f"消息聚合 [{session_key}] 缓冲 {count} 条")

        # 达到最大缓冲数：立即触发处理
        if count >= max_buffer:
            await self._flush_buffer(session_key)
            return

        # 重置定时器
        old_timer = self._msg_timers.get(session_key)
        if old_timer and not old_timer.done():
            old_timer.cancel()

        self._msg_timers[session_key] = asyncio.create_task(
            self._buffer_timer_task(session_key, window)
        )

    async def _buffer_timer_task(self, session_key: str, window: float) -> None:
        """{!--< internal-use >!--} 聚合定时器任务，窗口到期后刷新缓冲

        :param session_key: 会话标识
        :param window: 聚合窗口秒数
        """
        try:
            await asyncio.sleep(window)
            # 处理已开始：从计时器表中移除，避免被新消息 cancel 杀死正在执行的处理
            self._msg_timers.pop(session_key, None)
            await self._flush_buffer(session_key)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"聚合定时器出错: {e}")

    async def _flush_buffer(self, session_key: str) -> None:
        """{!--< internal-use >!--} 刷新聚合缓冲区，合并消息并交给 _process_message

        :param session_key: 会话标识
        """
        buf = self._msg_buffers.pop(session_key, None)
        timer = self._msg_timers.pop(session_key, None)
        if timer and not timer.done():
            timer.cancel()

        if not buf or not buf["messages"]:
            return

        # 合并消息文本
        combined_message = "\n".join(buf["messages"])
        all_images = list(set(buf["images"]))

        self.logger.info(
            f"聚合触发 [{session_key}] - 合并 {len(buf['messages'])} 条消息: "
            f"{truncate_message(combined_message, 80)}"
        )

        await self._process_message(
            buf["data"],
            combined_message,
            all_images,
            buf["user_id"],
            buf["group_id"],
            buf["user_nickname"],
            buf["group_name"],
            buf["platform"],
        )

    async def _process_message(
        self,
        data: Dict[str, Any],
        alt_message: str,
        image_urls: List[str],
        user_id: str,
        group_id: Optional[str],
        user_nickname: str,
        group_name: str,
        platform: str,
    ) -> None:
        """
        {!--< internal-use >!--} 处理单条/聚合后的消息：记忆 → 回复判定 → 生成 → 发送 → 行为链

        :param data: 消息事件数据
        :param alt_message: 消息文本（聚合时为多行合并文本）
        :param image_urls: 图片 URL 列表
        :param user_id: 用户 ID
        :param group_id: 群组 ID，私聊为 None
        :param user_nickname: 用户昵称
        :param group_name: 群名称
        :param platform: 平台标识
        """
        try:
            # 累积到短期记忆
            await self.memory.add_short_term_memory(
                user_id, "user", alt_message, group_id, user_nickname
            )

            # 判断是否回复
            bot_nicknames = self.config.get("bot_nicknames", [])
            should_reply = await self._check_should_reply(
                data, alt_message, user_id, group_id
            )

            if not should_reply:
                self.logger.debug("窥屏模式决定不回复")
                return

            # 已读不回（低概率跳过，模拟真人偶尔看了不回）
            # 私聊场景不触发：用户主动私聊本身就是强意图，"已读不回"会严重伤害体验
            if group_id is not None and self.humanizer.should_read_receipt_skip():
                return

            # 检测是否被提及（用于注入提示词）
            is_mentioned = self._is_mentioned(data, bot_nicknames, alt_message)

            session_desc = get_session_description(
                user_id, user_nickname, group_id, group_name
            )
            self.logger.info(
                f"开始回复 - {session_desc} - {truncate_message(alt_message, 80)}"
            )

            # 记忆意图拦截（记住/忘记指令，不消耗 AI）
            intent_reply = await self.memory.handle_memory_intent(
                user_id, alt_message, group_id
            )
            if intent_reply:
                delay = self.humanizer.calc_typing_delay(intent_reply)
                if delay > 0:
                    await asyncio.sleep(delay)
                await self._send_response(data, intent_reply, platform)
                self._stats["total_replies"] += 1
                self.session.update_last_reply_time(user_id, group_id)
                self.logger.info(
                    f"记忆指令拦截 - {session_desc} - {truncate_message(intent_reply, 60)}"
                )
                return

            # 独立输出行为检查（表情包/图片等，不消耗 AI）
            output_result = self._check_output_behaviors(
                alt_message, user_id, group_id, user_nickname
            )
            if output_result:
                delay = self.humanizer.calc_typing_delay(output_result)
                if delay > 0:
                    await asyncio.sleep(delay)
                await self._send_response(data, output_result, platform)
                self._stats["total_replies"] += 1
                self.logger.info(
                    f"输出行为触发 - {session_desc} - {truncate_message(output_result, 60)}"
                )
                self.session.update_last_reply_time(user_id, group_id)
                return

            # 速率限制（估算包含系统提示词+历史+用户消息）
            history = await self.memory.get_session_history(user_id, group_id)
            history_tokens = sum(
                SessionManager.estimate_tokens(m.get("content", "")) for m in history[-15:]
            )
            est_tokens = (
                SessionManager.estimate_tokens(alt_message)
                + history_tokens
                + 200  # 系统提示词估算
            )
            self._stats["total_tokens_est"] += est_tokens
            if not self.session.check_rate_limit(est_tokens, user_id, group_id):
                self.logger.warning("触发速率限制，跳过回复")
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
                is_mentioned=is_mentioned,
            )

            if not response:
                return

            # 拟人化后处理（错字纠正、打字中断等）
            response = self.humanizer.apply_postprocess(response)

            # 拟人化打字延迟
            delay = self.humanizer.calc_typing_delay(response)
            if delay > 0:
                self.logger.debug(f"打字延迟: {delay:.1f}s")
                await asyncio.sleep(delay)

            # 群聊随机@对方
            if group_id and self.config.get("humanize.random_at_probability", 0.15) > 0:
                response = self.humanizer.maybe_at_mention(response, user_nickname)

            # 发送回复（返回清理后的文本）
            sent_text = await self._send_response(data, response, platform)
            self._stats["total_replies"] += 1
            self.logger.info(
                f"回复已发送 - {session_desc} - {truncate_message(sent_text or response, 60)}"
            )

            # 更新回复时间
            self.session.update_last_reply_time(user_id, group_id)
            self.session.clear_cached_images(user_id, group_id)

            # 保存AI回复到记忆（用清理后的文本，避免历史污染）
            bot_names = self.config.get("bot_nicknames", [])
            bot_name = bot_names[0] if bot_names else ""
            clean_for_memory = self.humanizer.clean_response_for_history(sent_text or response)
            await self.memory.add_short_term_memory(
                user_id, "assistant", clean_for_memory, group_id, bot_name
            )

            # 行为链：群聊后续监听
            if group_id:
                asyncio.create_task(
                    self._continue_conversation(user_id, group_id, platform)
                )

            # 行为链：回复后异步提取记忆（memory 无模型时 fallback 到 dialogue）
            if self.ai_engine.is_available("memory") or self.ai_engine.is_available("dialogue"):
                if not self.ai_engine.is_available("memory"):
                    self.logger.warning(i18n.t("QvQChat.memory_fallback_to_dialogue"))
                if Humanizer.is_trivial_message(alt_message):
                    self.logger.debug("消息无记忆价值，跳过提取")
                else:
                    asyncio.create_task(self._extract_memory_async(user_id, group_id))

        except asyncio.CancelledError:
            self.logger.warning(f"处理被取消(可能被新消息聚合抢占): {truncate_message(alt_message, 40)}")
            raise
        except Exception as e:
            self.logger.error(f"处理消息出错: {e}\n{traceback.format_exc()}")

    async def _check_should_reply(
        self,
        data: Dict[str, Any],
        alt_message: str,
        user_id: str,
        group_id: Optional[str],
    ) -> bool:
        """
        {!--< internal-use >!--} 群聊回复判定链：@感知 → 活跃模式 → 夜间模式 → 预测/窥屏策略

        :param data: 消息事件数据
        :param alt_message: 消息文本
        :param user_id: 用户 ID
        :param group_id: 群组 ID，私聊为 None
        :return: bool 是否回复
        """
        bot_nicknames = self.config.get("bot_nicknames", [])

        # 检查 @机器人（仅使用事件 self.user_id）
        is_mentioned = self._is_mentioned(data, bot_nicknames, alt_message)

        # 私聊：始终回复
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

        # 夜间模式：夜间自动开启窥屏
        night_cfg = self.config.get("stalker_mode.night_mode", {})
        if night_cfg.get("enabled", True):
            from datetime import datetime

            hour = datetime.now().hour
            begin = night_cfg.get("begin", 23)
            end = night_cfg.get("end", 7)
            if begin > end:
                is_night = hour >= begin or hour < end
            else:
                is_night = begin <= hour < end
            if is_night:
                self.logger.debug(f"夜间模式({begin}:00-{end}:00)，进入窥屏")
                # fall through to stalker mode
            else:
                # 白天，窥屏关闭时直接回复
                if not self.config.get("stalker_mode.enabled", True):
                    return True
        elif not self.config.get("stalker_mode.enabled", True):
            return True

        # 获取对话行为的触发模式
        trigger_mode = self.behavior_manager.get_trigger_mode("dialogue")
        session_key = self.session.get_session_key(user_id, group_id)

        if trigger_mode == "prediction":
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

        # 标准模式：多层级回复策略
        self.logger.debug(f"群聊进入回复策略判断 - 会话: {session_key}")
        return await self.session.should_reply(
            self.ai_engine,
            data,
            alt_message,
            user_id,
            group_id,
            bot_nicknames,
        )

    async def _run_prediction(self, messages_batch: List[str], bot_name: str) -> str:
        """
        {!--< internal-use >!--} 执行预测模式判定（reply_judge 行为，低 token 消耗）

        :param messages_batch: 聚合的群聊消息列表
        :param bot_name: 机器人昵称，用于提示词
        :return: str 预测结果文本（含触发词或「跳过」）
        """
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

    def _check_output_behaviors(
        self, alt_message: str, user_id: str, group_id: Optional[str], user_nickname: str
    ) -> Optional[str]:
        """
        检查独立输出行为（表情包/图片等）

        遍历 behavior_type == "output" 的行为，按触发概率/触发词检查。
        命中时返回模板内容（含 [img]/[sticker] 标签），不消耗 AI 调用。

        :param alt_message: 消息文本
        :param user_id: 用户 ID
        :param group_id: 群组 ID
        :param user_nickname: 用户昵称，用于模板 {at_user} 占位符
        :return: Optional[str] 触发的输出内容，未触发返回 None
        """
        for behavior in self.behavior_manager.list_behaviors():
            if not behavior.get("enabled", True):
                continue
            if behavior.get("behavior_type") != "output":
                continue
            template = behavior.get("response_template", "")
            if not template:
                continue

            # 触发词检查（如果配置了）
            trigger_words = behavior.get("trigger_words", [])
            if trigger_words:
                if not any(tw in alt_message for tw in trigger_words):
                    continue

            # 概率检查
            trigger_prob = behavior.get("trigger_probability", 0)
            if trigger_prob <= 0 or random.random() >= trigger_prob:
                continue

            bname = behavior.get("name", behavior.get("id", ""))
            self.logger.info(f"输出行为[{bname}]触发")
            at_text = f"@{user_nickname}" if user_nickname else ""
            result = template.replace("{at_user}", at_text)
            return result
        return None

    def _apply_behavior_templates(self, response, user_id, group_id, user_nickname):
        """
        {!--< internal-use >!--} 概率性应用场景行为的输出模板

        模板占位符：{ai_response}（AI 回复文本）、{at_user}（@昵称）、
        [img]url[/img]（图片，由发送器处理）。

        :param response: AI 回复文本
        :param user_id: 用户 ID
        :param group_id: 群组 ID
        :param user_nickname: 用户昵称
        :return: str 应用模板后的回复
        """
        result = response
        for behavior in self.behavior_manager.list_behaviors():
            if not behavior.get("enabled", True):
                continue
            btype = behavior.get("behavior_type", "")
            if btype == "ai":
                continue  # AI行为不应用模板
            if btype == "output":
                continue  # 独立输出行为已单独处理
            template = behavior.get("response_template", "")
            if not template:
                continue
            trigger_prob = behavior.get("trigger_probability", 0)
            if trigger_prob <= 0 or random.random() >= trigger_prob:
                continue

            # 应用模板
            bname = behavior.get("name", behavior.get("id", ""))
            self.logger.info(f"行为[{bname}]输出模板触发")
            at_text = f"@{user_nickname}" if user_nickname else ""
            result = template.replace("{ai_response}", response).replace(
                "{at_user}", at_text
            )
            if result:
                break  # 只应用第一个触发的模板
        return result

    # ==================== 人类状态（情绪/精力） ====================

    def _get_human_state(self, session_key: str) -> Dict[str, float]:
        """
        {!--< internal-use >!--} 计算当前情绪/精力状态（含作息与时间段修正）

        :param session_key: 会话标识（当前为全局状态，参数保留扩展用）
        :return: Dict 包含 mood/energy 的状态字典，取值范围 0.1~1.0
        """
        state_cfg = self.config.get("human_state", {})
        if not state_cfg.get("enabled", True):
            return {"mood": 0.6, "energy": 0.8}

        hour = datetime.now().hour
        energy = float(state_cfg.get("energy", 0.8))
        mood = float(state_cfg.get("mood", 0.6))

        sleep_cfg = state_cfg.get("sleep_schedule", {})
        if sleep_cfg.get("enabled", False):
            sleep_time = int(sleep_cfg.get("sleep_time", 2))
            wake_time = int(sleep_cfg.get("wake_time", 8))
            if sleep_time > wake_time:
                is_sleepy = hour >= sleep_time or hour < wake_time
            else:
                is_sleepy = sleep_time <= hour < wake_time
            if is_sleepy:
                energy *= 0.3
                mood *= 0.7

        hour_progress = (hour + datetime.now().minute / 60) / 24
        energy += 0.2 * (1 - abs(hour_progress - 0.4) * 2)

        return {
            "mood": max(0.1, min(1.0, mood)),
            "energy": max(0.1, min(1.0, energy)),
        }

    def get_human_state(self) -> Dict[str, Any]:
        """
        获取当前人类状态（供 Dashboard 显示）

        :return: Dict mood/energy 状态字典
        """
        return self._get_human_state("global")

    @staticmethod
    def _mood_to_text(mood: float) -> str:
        """{!--< internal-use >!--} 情绪值转随机中文描述"""
        if mood >= 0.8:
            return random.choice(["心情特别好", "今天超开心", "心情很愉快"])
        elif mood >= 0.6:
            return random.choice(["心情还不错", "挺开心的", "心情挺好"])
        elif mood >= 0.4:
            return random.choice(["心情一般般", "没什么特别的", "心情平淡"])
        elif mood >= 0.2:
            return random.choice(["有点不开心", "心情不太好", "有点低落"])
        else:
            return random.choice(["心情很糟", "今天很不爽", "心情差到极点"])

    @staticmethod
    def _energy_to_text(energy: float) -> str:
        """{!--< internal-use >!--} 精力值转随机中文描述"""
        if energy >= 0.8:
            return random.choice(["精力充沛", "精神很好", "充满活力"])
        elif energy >= 0.6:
            return random.choice(["还算有精神", "状态还行", "挺清醒的"])
        elif energy >= 0.4:
            return random.choice(["有点累了", "稍微有点困", "一般般"])
        elif energy >= 0.2:
            return random.choice(["很困了", "快撑不住了", "累得不行"])
        else:
            return random.choice(["困死了", "已经迷糊了", "随时会睡着"])

    def get_status(self) -> Dict[str, Any]:
        """
        获取模块完整状态（供 Dashboard 与调试）

        :return: Dict 包含模型/行为/智能体/知识库/工具统计与功能开关的字典
        """
        active_agents = self.multi_agent.list_agents()
        default_agent = self.multi_agent.get_agent("default")
        bindings = self.multi_agent.list_bindings()
        return {
            "config_loaded": bool(self.config.config),
            "models": self.model_pool.get_stats(),
            "behaviors": self.behavior_manager.get_stats(),
            "behavior_status": self.ai_engine.get_behavior_status(),
            "agents": {
                "total": len(active_agents),
                "default_prompt": default_agent.get("system_prompt", "")[:80]
                if default_agent
                else "",
            },
            "agent_bindings": len(bindings),
            "knowledge": self.knowledge_base.get_stats(),
            "tools": self.mcp_manager.get_stats(),
            "groups": len(self.config.list_all_groups()),
            "features": {
                "multi_agent": self.config.get("multi_agent.enabled", True),
                "knowledge_base": self.config.get("knowledge_base.enabled", True),
                "mcp": self.config.get("mcp.enabled", True),
                "voice": self.config.get("voice.enabled", False),
                "stalker": self.config.get("stalker_mode.enabled", True),
            },
        }

    def _is_mentioned(
        self,
        data: Dict[str, Any],
        bot_nicknames: List[str],
        message: str,
    ) -> bool:
        """
        {!--< internal-use >!--} 检测消息是否指向自己（mention 段或昵称命中）

        仅使用事件中的 self.user_id 判断 mention 段，无需配置 bot_ids。

        :param data: 消息事件数据
        :param bot_nicknames: 机器人昵称列表
        :param message: 消息文本
        :return: bool 是否被提及
        """
        self_user_id = str(data.get("self", {}).get("user_id", ""))

        for seg in data.get("message", []):
            if seg.get("type") == "mention":
                mentioned_id = str(seg.get("data", {}).get("user_id", ""))
                if mentioned_id and mentioned_id == self_user_id:
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
        is_mentioned: bool = False,
    ) -> Optional[str]:
        """
        {!--< internal-use >!--} 生成 AI 回复：管线提示词 → 记忆/图片/工具注入 → 对话行为 → 工具循环

        :param user_id: 用户 ID
        :param group_id: 群组 ID，私聊为 None
        :param user_input: 用户消息文本
        :param image_urls: 图片 URL 列表
        :param user_nickname: 用户昵称
        :param group_name: 群名称
        :param platform: 平台标识
        :param data: 消息事件数据（工具调用转发用）
        :param is_mentioned: 是否被 @ 或叫名字
        :return: Optional[str] 生成的回复文本；判定为无效/失败时返回 None
        """
        try:
            history = await self.memory.get_session_history(user_id, group_id)

            # 构建系统提示词（通过注入管线）
            ctx = PromptContext(
                user_id=user_id,
                group_id=group_id,
                user_input=user_input,
                user_nickname=user_nickname,
                group_name=group_name,
                platform=platform,
                is_mentioned=is_mentioned,
                is_group=group_id is not None,
            )
            system_prompt = await self.pipeline.build(ctx)

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # 记忆上下文（按当前消息相关性检索）
            memory_ctx = await self._build_memory_context(
                user_id, history, group_id, user_input
            )
            if memory_ctx:
                messages.append({"role": "system", "content": memory_ctx})

            # 添加历史
            messages.extend(history[-15:])

            # 图片处理（检查视觉行为可用性）
            if image_urls:
                if self.ai_engine.is_available("vision"):
                    await self._inject_images(messages, image_urls, user_input)
                else:
                    self.logger.debug("视觉行为不可用，跳过图片分析")

            # MCP 工具（检查配置 + 对话工具支持）
            tools = None
            if self.config.get("mcp.enabled", True) and self.config.get(
                "mcp.auto_inject", True
            ):
                mcp_tools = self.mcp_manager.get_openai_tools_schema()
                if mcp_tools:
                    tools = list(mcp_tools)

            # 表情包始终可用（内嵌标签方式，不依赖函数调用）
            sticker_cfg = self.config.get("stickers", {})
            if sticker_cfg.get("enabled", True) and random.random() < sticker_cfg.get("probability", 0.3):
                catalog = self.sticker_manager.get_catalog_text()
                if catalog:
                    messages.insert(0, {
                        "role": "system",
                        "content": (
                            "【可用表情包】用 <|sticker|>名称</sticker|> 内嵌到回复里。"
                            "如果不知道说什么，也可以只发送【一个】表情包，不附带文字。\n"
                            + catalog
                        ),
                    })

            # 调用对话行为
            if not self.ai_engine.is_available("dialogue"):
                self.logger.warning("对话行为不可用，请配置模型")
                return None
            self.logger.info(f"调用对话行为 - 消息数: {len(messages)}")
            response = await self.ai_engine.dialogue(messages, tools=tools)

            # 多轮 MCP 工具调用处理（tool_call → tool_result → 再调用 AI → 直到返回文本）
            total_tool_cost = 0
            for _ in range(MAX_TOOL_ROUNDS):
                if not response or isinstance(response, str):
                    break
                # 执行工具调用
                tool_results = await self._handle_tool_calls(response, data)
                if not tool_results:
                    response = getattr(response, "content", None) or ""
                    break
                total_tool_cost += len(tool_results)
                # 超过调用次数上限 → 强制基于已有结果作答
                if total_tool_cost > MAX_TOOL_CALLS:
                    self.logger.warning(
                        f"工具调用次数过多 ({total_tool_cost})，强制结束"
                    )
                    response = await self._force_final_answer(messages)
                    break
                # 追加 assistant 消息（转 dict）
                if hasattr(response, "model_dump"):
                    msg_dict = response.model_dump(exclude_none=True)
                elif hasattr(response, "dict"):
                    msg_dict = response.dict(exclude_none=True)
                else:
                    msg_dict = {"role": "assistant", "content": response.content}
                    if hasattr(response, "tool_calls") and response.tool_calls:
                        msg_dict["tool_calls"] = [
                            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                            for tc in response.tool_calls
                        ]
                messages.append(msg_dict)
                messages.extend(tool_results)
                # 再次调用 AI，带上工具结果
                self.logger.info(f"工具结果已反馈，继续调用 AI，消息数: {len(messages)}")
                response = await self.ai_engine.dialogue(messages, tools=tools)

            # 工具查完了但模型没给出正文（推理额度被推理耗尽/截断等）→ 无工具重试强制作答
            if (not isinstance(response, str) or not response.strip()) and total_tool_cost > 0:
                response = await self._force_final_answer(messages)

            if not response or not isinstance(response, str):
                return None
            response = response.strip()

            # 过滤无效回复
            if self.humanizer.is_skip_response(response, is_private=group_id is None):
                self.logger.info(f"回复无效，不发送: {truncate_message(response, 40)}")
                return None

            # 行为输出模板
            response = self._apply_behavior_templates(
                response, user_id, group_id, user_nickname
            )

            self.logger.info(f"对话行为完成 - 回复: {truncate_message(response, 80)}")
            return response

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.error(f"生成回复失败: {e}")
            return None

    async def _force_final_answer(self, messages: List[Dict[str, Any]]) -> str:
        """
        {!--< internal-use >!--} 工具调用后未获得正文时，追加提醒并无工具重试强制作答

        适用场景：推理模型将 max_tokens 耗尽在推理阶段、响应被截断等导致
        content 为空。messages 以完整工具结果结尾，追加 user 提醒是合法序列。

        :param messages: 当前对话消息列表（以工具结果结尾）
        :return: str 模型最终回答，失败返回空字符串
        """
        self.logger.warning("工具调用后未获得正文，追加提醒并无工具重试强制作答")
        try:
            messages.append({
                "role": "user",
                "content": (
                    "（系统提示）工具调用到此为止。"
                    "基于上面已经查到的结果，直接把回答写给用户，不要再调用工具。"
                ),
            })
            result = await self.ai_engine.dialogue(messages, tools=None)
            return result if isinstance(result, str) else ""
        except Exception as e:
            self.logger.warning(f"强制作答失败: {e}")
            return ""

    async def _handle_tool_calls(self, message, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        {!--< internal-use >!--} 执行 AI 返回的 MCP 工具调用

        超长结果按 TOOL_RESULT_MAX_CHARS 截断，防止撑爆上下文。

        :param message: 含 tool_calls 的 assistant message 对象
        :param data: 消息事件数据（保留）
        :return: List[Dict] tool 角色结果消息列表（含失败占位结果）
        """
        tool_calls = getattr(message, "tool_calls", None) or []
        results = []
        for tc in tool_calls:
            func = getattr(tc, "function", None)
            if not func:
                continue
            try:
                arguments = json.loads(func.arguments)
            except Exception:
                arguments = {}
            try:
                result = await self.mcp_manager.call_tool(func.name, arguments)
                self.logger.debug(f"工具 {func.name} 返回: {truncate_message(result, 100)}")
                if isinstance(result, str) and len(result) > TOOL_RESULT_MAX_CHARS:
                    result = result[:TOOL_RESULT_MAX_CHARS] + "\n…(结果过长已截断)"
                    self.logger.info(
                        f"工具 {func.name} 结果过长，已截断至 {TOOL_RESULT_MAX_CHARS} 字符"
                    )
                results.append({
                    "role": "tool",
                    "tool_call_id": getattr(tc, "id", "call_") or "call_",
                    "content": result,
                })
            except Exception as e:
                self.logger.warning(f"工具 {func.name} 调用失败: {e}")
                results.append({
                    "role": "tool",
                    "tool_call_id": getattr(tc, "id", "call_") or "call_",
                    "content": f"调用失败: {e}",
                })
        return results

    def _find_sticker(self, name: str) -> Optional[dict]:
        """
        {!--< internal-use >!--} 匹配表情包：精确 → 双向包含/描述 → 截断模糊

        :param name: AI 输出的表情包名称
        :return: Optional[dict] 命中的表情包定义，未命中返回 None
        """
        name = name.strip().lower()
        if not name:
            return None
        # 精确匹配
        for s in self.sticker_manager.list_stickers():
            if s.get("name", "").lower() == name:
                return s
        # 包含匹配（双向：AI名在贴纸名中，或贴纸名在AI名中）
        for s in self.sticker_manager.list_stickers():
            sname = s.get("name", "").lower()
            if name in sname or sname in name:
                return s
            if name in s.get("description", "").lower():
                return s
        # 截断模糊（AI可能多写或少写一个字）
        if len(name) > 2:
            shortened = name[:-1]
            for s in self.sticker_manager.list_stickers():
                if shortened in s.get("name", "").lower():
                    return s
        return None

    async def _send_image(self, data: Dict[str, Any], platform: str, image_path: str) -> None:
        """
        {!--< internal-use >!--} 发送单张图片，统一转为 bytes 以规避跨容器路径问题

        支持 HTTP(S) URL（下载）、本地路径（读取）、base64:// 前缀（透传）。

        :param data: 消息事件数据（提取发送目标）
        :param platform: 平台标识
        :param image_path: 图片来源（URL/路径/base64）
        """
        detail_type = data.get("detail_type", "private")
        target_type = "group" if detail_type == "group" else "user"
        target_id = str(data.get("group_id", "")) if target_type == "group" else str(data.get("user_id", ""))
        if not target_id:
            return
        adapter = getattr(self.sdk.adapter, platform, None)
        if not adapter:
            return
        try:
            send_methods = self.sdk.adapter.list_sends(platform)
        except Exception:
            send_methods = []
        if "Image" not in send_methods:
            self.logger.warning(
                f"平台 {platform} 不支持 Image 发送，支持的方法: {send_methods}"
            )
            return

        try:
            if image_path.startswith("base64://"):
                # 已是适配器格式，直接透传
                await adapter.Send.To(target_type, target_id).Image(image_path)
            elif image_path.startswith(("http://", "https://")):
                # HTTP URL → 下载为 bytes
                resp = await self.sdk.client.get(image_path, timeout=30)
                if hasattr(resp, "content"):
                    img_bytes = resp.content
                else:
                    img_bytes = await resp.read() if hasattr(resp, "read") else resp
                self.logger.info(f"图片下载完成: {len(img_bytes)} bytes from {image_path}")
                await adapter.Send.To(target_type, target_id).Image(img_bytes)
            else:
                # 本地文件路径 → 读取为 bytes（不依赖适配器读文件）
                import os
                if not os.path.exists(image_path):
                    self.logger.warning(f"图片文件不存在: {image_path}")
                    return
                with open(image_path, "rb") as f:
                    img_bytes = f.read()
                if not img_bytes:
                    self.logger.warning(f"图片文件为空: {image_path}")
                    return
                self.logger.info(f"图片读取完成: {len(img_bytes)} bytes from {image_path}")
                await adapter.Send.To(target_type, target_id).Image(img_bytes)
            self.logger.info(f"已发送图片: {image_path}")
        except Exception as e:
            self.logger.warning(f"发送图片失败: {image_path} - {e}")

    async def _build_memory_context(
        self, user_id: str, history: List[Dict[str, str]], group_id: Optional[str],
        user_input: str = "",
    ) -> str:
        """构建记忆上下文（按相关性检索，替代旧的取最后N条）"""
        try:
            result = await self.memory.retrieve_relevant(
                user_id, user_input, group_id, top_k=8
            )
            user_mems = result.get("user", [])
            sender_mems = result.get("sender", [])

            if not user_mems and not sender_mems:
                return ""

            parts = []
            if user_mems:
                mem_lines = [f"- {m.get('content', '')}" for m in user_mems]
                parts.append("你记得关于对方的事情:\n" + "\n".join(mem_lines))

            if sender_mems:
                sender_lines = [f"- {m.get('content', '')}" for m in sender_mems]
                parts.append("你记得这个人说过的:\n" + "\n".join(sender_lines))

            return "\n\n".join(parts)
        except Exception:
            return ""

    @staticmethod
    def _platform_supports_voice(platform: str) -> bool:
        """
        {!--< internal-use >!--} 检查平台适配器是否支持语音发送

        :param platform: 平台标识
        :return: bool 是否支持 Voice 发送方法
        """
        try:
            return "Voice" in sdk.adapter.list_sends(platform)
        except Exception:
            return False

    async def _inject_images(
        self, messages: List[Dict[str, Any]], image_urls: List[str], user_input: str
    ) -> None:
        """
        {!--< internal-use >!--} 分析图片并将文字描述注入最后一条用户消息

        :param messages: 对话消息列表（就地修改）
        :param image_urls: 图片 URL 列表，最多取前 3 张
        :param user_input: 用户消息文本（单图分析时作为提示）
        """
        try:
            descriptions = []
            for url in image_urls[:3]:
                desc = await self.ai_engine.analyze_image(
                    url, user_input if len(image_urls) == 1 else ""
                )
                if desc:
                    descriptions.append(desc)

            if descriptions:
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i].get("role") == "user":
                        content = messages[i].get("content", "")
                        if isinstance(content, str):
                            messages[i]["content"] = (
                                content + "\n\n图片内容:\n" + "\n".join(descriptions)
                            )
                        break
            else:
                # 视觉分析全部失败时不注入 multimodal 内容
                # 对话模型多数是纯文本模型，无法处理 image_url 格式
                self.logger.debug(
                    f"视觉分析全部失败({len(image_urls)}张图片)，保持纯文本消息"
                )
        except Exception as e:
            self.logger.warning(f"图片处理失败: {e}")

    # ==================== 行为链：记忆提取 ====================

    _memory_locks: Dict[str, bool] = {}

    async def _extract_memory_async(
        self, user_id: str, group_id: Optional[str]
    ) -> None:
        """
        {!--< internal-use >!--} 异步提取长期记忆（会话级并发锁防重入）

        :param user_id: 用户 ID
        :param group_id: 群组 ID，私聊为 None
        """
        session_key = self.session.get_session_key(user_id, group_id)

        if Main._memory_locks.get(session_key):
            self.logger.debug(f"记忆提取跳过（上次仍在执行）: {session_key}")
            return
        Main._memory_locks[session_key] = True

        try:
            await self.memory.extract_from_history(user_id, group_id)
        except Exception as e:
            self.logger.debug(f"记忆提取异常: {e}")
        finally:
            Main._memory_locks[session_key] = False

    # ==================== 行为链：对话延续 ====================

    async def _continue_conversation(
        self, user_id: str, group_id: str, platform: str
    ) -> None:
        """
        {!--< internal-use >!--} 回复后的群聊持续监听：话题继续时可能追加回复

        在 continue_conversation 配置的消息数/时长限制内轮询新消息，
        由 reply_judge 行为判定是否继续参与。

        :param user_id: 用户 ID
        :param group_id: 群组 ID
        :param platform: 平台标识
        """
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

            for round_idx in range(max_msgs):
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > max_duration:
                    break

                # 轮询等待新消息（500ms 间隔，更流畅）
                waited = 0
                while waited < 10:
                    await asyncio.sleep(0.5)
                    waited += 0.5
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed > max_duration:
                        return
                    current = await self.memory.get_session_history(user_id, group_id)
                    if len(current) > initial_len:
                        break
                else:
                    # 10秒内无新消息，结束监听
                    self.logger.debug("持续监听：无新消息，结束")
                    return

                current = await self.memory.get_session_history(user_id, group_id)
                if len(current) <= initial_len:
                    continue

                # AI 判断是否继续
                if not self.ai_engine.is_available("reply_judge"):
                    return
                should = await self.ai_engine.should_continue(current[-8:], bot_name)
                if not should:
                    self.logger.debug("持续监听：AI 判断不需要继续")
                    return

                # 构建完整上下文回复（带系统提示词、场景等）
                latest_msg = current[-1].get("content", "") if current else ""
                response = await self._generate_response(
                    user_id, group_id, latest_msg, [],
                    current[-1].get("nickname", "") if current else "",
                    "", platform, {"detail_type": "group", "group_id": group_id},
                )
                if not response or not isinstance(response, str):
                    return

                # 拟人化延迟
                delay = self.humanizer.calc_typing_delay(response)
                if delay > 0:
                    await asyncio.sleep(delay)

                await self.message_sender.send(platform, "group", group_id, response)
                clean_resp = self.humanizer.clean_response_for_history(response)
                await self.memory.add_short_term_memory(
                    user_id, "assistant", clean_resp, group_id, bot_name
                )
                self._stats["total_replies"] += 1
                initial_len = len(
                    await self.memory.get_session_history(user_id, group_id)
                )
                self.logger.info(f"持续监听第{round_idx + 1}轮回复已发送")

        except Exception as e:
            self.logger.debug(f"持续监听结束: {e}")

    # ==================== 发送 ====================

    async def _send_response(
        self, data: Dict[str, Any], response: str, platform: str
    ) -> str:
        """
        {!--< internal-use >!--} 发送回复：解析表情包标签出图、清理标签碎片后发送文本

        表情包标签匹配支持标准/开标签带右尖括号/function calling 兼容/
        未闭合等多种格式，未命中的表情包名保留为纯文本。

        :param data: 消息事件数据（提取发送目标）
        :param response: 回复文本（可含 <|sticker|> 等内嵌标签）
        :param platform: 平台标识
        :return: str 清理标签后的文本内容
        """
        try:
            if not platform:
                return
            detail_type = data.get("detail_type", "private")
            if detail_type == "group":
                target_type, target_id = "group", data.get("group_id")
            else:
                target_type, target_id = "user", data.get("user_id")
            if not target_id:
                return

            # 解析文本中的表情包内嵌标签（统一正则，一次性匹配所有格式）
            # 格式1: <|sticker|名称</sticker|>  标准（注意：开标签无 >）
            # 格式2: <|sticker|>名称</sticker|>  开标签有 >
            # 格式3: <send_sticker><parameter...>名称</parameter></send_sticker>  兼容function calling
            # 格式4: <send_sticker>名称</send_sticker>  兼容
            # 格式5: <|sticker|名称  未闭合
            sticker_re = re.compile(
                r"<\|?\s*(?:sticker|send_sticker)\s*\|?>?"  # 开标签（> 可选）
                r"(?:\s*<parameter[^>]*>\s*)?"
                r"([^<>《\n]{1,30})"
                r"(?:\s*</parameter>\s*)?"
                r"\s*(?:<\|?\s*/?\s*(?:sticker|send_sticker)\s*\|?>|$)",
                re.IGNORECASE
            )
            # 反向遍历以保持索引正确
            sent_sticker_count = 0
            for match in reversed(list(sticker_re.finditer(response))):
                name = match.group(1).strip()
                if name:
                    matched = self._find_sticker(name)
                    if matched:
                        await self._send_image(data, platform, matched["file"])
                        sent_sticker_count += 1
                        # 表情包发送成功，从文本中移除整个标签
                        response = response[:match.start()] + response[match.end():]
                    else:
                        self.logger.warning(f"表情包标签未匹配: {name}")
                        # 未找到表情包，保留名称文本，只去除标签语法
                        response = response[:match.start()] + name + response[match.end():]

            # 清理残留的空标签碎片（不含内容，避免误删文本）
            response = re.sub(
                r"<\|?\s*/?(?:sticker|send_sticker)\s*\|?>"
                r"|</?parameter[^>]*>",
                "", response, flags=re.IGNORECASE
            ).strip()

            # 纯表情包场景：只发了图片没有文本，不发送空消息
            if response == "" and sent_sticker_count > 0:
                return

            if response:
                await self.message_sender.send(platform, target_type, target_id, response)
            return response
        except Exception as e:
            self.logger.error(f"发送回复失败: {e}")
            return response

    def _extract_images(self, data: Dict[str, Any]) -> List[str]:
        """
        {!--< internal-use >!--} 提取消息中的图片 URL（兼容 url/file/path/src 字段）

        :param data: 消息事件数据
        :return: List[str] 图片 URL 列表
        """
        urls = []
        for seg in data.get("message", []):
            if seg.get("type") in ("image", "img"):
                seg_data = seg.get("data", {})
                # 按优先级尝试多种字段名
                url = (
                    seg_data.get("url")
                    or seg_data.get("file")
                    or seg_data.get("path")
                    or seg_data.get("src")
                )
                if url:
                    urls.append(url)
        return urls
