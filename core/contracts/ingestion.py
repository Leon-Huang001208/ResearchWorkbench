"""
Core contracts for the unified ingestion queue.

This module defines Pydantic models for the unified ingestion queue in AlphaFoundry,
including queue items, statistics, enqueue requests/responses, process responses,
and retry responses.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class IngestionQueueItem(BaseModel):
    """统一摄取队列项.

    Represents an item in the unified ingestion queue, including item ID,
    source type, source ID, raw content, title, URL, priority, status,
    retry count, max retries, failure reason, creation/processing timestamps,
    and deduplication hash.

    Attributes:
        item_id: Unique identifier for the queue item.
        source_type: Type of source (e.g., "cls", "cnstock", "zq", "report", "manual", "future").
        source_id: Optional ID from the source (used for deduplication).
        raw_content: Raw content of the item.
        title: Optional title of the item.
        url: Optional URL of the item.
        priority: Priority of the item (0=normal, 1=high, 2=urgent) (default 0).
        status: Status of the item (pending, processing, completed, failed) (default "pending").
        retry_count: Number of retries attempted so far (default 0).
        max_retries: Maximum number of retries allowed (default 3).
        failure_reason: Optional reason for failure (if applicable).
        created_at: Timestamp when the item was created.
        processed_at: Timestamp when the item was processed (if applicable).
        dedup_hash: Optional hash used for deduplication.
    """

    item_id: str = Field(description="Unique identifier for the queue item")
    source_type: str = Field(description="Type of source (e.g., cls, cnstock, zq, report, manual, future)")
    source_id: Optional[str] = Field(default=None, description="Optional source ID (used for deduplication)")
    raw_content: str = Field(description="Raw content of the item")
    title: Optional[str] = Field(default=None, description="Optional title of the item")
    url: Optional[str] = Field(default=None, description="Optional URL of the item")
    priority: int = Field(default=0, description="Priority of the item (0=normal, 1=high, 2=urgent)")
    status: str = Field(default="pending", description="Status of the item (pending, processing, completed, failed)")
    retry_count: int = Field(default=0, description="Number of retries attempted so far")
    max_retries: int = Field(default=3, description="Maximum number of retries allowed")
    failure_reason: Optional[str] = Field(default=None, description="Optional reason for failure (if applicable)")
    created_at: datetime = Field(description="Timestamp when the item was created")
    processed_at: Optional[datetime] = Field(default=None, description="Timestamp when the item was processed (if applicable)")
    dedup_hash: Optional[str] = Field(default=None, description="Optional hash used for deduplication")


class IngestionQueueStats(BaseModel):
    """队列统计.

    Represents statistics for the ingestion queue, including depth, pending,
    processing, completed, failed counts, and average latency in milliseconds.

    Attributes:
        depth: Current depth of the queue (total pending/processing items).
        pending: Number of items in pending status.
        processing: Number of items in processing status.
        completed: Number of items in completed status.
        failed: Number of items in failed status.
        avg_latency_ms: Average latency from creation to processing (in milliseconds).
    """

    depth: int = Field(description="Current depth of the queue (total pending/processing items)")
    pending: int = Field(description="Number of items in pending status")
    processing: int = Field(description="Number of items in processing status")
    completed: int = Field(description="Number of items in completed status")
    failed: int = Field(description="Number of items in failed status")
    avg_latency_ms: float = Field(description="Average latency from creation to processing (in milliseconds)")


class EnqueueRequest(BaseModel):
    """入队请求.

    Request schema for enqueuing a new item, including source type, source ID,
    raw content, title, URL, and priority.

    Attributes:
        source_type: Type of source (e.g., "cls", "cnstock", "zq", "report", "manual", "future").
        source_id: Optional ID from the source (used for deduplication).
        raw_content: Raw content of the item.
        title: Optional title of the item.
        url: Optional URL of the item.
        priority: Priority of the item (0=normal, 1=high, 2=urgent) (default 0).
    """

    source_type: str = Field(..., description="Type of source (e.g., cls, cnstock, zq, report, manual, future)")
    source_id: Optional[str] = Field(None, description="Optional source ID (used for deduplication)")
    raw_content: str = Field(..., description="Raw content of the item")
    title: Optional[str] = Field(None, description="Optional title of the item")
    url: Optional[str] = Field(None, description="Optional URL of the item")
    priority: int = Field(0, description="Priority of the item (0=normal, 1=high, 2=urgent)")


class EnqueueResponse(BaseModel):
    """入队响应.

    Response schema for an enqueue request, including item ID, deduplication hash,
    whether it was a duplicate, and a message.

    Attributes:
        item_id: Unique identifier for the enqueued item.
        dedup_hash: Hash used for deduplication.
        was_duplicate: Whether the item was a duplicate (True) or not (False) (default False).
        message: Response message (default "enqueued").
    """

    item_id: str = Field(description="Unique identifier for the enqueued item")
    dedup_hash: str = Field(description="Hash used for deduplication")
    was_duplicate: bool = Field(default=False, description="Whether the item was a duplicate")
    message: str = Field(default="enqueued", description="Response message")


class ProcessResponse(BaseModel):
    """处理响应.

    Response schema for processing queue items, including processed count and results.

    Attributes:
        processed_count: Number of items processed in this operation.
        results: List of result dictionaries for processed items.
    """

    processed_count: int = Field(description="Number of items processed in this operation")
    results: list[dict] = Field(default_factory=list, description="List of result dictionaries for processed items")


class RetryResponse(BaseModel):
    """重试响应.

    Response schema for retrying failed items, including retried count and message.

    Attributes:
        retried_count: Number of items retried in this operation.
        message: Response message.
    """

    retried_count: int = Field(description="Number of items retried in this operation")
    message: str = Field(description="Response message")
