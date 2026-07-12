"""MinerU 转换策略 —— 基于 opendatalab/mineru 的高质量 PDF 解析

作为高质量选项，适用于复杂研报 PDF，保留表格结构和文档布局。
不可用时优雅降级。
"""
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.contracts.pdf_conversion import ConversionResult, StrategyType
from ingestion.converters.base import PDFConversionStrategy

logger = logging.getLogger(__name__)

# 检测 mineru 是否可用
try:
    import importlib.util

    HAS_MINERU = importlib.util.find_spec("mineru") is not None
except Exception:
    HAS_MINERU = False


class MinerUStrategy(PDFConversionStrategy):
    """基于 opendatalab/mineru 的高质量 PDF 转换策略

    支持两种后端：
    - Python API：直接使用 mineru Python 模块
    - CLI 回退：通过 magic-pdf 命令行工具
    - pipeline 模式：适用于 CPU 环境
    """

    def __init__(self, backend: str = "auto", method: str = "auto"):
        """
        Args:
            backend: mineru 后端模式 ("auto", "pipeline", "api")
            method: 解析方法 ("auto", "ocr", "txt")
        """
        self._backend = backend
        self._method = method
        self._last_error = ""

    def is_available(self) -> bool:
        if not HAS_MINERU:
            return False
        # 进一步检查 CLI 是否可用
        if self._backend in ("auto", "pipeline"):
            return self._check_cli_available() and self._model_cache_ready()
        return True

    @staticmethod
    def _check_cli_available() -> bool:
        """检查 MinerU CLI 是否可用，兼容新版 mineru 和旧版 magic-pdf。"""
        if shutil.which("mineru") or shutil.which("magic-pdf"):
            return True
        try:
            result = subprocess.run(["mineru", "--help"], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            try:
                import mineru  # noqa: F401

                return True
            except ImportError:
                return False

    @staticmethod
    def _model_cache_ready() -> bool:
        """检查 MinerU 本地模型是否已准备好。

        新版 MinerU pipeline 会从 HuggingFace 拉取 opendatalab/PDF-Extract-Kit-1.0。
        如果没有本地缓存，自动队列里直接尝试会长时间阻塞后失败；只有显式允许
        在线下载时才把它视为可用。
        """
        if os.environ.get("MINERU_ALLOW_MODEL_DOWNLOAD") == "1":
            return True

        cache_roots = [
            Path(os.environ.get("HF_HOME", "")).expanduser() / "hub"
            if os.environ.get("HF_HOME")
            else None,
            Path.home() / ".cache" / "huggingface" / "hub",
        ]
        for root in [p for p in cache_roots if p]:
            repo_dir = root / "models--opendatalab--PDF-Extract-Kit-1.0"
            snapshots = repo_dir / "snapshots"
            if snapshots.exists() and any(snapshots.iterdir()):
                return True
        return False

    def convert(self, pdf_path: str) -> ConversionResult:
        if not HAS_MINERU:
            return ConversionResult(
                success=False,
                strategy_used=self.name,
                error_message="mineru 未安装，请执行: pip install mineru[all]",
            )

        if not os.path.exists(pdf_path):
            return ConversionResult(
                success=False,
                strategy_used=self.name,
                error_message=f"文件不存在: {pdf_path}",
            )

        output_dir = tempfile.mkdtemp(prefix="mineru_output_")

        try:
            self._last_error = ""
            result_path = self._run_mineru(pdf_path, output_dir)

            if result_path and os.path.exists(result_path):
                markdown = self._read_output(result_path)
                page_count = self._count_pages(markdown)
                token_count = self.estimate_tokens(markdown)
                features = self._detect_features(markdown)
                quality_score = self._compute_quality_score(markdown, features)

                return ConversionResult(
                    success=True,
                    strategy_used=self.name,
                    markdown=markdown,
                    page_count=page_count,
                    token_count=token_count,
                    quality_score=quality_score,
                    has_tables=features.get("has_tables", False),
                    has_images=features.get("has_images", False),
                    has_code_blocks=features.get("has_code_blocks", False),
                    metadata=features,
                )

            return ConversionResult(
                success=False,
                strategy_used=self.name,
                error_message=self._last_error or f"mineru 输出为空: {output_dir}",
            )
        except Exception as e:
            logger.warning(f"MinerU 转换失败: {e}")
            return ConversionResult(
                success=False,
                strategy_used=self.name,
                error_message=str(e),
            )

    def _run_mineru(self, pdf_path: str, output_dir: str) -> Optional[str]:
        """执行 mineru 转换，返回输出 markdown 文件路径"""
        if self._backend in ("auto", "pipeline"):
            # 尝试新版 mineru CLI 或旧版 magic-pdf CLI。
            try:
                cmd = self._build_cli_command(pdf_path, output_dir)
                if cmd:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=900,
                        env=self._subprocess_env(),
                    )
                    if result.returncode != 0:
                        self._last_error = self._format_cli_error(result, cmd)
                        logger.warning(self._last_error)
                        return None

                    md_path = self._find_markdown_output(output_dir, pdf_path)
                    if md_path:
                        return md_path
            except Exception as e:
                self._last_error = f"MinerU CLI 失败: {e}"
                logger.debug(f"{self._last_error}，尝试 Python API")

        # 尝试 Python API
        try:
            from mineru import MagicPDF

            parser = MagicPDF()
            result = parser.parse(pdf_path, output_dir=output_dir)

            if hasattr(result, "markdown_path"):
                return result.markdown_path
            if isinstance(result, dict):
                return result.get("markdown_path")
        except Exception:
            if not self._last_error:
                self._last_error = "MinerU Python API 不可用或执行失败"

        # 最后尝试：查找 output_dir 下的任何 .md 文件
        md_path = self._find_markdown_output(output_dir, pdf_path)
        if md_path:
            return md_path

        return None

    def _build_cli_command(self, pdf_path: str, output_dir: str) -> Optional[List[str]]:
        mineru_cli = shutil.which("mineru")
        if mineru_cli:
            cmd = [
                mineru_cli,
                "-p",
                pdf_path,
                "-o",
                output_dir,
                "-m",
                self._method,
            ]
            if self._backend != "auto":
                cmd.extend(["-b", self._backend])
            else:
                cmd.extend(["-b", "pipeline"])
            return cmd

        magic_pdf_cli = shutil.which("magic-pdf")
        if magic_pdf_cli:
            return [
                magic_pdf_cli,
                "-p",
                pdf_path,
                "-o",
                output_dir,
                "-m",
                self._method,
            ]

        return None

    @staticmethod
    def _subprocess_env() -> Dict[str, str]:
        env = os.environ.copy()
        for key in (
            "http_proxy",
            "https_proxy",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "all_proxy",
            "ALL_PROXY",
        ):
            env.pop(key, None)
        env["NO_PROXY"] = "*"
        env["no_proxy"] = "*"
        return env

    @staticmethod
    def _format_cli_error(result: subprocess.CompletedProcess, cmd: List[str]) -> str:
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        combined = "\n".join(part for part in (stdout, stderr) if part)
        if len(combined) > 4000:
            combined = combined[-4000:]
        return f"MinerU CLI 执行失败: exit={result.returncode}, cmd={' '.join(cmd)}" + (
            f"\n{combined}" if combined else ""
        )

    @staticmethod
    def _find_markdown_output(output_dir: str, pdf_path: str) -> Optional[str]:
        if not os.path.exists(output_dir):
            return None

        pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
        likely_paths = [
            os.path.join(output_dir, pdf_basename, f"{pdf_basename}.md"),
            os.path.join(output_dir, f"{pdf_basename}.md"),
        ]
        for path in likely_paths:
            if os.path.exists(path):
                return path

        for root, _, files in os.walk(output_dir):
            for f in files:
                if f.endswith(".md"):
                    return os.path.join(root, f)
        return None

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.MINERU

    @property
    def name(self) -> str:
        return "mineru"

    @staticmethod
    def _read_output(result_path: str) -> str:
        """读取 mineru 输出的 markdown 文件"""
        with open(result_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def _count_pages(markdown: str) -> int:
        """从 markdown 内容估算页数（通过页面锚点）"""
        import re

        matches = re.findall(r"<!-- page: (\d+) -->", markdown)
        if matches:
            return max(int(m) for m in matches)
        # 没有锚点时估算
        return max(1, len(markdown) // 3000)

    @staticmethod
    def _detect_features(markdown: str) -> Dict[str, Any]:
        """检测 Markdown 内容特征"""
        return {
            "has_tables": "| " in markdown and " |" in markdown,
            "has_images": "![" in markdown,
            "has_code_blocks": "```" in markdown,
        }

    @staticmethod
    def _compute_quality_score(markdown: str, features: Dict[str, Any]) -> float:
        """计算转换质量评分"""
        if not markdown.strip():
            return 0.0

        score = 0.7  # mineru 基准质量最高

        if features.get("has_tables"):
            score += 0.15
        if features.get("has_images"):
            score += 0.05

        # 标题层级丰富度
        heading_levels = set()
        for line in markdown.split("\n"):
            if line.startswith("#"):
                heading_levels.add(min(len(line) - len(line.lstrip("#")), 4))
        if len(heading_levels) >= 3:
            score += 0.1

        return min(score, 1.0)
