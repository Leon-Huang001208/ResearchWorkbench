"""测试并发 LLM 抽取器"""

from unittest.mock import Mock

from knowledge_layer.extraction.concurrent_extractor import (
    ChunkExtractionResult,
    ConcurrentLLMExtractor,
)


class TestChunkExtractionResult:
    """测试 ChunkExtractionResult dataclass"""

    def test_default_values(self):
        result = ChunkExtractionResult(chunk_index=0)
        assert result.chunk_index == 0
        assert result.assertions == []
        assert result.events == []
        assert result.error is None
        assert result.latency_sec == 0.0

    def test_with_data(self):
        result = ChunkExtractionResult(
            chunk_index=1,
            assertions=["a1", "a2"],
            events=["e1"],
            latency_sec=0.5,
        )
        assert len(result.assertions) == 2
        assert len(result.events) == 1
        assert result.error is None

    def test_with_error(self):
        result = ChunkExtractionResult(
            chunk_index=2,
            error="timeout",
            latency_sec=10.0,
        )
        assert result.error == "timeout"
        assert result.assertions == []


class TestConcurrentLLMExtractor:
    """测试 ConcurrentLLMExtractor"""

    def _make_mock_gateway(self, responses: list[str]):
        """创建模拟的 model gateway，返回指定的响应序列"""
        mock_gw = Mock()
        mock_gw.chat = Mock(side_effect=[Mock(content=r) for r in responses])
        return mock_gw

    def _make_extractor(self, mock_gw, max_workers=2):
        """创建测试用的 extractor"""

        def build_assertion(data, doc_id, chunk_index=None):
            return {"type": "assertion", **data, "chunk_index": chunk_index}

        def build_event(data, doc_id, chunk_index=None):
            return {"type": "event", **data, "chunk_index": chunk_index}

        def parse_response(content):
            import json

            return json.loads(content)

        return ConcurrentLLMExtractor(
            model_gateway=mock_gw,
            build_assertion_fn=build_assertion,
            build_event_fn=build_event,
            parse_response_fn=parse_response,
            max_workers=max_workers,
            max_retries=2,
        )

    def test_empty_chunks(self):
        mock_gw = self._make_mock_gateway([])
        extractor = self._make_extractor(mock_gw)

        assertions, events, stats = extractor.extract_chunks([], "doc-1")

        assert assertions == []
        assert events == []
        assert stats["chunk_count"] == 0

    def test_single_chunk_success(self):
        import json

        response = json.dumps(
            {
                "assertions": [{"subject": "茅台", "predicate": "增长"}],
                "events": [{"event_type": "earnings", "summary": "财报发布"}],
            }
        )
        mock_gw = self._make_mock_gateway([response])
        extractor = self._make_extractor(mock_gw)

        assertions, events, stats = extractor.extract_chunks(["茅台发布财报"], "doc-1")

        assert len(assertions) == 1
        assert assertions[0]["subject"] == "茅台"
        assert len(events) == 1
        assert events[0]["event_type"] == "earnings"
        assert stats["chunk_count"] == 1
        assert stats["success_chunks"] == 1
        assert stats["failed_chunks"] == 0

    def test_multiple_chunks_concurrent(self):
        import json

        r1 = json.dumps({"assertions": [{"subject": "A"}], "events": []})
        r2 = json.dumps({"assertions": [{"subject": "B"}], "events": []})
        r3 = json.dumps({"assertions": [], "events": [{"summary": "event"}]})

        mock_gw = self._make_mock_gateway([r1, r2, r3])
        extractor = self._make_extractor(mock_gw, max_workers=3)

        assertions, events, stats = extractor.extract_chunks(
            ["chunk-a", "chunk-b", "chunk-c"], "doc-1"
        )

        assert len(assertions) == 2
        assert len(events) == 1
        assert stats["chunk_count"] == 3
        assert stats["success_chunks"] == 3
        assert stats["failed_chunks"] == 0
        assert stats["max_workers"] == 3

    def test_results_sorted_by_chunk_index(self):
        import json

        r1 = json.dumps({"assertions": [{"subject": "first"}], "events": []})
        r2 = json.dumps({"assertions": [{"subject": "second"}], "events": []})

        mock_gw = self._make_mock_gateway([r1, r2])
        extractor = self._make_extractor(mock_gw, max_workers=2)

        assertions, events, stats = extractor.extract_chunks(["chunk-0", "chunk-1"], "doc-1")

        # 验证 chunk_index 被正确传递
        chunk_indices = [a["chunk_index"] for a in assertions]
        assert sorted(chunk_indices) == chunk_indices

    def test_failed_chunk_does_not_block_others(self):
        import json

        def side_effect(messages, **kwargs):
            # 第二个 chunk 失败
            msg = messages[1]["content"]
            if "chunk-1" in msg:
                raise RuntimeError("simulated failure")
            return Mock(content=json.dumps({"assertions": [{"subject": "ok"}], "events": []}))

        mock_gw = Mock()
        mock_gw.chat = Mock(side_effect=side_effect)
        extractor = self._make_extractor(mock_gw, max_workers=2)

        assertions, events, stats = extractor.extract_chunks(["chunk-0", "chunk-1"], "doc-1")

        # chunk-0 应该成功
        assert len(assertions) == 1
        assert stats["success_chunks"] == 1
        assert stats["failed_chunks"] == 1
        assert len(stats["errors"]) == 1

    def test_retry_on_failure(self):
        import json

        call_count = [0]

        def side_effect(messages, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise RuntimeError("temporary failure")
            return Mock(content=json.dumps({"assertions": [], "events": []}))

        mock_gw = Mock()
        mock_gw.chat = Mock(side_effect=side_effect)
        extractor = self._make_extractor(mock_gw, max_workers=1)

        assertions, events, stats = extractor.extract_chunks(["test"], "doc-1")

        # 第3次尝试应该成功
        assert stats["success_chunks"] == 1
        assert stats["failed_chunks"] == 0

    def test_chunk_index_passed_to_build_functions(self):
        import json

        captured_chunk_indices = []

        def build_assertion(data, doc_id, chunk_index=None):
            captured_chunk_indices.append(chunk_index)
            return {"type": "assertion", **data}

        def build_event(data, doc_id, chunk_index=None):
            return None

        def parse_response(content):
            return json.loads(content)

        mock_gw = Mock()
        mock_gw.chat.return_value = Mock(
            content=json.dumps({"assertions": [{"subj": "X"}], "events": []})
        )

        extractor = ConcurrentLLMExtractor(
            model_gateway=mock_gw,
            build_assertion_fn=build_assertion,
            build_event_fn=build_event,
            parse_response_fn=parse_response,
            max_workers=1,
            max_retries=1,
        )

        extractor.extract_chunks(["chunk-0", "chunk-1"], "doc-1")
        assert captured_chunk_indices == [0, 1]

    def test_model_parameter_passed_to_gateway(self):
        import json

        captured_models = []

        def side_effect(messages, **kwargs):
            captured_models.append(kwargs.get("model"))
            return Mock(content=json.dumps({"assertions": [], "events": []}))

        mock_gw = Mock()
        mock_gw.chat = Mock(side_effect=side_effect)

        extractor = ConcurrentLLMExtractor(
            model_gateway=mock_gw,
            build_assertion_fn=lambda d, doc_id, chunk_index=None: d,
            build_event_fn=lambda d, doc_id, chunk_index=None: None,
            parse_response_fn=json.loads,
            max_workers=1,
            max_retries=1,
            model="gpt-4o-mini",
        )

        extractor.extract_chunks(["chunk-0", "chunk-1"], "doc-1")
        assert all(m == "gpt-4o-mini" for m in captured_models), captured_models

    def test_model_none_when_not_set(self):
        import json

        captured_models = []

        def side_effect(messages, **kwargs):
            captured_models.append(kwargs.get("model"))
            return Mock(content=json.dumps({"assertions": [], "events": []}))

        mock_gw = Mock()
        mock_gw.chat = Mock(side_effect=side_effect)

        extractor = ConcurrentLLMExtractor(
            model_gateway=mock_gw,
            build_assertion_fn=lambda d, doc_id, chunk_index=None: d,
            build_event_fn=lambda d, doc_id, chunk_index=None: None,
            parse_response_fn=json.loads,
            max_workers=1,
            max_retries=1,
        )

        extractor.extract_chunks(["chunk-0"], "doc-1")
        assert captured_models == [None]

    def test_many_chunks_all_processed(self):
        import json

        response = json.dumps({"assertions": [{"subject": "X"}], "events": []})
        mock_gw = self._make_mock_gateway([response] * 32)
        extractor = self._make_extractor(mock_gw, max_workers=8)

        chunks = [f"chunk-{i}" for i in range(32)]
        assertions, events, stats = extractor.extract_chunks(chunks, "doc-1")

        assert len(assertions) == 32
        assert stats["chunk_count"] == 32
        assert stats["success_chunks"] == 32
        assert stats["failed_chunks"] == 0

    def test_concurrent_faster_than_serial(self):
        import json
        import time

        def delayed_response(messages, **kwargs):
            time.sleep(0.05)
            return Mock(content=json.dumps({"assertions": [], "events": []}))

        mock_gw = Mock()
        mock_gw.chat = Mock(side_effect=delayed_response)

        chunks = [f"chunk-{i}" for i in range(8)]

        # serial (max_workers=1)
        extractor_serial = ConcurrentLLMExtractor(
            model_gateway=mock_gw,
            build_assertion_fn=lambda d, doc_id, chunk_index=None: d,
            build_event_fn=lambda d, doc_id, chunk_index=None: None,
            parse_response_fn=json.loads,
            max_workers=1,
            max_retries=1,
        )
        t0 = time.perf_counter()
        extractor_serial.extract_chunks(chunks, "doc-1")
        serial_time = time.perf_counter() - t0

        # concurrent (max_workers=8)
        extractor_concurrent = ConcurrentLLMExtractor(
            model_gateway=mock_gw,
            build_assertion_fn=lambda d, doc_id, chunk_index=None: d,
            build_event_fn=lambda d, doc_id, chunk_index=None: None,
            parse_response_fn=json.loads,
            max_workers=8,
            max_retries=1,
        )
        t0 = time.perf_counter()
        extractor_concurrent.extract_chunks(chunks, "doc-1")
        concurrent_time = time.perf_counter() - t0

        # 8 并发应该显著快于串行（每个 chunk 延迟 0.05s）
        assert (
            concurrent_time < serial_time * 0.5
        ), f"serial={serial_time:.3f}s, concurrent={concurrent_time:.3f}s"

    def test_retry_success_counts_as_success(self):
        import json

        call_count = {"count": 0}

        def side_effect(messages, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                raise RuntimeError("first attempt fails")
            return Mock(
                content=json.dumps({"assertions": [{"subject": "recovered"}], "events": []})
            )

        mock_gw = Mock()
        mock_gw.chat = Mock(side_effect=side_effect)
        extractor = self._make_extractor(mock_gw, max_workers=1)

        assertions, events, stats = extractor.extract_chunks(["test"], "doc-1")

        assert stats["success_chunks"] == 1
        assert stats["failed_chunks"] == 0
        assert len(assertions) == 1
        assert assertions[0]["subject"] == "recovered"
