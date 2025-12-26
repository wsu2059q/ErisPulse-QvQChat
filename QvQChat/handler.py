from typing import Dict, List, Any, Optional


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
    
    async def handle_dialogue(
        self,
        user_id: str,
        group_id: Optional[str],
        params: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> str:
        """
        处理普通对话
        
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

        # 获取会话历史（已包含当前用户消息，因为Core.py已添加）
        session_history = await self.memory.get_session_history(user_id, group_id)

        # 获取相关记忆（使用更多关键词进行搜索）
        search_results = await self.memory.search_memory(user_id, user_input, group_id)

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

        # 添加相关记忆作为上下文
        if search_results:
            # 分类记忆：用户个人记忆和群聊记忆
            user_memories = [r for r in search_results if r['source'] == 'long_term']
            group_memories = [r for r in search_results if r['source'] in ['group_sender', 'group_context']]

            memory_context_parts = []
            if user_memories:
                memory_context_parts.append("【用户个人记忆】")
                memory_context_parts.extend([f"- {r['content']}" for r in user_memories[:3]])

            if group_memories:
                memory_context_parts.append("【群聊记忆】")
                memory_context_parts.extend([f"- {r['content']}" for r in group_memories[:3]])

            if memory_context_parts:
                memory_context = "\n".join(memory_context_parts)
                messages.append({"role": "system", "content": memory_context})
        else:
            # 如果没有找到相关记忆，提示AI不需要依赖记忆
            messages.append({"role": "system", "content": "当前没有找到相关的历史记忆，直接根据对话内容回复。"})

        # 添加当前上下文提示
        if group_id:
            messages.append({"role": "system", "content": "当前是群聊场景，你是一个普通群友，像真人一样自然参与对话，不需要每条消息都回复。"})
        else:
            messages.append({"role": "system", "content": "当前是私聊场景，你是一个普通群友，可以更自由地表达，但也要保持自然。"})

        # 使用历史消息（包含刚添加的用户消息，使用更多历史）
        messages.extend(session_history[-15:])

        # 调用对话AI
        try:
            # 如果有图片，先尝试使用视觉AI分析图片内容
            if image_urls:
                use_multimodal = True
                image_descriptions = []

                # 尝试使用视觉AI分析图片
                for url in image_urls[:3]:  # 最多3张图片
                    description = await self.ai_manager.analyze_image(url, user_input if len(image_urls) == 1 else "")
                    if description:
                        image_descriptions.append(description)

                # 如果成功分析了图片，使用视觉分析结果
                if image_descriptions:
                    image_analysis = "\n".join([f"[图片{i+1}]: {desc}" for i, desc in enumerate(image_descriptions)])
                    self.logger.info(f"视觉AI分析图片: {len(image_descriptions)}/{len(image_urls)} 张图片")

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

            response = await self.ai_manager.dialogue(messages)

            # 移除Markdown格式
            response = self._remove_markdown(response)

            # 保存AI回复到会话历史（用户消息已在Core.py中添加）
            await self.memory.add_short_term_memory(user_id, "assistant", response, group_id)

            # 重新获取会话历史（包含刚保存的 AI 回复）
            updated_session_history = await self.memory.get_session_history(user_id, group_id)

            # 自动提取重要信息到长期记忆（让记忆系统真正起作用）
            await self._extract_and_save_memory(user_id, updated_session_history, response, group_id)

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
                        response = self._remove_markdown(response)
                        await self.memory.add_short_term_memory(user_id, "assistant", response, group_id)
                        await self._extract_and_save_memory(user_id, session_history, response, group_id)
                        await self.state.increment_interaction(user_id, group_id)
                        return response
                    except Exception as retry_error:
                        self.logger.error(f"不使用图片的对话也失败: {retry_error}")
                        return "抱歉，我现在无法回复。请稍后再试。"
                else:
                    self.logger.info("用户只发送了图片且模型不支持视觉，跳过回复")
                    return None
            return "抱歉，我现在无法回复。请稍后再试。"

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

        # 场景信息
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

        # 发送者信息
        user_nickname = context_info.get("user_nickname", "")
        user_id = context_info.get("user_id", "")
        if user_nickname:
            prompt_lines.append(f"【发送者】{user_nickname} (ID: {user_id})")
        elif user_id:
            prompt_lines.append(f"【发送者ID】{user_id}")

        # 机器人信息
        bot_nickname = context_info.get("bot_nickname", "")
        if bot_nickname:
            prompt_lines.append(f"【你的名字】{bot_nickname}")

        # 平台信息
        platform = context_info.get("platform", "")
        if platform:
            prompt_lines.append(f"【平台】{platform}")

        # 当前时间
        import datetime
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        prompt_lines.append(f"【时间】{current_time}")

        return "\n".join(prompt_lines) if prompt_lines else ""

    def _parse_multi_messages(self, text: str) -> list:
        """
        解析多条消息（带延迟）
        
        Args:
            text: 包含多条消息格式的文本
            
        Returns:
            list: 消息列表，每条消息包含content和delay
        """
        import re

        # 尝试解析多消息格式：消息1\n\n[间隔:3]\n\n消息2
        pattern = r'\[间隔:(\d+)\]'
        parts = re.split(pattern, text)

        messages = []
        current_msg = parts[0].strip()

        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                next_msg = parts[i + 1].strip()

                if current_msg:
                    messages.append({"content": current_msg, "delay": 0})
                current_msg = next_msg

        if current_msg:
            messages.append({"content": current_msg, "delay": 0})

        # 如果没有找到间隔标记，返回单条消息
        if len(messages) <= 1:
            # 第一条消息可能有延迟（如果第一部分就是 [间隔:3] 开头）
            # 但这种格式不太可能，直接返回整个文本
            if len(messages) == 0:
                return [{"content": text.strip(), "delay": 0}]
        else:
            # 设置延迟（第一条延迟为0，后续按标记设置）
            for i in range(len(messages)):
                if i > 0 and i * 2 - 1 < len(parts):
                    messages[i]["delay"] = int(parts[i * 2 - 1])

        # 最多返回3条消息
        return messages[:3]

    def _remove_markdown(self, text: str) -> str:
        """
        移除Markdown格式
        
        Args:
            text: 原始文本
            
        Returns:
            str: 移除Markdown后的文本
        """
        import re
        if not text:
            return text
        # 移除粗体 **text** 或 __text__
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'__(.*?)__', r'\1', text)
        # 移除斜体 *text* 或 _text_
        text = re.sub(r'\*(?!\*)(.*?)\*(?!\*)', r'\1', text)
        text = re.sub(r'_(?!_)(.*?)_(?!_)', r'\1', text)
        # 移除代码 `code`
        text = re.sub(r'`(.*?)`', r'\1', text)
        # 移除代码块 ```code```
        text = re.sub(r'```[\s\S]*?```', '', text)
        # 移除标题 # heading
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        # 移除列表标记 - 或 *
        text = re.sub(r'^[\s]*[-*]\s+', '', text, flags=re.MULTILINE)
        # 移除有序列表 1.
        text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
        # 移除链接 [text](url)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # 移除多余的空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    async def handle_memory_query(
        self,
        user_id: str,
        group_id: Optional[str],
        params: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> str:
        """
        处理记忆查询
        
        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
            params: 参数字典
            intent_data: 意图数据
            
        Returns:
            str: 查询结果
        """
        query = params.get("query", intent_data["raw_input"])
        
        # 搜索记忆
        search_results = await self.memory.search_memory(user_id, query, group_id)
        
        if not search_results:
            return f"我没有找到关于'{query}'的记忆。"
        
        # 直接返回搜索结果
        return f"找到 {len(search_results)} 条相关记忆:\n" + "\n".join([
            f"{i+1}. {r['content']}" for i, r in enumerate(search_results)
        ])
    
    async def handle_memory_add(
        self,
        user_id: str,
        params: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> str:
        """
        处理添加记忆
        
        Args:
            user_id: 用户ID
            params: 参数字典（保留用于兼容性）
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

    async def handle_intent_execution(
        self,
        user_id: str,
        params: Dict[str, Any],
        intent_data: Dict[str, Any],
        context_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        使用意图执行模型处理系统操作（替代传统命令）
        
        Args:
            user_id: 用户ID
            params: 参数字典（用于获取上下文信息，由Core.py传递）
            intent_data: 意图数据
            context_info: 上下文信息（可选）
            
        Returns:
            str: 执行结果
        """
        try:
            user_input = intent_data["raw_input"]

            # 使用AI判断应该执行什么操作并返回结构化结果
            # AI会直接返回自然语言回复给用户
            execution_result = await self.ai_manager.execute_intent(user_input, context_info)
            self.logger.debug(f"AI意图执行结果: {execution_result}")

            # AI会直接返回自然语言回复，无需额外处理
            return execution_result

        except Exception as e:
            self.logger.error(f"意图执行失败: {e}")
            return "抱歉，执行操作时出现错误。"
