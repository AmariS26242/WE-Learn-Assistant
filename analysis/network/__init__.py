"""脱敏网络事件元数据模型（仅保留非敏感请求摘要）。"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from core.logging_utils import mask_sensitive_text


@dataclass(slots=True)
class SanitizedNetworkEvent:
    """脱敏后的请求摘要（不存储请求体、Cookie 或认证头）。"""

    method: str
    host: str
    path: str
    status_code: int | None = None
    content_type: str = ""

    @classmethod
    def from_url(
        cls,
        method: str,
        url: str,
        *,
        status_code: int | None = None,
        content_type: str = "",
    ) -> SanitizedNetworkEvent:
        parsed = urlsplit(url)
        return cls(
            method=method.upper(),
            host=parsed.netloc,
            path=mask_sensitive_text(parsed.path or "/"),
            status_code=status_code,
            content_type=content_type,
        )
