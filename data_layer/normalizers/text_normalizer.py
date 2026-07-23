"""文本标准化器"""

import re
import unicodedata

from core.observability import get_logger

logger = get_logger(__name__)


class TextNormalizer:
    """文本标准化器"""

    def __init__(self):
        pass

    def normalize(self, text: str) -> str:
        """标准化文本"""
        if not text:
            return ""

        # Unicode 标准化
        text = unicodedata.normalize("NFKC", text)

        # 统一换行符
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 去除不可见字符
        text = self._remove_invisible_chars(text)

        # 规范化空白字符
        text = self._normalize_whitespace(text)

        return text.strip()

    def _remove_invisible_chars(self, text: str) -> str:
        """去除不可见字符"""
        # 保留换行、制表符等基本空白字符
        # 移除其他控制字符
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        # 移除零宽字符
        text = re.sub(r"[​-‍﻿]", "", text)
        return text

    def _normalize_whitespace(self, text: str) -> str:
        """规范化空白字符"""
        # 将多个空格替换为单个空格（不影响换行）
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        # 行内多个空格替换为单个
        text = re.sub(r"[ \t]+", " ", text)
        # 多个空行保留最多两个
        text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)
        return text

    def normalize_fullwidth(self, text: str) -> str:
        """全角字符转半角"""
        result = []
        for char in text:
            code = ord(char)
            # 全角 ASCII 字符范围
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            # 全角空格
            elif code == 0x3000:
                result.append(" ")
            else:
                result.append(char)
        return "".join(result)

    def extract_clean_sentences(self, text: str) -> list[str]:
        """提取清洗后的句子"""
        sentences = re.split(r"[。！？!?\n]+", text)
        return [s.strip() for s in sentences if s.strip()]
