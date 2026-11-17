"""基于 Playwright 的 Microsoft Edge Web 适配器。"""

from adapters.web.edge_adapter import (
    EdgeAdapter,
    EdgeCheckResult,
    LoginVisibilityResult,
    PageStructureSummary,
    WebAdapterError,
)

__all__ = [
    "EdgeAdapter",
    "EdgeCheckResult",
    "LoginVisibilityResult",
    "PageStructureSummary",
    "WebAdapterError",
]
