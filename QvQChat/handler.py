import json
from typing import Dict, List, Any, Optional
from ErisPulse import sdk


class QvQHandler:
    """意图处理器"""
    
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
        """处理普通对话"""
        user_input = intent_data["raw_input"]

        # 构建对话消息
        system_prompt = self.config.get_effective_system_prompt(user_id, group_id)

        # 获取会话历史（已包含当前用户消息，因为Core.py已添加）
        session_history = await self.memory.get_session_history(user_id, group_id)

        # 获取相关记忆（使用更多关键词进行搜索）
        search_results = await self.memory.search_memory(user_id, user_input, group_id)

        # 构建消息列表
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 添加相关记忆作为上下文
        if search_results:
            memory_context = "【重要记忆】\n" + "\n".join([
                f"- {r['content']}" for r in search_results[:5]
            ])
            messages.append({"role": "system", "content": memory_context})

        # 添加当前上下文提示
        if group_id:
            messages.append({"role": "system", "content": "当前是群聊场景，注意群聊氛围，适当参与互动。"})
        else:
            messages.append({"role": "system", "content": "当前是私聊场景，可以更自由地表达。"})

        # 使用历史消息（包含刚添加的用户消息，使用更多历史）
        messages.extend(session_history[-15:])

        # 调用对话AI
        try:
            response = await self.ai_manager.dialogue(messages)

            # 移除Markdown格式
            response = self._remove_markdown(response)

            # 保存AI回复到会话历史（用户消息已在Core.py中添加）
            await self.memory.add_short_term_memory(user_id, "assistant", response, group_id)

            # 更新状态
            await self.state.increment_interaction(user_id, group_id)

            return response
        except Exception as e:
            self.logger.error(f"对话处理失败: {e}")
            return "抱歉，我现在无法回复。请稍后再试。"

    def _remove_markdown(self, text: str) -> str:
        """移除Markdown格式"""
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
        """处理记忆查询"""
        query = params.get("query", intent_data["raw_input"])
        
        # 构建查询提示
        search_results = await self.memory.search_memory(user_id, query, group_id)
        
        if not search_results:
            return f"我没有找到关于'{query}'的记忆。"
        
        # 使用查询AI生成自然回复（如果可用）
        if self.ai_manager.get_client("query"):
            try:
                memory_text = "\n".join([f"{i+1}. {r['content']}" for i, r in enumerate(search_results)])
                prompt = f"""用户查询: {query}

找到的相关记忆:
{memory_text}

请用自然语言回答用户的问题，不要直接列出记忆。"""
                response = await self.ai_manager.query(prompt)
                return response
            except Exception as e:
                self.logger.error(f"记忆查询AI处理失败: {e}")
        
        # 直接返回搜索结果
        return f"找到 {len(search_results)} 条相关记忆:\n" + "\n".join([
            f"{i+1}. {r['content']}" for i, r in enumerate(search_results)
        ])
    
    async def handle_memory_add(
        self,
        user_id: str,
        group_id: Optional[str],
        params: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> str:
        """处理添加记忆"""
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
    
    async def handle_memory_management(
        self,
        user_id: str,
        group_id: Optional[str],
        params: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> str:
        """处理记忆管理命令"""
        groups = params.get("groups", [])
        if not groups:
            return "请指定操作: list, search, compress, delete"
        
        action = groups[0].lower()
        
        if action == "list":
            return await self.memory.get_memory_summary(user_id, group_id)
        
        elif action == "search":
            if len(groups) < 2:
                return "请提供搜索关键词"
            query = groups[1]
            results = await self.memory.search_memory(user_id, query, group_id)
            if results:
                return "\n".join([f"{i+1}. {r['content']}" for i, r in enumerate(results)])
            return "没有找到相关记忆"
        
        elif action == "compress":
            memory_client = self.ai_manager.get_client("memory")
            if not memory_client:
                return "记忆AI未配置，无法压缩记忆。请在配置中设置[QvQChat.memory].api_key"
            try:
                result = await self.memory.compress_memory(user_id, memory_client)
                return result
            except Exception as e:
                return f"压缩记忆失败: {e}"
        
        elif action == "delete":
            if len(groups) < 2:
                return "请提供要删除的记忆索引"
            try:
                index = int(groups[1])
                success = await self.memory.delete_memory(user_id, index, group_id)
                return "记忆已删除" if success else "删除失败，索引无效"
            except ValueError:
                return "请提供有效的数字索引"
        
        else:
            return f"未知的操作: {action}"
    
    async def handle_system_control(
        self,
        user_id: str,
        group_id: Optional[str],
        params: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> str:
        """处理系统控制命令"""
        groups = params.get("groups", [])
        
        if not groups or groups[0] == "config":
            # 显示配置
            ai_status = await self.ai_manager.test_all_connections()
            status_text = "\n".join([
                f"{ai_type}: {'✓' if status else '✗'}" 
                for ai_type, status in ai_status.items()
            ])
            return f"系统状态:\n{status_text}\n\n使用 /qvc model <类型> 切换AI模型"
        
        elif groups[0] == "model":
            # 切换模型
            if len(groups) < 2:
                return "请指定要切换的AI类型: dialogue, memory, query, intent"
            ai_type = groups[1].lower()
            if ai_type in ["dialogue", "memory", "query", "intent"]:
                success = self.ai_manager.reload_client(ai_type)
                return f"{ai_type} AI已重新加载" if success else f"{ai_type} AI重新加载失败"
            else:
                return "无效的AI类型"
        
        else:
            return f"未知的系统命令: {groups[0]}"
    
    async def handle_group_config(
        self,
        user_id: str,
        group_id: Optional[str],
        params: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> str:
        """处理群配置命令"""
        if not group_id:
            return "此命令仅在群聊中可用"
        
        groups = params.get("groups", [])
        if not groups:
            group_config = self.config.get_group_config(group_id)
            return f"群配置:\n提示词: {group_config.get('system_prompt', '未设置')}\n记忆模式: {group_config.get('memory_mode', 'sender_only')}"
        
        action = groups[0].lower()
        
        if action == "info":
            return await self.handle_group_config(user_id, group_id, {}, intent_data)
        
        elif action == "prompt":
            if len(groups) < 2:
                return "请提供提示词内容"
            prompt = " ".join(groups[1:])
            group_config = self.config.get_group_config(group_id)
            group_config["system_prompt"] = prompt
            self.config.set_group_config(group_id, group_config)
            return "群提示词已更新"
        
        elif action == "style":
            if len(groups) < 2:
                return "请提供风格"
            style = " ".join(groups[1:])
            group_config = self.config.get_group_config(group_id)
            group_config["style"] = style
            self.config.set_group_config(group_id, group_config)
            return f"群对话风格已设置为: {style}"
        
        else:
            return f"未知的群配置操作: {action}"
    
    async def handle_prompt_custom(
        self,
        user_id: str,
        group_id: Optional[str],
        params: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> str:
        """处理自定义提示词"""
        groups = params.get("groups", [])
        if not groups:
            return "请提供提示词内容"
        
        prompt = " ".join(groups)
        user_config = self.config.get_user_config(user_id)
        user_config["custom_prompt"] = prompt
        self.config.set_user_config(user_id, user_config)
        return "个人提示词已更新"
    
    async def handle_style_change(
        self,
        user_id: str,
        group_id: Optional[str],
        params: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> str:
        """处理风格改变"""
        groups = params.get("groups", [])
        if not groups:
            return "请指定风格: 友好, 专业, 幽默, 简洁"
        
        style = groups[0].lower()
        valid_styles = ["友好", "专业", "幽默", "简洁", "友好", "专业", "幽默", "简洁"]
        
        if style in valid_styles:
            user_config = self.config.get_user_config(user_id)
            user_config["style"] = style
            self.config.set_user_config(user_id, user_config)
            return f"对话风格已设置为: {style}"
        else:
            return f"无效的风格，可选: {', '.join(valid_styles)}"
    
    async def handle_session_clear(
        self,
        user_id: str,
        group_id: Optional[str],
        params: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> str:
        """处理清除会话"""
        await self.memory.clear_session(user_id, group_id)
        return "当前会话历史已清除"
    
    async def handle_export(
        self,
        user_id: str,
        group_id: Optional[str],
        params: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> str:
        """处理导出记忆"""
        export_data = await self.memory.export_memory(user_id, group_id)
        
        # 简化输出
        summary = export_data["user_memory"]
        count = len(summary.get("long_term", []))
        
        if group_id:
            group_memory = export_data.get("group_memory", {})
            sender_count = len(group_memory.get("sender_memory", {}).get(user_id, []))
            return f"用户记忆: {count} 条\n群聊记忆: {sender_count} 条\n完整数据已保存到存储中"
        else:
            return f"用户记忆: {count} 条\n完整数据已保存到存储中"
    
    async def handle_help(
        self,
        user_id: str,
        group_id: Optional[str],
        params: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> str:
        """处理帮助"""
        return """QvQChat 智能助手

基础命令：
/qvc clear       - 清除当前会话历史
/qvc help        - 显示帮助信息

记忆管理：
/qvc memory list      - 查看记忆摘要
/qvc memory search <关键词>  - 搜索记忆
/qvc memory compress  - 压缩整理记忆
/qvc memory delete <索引>   - 删除指定记忆

系统控制：
/qvc config           - 查看当前配置
/qvc model <类型>     - 切换AI模型（dialogue/memory/query）
/qvc export           - 导出记忆

群聊配置：
/qvc group info       - 查看群配置
/qvc group prompt <内容>   - 设置群提示词
/qvc group style <风格>   - 设置对话风格

个性化：
/qvc prompt <内容>    - 自定义个人提示词
/qvc style <风格>      - 设置对话风格

直接与我对话，我会自动识别您的意图并做出响应！"""
