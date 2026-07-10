"""
表情包/贴纸管理器

用户可上传表情包图片，添加名称和描述。
AI 对话时可自主选择发送表情包（通过 function calling）。

表情包存储：
- 元数据（名称、描述、文件路径）保存在 sdk.storage
- 图片文件保存在本地 data 目录
"""

import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ErisPulse import sdk


class StickerManager:
    """
    表情包管理器

    管理用户上传的表情包，支持：
    - 上传（保存图片文件 + 元数据）
    - 查询/搜索（按名称或关键词）
    - 删除
    - 生成 AI 工具定义（让 AI 自主选择表情包）
    """

    STORAGE_KEY = "QvQChat.stickers"
    SUPPORTED_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.get_child("StickerManager")
        self.storage = sdk.storage
        self._stickers: Dict[str, Dict[str, Any]] = {}
        # 使用绝对路径，避免跨容器/CWD 不一致找不到文件
        self.sticker_dir = str(Path.cwd() / "data" / "QvQChat" / "stickers")
        self._load()
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """确保表情包存储目录存在"""
        Path(self.sticker_dir).mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        """从存储加载表情包数据"""
        data = self.storage.get(self.STORAGE_KEY, {})
        self._stickers = data.get("stickers", {})

    def _save(self) -> None:
        """保存表情包数据到存储"""
        self.storage.set(self.STORAGE_KEY, {"stickers": self._stickers})

    def list_stickers(self) -> List[Dict[str, Any]]:
        """列出所有表情包"""
        return list(self._stickers.values())

    def get_sticker(self, sticker_id: str) -> Optional[Dict[str, Any]]:
        """获取指定表情包"""
        return self._stickers.get(sticker_id)

    def add_sticker(
        self,
        name: str,
        description: str,
        file_data: bytes,
        filename: str,
    ) -> Dict[str, Any]:
        """
        添加表情包

        Args:
            name: 表情包名称（用户可读）
            description: 表情包描述/用途说明（供 AI 参考）
            file_data: 图片二进制数据
            filename: 原始文件名（用于推断扩展名）

        Returns:
            创建的表情包数据
        """
        sticker_id = f"sticker_{uuid.uuid4().hex[:8]}"
        ext = Path(filename).suffix.lower()
        if ext not in self.SUPPORTED_TYPES:
            ext = ".png"

        saved_filename = f"{sticker_id}{ext}"
        filepath = str(Path(self.sticker_dir) / saved_filename)

        with open(filepath, "wb") as f:
            f.write(file_data)

        sticker = {
            "id": sticker_id,
            "name": name.strip(),
            "description": description.strip(),
            "file": filepath,
            "filename": saved_filename,
            "created_at": time.time(),
        }
        self._stickers[sticker_id] = sticker
        self._save()
        self.logger.info(f"添加表情包: {name} ({sticker_id})")
        return sticker

    def add_sticker_by_url(
        self,
        name: str,
        description: str,
        url: str,
    ) -> Dict[str, Any]:
        """
        通过 URL 添加表情包（直接引用远程图片，不下载）

        Args:
            name: 表情包名称
            description: 表情包描述
            url: 图片 URL

        Returns:
            创建的表情包数据
        """
        sticker_id = f"sticker_{uuid.uuid4().hex[:8]}"
        sticker = {
            "id": sticker_id,
            "name": name.strip(),
            "description": description.strip(),
            "file": url,
            "filename": "",
            "is_url": True,
            "created_at": time.time(),
        }
        self._stickers[sticker_id] = sticker
        self._save()
        self.logger.info(f"添加表情包(URL): {name} ({sticker_id})")
        return sticker

    def update_sticker(
        self, sticker_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """更新表情包元数据（名称、描述）"""
        sticker = self._stickers.get(sticker_id)
        if not sticker:
            return None
        for key in ("name", "description"):
            if key in data:
                sticker[key] = data[key]
        self._save()
        return sticker

    def delete_sticker(self, sticker_id: str) -> bool:
        """删除表情包（同时删除本地文件）"""
        sticker = self._stickers.get(sticker_id)
        if not sticker:
            return False

        # 删除本地文件（URL 引用的不删）
        if not sticker.get("is_url"):
            filepath = sticker.get("file", "")
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    self.logger.warning(f"删除表情包文件失败: {e}")

        del self._stickers[sticker_id]
        self._save()
        self.logger.info(f"删除表情包: {sticker_id}")
        return True

    def search_stickers(self, keyword: str) -> List[Dict[str, Any]]:
        """按关键词搜索表情包"""
        keyword = keyword.lower().strip()
        if not keyword:
            return self.list_stickers()
        results = []
        for sticker in self._stickers.values():
            if (
                keyword in sticker.get("name", "").lower()
                or keyword in sticker.get("description", "").lower()
            ):
                results.append(sticker)
        return results

    def get_sticker_file(self, sticker_id: str) -> Optional[str]:
        """获取表情包文件路径或 URL"""
        sticker = self._stickers.get(sticker_id)
        if not sticker:
            return None
        return sticker.get("file", "")

    def get_openai_tool_schema(self) -> Optional[Dict[str, Any]]:
        """
        生成 send_sticker 工具的 OpenAI function calling 定义

        如果没有表情包则返回 None。
        """
        if not self._stickers:
            return None

        return {
            "type": "function",
            "function": {
                "name": "send_sticker",
                "description": (
                    "发送一个表情包/贴纸来丰富你的表达。"
                    "在合适的时候（搞笑、开心、无奈、卖萌等场景）使用。"
                    "不要过度使用。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sticker_name": {
                            "type": "string",
                            "description": "要发送的表情包名称",
                        }
                    },
                    "required": ["sticker_name"],
                },
            },
        }

    def build_sticker_catalog_text(self) -> str:
        """
        生成表情包目录文本（注入系统提示词）

        格式：名称 - 描述
        """
        if not self._stickers:
            return ""
        lines = []
        for sticker in self._stickers.values():
            name = sticker.get("name", "")
            desc = sticker.get("description", "")
            if desc:
                lines.append(f"- {name}: {desc}")
            else:
                lines.append(f"- {name}")
        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """获取表情包统计信息"""
        return {
            "total": len(self._stickers),
            "local": sum(1 for s in self._stickers.values() if not s.get("is_url")),
            "url": sum(1 for s in self._stickers.values() if s.get("is_url")),
        }
