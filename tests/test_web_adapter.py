"""Web Adapter（Playwright + Edge）单元与本地离线浏览器测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.web.edge_adapter import EdgeAdapter, WebAdapterError, find_edge_executable
from core.config import WebConfig


class _FakePage:
    def __init__(self) -> None:
        self.url = "https://example.local/course"
        self._title = "WE Learn 测试页"
        self.timeout = 0

    def set_default_timeout(self, ms: int) -> None:
        self.timeout = ms

    def goto(self, url: str, **_kwargs) -> None:
        self.url = url

    def title(self) -> str:
        return self._title

    def screenshot(self, path: str, **_kwargs) -> None:
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\nfake")

    def evaluate(self, script: str):
        if "heading_count" in script:
            return {
                "heading_count": 2,
                "headings": ["Unit 1", "Listening"],
                "link_count": 5,
                "button_count": 3,
                "input_count": 1,
                "iframe_count": 0,
                "has_audio": True,
                "has_video": False,
            }
        return {
            "passwordVisible": True,
            "loginButtonVisible": True,
            "formVisible": True,
        }


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self.pages = [page]

    def new_page(self) -> _FakePage:
        return self.pages[0]


class _FakeBrowser:
    def __init__(self, page: _FakePage) -> None:
        self.version = "157.0.0.0"
        self.contexts = [_FakeContext(page)]

    def new_context(self) -> _FakeContext:
        return self.contexts[0]

    def close(self) -> None:
        return None


class _FakeChromium:
    def __init__(self, page: _FakePage) -> None:
        self._page = page

    def launch(self, **_kwargs) -> _FakeBrowser:
        return _FakeBrowser(self._page)


class _FakePlaywright:
    def __init__(self, page: _FakePage) -> None:
        self.chromium = _FakeChromium(page)

    def start(self) -> _FakePlaywright:
        return self

    def stop(self) -> None:
        return None


def test_web_adapter_require_connection_raises() -> None:
    adapter = EdgeAdapter()
    with pytest.raises(WebAdapterError):
        adapter.get_title()


def test_web_adapter_with_mock_playwright(tmp_path: Path) -> None:
    fake_page = _FakePage()
    adapter = EdgeAdapter(
        WebConfig(headless=True),
        playwright_factory=lambda: _FakePlaywright(fake_page),
    )
    check = adapter.connect_or_launch(headless=True)
    assert check.launch_ok is True

    title, url = adapter.navigate("https://example.local/unit1")
    assert title == "WE Learn 测试页"
    assert url == "https://example.local/unit1"

    summary = adapter.analyze_page_structure()
    assert summary.has_audio is True
    assert summary.heading_count == 2

    login = adapter.check_login_visibility()
    assert login.login_form_visible is True
    assert login.password_input_visible is True
    assert login.likely_logged_in is False

    shot = adapter.capture_screenshot(tmp_path / "shot.png")
    assert shot.exists()
    adapter.close()


def test_real_edge_local_html_launch_and_inspection(tmp_path: Path) -> None:
    """若本机存在 Microsoft Edge，使用本地离线 HTML 验证真实 Playwright 驱动、分析与截图。"""
    exe = find_edge_executable()
    if not exe:
        pytest.skip("本机未检测到 Microsoft Edge，跳过真实浏览器集成验证")

    html_file = tmp_path / "sample.html"
    html_file.write_text(
        """
        <!doctype html>
        <html lang="zh-CN">
        <head><meta charset="utf-8"><title>WE Learn Local Verify</title></head>
        <body>
          <h1>Course Overview</h1>
          <audio controls></audio>
          <a href="#unit1">Unit 1</a>
          <button>Start</button>
        </body>
        </html>
        """,
        encoding="utf-8",
    )

    adapter = EdgeAdapter(WebConfig(headless=True, timeout_ms=10000))
    check = adapter.connect_or_launch(headless=True)
    try:
        assert check.available is True
        assert check.launch_ok is True, f"Edge 启动失败: {check.error_message}"
        title, url = adapter.navigate(html_file.as_uri())
        assert title == "WE Learn Local Verify"
        assert "sample.html" in url

        summary = adapter.analyze_page_structure()
        assert summary.heading_count == 1
        assert summary.has_audio is True
        assert summary.button_count == 1

        login = adapter.check_login_visibility()
        assert login.login_form_visible is False
        assert login.password_input_visible is False

        shot = adapter.capture_screenshot(tmp_path / "real_edge.png")
        assert shot.exists() and shot.stat().st_size > 100
    finally:
        adapter.close()
