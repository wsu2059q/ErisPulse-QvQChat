"""
拟人化后处理器

模拟真人输入行为的输出后处理：打字延迟、错字纠正、半句发出、
已读不回、随机@，以及 AI 回复的合法性检测与历史记录清洗。

{!--< tips >!--}
所有概率类行为均通过 humanize 配置段控制，权重为 0 时完全禁用。
{!--< /tips >!--}
"""

import random
import re
from typing import Any, Dict, Optional


class Humanizer:
    """拟人化后处理器

    :param config: QvQConfig 配置包装器，读取 humanize 配置段
    :param logger: 日志记录器
    """

    # AI 可能输出的"不回复"标记（需过滤）
    SKIP_MARKERS = [
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

    # 带括号的不回复推理、聊天记录格式正则
    SKIP_REGEX = [
        r"（[^）]*不[^）]*回复[^）]*）",
        r"\([^)]*不[^)]*回复[^)]*\)",
        r"\[[^\]]*:\s*$",
        # 多行「昵称:内容」格式（AI在输出聊天记录）
        r"^[^:\n]{1,10}:\s.*\n[^:\n]{1,10}:\s",
    ]

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.get_child("Humanize")

    # ==================== 打字延迟 ====================

    def calc_typing_delay(self, text: str) -> float:
        """根据回复长度计算打字延迟秒数

        :param text: 待发送的回复文本
        :return: float 延迟秒数，功能关闭时返回 0
        """
        if not self.config.get("humanize.typing_delay", True):
            return 0
        min_d = float(self.config.get("humanize.min_delay", 0.5))
        max_d = float(self.config.get("humanize.max_delay", 5.0))
        length = len(text)
        if length <= 10:
            return random.uniform(min_d, min_d + 1.0)
        elif length <= 30:
            return random.uniform(min_d + 0.5, min_d + 2.0)
        elif length <= 80:
            return random.uniform(max_d - 2.0, max_d)
        return max_d

    # ==================== 输出后处理 ====================

    def apply_postprocess(self, response: str) -> str:
        """应用输出后处理：错字纠正、半句发出

        :param response: AI 原始回复
        :return: str 处理后的回复（可能含 <|wait|> 分隔的多段内容）
        """
        humanize = self.config.get("humanize", {})

        typo_prob = float(humanize.get("typo_probability", 0)) if humanize else 0
        if typo_prob > 0 and random.random() < typo_prob:
            response = self._inject_typo_correction(response)

        half_prob = float(humanize.get("half_send_probability", 0)) if humanize else 0
        if half_prob > 0 and random.random() < half_prob:
            response = self._inject_half_send(response)

        return response

    def should_read_receipt_skip(self) -> bool:
        """判定本次是否"已读不回"（按 humanize.read_receipt_skip 概率）"""
        skip_prob = float(self.config.get("humanize.read_receipt_skip", 0))
        if skip_prob > 0 and random.random() < skip_prob:
            self.logger.debug("已读不回（拟人化）")
            return True
        return False

    def maybe_at_mention(self, response: str, user_nickname: str) -> str:
        """按概率在群聊回复前追加 @昵称

        :param response: 回复文本
        :param user_nickname: 对方昵称，为空时不处理
        :return: str 处理后的回复
        """
        prob = float(self.config.get("humanize.random_at_probability", 0.15))
        if random.random() < prob and user_nickname:
            if f"@{user_nickname}" not in response:
                return f"@{user_nickname} {response}"
        return response

    def _inject_typo_correction(self, text: str) -> str:
        """{!--< internal-use >!--} 注入错字纠正：交换相邻中文字符，纠正消息以 <|wait|> 分隔"""
        chinese_indices = [i for i, c in enumerate(text) if "\u4e00" <= c <= "\u9fff"]
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
        """{!--< internal-use >!--} 注入半句发出：在标点或句中截断，后半句以 <|wait|> 分隔"""
        if len(text) < 8:
            return text

        break_chars = ["，", "。", "；", "、", "！", "？", ",", " ", "~", "～"]
        break_positions = [
            i for i, c in enumerate(text) if c in break_chars and 3 < i < len(text) - 3
        ]

        if break_positions:
            pos = random.choice(break_positions)
            first_half = text[: pos + 1].strip()
            second_half = text[pos + 1:].strip()
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

    # ==================== 回复检测与清洗 ====================

    def is_skip_response(self, text: str, is_private: bool = False) -> bool:
        """检测 AI 回复是否为无效内容（沉默标记/推理过程/聊天记录格式）

        :param text: 待检测的回复文本
        :param is_private: 私聊场景为 True。私聊只做沉默标记与括号推理检测，
            跳过多行聊天记录格式检测（避免误判正常多行回复）
        :return: bool True 表示该回复不应发送
        """
        stripped = text.strip()
        if len(stripped) <= 60:
            for marker in self.SKIP_MARKERS:
                if marker in stripped:
                    return True

        # 代码块回复：跳过聊天记录格式检测（代码中的 key: value 行会误判）
        has_code_block = "```" in stripped
        patterns = self.SKIP_REGEX[:2] if has_code_block else self.SKIP_REGEX
        for pattern in patterns:
            if re.search(pattern, stripped):
                return True
        if has_code_block:
            return False
        if is_private:
            return False

        # 多行且大部分为「名字: 内容」格式 → 判定为输出聊天记录
        lines = [l for l in stripped.split("\n") if l.strip()]
        if len(lines) >= 2:
            chat_count = sum(1 for l in lines if re.match(r"^[^:\n]{1,15}\s*:\s*", l))
            if chat_count >= len(lines) * 0.6:
                return True
        return False

    @staticmethod
    def clean_response_for_history(response: str) -> str:
        """清理回复中的功能标签，用于写入历史记录

        移除表情包/语音/等待分隔符/历史遗留渲染与卡片标签，防止 AI
        从历史中习得标签格式后在功能关闭时仍尝试输出。
        清理结果为空时返回占位文本。

        :param response: 原始回复文本
        :return: str 清理后的文本
        """
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
        # 历史遗留的渲染/卡片标签（旧版本数据兼容）
        response = re.sub(
            r"<\|?\s*render\s*\|?>.*?<\|?\s*/\s*\|?\s*render\s*\|?>",
            "", response, flags=re.IGNORECASE | re.DOTALL
        )
        response = re.sub(
            r"<\|?\s*card\s*\|?>.*?(?:<\|?\s*/\s*\|?\s*card\s*\|?>|$)",
            "", response, flags=re.IGNORECASE | re.DOTALL
        )
        # [img] / [sticker] BBCode 标签
        response = re.sub(
            r"\[(?:img|sticker)\].*?\[/(?:img|sticker)\]", "", response, flags=re.IGNORECASE | re.DOTALL
        )
        response = re.sub(r"  +", " ", response).strip()
        return response if response else "(表情包/语音回复)"

    @staticmethod
    def is_trivial_message(text: str) -> bool:
        """判断消息是否无记忆价值（纯数字/单字/表情/噪音词）

        :param text: 消息文本
        :return: bool True 表示不值得提取记忆
        """
        t = (text or "").strip()
        if not t:
            return True
        if len(t) <= 1:
            return True
        if re.fullmatch(r"[\d\s.,，。!！?？~～:：、]+", t):
            return True
        if re.fullmatch(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]+", t):
            return True
        noise = {
            "123", "测试", "哈哈", "哈哈哈", "嗯", "好", "ok", "okay",
            "在吗", "在", "试试", "没事", "无", "没有",
        }
        return t in noise
