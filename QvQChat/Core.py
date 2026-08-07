"""
QvQChat 主模块

消息处理编排器。核心创新：
- 行为链：行为可触发后续行为（如对话→表情→记忆）
- 拟人化回复：打字延迟、时间感知、情绪感知
- 预测模式：低token批量判断
"""

import asyncio
import random
import time
import traceback
from typing import Any, Dict, List, Optional

from ErisPulse import i18n, sdk
from ErisPulse.Core.Bases import BaseModule
from ErisPulse.Core.Event import message

from .config import QvQConfig, QvQConfigData
from .I18n import QvQI18n
from .agent.knowledge import KnowledgeBase
from .agent.multi import MultiAgentManager
from .agent.tools import MCPManager
from .ai import AIEngine, BehaviorManager, ModelPool
from .chat.memory import QvQMemory
from .chat.session import SessionManager
from .chat.sticker import StickerManager
from .dashboard import DashboardManager
from .utils import MessageSender, get_session_description, truncate_message

# ==================== 拟人化工具 ====================


def _calc_typing_delay(text: str, config=None) -> float:
    """根据回复长度计算拟人化打字延迟（秒）"""
    if config and not config.get("humanize.typing_delay", True):
        return 0
    min_d = config.get("humanize.min_delay", 0.5) if config else 0.5
    max_d = config.get("humanize.max_delay", 5.0) if config else 5.0
    length = len(text)
    if length <= 10:
        return random.uniform(min_d, min_d + 1.0)
    elif length <= 30:
        return random.uniform(min_d + 0.5, min_d + 2.0)
    elif length <= 80:
        return random.uniform(max_d - 2.0, max_d)
    else:
        return max_d


