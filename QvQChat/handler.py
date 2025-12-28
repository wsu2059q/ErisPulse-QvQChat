from typing import Dict, List, Any, Optional
from .utils import get_session_description, truncate_message


class QvQHandler:
    """
    意图处理器
    
    负责处理各种意图的具体执行逻辑，包括：
    - 普通对话
    - 记忆查询、添加、删除
    - 群配置管理
    - 会话管理
    """
    
    def __init__(self, config, memory, ai_manager, state_manager, logger):
        self.config = config
        self.memory = memory
        self.ai_manager = ai_manager
        self.state = state_manager
        self.logger = logger.get_child("QvQHandler")

    def is_voice_available(self, platform: Optional[str] = None) -> bool:
        """
        检查语音功能是否可用

        Args:
            platform: 平台名称（可选）

        Returns:
            bool: 语音功能是否可用
        """
        # 检查语音配置
        voice_config = self.config.get("voice", {})
        if not voice_config.get("enabled", False):
            return False

        # 检查API密钥
        api_key = voice_config.get("api_key", "")
        if not api_key or not api_key.strip():
            return False

        # 如果提供了平台，检查平台支持
        if platform:
            supported_platforms = self.config.get("voice.platforms", ["qq", "onebot11"])
            return platform in supported_platforms

        return True
    
    async def handle_dialogue(
        self,
        user_id: str,
        group_id: Optional[str],
        params: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> str:
        """
        处理普通对话（记忆自然融入对话）

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
            params: 参数字典（包含image_urls和context_info）
            intent_data: 意图数据

        Returns:
            str: AI回复内容
        """
        user_input = intent_data["raw_input"]
        image_urls = params.get("image_urls", [])  # 获取图片URL列表
        context_info = params.get("context_info", {})  # 获取上下文信息

        # 获取会话描述用于日志
        session_desc = get_session_description(
            user_id,
            context_info.get("user_nickname", ""),
            group_id,
            context_info.get("group_name", "")
        )

        # 获取会话历史（已包含当前用户消息，因为Core.py已添加）
        session_history = await self.memory.get_session_history(user_id, group_id)

        # 记录对话处理开始
        self.logger.info(f"🗣️ 对话处理 - {session_desc} - 输入: {truncate_message(user_input, 80)}")
        if image_urls:
            self.logger.info(f"🖼️ 包含图片 - {session_desc} - 数量: {len(image_urls)}张")

        # 构建消息列表
        messages = []
        system_prompt = self.config.get_effective_system_prompt(user_id, group_id)

        # 添加上下文信息到系统提示
        context_prompt = self._build_context_prompt(context_info, group_id is not None)
        if context_prompt:
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "system", "content": context_prompt})
            else:
                messages.append({"role": "system", "content": context_prompt})
        elif system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 准备记忆上下文（在对话之前总结之前的会话历史）
        memory_context = await self._prepare_memory_context(user_id, session_history, group_id)
        if memory_context:
            messages.append({"role": "system", "content": memory_context})

        # 添加当前上下文提示（包含用户昵称）
        user_nickname = context_info.get("user_nickname", "")
        platform = context_info.get("platform", "")

        # 检查语音功能是否可用（平台支持+API配置）
        voice_available = self.is_voice_available(platform)
        voice_hint = ""

        # 多消息回复格式规则
        multi_message_hint = """
【多消息回复格式】
如果你想说多句话，用这种格式：
第一句话
<|wait time="1"|>
第二句话
<|wait time="2"|>
第三句话


数字表示秒数，最多3条消息，每条间隔1-5秒。"""

        if voice_available:
            voice_hint = """
【语音输出功能】
- 每条消息都可以独立包含语音，支持一次发送多条语音
- 语音格式：在消息中用 <|voice style="语气风格"|>语音内容<|/voice|> 标签
- `style` 控制语音特性（方言、语气等，可用自然语言描述）
- 【重要】每条语音都必须有完整的开始和结束标签
- 【示例】：
  第一句文本 <|voice style="开心的语气"|>第一句语音<|/voice|>
  <|wait time="1"|>
  第二句文本 <|voice style="撒娇的语气"|>第二句语音<|/voice|>
"""

        if group_id:
            scene_prompt = "当前是群聊场景，你是一个普通群友，像真人一样自然参与对话，不需要每条消息都回复。"
            if user_nickname:
                scene_prompt += f" 对方的名字是「{user_nickname}」，回复时可以自然地称呼对方。"
            scene_prompt += voice_hint
            scene_prompt += multi_message_hint
            scene_prompt += "\n\n【重要】回复时直接说内容，不要加「Amer：」或「xxx：」这样的前缀，你的消息会直接发出去，不需要加名字。"
            messages.append({"role": "system", "content": scene_prompt})
        else:
            scene_prompt = "当前是私聊场景，你是一个普通群友，可以更自由地表达，但也要保持自然。"
            if user_nickname:
                scene_prompt += f" 对方的名字是「{user_nickname}」，回复时可以自然地称呼对方。"
            scene_prompt += voice_hint
            scene_prompt += multi_message_hint
            scene_prompt += "\n\n【重要】回复时直接说内容，不要加「Amer：」或「xxx：」这样的前缀，你的消息会直接发出去，不需要加名字。"
            messages.append({"role": "system", "content": scene_prompt})

        messages.extend(session_history[-15:])

        # 调用对话AI
        try:
            # 如果有图片，先尝试使用视觉AI分析图片内容
            if image_urls:
                use_multimodal = True
                image_descriptions = []

                self.logger.info(f"👁️ 视觉AI分析 - {session_desc} - 图片数量: {len(image_urls)}")

                # 尝试使用视觉AI分析图片
                for url in image_urls[:3]:  # 最多3张图片
                    description = await self.ai_manager.analyze_image(url, user_input if len(image_urls) == 1 else "")
                    if description:
                        image_descriptions.append(description)

                # 如果成功分析了图片，使用视觉分析结果
                if image_descriptions:
                    image_analysis = "\n".join([f"[图片{i+1}]: {desc}" for i, desc in enumerate(image_descriptions)])
                    self.logger.info(f"✅ 视觉AI分析完成 - {session_desc} - 成功: {len(image_descriptions)}/{len(image_urls)}张")

                # 找到最后一条用户消息（当前用户的消息）
                last_user_msg = None
                last_user_msg_index = -1
                for i, msg in enumerate(messages):
                    if msg["role"] == "user":
                        last_user_msg = msg
                        last_user_msg_index = i

                if last_user_msg:
                    # 将用户消息转换为文字+图片描述的格式
                    combined_content = last_user_msg["content"]
                    if image_analysis:
                        combined_content += f"\n\n{image_analysis}"

                    messages[last_user_msg_index] = {
                        "role": "user",
                        "content": combined_content
                    }
                    use_multimodal = False
                    self.logger.debug("使用视觉AI分析结果，图片描述已合并到文本")

            # 如果没有视觉分析结果，使用多模态模式
            if image_urls and use_multimodal:
                # 找到最后一条用户消息（当前用户的消息）
                last_user_msg = None
                last_user_msg_index = -1
                for i, msg in enumerate(messages):
                    if msg["role"] == "user":
                        last_user_msg = msg
                        last_user_msg_index = i

                if last_user_msg:
                    # 将用户消息转换为多模态格式（文字+图片）
                    messages[last_user_msg_index] = {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": last_user_msg["content"]},
                            *[{"type": "image_url", "image_url": {"url": url}} for url in image_urls[:3]]  # 最多3张图片
                        ]
                    }
                    self.logger.debug("使用多模态模式，图片直接传递给AI")

            self.logger.info(f"🤖 调用对话AI - {session_desc} - 模型: {self.config.get('dialogue.model', 'unknown')}")
            response = await self.ai_manager.dialogue(messages)

            # 记录AI回复
            response_preview = truncate_message(response, 150)
            self.logger.info(f"🤖 AI回复生成 - {session_desc} - 内容: {response_preview}")

            # 保存AI回复到会话历史（用户消息已在Core.py中添加）
            await self.memory.add_short_term_memory(user_id, "assistant", response, group_id)

            # 更新状态
            await self.state.increment_interaction(user_id, group_id)

            return response
        except Exception as e:
            self.logger.error(f"对话处理失败: {e}")
            # 如果是图片处理失败且有图片，尝试不使用图片重试
            error_lower = str(e).lower()
            if image_urls and ("vision" in error_lower or "image" in error_lower or "unsupported" in error_lower):
                # 检查是否有文本内容（用户消息）
                has_text = False
                for msg in messages:
                    if msg["role"] == "user":
                        content = msg.get("content")
                        if isinstance(content, list):
                            # 多模态消息，检查是否有文本
                            for item in content:
                                if item.get("type") == "text" and item.get("text", "").strip():
                                    has_text = True
                                    break
                        elif isinstance(content, str) and content.strip():
                            has_text = True
                        break

                if has_text:
                    self.logger.info("模型不支持图片，尝试不使用图片重新对话")
                    try:
                        # 重新构建消息（不包含图片）
                        no_image_messages = []
                        for msg in messages:
                            if msg["role"] == "system":
                                no_image_messages.append(msg)
                            elif msg["role"] == "user" and isinstance(msg.get("content"), list):
                                # 将多模态消息转换为纯文本
                                text_content = ""
                                for item in msg["content"]:
                                    if item.get("type") == "text":
                                        text_content = item.get("text", "")
                                        break
                                if text_content:
                                    no_image_messages.append({"role": "user", "content": text_content})
                            else:
                                no_image_messages.append(msg)

                        response = await self.ai_manager.dialogue(no_image_messages)
                        await self.memory.add_short_term_memory(user_id, "assistant", response, group_id)
                        await self.state.increment_interaction(user_id, group_id)
                        return response
                    except Exception as retry_error:
                        self.logger.error(f"不使用图片的对话也失败: {retry_error}")
                        return "抱歉，我现在无法回复。请稍后再试。"
                else:
                    self.logger.info("用户只发送了图片且模型不支持视觉，跳过回复")
                    return None

        return "抱歉，我现在无法回复。请稍后再试。"

    async def _prepare_memory_context(self, user_id: str, session_history: List[Dict[str, str]], group_id: Optional[str] = None) -> str:
        """
        准备记忆上下文（在对话之前总结之前的会话历史和长期记忆）

        Args:
            user_id: 用户ID
            session_history: 会话历史
            group_id: 群ID（可选）

        Returns:
            str: 记忆上下文文本
        """
        # 获取长期记忆
        user_memory = await self.memory.get_user_memory(user_id)
        long_term_memories = user_memory.get("long_term", [])

        if not long_term_memories and not session_history:
            return ""

        # 获取记忆AI客户端
        memory_client = self.ai_manager.get_client("memory")
        if not memory_client:
            # 如果没有记忆AI，简单返回长期记忆
            if long_term_memories:
                memory_list = [mem["content"] for mem in long_term_memories[-10:]]
                return "【用户长期记忆】\n" + "\n".join([f"- {mem}" for mem in memory_list])
            return ""

        try:
            # 构建会话历史文本（最近15条）
            recent_history = session_history[-15:] if len(session_history) > 15 else session_history
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_history])

            # 构建长期记忆文本
            if long_term_memories:
                memory_list = [mem["content"] for mem in long_term_memories[-10:]]
                existing_memory_text = "\n".join([f"- {mem}" for mem in memory_list])
            else:
                existing_memory_text = "（暂无长期记忆）"

            prompt = f"""你是一个智能记忆助手，负责总结和提取对话中的重要信息。

【长期记忆（已保存）】
{existing_memory_text}

【最近对话历史】
{history_text}

【任务】
1. 从对话历史中提取值得记住的重要信息
2. 判断是否需要更新长期记忆
3. 将重要信息按类别组织：喜好、习惯、信息、关系、状态、计划、其他

【提取标准】（作为朋友，你会记住什么）：
1. 对方的个人信息：生日、重要日期、工作、学校
2. 对方的喜好：爱吃的、不爱吃的、兴趣爱好
3. 对方的习惯：作息时间、运动习惯、特殊习惯
4. 对方的重要关系：家人、伴侣、好朋友
5. 对方最近的状态：生病、忙碌、考试、搬家
6. 对方的目标和计划：要考试、要旅行、要找工作

【你不会记住的】：
1. 日常闲聊："在吗"、"大家好"、"哈哈哈"
2. 简单回应："好的"、"嗯"、"收到"、"知道了"
3. 表情包、纯表情消息
4. 一次性话题："今天天气不错"、"这菜不错"
5. 纯粹吐槽、发泄（无具体信息）
6. 已经说过很多次的事情

【输出格式】：
如果没有新的重要信息，只返回"无"。
如果有新的重要信息，按以下格式输出：
【需要新增的记忆】
- <类型>：<内容>

【需要更新的记忆】
- <类型>：<内容>

注意：只输出对话历史中新增或需要更新的信息，不要重复已有的长期记忆。"""

            result = await memory_client.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=800
            )

            result = result.strip()

            # 如果有新的记忆，保存到长期记忆
            if result and result.lower() != "无":
                await self._save_summarized_memories(user_id, result, group_id)

            # 构建记忆上下文（长期记忆）
            if long_term_memories:
                memory_list = [mem["content"] for mem in long_term_memories[-10:]]
                memory_text = "【用户长期记忆】\n" + "\n".join([f"- {mem}" for mem in memory_list])
                return memory_text
            else:
                return ""

        except Exception as e:
            self.logger.warning(f"准备记忆上下文失败: {e}")
            # 降级：直接返回长期记忆
            if long_term_memories:
                memory_list = [mem["content"] for mem in long_term_memories[-10:]]
                return "【用户长期记忆】\n" + "\n".join([f"- {mem}" for mem in memory_list])
            return ""

    async def _save_summarized_memories(self, user_id: str, summarized_text: str, group_id: Optional[str] = None) -> None:
        """
        保存总结后的记忆

        Args:
            user_id: 用户ID
            summarized_text: 总结后的记忆文本
            group_id: 群ID（可选）
        """
        if not summarized_text or summarized_text.lower() == "无":
            return

        # 解析总结后的记忆
        lines = summarized_text.split('\n')
        new_memories = []

        for line in lines:
            line = line.strip()
            if line.startswith('-') and '：' in line:
                new_memories.append(line[1:].strip())

        if not new_memories:
            return

        # 保存到用户长期记忆
        user_memory = await self.memory.get_user_memory(user_id)
        existing_user_memories = [mem['content'].lower() for mem in user_memory.get('long_term', [])]

        saved_count = 0
        for memory in new_memories:
            # 去重：检查是否已存在相似记忆
            is_duplicate = False
            for existing in existing_user_memories:
                if memory.lower() in existing or existing in memory.lower():
                    is_duplicate = True
                    break

            if not is_duplicate:
                await self.memory.add_long_term_memory(user_id, memory, tags=["auto"])
                saved_count += 1

        if saved_count > 0:
            session_desc = get_session_description(user_id, "", group_id, "")
            self.logger.info(f"💾 记忆保存 - {session_desc} - 用户长期记忆: {saved_count}条")

        # 如果是群聊，根据记忆模式决定是否保存到群记忆
        if group_id:
            group_config = self.config.get_group_config(group_id)
            memory_mode = group_config.get('memory_mode', 'mixed')

            # 混合模式或 sender_only 模式都保存群记忆
            if memory_mode in ['mixed', 'sender_only']:
                group_memory = await self.memory.get_group_memory(group_id)
                sender_memory = group_memory.get("sender_memory", {}).get(user_id, [])
                existing_group_memories = [mem['content'].lower() for mem in sender_memory]

                group_saved_count = 0
                for memory in new_memories:
                    is_duplicate = False
                    for existing in existing_group_memories:
                        if memory.lower() in existing or existing in memory.lower():
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        await self.memory.add_group_memory(group_id, user_id, memory)
                        group_saved_count += 1

                if group_saved_count > 0:
                    session_desc = get_session_description(user_id, "", group_id, "")
                    self.logger.info(f"💾 记忆保存 - {session_desc} - 群记忆: {group_saved_count}条")

    async def extract_and_save_memory(self, user_id: str, session_history: List[Dict[str, str]], response: str, group_id: Optional[str] = None) -> None:
        """
        公共方法：智能提取重要信息并保存到长期记忆（多AI协同）
        
        Args:
            user_id: 用户ID
            session_history: 会话历史
            response: AI回复
            group_id: 群ID（可选）
        """
        await self._extract_and_save_memory(user_id, session_history, response, group_id)

    async def _extract_and_save_memory(self, user_id: str, session_history: List[Dict[str, str]], response: str, group_id: Optional[str] = None) -> None:
        """
        智能提取重要信息并保存到长期记忆（多AI协同）
        
        Args:
            user_id: 用户ID
            session_history: 会话历史
            response: AI回复
            group_id: 群ID（可选）
        """
        try:
            # 获取最近15条对话
            recent_dialogues = session_history[-15:] if len(session_history) > 15 else session_history

            # 构建对话文本
            dialogue_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_dialogues])

            # 如果没有 AI 回复（窥屏模式可能不回复），只判断对话内容
            ai_response = response if response and response.strip() else "（未回复）"

            # 第一步：多AI协同判断是否值得记录
            should_remember = await self._should_remember_dialogue(dialogue_text, ai_response)
            if not should_remember:
                self.logger.debug("AI判断本次对话不值得记录到长期记忆")
                return

            # 第二步：提取关键信息（更严格的提取标准）
            memory_client = self.ai_manager.get_client("memory")
            if not memory_client:
                return

            extract_prompt = f"""你是一个普通群友，在和朋友聊天。从对话中提取值得记住的信息。

【对话内容】
{dialogue_text}

【你的回复】
{response}

【作为朋友，你会记住什么】：
1. 对方的个人信息：生日、重要日期、工作、学校
2. 对方的喜好：爱吃的、不爱吃的、兴趣爱好
3. 对方的习惯：作息时间、运动习惯、特殊习惯
4. 对方的重要关系：家人、伴侣、好朋友
5. 对方最近的状态：生病、忙碌、考试、搬家
6. 对方的目标和计划：要考试、要旅行、要找工作

【你不会记住的】：
1. 日常闲聊："在吗"、"大家好"、"哈哈哈"
2. 简单回应："好的"、"嗯"、"收到"、"知道了"
3. 表情包、纯表情消息
4. 一次性话题："今天天气不错"、"这菜不错"
5. 纯粹吐槽、发泄（无具体信息）
6. 对你的评价（除非重要）
7. 已经说过很多次的事情

【记忆价值测试】：
- 这条信息是关于对方独有的吗？
- 忘了这条信息，会影响你们的关系吗？
- 下次聊天，这条信息会用到吗？

【输出要求】：
- 如果没有值得记住的，只返回"无"
- 如果有，每条信息一行，格式：<类型>：<内容>
  - 类型：喜好、习惯、信息、关系、状态、计划、其他
  - 内容要自然简洁，像朋友记住的方式

【示例】：
- 不要提取：用户说"今天天气不错"
- 应该提取：用户说"我每天早上7点起床跑步" -> 习惯：每天早上7点起床跑步
- 不要提取：用户说"哈哈哈"
- 应该提取：用户说"我下周五生日" -> 信息：下周五生日
- 不要提取：用户说"好的"
- 应该提取：用户说"我不吃辣" -> 喜好：不吃辣

提取结果（如果没有则返回"无"）："""

            important_info = await memory_client.chat(
                [{"role": "user", "content": extract_prompt}],
                temperature=0.2,  # 降低温度，更严格的判断
                max_tokens=500
            )

            # 清理结果
            important_info = important_info.strip()

            # 如果提取到了重要信息，进行去重和保存
            if important_info and important_info.lower() != "无":
                await self._save_filtered_memories(user_id, important_info, group_id)

        except Exception as e:
            self.logger.warning(f"提取和保存记忆失败: {e}")

    async def _should_remember_dialogue(self, dialogue_text: str, ai_response: str) -> bool:
        """
        AI判断是否值得记录本次对话（普通群友记忆模式）
        
        Args:
            dialogue_text: 对话文本
            ai_response: AI回复
            
        Returns:
            bool: 是否值得记录
        """
        try:
            # 使用dialogue AI进行判断
            dialogue_client = self.ai_manager.get_client("dialogue")
            if not dialogue_client:
                return False  # 没有AI就不自动记忆

            judge_prompt = f"""你是一个普通群友，判断这段对话是否值得记住。

【对话内容】
{dialogue_text}

【你的回复】
{ai_response}

【判断标准】（作为朋友，你会记住什么）：
1. 真正重要的个人信息（生日、重要日期、正在做的事情）
2. 对方的喜好、习惯、兴趣爱好
3. 对方提到的重要关系（家人、朋友、伴侣）
4. 对方的工作、学习情况
5. 对方最近的状态（生病、忙碌、开心、难过）

【你不会记住的】：
1. 日常闲聊、打招呼、"好的"、"嗯"
2. 一次性的话题讨论
3. 纯粹的情绪发泄、吐槽
4. 天气、时间等通用信息
5. 对你的评价（除非影响后续交流）
6. 已经说过很多次的事情

【记忆价值测试】：
- 这条信息是对方独有的吗？
- 如果忘了这条信息，会影响你们的关系吗？
- 这条信息在未来对话中会用到吗？

【输出格式】
只回答"值得"或"不值得"，不要解释。

是否值得记住："""

            result = await dialogue_client.chat(
                [{"role": "user", "content": judge_prompt}],
                temperature=0.2,  # 稍高的温度，更灵活的判断
                max_tokens=10
            )

            is_worth = "值得" in result
            self.logger.debug(f"AI记忆判断: {is_worth} (结果: {result.strip()})")
            return is_worth

        except Exception as e:
            self.logger.debug(f"记忆价值判断失败: {e}")
            return False

    async def _save_filtered_memories(self, user_id: str, important_info: str, group_id: Optional[str] = None) -> None:
        """
        保存记忆（带去重机制，支持群聊混合模式）
        
        Args:
            user_id: 用户ID
            important_info: 重要信息
            group_id: 群ID（可选）
        """
        # 分割新信息
        new_memories = []
        for line in important_info.split('\n'):
            line = line.strip()
            if line:
                new_memories.append(line)

        if not new_memories:
            return

        # 保存到用户长期记忆（个人记忆）- 始终保存
        user_memory = await self.memory.get_user_memory(user_id)
        existing_user_memories = [mem['content'].lower() for mem in user_memory.get('long_term', [])]

        saved_count = 0
        for memory in new_memories:
            # 去重：检查是否已存在相似记忆
            is_duplicate = False
            for existing in existing_user_memories:
                if memory.lower() in existing or existing in memory.lower():
                    is_duplicate = True
                    break

            if not is_duplicate:
                await self.memory.add_long_term_memory(user_id, memory, tags=["auto"])
                saved_count += 1

        if saved_count > 0:
            self.logger.info(f"本次对话共保存 {saved_count} 条用户长期记忆")

        # 如果是群聊，根据记忆模式决定是否保存到群记忆
        if group_id:
            group_config = self.config.get_group_config(group_id)
            memory_mode = group_config.get('memory_mode', 'mixed')

            # 混合模式或 sender_only 模式都保存群记忆
            # 区别是：混合模式会保存群共享上下文，sender_only 只保存 sender_memory
            if memory_mode in ['mixed', 'sender_only']:
                # 检查群记忆是否已有重复
                group_memory = await self.memory.get_group_memory(group_id)
                sender_memory = group_memory.get("sender_memory", {}).get(user_id, [])
                existing_group_memories = [mem['content'].lower() for mem in sender_memory]

                group_saved_count = 0
                for memory in new_memories:
                    # 去重检查
                    is_duplicate = False
                    for existing in existing_group_memories:
                        if memory.lower() in existing or existing in memory.lower():
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        await self.memory.add_group_memory(group_id, user_id, memory)
                        group_saved_count += 1

                if group_saved_count > 0:
                    self.logger.info(f"本次对话共保存 {group_saved_count} 条群记忆")

            # 仅混合模式保存群共享上下文
            if memory_mode == 'mixed':
                # 保存一些重要的共享上下文（如群规则、重要事件）
                # 简单判断：如果包含"群"、"规则"、"注意"等关键词，保存为共享上下文
                for memory in new_memories:
                    if any(keyword in memory for keyword in ["群", "规则", "注意", "禁止", "活动", "约定"]):
                        await self.memory.add_group_memory(group_id, user_id, memory, is_context=True)
                        self.logger.info(f"✓ 自动保存到群共享上下文: {memory}")
                        break  # 只保存一条

    def _build_context_prompt(self, context_info: Dict[str, Any], is_group: bool) -> str:
        """
        构建上下文提示

        Args:
            context_info: 上下文信息字典
            is_group: 是否是群聊

        Returns:
            str: 上下文提示文本
        """
        prompt_lines = []

        # === 场景信息 ===
        if is_group:
            prompt_lines.append("【当前场景】群聊")
            group_name = context_info.get("group_name", "")
            group_id = context_info.get("group_id", "")
            if group_name:
                prompt_lines.append(f"【群名】{group_name}")
            if group_id:
                prompt_lines.append(f"【群ID】{group_id}")
        else:
            prompt_lines.append("【当前场景】私聊")

        # === 发送者信息 ===
        user_nickname = context_info.get("user_nickname", "")
        user_id = context_info.get("user_id", "")
        if user_nickname:
            prompt_lines.append(f"【发送者】{user_nickname} (ID: {user_id})")
        elif user_id:
            prompt_lines.append(f"【发送者ID】{user_id}")

        # === 机器人信息 ===
        bot_nickname = context_info.get("bot_nickname", "")
        if bot_nickname:
            prompt_lines.append(f"【你的名字】{bot_nickname}")

        # === 平台信息 ===
        platform = context_info.get("platform", "")
        if platform:
            prompt_lines.append(f"【平台】{platform}")

        # === 当前时间 ===
        event_time = context_info.get("time", 0)
        if event_time:
            from datetime import datetime as dt
            # 转换为可读时间（event-conversion.md 使用10位Unix时间戳）
            event_time_str = dt.fromtimestamp(event_time).strftime("%Y-%m-%d %H:%M:%S")
            prompt_lines.append(f"【消息时间】{event_time_str}")
        else:
            current_time = dt.now().strftime("%Y-%m-%d %H:%M:%S")
            prompt_lines.append(f"【当前时间】{current_time}")

        # === @（mention）信息 ===
        mentions = context_info.get("mentions", [])
        if mentions:
            prompt_lines.append("【@的用户】")
            for mention in mentions:
                mention_id = mention.get("user_id", "")
                mention_nickname = mention.get("nickname", "")
                if mention_nickname:
                    prompt_lines.append(f"- {mention_nickname} (ID: {mention_id})")
                else:
                    prompt_lines.append(f"- 用户ID: {mention_id}")

        # === 消息段信息 ===
        message_segments = context_info.get("message_segments", [])
        if message_segments:
            # 统计消息内容类型
            segment_types = set()
            for seg in message_segments:
                seg_type = seg.get("type", "")
                if seg_type:
                    segment_types.add(seg_type)

            if segment_types:
                type_names = {
                    "text": "文本",
                    "image": "图片",
                    "at": "@",
                    "mention": "@",
                    "face": "表情",
                    "record": "语音",
                    "video": "视频",
                    "forward": "转发"
                }
                type_list = [type_names.get(t, t) for t in segment_types]
                prompt_lines.append(f"【消息类型】{', '.join(type_list)}")

        return "\n".join(prompt_lines) if prompt_lines else ""

    async def handle_memory_add(
        self,
        user_id: str,
        _params: Dict[str, Any],  # type: ignore[unused-argument]
        intent_data: Dict[str, Any]
    ) -> str:
        """
        处理添加记忆

        Args:
            user_id: 用户ID
            _params: 参数字典（保留用于兼容性，当前未使用）
            intent_data: 意图数据

        Returns:
            str: 添加结果
        """
        content = intent_data["raw_input"]

        # 使用记忆AI提取关键信息（如果可用）
        if self.ai_manager.get_client("memory"):
            try:
                prompt = f"请从以下内容中提取需要长期记住的重要信息:\n{content}"
                extracted = await self.ai_manager.memory_process(prompt)

                if extracted and extracted.strip():
                    await self.memory.add_long_term_memory(user_id, extracted, tags=["manual"])
                    return f"已记住: {extracted}"
            except Exception as e:
                self.logger.warning(f"记忆AI提取失败，直接保存原始内容: {e}")

        # 直接保存原始内容
        await self.memory.add_long_term_memory(user_id, content, tags=["manual"])
        return "已记住该信息。"

    async def handle_memory_delete(
        self,
        user_id: str,
        params: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> str:
        """
        处理删除记忆
        
        Args:
            user_id: 用户ID
            params: 参数字典（用于获取命令参数）
            intent_data: 意图数据
            
        Returns:
            str: 删除结果
        """
        # 如果是命令模式，使用命令参数
        groups = params.get("groups", [])
        if groups and len(groups) >= 2 and groups[0].lower() == "memory" and groups[1].lower() == "delete":
            try:
                index = int(groups[2]) if len(groups) > 2 else 0
                success = await self.memory.delete_memory(user_id, index)
                return "记忆已删除" if success else "删除失败，索引无效"
            except ValueError:
                return "请提供有效的数字索引"
        else:
            # 如果是意图识别模式，尝试从用户输入中提取索引
            import re
            input_text = intent_data["raw_input"]
            # 尝试提取数字
            match = re.search(r'\d+', input_text)
            if match:
                try:
                    index = int(match.group())
                    success = await self.memory.delete_memory(user_id, index)
                    return "记忆已删除" if success else "删除失败，索引无效"
                except ValueError:
                    pass
            return "请提供要删除的记忆索引（如：删除第1条记忆）"


