"""
并发 LLM 抽取器 - 使用 ThreadPoolExecutor 对文本 chunk 并发调用 LLM 提取断言和事件
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from core.observability import get_logger
from knowledge_layer.assertions.prompts import AssertionPrompts

logger = get_logger(__name__)


class ModelResponseLike(Protocol):
    content: str


class ModelGatewayLike(Protocol):
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = ...,
        model: str | None = ...,
        **kwargs: Any,
    ) -> ModelResponseLike:
        ...


BuildAssertionFn = Callable[[dict[str, Any], str, int | None], Any]
BuildEventFn = Callable[[dict[str, Any], str, int | None], Any]
ParseResponseFn = Callable[[str], dict[str, Any]]


@dataclass
class ChunkExtractionResult:
    """单个 chunk 的提取结果"""

    chunk_index: int
    assertions: list[Any] = field(default_factory=list)
    events: list[Any] = field(default_factory=list)
    error: str | None = None
    latency_sec: float = 0.0


class ConcurrentLLMExtractor:
    """并发 LLM 抽取器 - 对多个 chunk 并发调用 LLM 提取断言和事件"""

    CHUNK_TIMEOUT_SEC = 120  # 单个 chunk 提取最大等待时间

    def __init__(
        self,
        model_gateway: ModelGatewayLike,
        build_assertion_fn: BuildAssertionFn,
        build_event_fn: BuildEventFn,
        parse_response_fn: ParseResponseFn,
        max_workers: int = 16,
        max_retries: int = 2,
        model: str | None = None,
        task: str | None = "extraction",
    ) -> None:
        self.model_gateway = model_gateway
        self.build_assertion_fn = build_assertion_fn
        self.build_event_fn = build_event_fn
        self.parse_response_fn = parse_response_fn
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.model = model
        self.task = task

    def extract_chunks(
        self,
        chunks: list[str],
        doc_id: str,
    ) -> tuple[list[Any], list[Any], dict[str, Any]]:
        """对 chunk 列表并发执行 LLM 提取

        Args:
            chunks: 文本 chunk 列表
            doc_id: 文档 ID

        Returns:
            (assertions, events, stats) 元组
        """
        if not chunks:
            return [], [], {"chunk_count": 0}

        results: list[ChunkExtractionResult] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._extract_one_chunk, chunk, doc_id, i): i
                for i, chunk in enumerate(chunks)
            }

            for future in as_completed(futures):
                result = future.result(timeout=self.CHUNK_TIMEOUT_SEC)
                results.append(result)

        results.sort(key=lambda x: x.chunk_index)

        assertions: list[Any] = []
        events: list[Any] = []
        errors: list[dict[str, Any]] = []

        for r in results:
            assertions.extend(r.assertions)
            events.extend(r.events)
            if r.error:
                errors.append({"chunk_index": r.chunk_index, "error": r.error})

        stats: dict[str, Any] = {
            "chunk_count": len(chunks),
            "max_workers": self.max_workers,
            "success_chunks": sum(1 for r in results if not r.error),
            "failed_chunks": sum(1 for r in results if r.error),
            "total_assertions": len(assertions),
            "total_events": len(events),
            "avg_latency_sec": (
                sum(r.latency_sec for r in results) / len(results) if results else 0
            ),
            "errors": errors[:10],
        }

        return assertions, events, stats

    def _extract_one_chunk(
        self,
        chunk: str,
        doc_id: str,
        chunk_index: int,
    ) -> ChunkExtractionResult:
        """提取单个 chunk 的断言和事件（带重试）"""
        start = time.perf_counter()
        last_error: str | None = None

        for attempt in range(self.max_retries + 1):
            try:
                system_prompt = AssertionPrompts.COMBINED_EXTRACT_SYSTEM_ZH
                user_prompt = AssertionPrompts.COMBINED_EXTRACT_USER_ZH.format(text=chunk)

                response = self.model_gateway.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.1,
                    model=self.model,
                    task=self.task,
                )

                raw_data = self.parse_response_fn(response.content)

                assertions = []
                for item in raw_data.get("assertions", []):
                    obj = self.build_assertion_fn(item, doc_id, chunk_index=chunk_index)
                    if obj:
                        assertions.append(obj)

                events = []
                for item in raw_data.get("events", []):
                    obj = self.build_event_fn(item, doc_id, chunk_index=chunk_index)
                    if obj:
                        events.append(obj)

                return ChunkExtractionResult(
                    chunk_index=chunk_index,
                    assertions=assertions,
                    events=events,
                    latency_sec=time.perf_counter() - start,
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "chunk extraction failed",
                    chunk_index=chunk_index,
                    attempt=attempt,
                    error=last_error,
                )
                time.sleep(min(2**attempt, 8))

        return ChunkExtractionResult(
            chunk_index=chunk_index,
            error=last_error,
            latency_sec=time.perf_counter() - start,
        )