class Main(BaseModule):
    """
    QvQChat 主模块

    子系统：
    - AI 引擎：模型池 + 行为管理 + 执行引擎（故障转移）
    - 对话处理：记忆 + 会话管理（速率限制/活跃模式/回复判断）
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
        from ErisPulse.loaders import ModuleLoadStrategy

        return ModuleLoadStrategy(lazy_load=False, priority=50)

    async def on_load(self, event: Dict[str, Any]) -> bool:
        try:
            self._register_event_handlers()
            self.dashboard.register()
            # 异步连接 MCP 服务器（不阻塞模块加载）
            if self.config.get("mcp.enabled", True):
                asyncio.create_task(self._connect_mcp_servers())
            # 主动发起对话循环
            if self.config.get("human_state.proactive_message.enabled", False):
                asyncio.create_task(self._proactive_loop())
            self.logger.info(i18n.t("QvQChat.module_loaded"))
            return True
        except Exception as e:
            self.logger.error(i18n.t("QvQChat.module_load_failed", error=e))
            return False

    async def on_unload(self, event: Dict[str, Any]) -> bool:
        try:
            await self.mcp_manager.disconnect_all_servers()
            self.dashboard.unregister()
            self.logger.info(i18n.t("QvQChat.module_unloaded"))
            return True
        except Exception as e:
            self.logger.error(i18n.t("QvQChat.module_unload_failed", error=e))
            return False

    def _register_event_handlers(self) -> None:
        message.on_message(priority=999)(self._handle_message)

    async def _connect_mcp_servers(self) -> None:
        """异步连接所有已配置的 MCP 服务器"""
        try:
            await self.mcp_manager.connect_all_servers()
        except Exception as e:
            self.logger.warning(f"连接 MCP 服务器失败: {e}")

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

    # ==================== 运行统计 ====================

    def get_stats(self) -> Dict[str, Any]:
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
        """消息处理主入口（含消息聚合）"""
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
        """缓冲消息用于聚合（debounce 窗口）"""
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
        """聚合定时器任务"""
        try:
            await asyncio.sleep(window)
            await self._flush_buffer(session_key)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"聚合定时器出错: {e}")

    async def _flush_buffer(self, session_key: str) -> None:
        """冲刷缓冲区，处理聚合消息"""
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
        """处理单条/聚合后的消息（生成回复并发送）"""
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
            if group_id is not None and self._should_read_receipt_skip():
                return

            # 检测是否被提及（用于注入提示词）
            is_mentioned = self._is_mentioned(data, bot_nicknames, alt_message)

            session_desc = get_session_description(
                user_id, user_nickname, group_id, group_name
            )
            self.logger.info(
                f"开始回复 - {session_desc} - {truncate_message(alt_message, 80)}"
            )

            # 独立输出行为检查（表情包/图片等，不消耗 AI）
            output_result = self._check_output_behaviors(
                alt_message, user_id, group_id, user_nickname
            )
            if output_result:
                delay = _calc_typing_delay(output_result, self.config)
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
            response = self._apply_humanize_postprocess(response)

            # 拟人化打字延迟
            delay = _calc_typing_delay(response, self.config)
            if delay > 0:
                self.logger.debug(f"打字延迟: {delay:.1f}s")
                await asyncio.sleep(delay)

            # 群聊随机@对方
            if group_id and self.config.get("humanize.random_at_probability", 0.15) > 0:
                response = self._maybe_at_mention(data, response, user_nickname)

            # 发送回复
            await self._send_response(data, response, platform)
            self._stats["total_replies"] += 1
            self.logger.info(
                f"回复已发送 - {session_desc} - {truncate_message(response, 60)}"
            )

            # 更新回复时间
            self.session.update_last_reply_time(user_id, group_id)
            self.session.clear_cached_images(user_id, group_id)

            # 保存AI回复到记忆（清理特殊标签，避免历史污染）
            bot_names = self.config.get("bot_nicknames", [])
            bot_name = bot_names[0] if bot_names else ""
            clean_for_memory = self._clean_response_for_history(response)
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
                asyncio.create_task(self._extract_memory_async(user_id, group_id))

        except Exception as e:
            self.logger.error(f"处理消息出错: {e}\n{traceback.format_exc()}")

    async def _check_should_reply(
        self,
        data: Dict[str, Any],
        alt_message: str,
        user_id: str,
        group_id: Optional[str],
    ) -> bool:
        """检查是否应该回复"""
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
        """执行预测（低token模式）"""
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

        Returns:
            Optional[str]: 触发的输出内容，未触发返回 None
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
        应用行为的输出模板

        遍历所有已启用的场景/输出行为，概率性应用其 response_template。
        模板支持占位符：
        - {ai_response}: AI生成的文本
        - {at_user}: @{user_nickname}
        - [img]url[/img]: 发送图片（通过多消息发送器）
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

    def _maybe_at_mention(self, data, response, user_nickname):
        """随机@对方（群聊时增加互动感）"""
        prob = self.config.get("humanize.random_at_probability", 0.15)
        if random.random() < prob and user_nickname:
            if f"@{user_nickname}" not in response:
                return f"@{user_nickname} {response}"
        return response

    # ==================== 拟人化后处理 ====================

    def _apply_humanize_postprocess(self, response: str) -> str:
        """拟人化后处理：错字纠正、打字中断、半句发出等"""
        humanize = self.config.get("humanize", {})

        # 错字纠正（先执行，因为可能产生多消息）
        typo_prob = float(humanize.get("typo_probability", 0)) if humanize else 0
        if typo_prob > 0 and random.random() < typo_prob:
            response = self._inject_typo_correction(response)

        # 打字中断（半句发出）
        half_prob = float(humanize.get("half_send_probability", 0)) if humanize else 0
        if half_prob > 0 and random.random() < half_prob:
            response = self._inject_half_send(response)

        return response

    def _inject_typo_correction(self, text: str) -> str:
        """模拟打错字后下一条消息纠正

        策略：随机交换两个相邻中文字符，然后用 <|wait|> 分隔发纠正消息
        效果示例：
          消息1: 我天今好开心
          消息2: 打错了 是 今天
        """
        chinese_indices = [
            i for i, c in enumerate(text) if "\u4e00" <= c <= "\u9fff"
        ]
        if len(chinese_indices) < 4 or len(text) < 6:
            return text

        adjacent_pairs = []
        for idx in range(len(chinese_indices) - 1):
            p1, p2 = chinese_indices[idx], chinese_indices[idx + 1]
            if p2 == p1 + 1 and text[p1] != text[p2]:
                adjacent_pairs.append((p1, p2))

        if not adjacent_pairs:
            return text

        pos1, pos2 = random.choice(adjacent_pairs)
        char1, char2 = text[pos1], text[pos2]

        typo_text = text[:pos1] + char2 + char1 + text[pos2 + 1:]
        correct_word = char1 + char2

        corrections = [
            correct_word,
            f"打错了，{correct_word}",
            f"打错了 是{correct_word}",
            f"{correct_word}*",
            f"是{correct_word}",
        ]
        correction = random.choice(corrections)

        wait_time = random.randint(1, 3)
        self.logger.debug(f"拟人化[错字纠正]: {char1}{char2} -> {char2}{char1}")
        return f"{typo_text} <|wait time=\"{wait_time}\"|> {correction}"

    def _inject_half_send(self, text: str) -> str:
        """模拟打字打到一半不小心发出，后半句下一条才出来

        策略：在标点符号处或句子中间截断
        效果示例：
          消息1: 今天去吃了
          消息2: 一家超好吃的火锅
        """
        if len(text) < 8:
            return text

        break_chars = ["，", "。", "；", "、", "！", "？", ",", " ", "~", "～"]
        break_positions = []
        for i, c in enumerate(text):
            if c in break_chars and 3 < i < len(text) - 3:
                break_positions.append(i)

        if break_positions:
            pos = random.choice(break_positions)
            first_half = text[: pos + 1].strip()
            second_half = text[pos + 1 :].strip()
        else:
            mid = len(text) // 2 + random.randint(-2, 2)
            mid = max(4, min(mid, len(text) - 3))
            first_half = text[:mid].strip()
            second_half = text[mid:].strip()

        if not first_half or not second_half:
            return text

        wait_time = random.randint(1, 3)
        self.logger.debug(f"拟人化[半句发出]: 在位置 {len(first_half)} 处截断")
        return f"{first_half} <|wait time=\"{wait_time}\"|> {second_half}"

    def _should_read_receipt_skip(self) -> bool:
        """已读不回判断（低概率跳过回复，模拟真人偶尔看了不回）"""
        skip_prob = float(self.config.get("humanize.read_receipt_skip", 0))
        if skip_prob > 0 and random.random() < skip_prob:
            self.logger.debug("已读不回（拟人化）")
            return True
        return False

    @staticmethod
    def _clean_response_for_history(response: str) -> str:
        """清理回复中的特殊标签，避免历史记录污染

        移除以下标签（防止 AI 从历史中学到格式后在功能关闭时仍尝试使用）：
        - <|sticker|xxx</sticker|> → 移除（表情包标签）
        - <|voice style=".."|>xxx<|/voice|> → 只保留语音正文
        - <|wait time="N"|> → 移除（多消息分隔符）
        - [img]url[/img] / [sticker]file[/sticker] → 移除
        """
        import re

        # 表情包标签（含内容一起移除）
        response = re.sub(
            r"<\|?\s*(?:sticker|send_sticker)\s*\|?>?"
            r"(?:\s*<parameter[^>]*>\s*)?"
            r"[^<>《\n]{0,30}"
            r"(?:\s*</parameter>\s*)?"
            r"\s*(?:<\|?\s*/?\s*(?:sticker|send_sticker)\s*\|?>)?",
            "", response, flags=re.IGNORECASE
        )
        # 语音标签 → 只保留正文
        response = re.sub(
            r"<\|?\s*voice\s+style\s*=\s*[\"']?[^\"'>]*[\"']?\s*\|?>",
            "", response, flags=re.IGNORECASE
        )
        response = re.sub(
            r"<\|?\s*/\s*voice\s*\|?>", "", response, flags=re.IGNORECASE
        )
        # wait 分隔符
        response = re.sub(
            r"<\|\s*wait\s+time\s*=\s*[\"']?\d+[\"']?\s*\|?>", "", response, flags=re.IGNORECASE
        )
        response = re.sub(
            r"<\|\s*wait\s+time\s*=\s*[\"']?\d+[\"']?\s*>", "", response, flags=re.IGNORECASE
        )
        # [img] / [sticker] BBCode 标签
        response = re.sub(
            r"\[(?:img|sticker)\].*?\[/(?:img|sticker)\]", "", response, flags=re.IGNORECASE | re.DOTALL
        )
        # 清理多余空格
        response = re.sub(r"  +", " ", response).strip()
        return response if response else "(表情包/语音回复)"

    # ==================== 人类状态（情绪/精力） ====================

    def _get_human_state(self, session_key: str) -> Dict[str, float]:
        """获取当前情绪/精力状态"""
        state_cfg = self.config.get("human_state", {})
        if not state_cfg.get("enabled", True):
            return {"mood": 0.6, "energy": 0.8}

        from datetime import datetime

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
        """获取人类状态（供 Dashboard 显示）"""
        return self._get_human_state("global")

    @staticmethod
    def _mood_to_text(mood: float) -> str:
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
        """获取模块完整状态（供调试）"""
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
        """检查是否被@或叫名字

        仅使用事件中的 self.user_id 判断 mention 段是否指向自己，
        无需手动配置 bot_ids。
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

    # AI 可能输出的"不回复"标记（需要过滤）
    _SKIP_MARKERS = [
        "保持安静",
        "不回复",
        "没提到我",
        "没有问到",
        "(沉默)",
        "（沉默）",
        "[不回复]",
        "【不回复】",
        "(保持安静)",
        "（保持安静）",
        "[沉默]",
        "【沉默】",
        "(跳过)",
        "（跳过）",
        "(不回复)",
        "（不回复）",
        "不参与",
        "不需要回复",
        "SKIP",
        "skip",
        "NOREPLY",
        "noreply",
    ]
    # 正则：带括号的不回复推理
    _SKIP_REGEX = [
        r"（[^）]*不[^）]*回复[^）]*）",
        r"\([^)]*不[^)]*回复[^)]*\)",
        r"\[[^\]]*:\s*$",
        # 多行「昵称:内容」格式（AI在输出聊天记录）
        r"^[^:\n]{1,10}:\s.*\n[^:\n]{1,10}:\s",
    ]

    def _is_skip_response(self, text: str, is_private: bool = False) -> bool:
        """检测AI是否输出了无效回复

        Args:
            text: 待检测的回复文本
            is_private: 是否为私聊场景。私聊下不应用 _SKIP_REGEX 多行格式检测
                       （多行检测会误判正常的"昵称:内容"风格回复），仅检明确标记。
        """
        stripped = text.strip()
        if len(stripped) <= 60:
            for marker in self._SKIP_MARKERS:
                if marker in stripped:
                    return True
        import re

        # 私聊场景：只跑第一条括号推理检测，跳过多行聊天记录格式检测
        # （多行检测会把 AI 的正常多行回复误判为"输出聊天记录"）
        if is_private:
            if re.search(self._SKIP_REGEX[0], stripped):
                return True
            return False

        for pattern in self._SKIP_REGEX:
            if re.search(pattern, stripped):
                return True
        # 多行，每行都是"名字: 内容"格式（AI在输出聊天记录）
        lines = [l for l in stripped.split("\n") if l.strip()]
        if len(lines) >= 2:
            chat_count = sum(1 for l in lines if re.match(r"^[^:\n]{1,15}\s*:\s*", l))
            if chat_count >= len(lines) * 0.6:
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
        """生成AI回复"""
        try:
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

            # 场景提示（含时间感知 + 情绪感知 + 被提及感知）
            scene = self._build_scene_prompt(
                user_nickname, group_id is not None, user_input, platform,
                is_mentioned=is_mentioned,
            )
            if scene:
                messages.append({"role": "system", "content": scene})

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
            max_tool_rounds = 15
            total_tool_cost = 0
            for _ in range(max_tool_rounds):
                if not response or isinstance(response, str):
                    break
                # 执行工具调用
                tool_results = await self._handle_tool_calls(response, data)
                if not tool_results:
                    response = getattr(response, "content", None) or ""
                    break
                total_tool_cost += len(tool_results)
                # 超过 10 次工具调用 → 强制结束
                if total_tool_cost > 10:
                    self.logger.warning(f"工具调用次数过多 ({total_tool_cost})，强制结束")
                    response = getattr(response, "content", None) or ""
                    if not response:
                        response = "已经查了足够多信息了，让我总结一下。"
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

            if not response or not isinstance(response, str):
                return None
            response = response.strip()

            # 过滤无效回复
            if self._is_skip_response(response, is_private=group_id is None):
                self.logger.info(f"回复无效，不发送: {truncate_message(response, 40)}")
                return None

            # 行为输出模板
            response = self._apply_behavior_templates(
                response, user_id, group_id, user_nickname
            )

            self.logger.info(f"对话行为完成 - 回复: {truncate_message(response, 80)}")
            return response

        except Exception as e:
            self.logger.error(f"生成回复失败: {e}")
            return None

    async def _handle_tool_calls(self, message, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """处理 AI 返回的 MCP 工具调用，返回 tool result 消息列表"""
        import json

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
        """模糊匹配表情包名称"""
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
        """发送单张图片

        统一转为 bytes 发送（避免跨容器路径不通的问题）：
        - HTTP(S) URL：下载为 bytes
        - 本地文件路径：读取为 bytes
        - base64:// 前缀：直接透传（适配器已支持）
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

    def _build_system_prompt(
        self,
        user_id: str,
        group_id: Optional[str],
        user_input: str,
        user_nickname: str,
        group_name: str,
    ) -> str:
        """构建系统提示词（多智能体 + 知识库 + 行为提示词）"""
        rules = (
            self.behavior_manager.get_behavior_prompt("dialogue")
            or "【回复格式规则】\n口语化、简短、不要用任何格式。"
        )

        # 多智能体：人格 + 行为规则
        if self.config.get("multi_agent.enabled", True):
            session_key = self.session.get_session_key(user_id, group_id)
            agent_prompt = self.multi_agent.get_effective_prompt(session_key)
            if agent_prompt:
                prompt = agent_prompt + "\n\n" + rules
                source = "多智能体+行为"
            else:
                prompt = "你是一个真实的普通人，不是AI助手。\n\n" + rules
                source = "行为[默认]"
        else:
            prompt = "你是一个真实的普通人，不是AI助手。\n\n" + rules
            source = "行为[默认]"

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

        self.logger.info(f"提示词来源: {source}{kb_note} (共{len(prompt)}字符)")

        # MCP 工具使用提示
        if self.config.get("mcp.enabled", True) and self.mcp_manager.get_stats().get("total", 0) > 0:
            prompt += (
                "\n\n【工具使用】你可以调用工具查询信息。"
                "获取足够信息后请用文字回复，不要持续调工具。"
            )

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
            ctx = "你记得关于对方的事情:\n" + "\n".join(f"- {m}" for m in memories)

            if group_id:
                group_memory = await self.memory.get_group_memory(group_id)
                sender_mem = group_memory.get("sender_memory", {}).get(user_id, [])
                if sender_mem:
                    ctx += "\n\n你记得这个人说过的:\n" + "\n".join(
                        f"- {m['content']}" for m in sender_mem[-5:]
                    )

            return ctx
        except Exception:
            return ""

    def _build_scene_prompt(
        self, user_nickname: str, is_group: bool, user_input: str, platform: str,
        is_mentioned: bool = False,
    ) -> str:
        """
        构建场景提示

        完全由行为系统驱动：遍历所有已启用的场景行为，
        收集它们的提示词作为上下文。
        用户可以自由开关时间感知、情绪感知等。
        """
        parts = []

        # 场景上下文（不含身份声明-身份由智能体/行为提示词决定）
        if is_group:
            parts.append("当前在群聊中。")
        else:
            parts.append("当前在私聊中。")

        if user_nickname:
            parts.append(f"对方: {user_nickname}")

        # 被提及感知（被@时注入提示词，让 AI 知道这是专门对自己说的）
        if is_mentioned:
            parts.append("【你被@了】对方专门@了你，这条消息是直接对你说的，请务必回复。")

        # 情绪/精力状态感知
        state_cfg = self.config.get("human_state", {})
        if state_cfg.get("enabled", True) and self.config.get("humanize.mood_aware", True):
            session_key = "global"
            state = self._get_human_state(session_key)
            mood_desc = self._mood_to_text(state["mood"])
            energy_desc = self._energy_to_text(state["energy"])
            parts.append(f"你现在的状态: {mood_desc}，{energy_desc}")

        # 语音感知（如果语音功能启用 且 平台支持语音）
        if self.config.get("voice.enabled", False) and self._platform_supports_voice(
            platform
        ):
            parts.append(
                "你已经启用了语音功能，这是真实的可用功能。"
                '在回复中用 <|voice style="语气"|>文本<|/voice|> 格式就能发送语音。'
                "style 可以用自然语言描述任何效果（欢快、撒娇、四川话等）。"
            )

        # 遍历所有已启用的场景行为
        for behavior in self.behavior_manager.list_behaviors():
            if not behavior.get("enabled", True):
                continue
            if behavior.get("behavior_type") != "scene":
                continue

            bid = behavior.get("id", "")
            prompt = behavior.get("system_prompt", "")
            if not prompt:
                continue

            # 特殊处理：时间感知行为需要填充当前时段
            if bid == "time_aware":
                time_desc = self._get_time_description()
                parts.append(prompt % time_desc if "%s" in prompt else prompt)
            else:
                parts.append(prompt)

        active_behaviors = [
            b["id"]
            for b in self.behavior_manager.list_behaviors()
            if b.get("behavior_type") == "scene" and b.get("enabled", True)
        ]
        self.logger.info(
            f"场景行为: {active_behaviors or '无'} | 语音: {'开' if self.config.get('voice.enabled', False) else '关'}"
        )
        return "\n".join(parts)

    @staticmethod
    def _platform_supports_voice(platform: str) -> bool:
        """检查平台是否支持语音发送"""
        try:
            return "Voice" in sdk.adapter.list_sends(platform)
        except Exception:
            return False

    @staticmethod
    def _get_time_description() -> str:
        """获取当前时段描述"""
        from datetime import datetime

        hour = datetime.now().hour
        if 5 <= hour < 8:
            return "清晨，你刚醒还有点迷糊"
        elif 8 <= hour < 11:
            return "上午，你精力充沛"
        elif 11 <= hour < 13:
            return "中午，你可能在吃饭"
        elif 13 <= hour < 17:
            return "下午，你有点困但还行"
        elif 17 <= hour < 20:
            return "傍晚，你心情不错比较放松"
        elif 20 <= hour < 24:
            return "晚上，你比较活跃"
        else:
            return "深夜，你有点困了但还在熬夜"

    async def _inject_images(
        self, messages: List[Dict[str, Any]], image_urls: List[str], user_input: str
    ) -> None:
        """将图片注入消息"""
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
        """异步提取记忆（带并发控制 + 超时）"""
        session_key = self.session.get_session_key(user_id, group_id)

        if Main._memory_locks.get(session_key):
            self.logger.debug(f"记忆提取跳过（上次仍在执行）: {session_key}")
            return
        Main._memory_locks[session_key] = True

        try:
            history = await self.memory.get_session_history(user_id, group_id)
            if len(history) < 4:
                return

            # 只取最近几轮对话，减少 prompt 大小（避免超时）
            recent = history[-8:]
            # 截断过长的单条消息
            dialogue_lines = []
            for m in recent:
                content = m.get("content", "")
                if len(content) > 200:
                    content = content[:200] + "..."
                role = "我" if m.get("role") == "assistant" else "对方"
                dialogue_lines.append(f"{role}: {content}")
            dialogue_text = "\n".join(dialogue_lines)

            prompt = (
                "从以下对话中提取值得长期记忆的关键信息"
                "（个人信息、偏好、重要事件、关系等）。\n"
                "如果没有值得记忆的就回复'无'。\n"
                "每条记忆一行，用 - 开头。\n\n"
                f"{dialogue_text}"
            )

            memory_timeout = float(self.config.get("memory.timeout", 60.0))
            result = await asyncio.wait_for(
                self.ai_engine.memory_process(prompt),
                timeout=memory_timeout,
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
            self.logger.warning(f"行为[memory]超时({int(self.config.get('memory.timeout', 60.0))}s)，跳过")
        except Exception as e:
            self.logger.debug(f"记忆提取跳过: {e}")
        finally:
            Main._memory_locks[session_key] = False

    # ==================== 行为链：对话延续 ====================

    async def _continue_conversation(
        self, user_id: str, group_id: str, platform: str
    ) -> None:
        """AI回复后的持续监听

        在群聊中，机器人回复后继续监听新消息，
        如果话题仍在继续，可能会再次回复。
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
                delay = _calc_typing_delay(response, self.config)
                if delay > 0:
                    await asyncio.sleep(delay)

                await self.message_sender.send(platform, "group", group_id, response)
                clean_resp = self._clean_response_for_history(response)
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

    # ==================== 主动发起对话 ====================

    async def _proactive_loop(self) -> None:
        """主动发起对话循环（间隔可配置）"""
        await asyncio.sleep(60)  # 启动后等待1分钟
        while True:
            try:
                await self._check_proactive_messages()
            except Exception as e:
                self.logger.debug(f"主动发起循环出错: {e}")
            interval = int(
                self.config.get(
                    "human_state.proactive_message.check_interval_minutes", 30
                )
            )
            await asyncio.sleep(max(interval, 5) * 60)

    @staticmethod
    def _humanize_duration(seconds: Optional[float]) -> str:
        """把秒数转成「x分钟/x小时/x天」的可读时长"""
        if seconds is None or seconds < 0:
            return "未知"
        mins = int(seconds / 60)
        if mins < 1:
            return "不到1分钟"
        if mins < 60:
            return f"{mins}分钟"
        hours = mins / 60
        if hours < 24:
            return f"{hours:.1f}小时"
        days = hours / 24
        return f"{days:.1f}天"

    @staticmethod
    def _relative_time_from_iso(ts_iso: str, now_ts: float) -> str:
        """把 ISO 时间戳转成相对当前的可读描述"""
        if not ts_iso:
            return ""
        from datetime import datetime

        try:
            t = datetime.fromisoformat(ts_iso).timestamp()
        except Exception:
            return ""
        gap = now_ts - t
        if gap < 60:
            return "刚刚"
        if gap < 3600:
            return f"{int(gap / 60)}分钟前"
        if gap < 86400:
            return f"{gap / 3600:.1f}小时前"
        return f"{gap / 86400:.1f}天前"

    async def _check_proactive_messages(self) -> None:
        """检查是否有需要主动发起的会话

        判定顺序：
        1. 沉寂门槛（距上次 AI 回复）
        2. 每日上限
        3. 概率命中
        """
        proactive_cfg = self.config.get("human_state.proactive_message", {})
        if not proactive_cfg.get("enabled", False):
            return

        min_hours = float(proactive_cfg.get("min_silence_hours", 6))
        probability = float(proactive_cfg.get("probability", 0.1))
        min_threshold = min_hours * 3600
        max_per_day = int(proactive_cfg.get("max_per_day", 1))

        if not self.ai_engine.is_available("dialogue"):
            return

        now = time.time()

        for session_key in self.session.get_all_session_keys():
            meta = self.session.get_session_meta(session_key)
            if not meta:
                continue

            # 1. 沉寂门槛（距上次 AI 回复）
            last_reply = self.session.get_last_reply_time_by_key(session_key)
            reply_silence = now - last_reply if last_reply else 999999
            if reply_silence < min_threshold:
                continue

            # 2. 每日上限
            if not self.session.check_proactive_daily_limit(
                session_key, max_per_day
            ):
                self.logger.debug(
                    f"{session_key} 主动发起已达每日上限({max_per_day})，跳过"
                )
                continue

            # 3. 概率命中
            if random.random() >= probability:
                continue

            await self._send_proactive_message(session_key, meta)

    @staticmethod
    def _iso_to_age_seconds(ts_iso: str, now_ts: float) -> Optional[float]:
        """把 ISO 时间戳转成「距今多少秒」，失败返回 None"""
        if not ts_iso:
            return None
        from datetime import datetime

        try:
            return now_ts - datetime.fromisoformat(ts_iso).timestamp()
        except Exception:
            return None

    @staticmethod
    def _format_history_label(age_seconds: Optional[float], role: str) -> str:
        """给历史消息生成时效性标签（让 AI 感知话题已陈旧）

        - 短（< 5 分钟）：[刚刚]
        - 中（5 分钟 ~ 1 小时）：[x分钟前]
        - 长（> 1 小时）：[x小时前 · 话题已结束]
        - 极长（> 1 天）：[x天前 · 已过时]
        """
        if age_seconds is None or age_seconds < 0:
            return ""
        mins = age_seconds / 60
        if mins < 5:
            tag = "刚刚"
        elif mins < 60:
            tag = f"{int(mins)}分钟前"
        elif mins < 1440:
            tag = f"{mins / 60:.1f}小时前 · 话题已结束"
            if role == "user":
                tag += " · 不要直接回应这条"
        else:
            tag = f"{mins / 1440:.1f}天前 · 已过时"
        return f"【{tag}】"

    def _get_proactive_motivation(self, hour: int) -> str:
        """按时段返回真人主动搭话的内在动机（用于让 AI 知道"为什么想说"）"""
        if 0 <= hour < 6:
            return (
                "你睡不着（或被什么惊醒），脑子里乱糟糟的，"
                "突然想找个人说点有的没的——多半是情绪化的、零碎的、私密的。"
            )
        if 6 <= hour < 9:
            return (
                "你刚醒没多久，还有点迷糊，"
                "可能想分享一下梦境、或者就单纯跟对方打个招呼说「早」。"
            )
        if 9 <= hour < 12:
            return (
                "上午你精神还行，如果主动找对方多半是"
                "想起某件具体的事、或者惦记着上次的某个话题。"
            )
        if 12 <= hour < 14:
            return (
                "中午吃饭的空档，你想随便扯两句——"
                "可能就是问问对方吃了没，或者吐槽一下手头的事。"
            )
        if 14 <= hour < 17:
            return (
                "下午你有点犯困/无聊想摸鱼，"
                "想找人说点轻松的、不费脑子的闲话。"
            )
        if 17 <= hour < 20:
            return (
                "傍晚你心情比较放松，"
                "想分享今天的见闻、吐槽一下白天发生的事。"
            )
        if 20 <= hour < 23:
            return (
                "晚上是你最活跃的时段，"
                "如果主动找对方多半是想正经聊聊、或者情绪到位想说点走心的。"
            )
        return (
            "深夜了你还醒着，"
            "想说点什么但又不至于太长——多半是临睡前的一句碎碎念。"
        )

    def _build_proactive_prompt(
        self,
        is_group: bool,
        time_desc: str,
        mood_text: str,
        energy_text: str,
        reply_gap: str,
        incoming_gap: str,
        incoming_silence: Optional[float],
    ) -> str:
        """构建主动发起对话的提示词

        核心策略：
        1. 明确告诉 AI "现在是主动发起，不是回复"
        2. 注入真实时间感（沉默多久 / 话题已结束多久）
        3. 注入真人主动搭话范式（few-shot）
        4. 时段化搭话动机
        5. 强约束：不要"接"最近一条消息、不要解释为什么突然说话
        """
        from datetime import datetime

        hour = datetime.now().hour
        motivation = self._get_proactive_motivation(hour)

        # 距最后一条他人消息的"陈旧度"
        if incoming_silence is None:
            incoming_staleness_hint = (
                "（群里/对方很久没说话了，可能是死群，要慎重新开话题）"
            )
        elif incoming_silence < 300:
            incoming_staleness_hint = (
                "——对方刚说完没多久，话题可能还热，但你要做的是「插话参与」而不是「回复」"
            )
        elif incoming_silence < 1800:
            incoming_staleness_hint = (
                "——话题还有点余温，但已经过去了，真人多半不会回头接"
            )
        elif incoming_silence < 7200:
            incoming_staleness_hint = "——话题早就凉了，不要回头接"
        else:
            incoming_staleness_hint = "——已经是很久以前的话，绝对不要直接回应"

        scene = "群聊" if is_group else "私聊"
        other = "群里" if is_group else "对方"

        prompt = (
            f"现在是{time_desc}，你{mood_text}，{energy_text}。\n\n"
            f"【时间感】\n"
            f"- 距离你上次开口说话：{reply_gap}\n"
            f"- 距离{other}最后一条消息：{incoming_gap} {incoming_staleness_hint}\n\n"
            f"【任务定位：这是「主动发起」，不是「回复」】\n"
            f"你现在身处{scene}，{motivation}\n"
            f"你想主动开口说一句话——是「想起来要说点什么」的主动行为，不是在回应别人刚说的话。\n\n"
            f"【真人主动搭话的本质特征（体会一下，不要背诵）】\n"
            f"- 真人开口前，脑子里一定先闪过一个念头（可能是件事、一种情绪、一个画面、甚至只是个声音）\n"
            f"- 这个念头不会每次都长得一样（今天可能是想起件旧事，明天可能是单纯睡不着）\n"
            f"- 真人不会为了「开口」而开口；是因为「有个念头想说」才开口\n"
            f"- 开头的那几个字，是念头自然溢出的结果，不是套公式\n\n"
            f"【强约束】\n"
            f"- 1~2 句话，简短、自然、口语化\n"
            f"- 不要解释「为什么突然说话」（真人不会解释）\n"
            f"- 不要回头接最后一条消息的内容（话题已经过去了）\n"
            f"- 不要长篇大论、不要强行没话找话\n"
            f"- **不要每次都用同一种方式开口**（真人不会每次都「对了」或都「突然想起」）\n"
            f"- 如果实在没什么想说的，只输出「(沉默)」选择不说\n\n"
            f"【下面的历史仅供你回忆上下文，禁止直接回应它们】\n"
        )
        return prompt

    async def _send_proactive_message(
        self, session_key: str, meta: Dict[str, str]
    ) -> None:
        """对指定会话主动发起对话（让 AI 感知真实时间跨度）"""
        platform = meta.get("platform", "")
        target_type = meta.get("target_type", "user")
        target_id = meta.get("target_id", "")
        if not platform or not target_id:
            return

        try:
            is_group = target_type == "group"
            user_id = "" if is_group else target_id
            group_id = target_id if is_group else None

            # 拉取带时间戳的完整历史
            detailed = await self.memory.get_session_history_detailed(
                user_id or target_id, group_id
            )

            # 计算真实时间跨度
            now = time.time()
            last_reply = self.session.get_last_reply_time_by_key(session_key)
            reply_silence = now - last_reply if last_reply else None
            last_incoming = self.session.get_last_incoming_time(session_key)
            incoming_silence = now - last_incoming if last_incoming else None

            time_desc = self._get_time_description()
            state = self._get_human_state(session_key)
            mood_text = self._mood_to_text(state["mood"])
            energy_text = self._energy_to_text(state["energy"])

            reply_gap = self._humanize_duration(reply_silence)
            incoming_gap = self._humanize_duration(incoming_silence)

            # 构建主动发起的提示词（注入真实时间跨度 + 真人化搭话动机）
            proactive_prompt = self._build_proactive_prompt(
                is_group=is_group,
                time_desc=time_desc,
                mood_text=mood_text,
                energy_text=energy_text,
                reply_gap=reply_gap,
                incoming_gap=incoming_gap,
                incoming_silence=incoming_silence,
            )

            system_prompt = self._build_system_prompt(
                user_id or target_id, group_id, "", "", ""
            )
            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_prompt or "你是一个真实的普通人。"},
                {"role": "system", "content": proactive_prompt},
            ]

            # 注入历史：把时间标注升级为时效性标注，让 AI 真切感知"话题已结束"
            if detailed:
                now_ts = time.time()
                for msg in detailed[-5:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    msg_ts_iso = msg.get("timestamp", "")
                    msg_age = self._iso_to_age_seconds(msg_ts_iso, now_ts)
                    label = self._format_history_label(msg_age, role)
                    if label:
                        content = f"{label} {content}".strip()
                    messages.append({"role": role, "content": content})

            response = await self.ai_engine.dialogue(messages)
            if not response or not isinstance(response, str):
                return
            response = response.strip()

            # AI 选择沉默 / 无效回复
            if self._is_skip_response(response) or not response:
                self.logger.info(
                    f"主动发起选择沉默 - {session_key} - {truncate_message(response, 40)}"
                )
                return

            delay = _calc_typing_delay(response, self.config)
            if delay > 0:
                await asyncio.sleep(delay)

            await self.message_sender.send(platform, target_type, target_id, response)
            self._stats["total_replies"] += 1

            # 主动发起成功 → 递增每日计数
            self.session.increment_proactive_count(session_key)
            # 更新该会话的「最后回复时间」
            self.session.update_last_reply_time(
                user_id or target_id, group_id
            )

            bot_names = self.config.get("bot_nicknames", [])
            bot_name = bot_names[0] if bot_names else ""
            clean_resp = self._clean_response_for_history(response)
            await self.memory.add_short_term_memory(
                user_id or target_id, "assistant", clean_resp, group_id, bot_name
            )
            self.logger.info(
                f"主动发起对话 - {session_key} - {truncate_message(response, 60)}"
            )
        except Exception as e:
            self.logger.debug(f"主动发起对话失败: {e}")

    # ==================== 工具方法 ====================

    async def _send_response(
        self, data: Dict[str, Any], response: str, platform: str
    ) -> None:
        """发送回复（自动处理文本中的 <|send_sticker|> 标签）"""
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
            import re
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

            # 纯表情包场景：只发了表情包没有文本，不发送空消息
            if sent_sticker_count > 0 and not response:
                return

            if response:
                await self.message_sender.send(platform, target_type, target_id, response)
        except Exception as e:
            self.logger.error(f"发送回复失败: {e}")

    def _extract_images(self, data: Dict[str, Any]) -> List[str]:
        """提取消息中的图片URL（兼容多种消息段格式）"""
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
