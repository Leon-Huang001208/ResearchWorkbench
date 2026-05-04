"""HTML 解析器"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.observability import get_logger

logger = get_logger(__name__)


@dataclass
class HTMLParseResult:
    """HTML 解析结果"""

    text: str
    title: str
    metadata: dict[str, Any]


class HTMLParser:
    """HTML 文档解析器"""

    def __init__(self):
        pass

    def parse(self, html_source: Path | str | bytes) -> HTMLParseResult:
        """解析 HTML 文件"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("beautifulsoup4 not installed. Please install it first.")
            raise

        if isinstance(html_source, Path):
            html_content = html_source.read_text(encoding="utf-8")
            source_path = str(html_source)
        elif isinstance(html_source, bytes):
            html_content = html_source.decode("utf-8", errors="ignore")
            source_path = None
        else:
            html_content = html_source
            source_path = None

        soup = BeautifulSoup(html_content, "lxml")

        # 提取标题
        title = self._extract_title(soup)

        # 提取正文
        text = self._extract_text(soup)

        # 提取元数据
        metadata = self._extract_metadata(soup)
        if source_path:
            metadata["source_path"] = source_path

        result = HTMLParseResult(
            text=text,
            title=title,
            metadata=metadata,
        )

        logger.info(f"Successfully parsed HTML: {title}")
        return result

    def _extract_title(self, soup: Any) -> str:
        """提取标题"""
        # 优先尝试 <title> 标签
        if soup.title and soup.title.string:
            return soup.title.string.strip()

        # 尝试 <h1> 标签
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)

        # 尝试 Open Graph 元标签
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        return "Untitled HTML"

    def _extract_text(self, soup: Any) -> str:
        """提取正文文本"""
        # 移除不需要的元素
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
            element.decompose()

        # 尝试找到主要内容区域
        main_content = self._find_main_content(soup)

        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

        # 清洗文本
        text = self._clean_text(text)
        return text

    def _find_main_content(self, soup: Any) -> Any:
        """尝试找到主要内容区域"""
        # 常见的主要内容容器选择器
        selectors = [
            "main",
            "article",
            '[role="main"]',
            "#content",
            ".content",
            "#main",
            ".main",
            "#article",
            ".article",
            ".post",
            ".entry",
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                # 检查这个元素是否有足够的内容
                if len(element.get_text(strip=True)) > 100:
                    return element

        return None

    def _extract_metadata(self, soup: Any) -> dict[str, Any]:
        """提取元数据"""
        metadata = {}

        # 提取 <meta> 标签
        for meta in soup.find_all("meta"):
            name = meta.get("name") or meta.get("property")
            content = meta.get("content")
            if name and content:
                metadata[name] = content

        # 提取 author
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta and author_meta.get("content"):
            metadata["author"] = author_meta["content"]

        # 提取 description
        desc_meta = soup.find("meta", attrs={"name": "description"})
        if desc_meta and desc_meta.get("content"):
            metadata["description"] = desc_meta["content"]

        return metadata

    def _clean_text(self, text: str) -> str:
        """清洗文本"""
        # 去除多余的空行
        text = re.sub(r"\n\s*\n", "\n\n", text)
        # 去除行尾空格
        text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
        return text.strip()
