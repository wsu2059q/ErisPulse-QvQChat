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
from .chat.sticker import StickerManager
from .config import QvQConfig
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

        # 运行统计
        self._stats = {
            "total_messages": 0,
            "total_replies": 0,
            "total_tokens_est": 0,
            "started_at": time.time(),
        }

        self.logger.info("QvQChat 模块初始化完成")

        # 检查配置引导
        if not self.model_pool.list_models():
            self.logger.warning(
                "尚未配置任何 AI 模型。请在 Dashboard 的「模型管理」中添加模型，"
                "然后在「行为管理」中为行为分配模型。"
            )
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
                    f"以下行为未分配模型: {', '.join(unassigned)}。"
                    "请在 Dashboard 的「行为管理」中分配。"
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
            self.logger.info("QvQChat 模块已加载")
            return True
        except Exception as e:
            self.logger.error(f"QvQChat 模块加载失败: {e}")
            return False

    async def on_unload(self, event: Dict[str, Any]) -> bool:
        try:
            await self.mcp_manager.disconnect_all_servers()
            self.dashboard.unregister()
            self.logger.info("QvQChat 模块已卸载")
            return True
        except Exception as e:
            self.logger.error(f"QvQChat 模块卸载失败: {e}")
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
        """消息处理主入口"""
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

            # 累积到短期记忆
            await self.memory.add_short_term_memory(
                user_id, "user", alt_message, group_id, user_nickname
            )

            # 更新群沉寂 + 注册群组
            if group_id:
                self.session.update_group_silence(user_id, group_id)
                # 确保群组被注册（Dashboard 可见）
                if group_id not in self.config.list_all_groups():
                    group_cfg = self.config.get_group_config(group_id)
                    if group_name:
                        group_cfg["group_name"] = group_name
                    self.config.set_group_config(group_id, group_cfg)
                    self.logger.info(f"发现新群组: {group_name or group_id}")

            # 判断是否回复
            should_reply = await self._check_should_reply(
                data, alt_message, user_id, group_id
            )

            if not should_reply:
                self.logger.debug("窥屏模式决定不回复")
                return

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
                # 独立输出行为命中，直接发送（跳过 AI 调用）
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

            # 速率限制
            est_tokens = SessionManager.estimate_tokens(alt_message) * 2
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
            )

            if not response:
                return
            
            import re
            is_sticker_only = bool(re.match(r'^\[.+\]$', response))

            if is_sticker_only:
                self._stats["total_replies"] += 1
                self.session.update_last_reply_time(user_id, group_id)
                self.logger.info(f"表情包已发送: {response}")
                return

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

            # 保存AI回复到记忆
            bot_names = self.config.get("bot_nicknames", [])
            bot_name = bot_names[0] if bot_names else ""
            await self.memory.add_short_term_memory(
                user_id, "assistant", response, group_id, bot_name
            )

            # 行为链：群聊后续监听
            if group_id:
                asyncio.create_task(
                    self._continue_conversation(user_id, group_id, platform)
                )

            # 行为链：回复后异步提取记忆（检查行为可用性）
            if self.ai_engine.is_available("memory"):
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

        # 检查 @机器人（优先使用事件 self.user_id）
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
            bot_ids,
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

        优先使用事件中的 self.user_id 判断 mention 段是否指向自己，
        而非依赖配置中手动维护的 bot_ids。
        """
        self_user_id = str(data.get("self", {}).get("user_id", ""))
        bot_ids = self.config.get("bot_ids", [])
        all_bot_ids = {self_user_id} | {str(b) for b in bot_ids if b}

        for seg in data.get("message", []):
            if seg.get("type") == "mention":
                mentioned_id = str(seg.get("data", {}).get("user_id", ""))
                if mentioned_id and mentioned_id in all_bot_ids:
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

    def _is_skip_response(self, text: str) -> bool:
        """检测AI是否输出了无效回复"""
        stripped = text.strip()
        if len(stripped) <= 60:
            for marker in self._SKIP_MARKERS:
                if marker in stripped:
                    return True
        import re

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

            # 场景提示（含时间感知 + 情绪感知）
            scene = self._build_scene_prompt(
                user_nickname, group_id is not None, user_input, platform
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

            # 表情包工具（AI 可自主选择发送表情包）
            sticker_cfg = self.config.get("stickers", {})
            if sticker_cfg.get("enabled", True):
                prob = sticker_cfg.get("probability", 0.3)
                if random.random() < prob:
                    sticker_tool = self.sticker_manager.get_openai_tool_schema()
                    if sticker_tool:
                        tools = tools or []
                        tools.append(sticker_tool)
                        # 仅当工具注入时才告诉 AI 有表情包
                        catalog = self.sticker_manager.build_sticker_catalog_text()
                        if catalog:
                            messages.insert(0, {
                                "role": "system",
                                "content": (
                                    "【可用表情包】你可以用 send_sticker 和文字配合使用。\n"
                                    + catalog
                                ),
                            })

            # 调用对话行为
            if not self.ai_engine.is_available("dialogue"):
                self.logger.warning("对话行为不可用，请配置模型")
                return None
            self.logger.info(f"调用对话行为 - 消息数: {len(messages)}")
            response = await self.ai_engine.dialogue(messages, tools=tools)

            # 处理 tool_calls（表情包等）
            if response and not isinstance(response, str):
                response = await self._handle_tool_calls(
                    response, user_id, group_id, user_nickname, platform, data
                )

            if not response or not isinstance(response, str):
                return None
            response = response.strip()

            # 过滤无效回复
            if self._is_skip_response(response):
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

    async def _handle_tool_calls(
        self,
        message,
        user_id: str,
        group_id: Optional[str],
        user_nickname: str,
        platform: str,
        data: Dict[str, Any],
    ) -> Optional[str]:
        """
        处理 AI 返回的 tool_calls

        支持：
        - send_sticker: 查找并发送表情包图片
        - MCP 工具: 调用 HTTP/stdio 工具并反馈结果

        Returns:
            最终文本回复（可能为空字符串表示已发送纯表情包）
        """
        import json

        tool_calls = getattr(message, "tool_calls", None) or []
        text_content = getattr(message, "content", None) or ""

        # 无工具调用也无文字 → 空回复
        if not tool_calls and not text_content.strip():
            return ""

        # 处理工具调用并发送表情包图片
        sticker_images = []
        for tc in tool_calls:
            func = getattr(tc, "function", None)
            if not func:
                continue
            tool_name = func.name
            try:
                arguments = json.loads(func.arguments)
            except Exception:
                arguments = {}

            if tool_name == "send_sticker":
                sticker_name = arguments.get("sticker_name", "")
                matched = self._find_sticker(sticker_name)
                if matched:
                    sticker_images.append(matched["file"])
                    self.logger.info(f"表情包匹配: {matched['name']}")
                else:
                    self.logger.debug(f"未找到表情包: {sticker_name}")
            else:
                try:
                    result = await self.mcp_manager.call_tool(tool_name, arguments)
                    self.logger.debug(f"工具 {tool_name} 返回: {truncate_message(result, 100)}")
                except Exception as e:
                    self.logger.warning(f"工具 {tool_name} 调用失败: {e}")

        # 发送表情包
        sent_sticker_names = []
        for img_path in sticker_images:
            try:
                await self._send_image(data, platform, img_path)
                for s in self.sticker_manager.list_stickers():
                    if s.get("file") == img_path:
                        sent_sticker_names.append(s.get("name", ""))
                        break
            except Exception as e:
                self.logger.warning(f"发送表情包失败: {e}")

        # 拼装回复（用于记忆/日志）
        text = text_content.strip()
        if sent_sticker_names:
            sticker_part = "[" + ", ".join(sent_sticker_names) + "]"
            return (text + " " + sticker_part) if text else sticker_part

        return text

    def _find_sticker(self, name: str) -> Optional[dict]:
        """模糊匹配表情包名称"""
        name = name.strip().lower()
        if not name:
            return None
        # 精确匹配
        for s in self.sticker_manager.list_stickers():
            if s.get("name", "").lower() == name:
                return s
        # 包含匹配
        for s in self.sticker_manager.list_stickers():
            if name in s.get("name", "").lower():
                return s
            if name in s.get("description", "").lower():
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
            self.logger.debug(f"平台 {platform} 不支持 Image")
            return

        try:
            if image_path.startswith("base64://"):
                # 已是适配器格式，直接透传
                await adapter.Send.To(target_type, target_id).Image(image_path)
            elif image_path.startswith(("http://", "https://")):
                # HTTP URL → 下载为 bytes
                resp = await self.sdk.client.get(image_path, timeout=30)
                img_bytes = resp.content if hasattr(resp, "content") else resp.read()
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
        self, user_nickname: str, is_group: bool, user_input: str, platform: str
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

            recent = history[-15:]
            dialogue_text = "\n".join(f"{m['role']}: {m['content']}" for m in recent)

            prompt = (
                "从以下对话中提取值得长期记忆的关键信息"
                "（个人信息、偏好、重要事件、关系等）。\n"
                "如果没有值得记忆的就回复'无'。\n"
                "每条记忆一行，用 - 开头。\n\n"
                f"{dialogue_text}"
            )

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
                await self.memory.add_short_term_memory(
                    user_id, "assistant", response, group_id, bot_name
                )
                self._stats["total_replies"] += 1
                initial_len = len(
                    await self.memory.get_session_history(user_id, group_id)
                )
                self.logger.info(f"持续监听第{round_idx + 1}轮回复已发送")

        except Exception as e:
            self.logger.debug(f"持续监听结束: {e}")

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

            # 解析文本中的 <|send_sticker|>name</send_sticker|> 标签
            import re
            sticker_pattern = re.compile(
                r"<\|\s*send_sticker\s*\|?>\s*(.*?)\s*<\|\s*/\s*send_sticker\s*\|?>",
                re.IGNORECASE | re.DOTALL,
            )
            for match in sticker_pattern.finditer(response):
                sticker_name = match.group(1).strip()
                if sticker_name:
                    matched = self._find_sticker(sticker_name)
                    if matched:
                        await self._send_image(data, platform, matched["file"])
            response = sticker_pattern.sub("", response).strip()

            if response:
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
